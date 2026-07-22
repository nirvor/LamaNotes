import sys
from enum import Enum

from helpers import CustomBaseModel, get_env
from logger import logger


class GlobalConfig:
    def __init__(self) -> None:
        logger.debug("Loading global config...")
        self.auth_type: AuthType = self._load_auth_type()
        self.quick_access_hide: bool = self._quick_access_hide()
        self.quick_access_title: str = self._quick_access_title()
        self.quick_access_term: str = self._quick_access_term()
        self.quick_access_sort: str = self._quick_access_sort()
        self.quick_access_limit: int = self._quick_access_limit()
        self.path_prefix: str = self._load_path_prefix()
        self.windows_update_dir: str = self._load_windows_update_dir()
        legacy_session_days = get_env(
            "LAMANOTES_SESSION_EXPIRY_DAYS",
            mandatory=False,
            default=30,
            cast_int=True,
            legacy_keys=("FLATNOTES_SESSION_EXPIRY_DAYS",),
        )
        self.session_expiry_hours: int = get_env(
            "LAMANOTES_SESSION_EXPIRY_HOURS",
            mandatory=False,
            default=12,
            cast_int=True,
            legacy_keys=("NIRVNOTES_SESSION_EXPIRY_HOURS",),
        )
        self.remember_expiry_days: int = get_env(
            "LAMANOTES_REMEMBER_EXPIRY_DAYS",
            mandatory=False,
            default=legacy_session_days,
            cast_int=True,
            legacy_keys=("NIRVNOTES_REMEMBER_EXPIRY_DAYS",),
        )
        self.session_cookie_name: str = get_env(
            "LAMANOTES_SESSION_COOKIE_NAME",
            mandatory=False,
            default="lamanotes_session",
            legacy_keys=("NIRVNOTES_SESSION_COOKIE_NAME",),
        )
        self.session_cookie_secure: bool = get_env(
            "LAMANOTES_SESSION_COOKIE_SECURE",
            mandatory=False,
            default=True,
            cast_bool=True,
            legacy_keys=("NIRVNOTES_SESSION_COOKIE_SECURE",),
        )
        self.accept_legacy_tokens: bool = get_env(
            "LAMANOTES_ACCEPT_LEGACY_TOKENS",
            mandatory=False,
            default=False,
            cast_bool=True,
            legacy_keys=("NIRVNOTES_ACCEPT_LEGACY_TOKENS",),
        )
        self.login_rate_limit_attempts: int = get_env(
            "LAMANOTES_LOGIN_RATE_LIMIT_ATTEMPTS",
            mandatory=False,
            default=8,
            cast_int=True,
            legacy_keys=("NIRVNOTES_LOGIN_RATE_LIMIT_ATTEMPTS",),
        )
        self.login_rate_limit_window_seconds: int = get_env(
            "LAMANOTES_LOGIN_RATE_LIMIT_WINDOW_SECONDS",
            mandatory=False,
            default=300,
            cast_int=True,
            legacy_keys=("NIRVNOTES_LOGIN_RATE_LIMIT_WINDOW_SECONDS",),
        )
        self.password_login_enabled: bool = get_env(
            "LAMANOTES_PASSWORD_LOGIN_ENABLED",
            mandatory=False,
            default=True,
            cast_bool=True,
            legacy_keys=("NIRVNOTES_PASSWORD_LOGIN_ENABLED",),
        )
        self.google_auth_enabled: bool = get_env(
            "LAMANOTES_GOOGLE_AUTH_ENABLED",
            mandatory=False,
            default=False,
            cast_bool=True,
            legacy_keys=("NIRVNOTES_GOOGLE_AUTH_ENABLED",),
        )
        self.google_client_id: str = get_env(
            "LAMANOTES_GOOGLE_CLIENT_ID",
            mandatory=False,
            default="",
            legacy_keys=("NIRVNOTES_GOOGLE_CLIENT_ID",),
        ).strip()
        self.google_client_secret: str = get_env(
            "LAMANOTES_GOOGLE_CLIENT_SECRET",
            mandatory=False,
            default="",
            legacy_keys=("NIRVNOTES_GOOGLE_CLIENT_SECRET",),
        ).strip()
        self.google_allowed_email: str = (
            get_env(
                "LAMANOTES_GOOGLE_ALLOWED_EMAIL",
                mandatory=False,
                default="",
                legacy_keys=("NIRVNOTES_GOOGLE_ALLOWED_EMAIL",),
            )
            .strip()
            .lower()
        )
        self.google_allowed_sub: str = get_env(
            "LAMANOTES_GOOGLE_ALLOWED_SUB",
            mandatory=False,
            default="",
            legacy_keys=("NIRVNOTES_GOOGLE_ALLOWED_SUB",),
        ).strip()
        self.google_public_origin: str = get_env(
            "LAMANOTES_GOOGLE_PUBLIC_ORIGIN",
            mandatory=False,
            default="",
            legacy_keys=("NIRVNOTES_GOOGLE_PUBLIC_ORIGIN",),
        ).rstrip("/")
        if self.google_auth_enabled:
            if self.auth_type in (AuthType.NONE, AuthType.READ_ONLY):
                raise RuntimeError(
                    "Google auth requires a writable authenticated LamaNotes mode."
                )
            required_google_values = (
                self.google_client_id,
                self.google_client_secret,
                self.google_allowed_email,
                self.google_public_origin,
            )
            if not all(required_google_values):
                raise RuntimeError(
                    "Google auth requires client ID, client secret, allowed email, "
                    "and public origin."
                )
            if not self.google_public_origin.startswith("https://"):
                raise RuntimeError("Google auth public origin must use HTTPS.")
        if (
            self.auth_type not in (AuthType.NONE, AuthType.READ_ONLY)
            and not self.password_login_enabled
            and not self.google_auth_enabled
        ):
            raise RuntimeError("At least one LamaNotes login method must be enabled.")
        self.publish_base_url: str = get_env(
            "LAMANOTES_PUBLISH_BASE_URL",
            mandatory=False,
            default="",
            legacy_keys=("NIRVNOTES_PUBLISH_BASE_URL",),
        )
        self.publish_token: str = get_env(
            "LAMANOTES_PUBLISH_TOKEN",
            mandatory=False,
            default="",
            legacy_keys=("NIRVNOTES_PUBLISH_TOKEN",),
        )
        self.public_base_url: str = get_env(
            "LAMANOTES_PUBLIC_BASE_URL",
            mandatory=False,
            default="https://pages.thuber.org",
            legacy_keys=("NIRVNOTES_PUBLIC_BASE_URL",),
        )
        self.publish_timeout_seconds: int = get_env(
            "LAMANOTES_PUBLISH_TIMEOUT_SECONDS",
            mandatory=False,
            default=20,
            cast_int=True,
            legacy_keys=("NIRVNOTES_PUBLISH_TIMEOUT_SECONDS",),
        )

    def load_auth(self):
        if self.auth_type in (AuthType.NONE, AuthType.READ_ONLY):
            return None
        elif self.auth_type in (AuthType.PASSWORD, AuthType.TOTP):
            from auth.local import LocalAuth

            return LocalAuth(self)

    def load_note_storage(self):
        from notes.file_system import FileSystemNotes

        return FileSystemNotes()

    def load_attachment_storage(self):
        from attachments.file_system import FileSystemAttachments

        return FileSystemAttachments()

    def _load_auth_type(self):
        key = "LAMANOTES_AUTH_TYPE"
        auth_type = get_env(
            key,
            mandatory=False,
            default=AuthType.PASSWORD.value,
            legacy_keys=("FLATNOTES_AUTH_TYPE",),
        )
        try:
            auth_type = AuthType(auth_type.lower())
        except ValueError:
            logger.error(
                f"Invalid value '{auth_type}' for {key}. "
                + "Must be one of: "
                + ", ".join([auth_type.value for auth_type in AuthType])
                + "."
            )
            sys.exit(1)
        return auth_type

    def _quick_access_hide(self):
        return get_env(
            "LAMANOTES_QUICK_ACCESS_HIDE",
            mandatory=False,
            default=False,
            cast_bool=True,
            legacy_keys=(
                "FLATNOTES_QUICK_ACCESS_HIDE",
                "FLATNOTES_HIDE_RECENTLY_MODIFIED",
            ),
        )

    def _quick_access_title(self):
        return get_env(
            "LAMANOTES_QUICK_ACCESS_TITLE",
            mandatory=False,
            default="RECENTLY MODIFIED",
            legacy_keys=("FLATNOTES_QUICK_ACCESS_TITLE",),
        )

    def _quick_access_term(self):
        return get_env(
            "LAMANOTES_QUICK_ACCESS_TERM",
            mandatory=False,
            default="*",
            legacy_keys=("FLATNOTES_QUICK_ACCESS_TERM",),
        )

    def _quick_access_sort(self):
        key = "LAMANOTES_QUICK_ACCESS_SORT"
        value = get_env(
            key,
            mandatory=False,
            default="lastModified",
            legacy_keys=("FLATNOTES_QUICK_ACCESS_SORT",),
        )
        valid_values = ["score", "title", "lastModified"]
        if value not in valid_values:
            logger.error(
                f"Invalid value '{value}' for {key}. "
                + "Must be one of: "
                + ", ".join(valid_values)
            )
            sys.exit(1)
        return value

    def _quick_access_limit(self):
        return get_env(
            "LAMANOTES_QUICK_ACCESS_LIMIT",
            mandatory=False,
            default=4,
            cast_int=True,
            legacy_keys=("FLATNOTES_QUICK_ACCESS_LIMIT",),
        )

    def _load_path_prefix(self):
        key = "LAMANOTES_PATH_PREFIX"
        value = get_env(
            key,
            mandatory=False,
            default="",
            legacy_keys=("FLATNOTES_PATH_PREFIX",),
        )
        if value and (not value.startswith("/") or value.endswith("/")):
            logger.error(
                f"Invalid value '{value}' for {key}. "
                + "Must start with '/' and not end with '/'."
            )
            sys.exit(1)
        return value

    def _load_windows_update_dir(self):
        return get_env(
            "LAMANOTES_WINDOWS_UPDATE_DIR",
            mandatory=False,
            default="",
            legacy_keys=("NIRVNOTES_WINDOWS_UPDATE_DIR",),
        )


class AuthType(str, Enum):
    NONE = "none"
    READ_ONLY = "read_only"
    PASSWORD = "password"
    TOTP = "totp"


class GlobalConfigResponseModel(CustomBaseModel):
    auth_type: AuthType
    google_auth_enabled: bool
    password_login_enabled: bool
    quick_access_hide: bool
    quick_access_title: str
    quick_access_term: str
    quick_access_sort: str
    quick_access_limit: int
