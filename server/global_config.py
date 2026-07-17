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
            "FLATNOTES_SESSION_EXPIRY_DAYS",
            mandatory=False,
            default=30,
            cast_int=True,
        )
        self.session_expiry_hours: int = get_env(
            "NIRVNOTES_SESSION_EXPIRY_HOURS",
            mandatory=False,
            default=12,
            cast_int=True,
        )
        self.remember_expiry_days: int = get_env(
            "NIRVNOTES_REMEMBER_EXPIRY_DAYS",
            mandatory=False,
            default=legacy_session_days,
            cast_int=True,
        )
        self.session_cookie_name: str = get_env(
            "NIRVNOTES_SESSION_COOKIE_NAME",
            mandatory=False,
            default="lamanotes_session",
        )
        self.session_cookie_secure: bool = get_env(
            "NIRVNOTES_SESSION_COOKIE_SECURE",
            mandatory=False,
            default=True,
            cast_bool=True,
        )
        self.accept_legacy_tokens: bool = get_env(
            "NIRVNOTES_ACCEPT_LEGACY_TOKENS",
            mandatory=False,
            default=False,
            cast_bool=True,
        )
        self.login_rate_limit_attempts: int = get_env(
            "NIRVNOTES_LOGIN_RATE_LIMIT_ATTEMPTS",
            mandatory=False,
            default=8,
            cast_int=True,
        )
        self.login_rate_limit_window_seconds: int = get_env(
            "NIRVNOTES_LOGIN_RATE_LIMIT_WINDOW_SECONDS",
            mandatory=False,
            default=300,
            cast_int=True,
        )
        self.publish_base_url: str = get_env(
            "NIRVNOTES_PUBLISH_BASE_URL", mandatory=False, default=""
        )
        self.publish_token: str = get_env(
            "NIRVNOTES_PUBLISH_TOKEN", mandatory=False, default=""
        )
        self.public_base_url: str = get_env(
            "NIRVNOTES_PUBLIC_BASE_URL",
            mandatory=False,
            default="https://pages.thuber.org",
        )
        self.publish_timeout_seconds: int = get_env(
            "NIRVNOTES_PUBLISH_TIMEOUT_SECONDS",
            mandatory=False,
            default=20,
            cast_int=True,
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
        key = "FLATNOTES_AUTH_TYPE"
        auth_type = get_env(key, mandatory=False, default=AuthType.PASSWORD.value)
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
        key = "FLATNOTES_QUICK_ACCESS_HIDE"
        value = get_env(key, mandatory=False, default=False, cast_bool=True)
        if value is False:
            depricated_key = "FLATNOTES_HIDE_RECENTLY_MODIFIED"
            value = get_env(
                depricated_key, mandatory=False, default=False, cast_bool=True
            )
            if value is True:
                logger.warning(
                    f"{depricated_key} is depricated. Please use {key} instead."
                )
        return value

    def _quick_access_title(self):
        key = "FLATNOTES_QUICK_ACCESS_TITLE"
        return get_env(key, mandatory=False, default="RECENTLY MODIFIED")

    def _quick_access_term(self):
        key = "FLATNOTES_QUICK_ACCESS_TERM"
        return get_env(key, mandatory=False, default="*")

    def _quick_access_sort(self):
        key = "FLATNOTES_QUICK_ACCESS_SORT"
        value = get_env(key, mandatory=False, default="lastModified")
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
        key = "FLATNOTES_QUICK_ACCESS_LIMIT"
        return get_env(key, mandatory=False, default=4, cast_int=True)

    def _load_path_prefix(self):
        key = "FLATNOTES_PATH_PREFIX"
        value = get_env(key, mandatory=False, default="")
        if value and (not value.startswith("/") or value.endswith("/")):
            logger.error(
                f"Invalid value '{value}' for {key}. "
                + "Must start with '/' and not end with '/'."
            )
            sys.exit(1)
        return value

    def _load_windows_update_dir(self):
        return get_env(
            "NIRVNOTES_WINDOWS_UPDATE_DIR",
            mandatory=False,
            default="",
        )


class AuthType(str, Enum):
    NONE = "none"
    READ_ONLY = "read_only"
    PASSWORD = "password"
    TOTP = "totp"


class GlobalConfigResponseModel(CustomBaseModel):
    auth_type: AuthType
    quick_access_hide: bool
    quick_access_title: str
    quick_access_term: str
    quick_access_sort: str
    quick_access_limit: int
