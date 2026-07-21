from __future__ import annotations

import base64
import hashlib
import re
import secrets
import threading
import time
from dataclasses import dataclass
from urllib.parse import urlencode, urlsplit

import httpx
from jose import JWTError, jwt

from auth.models import Token

GOOGLE_AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_ENDPOINT = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}
PKCE_CHALLENGE_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")
PKCE_VERIFIER_RE = re.compile(r"^[A-Za-z0-9._~-]{43,128}$")
CLIENT_STATE_RE = re.compile(r"^[A-Za-z0-9_-]{20,128}$")


class GoogleAuthError(ValueError):
    pass


@dataclass(frozen=True)
class GoogleIdentity:
    subject: str
    email: str


class GoogleOAuthService:
    JWT_ALGORITHM = "HS256"
    JWT_ISSUER = "nirvnotes-google-auth"
    STATE_AUDIENCE = "nirvnotes-google-state"
    HANDOFF_AUDIENCE = "nirvnotes-native-handoff"

    def __init__(self, config, auth) -> None:
        self.config = config
        self.auth = auth
        self.client_id = config.google_client_id
        self.client_secret = config.google_client_secret
        self.allowed_email = config.google_allowed_email.casefold()
        self.allowed_subject = config.google_allowed_sub
        self.callback_uri = (
            f"{config.google_public_origin}{config.path_prefix}"
            "/api/auth/google/callback"
        )
        self.secret_key = auth.secret_key
        self._used_handoffs: dict[str, int] = {}
        self._handoff_lock = threading.Lock()

    def authorization_url(
        self,
        *,
        flow: str,
        next_path: str = "/",
        loopback_uri: str = "",
        code_challenge: str = "",
        client_state: str = "",
    ) -> str:
        nonce = secrets.token_urlsafe(24)
        state_payload = {
            "flow": flow,
            "nonce": nonce,
            "marker": secrets.token_urlsafe(16),
        }
        if flow == "native":
            state_payload.update(
                {
                    "loopback": self._validate_loopback_uri(loopback_uri),
                    "challenge": self._validate_code_challenge(code_challenge),
                    "client_state": self._validate_client_state(client_state),
                }
            )
        elif flow == "web":
            state_payload["next"] = self._safe_next_path(next_path)
        else:
            raise GoogleAuthError("The Google login flow is invalid.")

        state = self._encode_token(
            state_payload,
            audience=self.STATE_AUDIENCE,
            ttl_seconds=600,
        )
        query = urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": self.callback_uri,
                "response_type": "code",
                "scope": "openid email profile",
                "state": state,
                "nonce": nonce,
                "login_hint": self.allowed_email,
            }
        )
        return f"{GOOGLE_AUTHORIZATION_ENDPOINT}?{query}"

    async def finish_callback(self, *, code: str, state: str) -> dict:
        state_payload = self._decode_token(state, self.STATE_AUDIENCE)
        identity = await self._exchange_and_verify(
            code=code,
            nonce=str(state_payload.get("nonce", "")),
        )
        return {**state_payload, "identity": identity}

    def create_native_handoff(self, callback_payload: dict) -> str:
        identity = callback_payload.get("identity")
        if not isinstance(identity, GoogleIdentity):
            raise GoogleAuthError("The Google identity is missing.")
        return self._encode_token(
            {
                "google_sub": identity.subject,
                "challenge": callback_payload.get("challenge", ""),
            },
            audience=self.HANDOFF_AUDIENCE,
            ttl_seconds=75,
        )

    def native_redirect_uri(self, callback_payload: dict, handoff: str) -> str:
        loopback = self._validate_loopback_uri(
            str(callback_payload.get("loopback", ""))
        )
        client_state = self._validate_client_state(
            str(callback_payload.get("client_state", ""))
        )
        return f"{loopback}?{urlencode({'handoff': handoff, 'state': client_state})}"

    def exchange_native_handoff(self, *, handoff: str, verifier: str) -> Token:
        payload = self._decode_token(handoff, self.HANDOFF_AUDIENCE)
        if not PKCE_VERIFIER_RE.fullmatch(verifier):
            raise GoogleAuthError("The native PKCE verifier is invalid.")
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        if not secrets.compare_digest(challenge, str(payload.get("challenge", ""))):
            raise GoogleAuthError("The native PKCE verifier does not match.")

        jti = str(payload.get("jti", ""))
        expires_at = int(payload.get("exp", 0))
        now = int(time.time())
        with self._handoff_lock:
            self._used_handoffs = {
                key: expiry
                for key, expiry in self._used_handoffs.items()
                if expiry > now
            }
            if not jti or jti in self._used_handoffs:
                raise GoogleAuthError("The native handoff was already used.")
            self._used_handoffs[jti] = expires_at
        return self.auth.issue_session(remember_me=True)

    async def _exchange_and_verify(self, *, code: str, nonce: str) -> GoogleIdentity:
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                token_response = await client.post(
                    GOOGLE_TOKEN_ENDPOINT,
                    data={
                        "code": code,
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "redirect_uri": self.callback_uri,
                        "grant_type": "authorization_code",
                    },
                )
                token_response.raise_for_status()
                id_token = str(token_response.json().get("id_token", ""))
                if not id_token:
                    raise GoogleAuthError("Google did not return an ID token.")
                jwks_response = await client.get(GOOGLE_JWKS_ENDPOINT)
                jwks_response.raise_for_status()
                keys = jwks_response.json().get("keys", [])
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise GoogleAuthError("Google login could not be verified.") from exc

        try:
            header = jwt.get_unverified_header(id_token)
            signing_key = next(
                key for key in keys if key.get("kid") == header.get("kid")
            )
            claims = jwt.decode(
                id_token,
                signing_key,
                algorithms=["RS256"],
                audience=self.client_id,
                options={"verify_iss": False},
            )
        except (JWTError, KeyError, StopIteration, TypeError) as exc:
            raise GoogleAuthError("Google returned an invalid ID token.") from exc

        return self._identity_from_claims(claims, nonce)

    def _identity_from_claims(self, claims: dict, nonce: str) -> GoogleIdentity:
        if claims.get("iss") not in GOOGLE_ISSUERS:
            raise GoogleAuthError("The Google token issuer is invalid.")
        if claims.get("azp") and claims.get("azp") != self.client_id:
            raise GoogleAuthError("The Google token client is invalid.")
        if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
            raise GoogleAuthError("The Google login nonce is invalid.")
        email = str(claims.get("email", "")).strip().casefold()
        if claims.get("email_verified") is not True or not secrets.compare_digest(
            email, self.allowed_email
        ):
            raise GoogleAuthError("This Google account is not allowed.")
        subject = str(claims.get("sub", "")).strip()
        if not subject:
            raise GoogleAuthError("The Google account identifier is missing.")
        if self.allowed_subject and not secrets.compare_digest(
            subject, self.allowed_subject
        ):
            raise GoogleAuthError("This Google account identifier is not allowed.")
        return GoogleIdentity(subject=subject, email=email)

    def _encode_token(self, payload: dict, *, audience: str, ttl_seconds: int) -> str:
        now = int(time.time())
        return jwt.encode(
            {
                **payload,
                "iss": self.JWT_ISSUER,
                "aud": audience,
                "iat": now,
                "exp": now + ttl_seconds,
                "jti": secrets.token_urlsafe(16),
            },
            self.secret_key,
            algorithm=self.JWT_ALGORITHM,
        )

    def _decode_token(self, token: str, audience: str) -> dict:
        try:
            return jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.JWT_ALGORITHM],
                audience=audience,
                issuer=self.JWT_ISSUER,
            )
        except JWTError as exc:
            raise GoogleAuthError(
                "The Google login state is invalid or expired."
            ) from exc

    @staticmethod
    def _safe_next_path(value: str) -> str:
        return value if value.startswith("/") and not value.startswith("//") else "/"

    @staticmethod
    def _validate_loopback_uri(value: str) -> str:
        try:
            parsed = urlsplit(value)
            port = parsed.port
        except ValueError as exc:
            raise GoogleAuthError("The native loopback URL is invalid.") from exc
        if (
            parsed.scheme != "http"
            or parsed.hostname != "127.0.0.1"
            or parsed.username
            or parsed.password
            or not port
            or parsed.path != "/auth/google/callback"
            or parsed.query
            or parsed.fragment
        ):
            raise GoogleAuthError("The native loopback URL is invalid.")
        return value

    @staticmethod
    def _validate_code_challenge(value: str) -> str:
        if not PKCE_CHALLENGE_RE.fullmatch(value):
            raise GoogleAuthError("The native PKCE challenge is invalid.")
        return value

    @staticmethod
    def _validate_client_state(value: str) -> str:
        if not CLIENT_STATE_RE.fullmatch(value):
            raise GoogleAuthError("The native client state is invalid.")
        return value
