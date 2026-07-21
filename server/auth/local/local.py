import hashlib
import json
import secrets
from base64 import b32encode
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pyotp import TOTP
from pyotp.utils import build_uri
from qrcode import QRCode

from global_config import AuthType, GlobalConfig
from helpers import get_env
from logger import logger

from ..base import BaseAuth
from ..models import AuthPrincipal, Login, Token
from ..scopes import ALL_SCOPES

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/token", auto_error=False)
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class LocalAuth(BaseAuth):
    JWT_ALGORITHM = "HS256"
    JWT_ISSUER = "lamanotes"
    JWT_AUDIENCE = "lamanotes-api"

    def __init__(self, config: GlobalConfig | None = None) -> None:
        self.config = config or GlobalConfig()
        self.username = get_env("FLATNOTES_USERNAME", mandatory=True).lower()
        self.password_hash = get_env(
            "FLATNOTES_PASSWORD_HASH", mandatory=False, default=""
        )
        self.legacy_password = get_env(
            "FLATNOTES_PASSWORD", mandatory=False, default=""
        )
        self.password_login_enabled = self.config.password_login_enabled
        if (
            self.password_login_enabled
            and not self.password_hash
            and not self.legacy_password
        ):
            raise RuntimeError(
                "FLATNOTES_PASSWORD_HASH or FLATNOTES_PASSWORD must be set."
            )
        if self.password_login_enabled and not self.password_hash:
            logger.warning(
                "FLATNOTES_PASSWORD is a compatibility fallback. Migrate to "
                "FLATNOTES_PASSWORD_HASH before exposing the service."
            )

        self.password_hasher = PasswordHasher()
        self.secret_key = get_env("FLATNOTES_SECRET_KEY", mandatory=True)
        self.session_expiry_hours = self.config.session_expiry_hours
        self.remember_expiry_days = self.config.remember_expiry_days
        self.accept_legacy_tokens = self.config.accept_legacy_tokens
        self.cookie_name = self.config.session_cookie_name
        self.api_tokens = self._load_api_tokens()

        self.is_totp_enabled = False
        if self.password_login_enabled and self.config.auth_type == AuthType.TOTP:
            self.is_totp_enabled = True
            self.totp_key = get_env("FLATNOTES_TOTP_KEY", mandatory=True)
            self.totp_key = b32encode(self.totp_key.encode("utf-8"))
            self.totp = TOTP(self.totp_key)
            self.last_used_totp = None
            self._display_totp_enrolment()

    def login(self, data: Login) -> Token:
        if not self.password_login_enabled:
            raise ValueError("Password login is disabled.")
        username_correct = secrets.compare_digest(self.username, data.username.lower())

        supplied_password = data.password
        if self.is_totp_enabled:
            current_totp = self.totp.now()
            totp_correct = supplied_password.endswith(current_totp)
            supplied_password = supplied_password[: -len(current_totp)]
        else:
            current_totp = None
            totp_correct = True

        password_correct = self._verify_password(supplied_password)
        totp_not_reused = (
            not self.is_totp_enabled or current_totp != self.last_used_totp
        )
        if not (
            username_correct and password_correct and totp_correct and totp_not_reused
        ):
            raise ValueError("Incorrect login credentials.")

        if self.is_totp_enabled:
            self.last_used_totp = current_totp

        return self.issue_session(remember_me=data.remember_me)

    def issue_session(self, remember_me: bool = True) -> Token:
        expiry = (
            timedelta(days=self.remember_expiry_days)
            if remember_me
            else timedelta(hours=self.session_expiry_hours)
        )
        access_token = self._create_access_token(
            subject=self.username,
            scopes=ALL_SCOPES,
            expiry=expiry,
        )
        return Token(
            access_token=access_token,
            expires_in=max(1, int(expiry.total_seconds())),
        )

    def authenticate(
        self, request: Request, token: str = Depends(oauth2_scheme)
    ) -> AuthPrincipal:
        credential_source = "bearer"
        if token is None:
            token = request.cookies.get(self.cookie_name)
            credential_source = "cookie"
        if token is None:
            token = request.cookies.get("token")
            credential_source = "legacy-cookie"

        if (
            credential_source.endswith("cookie")
            and request.method.upper() not in SAFE_METHODS
            and request.headers.get("sec-fetch-site", "").lower() == "cross-site"
        ):
            raise self._authentication_error()

        try:
            if token and token.startswith("lmn_"):
                return self._validate_api_token(token)
            return self._validate_session_token(token)
        except (JWTError, ValueError):
            raise self._authentication_error()

    def _verify_password(self, supplied_password: str) -> bool:
        if self.password_hash:
            try:
                return bool(
                    self.password_hasher.verify(
                        self.password_hash,
                        supplied_password,
                    )
                )
            except (InvalidHashError, VerificationError):
                return False
        return secrets.compare_digest(self.legacy_password, supplied_password)

    def _validate_api_token(self, token: str) -> AuthPrincipal:
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        for configured in self.api_tokens:
            if secrets.compare_digest(digest, configured["sha256"]):
                return AuthPrincipal(
                    subject=configured["name"],
                    kind="api-token",
                    scopes=configured["scopes"],
                )
        raise ValueError("Unknown API token.")

    def _validate_session_token(self, token: str | None) -> AuthPrincipal:
        if token is None:
            raise ValueError("Missing token.")
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.JWT_ALGORITHM],
                audience=self.JWT_AUDIENCE,
                issuer=self.JWT_ISSUER,
            )
        except JWTError:
            if not self.accept_legacy_tokens:
                raise
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.JWT_ALGORITHM],
            )

        username = payload.get("sub")
        if username is None or username.lower() != self.username:
            raise ValueError("Invalid subject.")
        raw_scopes = payload.get("scope")
        scopes = frozenset(str(raw_scopes).split()) if raw_scopes else ALL_SCOPES
        return AuthPrincipal(
            subject=self.username,
            kind="session",
            scopes=scopes,
        )

    def _create_access_token(
        self,
        subject: str,
        scopes: frozenset[str],
        expiry: timedelta,
    ) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": subject,
            "iss": self.JWT_ISSUER,
            "aud": self.JWT_AUDIENCE,
            "iat": now,
            "exp": now + expiry,
            "jti": secrets.token_urlsafe(16),
            "scope": " ".join(sorted(scopes)),
        }
        return jwt.encode(
            payload,
            self.secret_key,
            algorithm=self.JWT_ALGORITHM,
        )

    def _load_api_tokens(self) -> list[dict]:
        raw = get_env("NIRVNOTES_API_TOKEN_HASHES", mandatory=False, default="[]")
        try:
            entries = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "NIRVNOTES_API_TOKEN_HASHES must be valid JSON."
            ) from exc
        if not isinstance(entries, list):
            raise RuntimeError("NIRVNOTES_API_TOKEN_HASHES must be a list.")

        parsed = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise RuntimeError("Every API token entry must be an object.")
            name = str(entry.get("name", "")).strip()
            digest = str(entry.get("sha256", "")).strip().lower()
            scopes = frozenset(str(scope) for scope in entry.get("scopes", []))
            if (
                not name
                or len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest)
                or not scopes
                or not scopes.issubset(ALL_SCOPES)
            ):
                raise RuntimeError("An API token entry is invalid.")
            parsed.append({"name": name, "sha256": digest, "scopes": scopes})
        return parsed

    @staticmethod
    def _authentication_error() -> HTTPException:
        return HTTPException(
            status_code=401,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    def _display_totp_enrolment(self) -> None:
        unpadded_secret = self.totp_key.rstrip(b"=")
        uri = build_uri(unpadded_secret, self.username, issuer="NirvNotes")
        qr = QRCode()
        qr.add_data(uri)
        print(
            "\nScan this QR code with your TOTP app of choice",
            "e.g. Authy or Google Authenticator:",
        )
        qr.print_ascii()
        print(f"Or manually enter this key: {self.totp.secret.decode('utf-8')}\n")
