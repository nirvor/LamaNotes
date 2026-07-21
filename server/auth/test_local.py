import hashlib
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from argon2 import PasswordHasher
from fastapi import HTTPException
from starlette.requests import Request

from auth.local import LocalAuth
from auth.models import Login
from auth.scopes import ALL_SCOPES, NOTES_READ
from global_config import AuthType


def request_for(method: str = "GET", headers: list | None = None) -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "scheme": "https",
            "path": "/api/auth-check",
            "headers": headers or [],
            "client": ("127.0.0.1", 12345),
            "server": ("notes.example", 443),
        }
    )


def config() -> SimpleNamespace:
    return SimpleNamespace(
        auth_type=AuthType.PASSWORD,
        session_expiry_hours=12,
        remember_expiry_days=30,
        accept_legacy_tokens=False,
        session_cookie_name="lamanotes_session",
        password_login_enabled=True,
    )


class LocalAuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.password = "correct horse battery staple"
        self.environment = {
            "FLATNOTES_USERNAME": "tom",
            "FLATNOTES_PASSWORD_HASH": PasswordHasher().hash(self.password),
            "FLATNOTES_SECRET_KEY": "s" * 64,
            "NIRVNOTES_API_TOKEN_HASHES": "[]",
        }

    def test_argon2_login_creates_scoped_session(self) -> None:
        with patch.dict(os.environ, self.environment, clear=False):
            auth = LocalAuth(config())
            token = auth.login(
                Login(
                    username="Tom",
                    password=self.password,
                    remember_me=True,
                )
            )

        principal = auth.authenticate(request_for(), token.access_token)

        self.assertEqual(principal.subject, "tom")
        self.assertEqual(principal.kind, "session")
        self.assertEqual(principal.scopes, ALL_SCOPES)
        self.assertGreaterEqual(token.expires_in, 29 * 24 * 60 * 60)

    def test_wrong_password_is_rejected(self) -> None:
        with patch.dict(os.environ, self.environment, clear=False):
            auth = LocalAuth(config())
            with self.assertRaises(ValueError):
                auth.login(Login(username="tom", password="wrong"))

    def test_trusted_identity_can_issue_session_without_password_login(
        self,
    ) -> None:
        google_only_config = config()
        google_only_config.password_login_enabled = False
        environment = {
            **self.environment,
            "FLATNOTES_PASSWORD_HASH": "",
        }
        with patch.dict(os.environ, environment, clear=False):
            auth = LocalAuth(google_only_config)
            token = auth.issue_session()
            with self.assertRaises(ValueError):
                auth.login(Login(username="tom", password=self.password))

        principal = auth.authenticate(request_for(), token.access_token)
        self.assertEqual(principal.subject, "tom")

    def test_api_token_has_only_configured_scopes(self) -> None:
        raw_token = "lmn_test-token-with-enough-entropy"
        entry = {
            "name": "telemetry",
            "sha256": hashlib.sha256(raw_token.encode()).hexdigest(),
            "scopes": [NOTES_READ],
        }
        environment = {
            **self.environment,
            "NIRVNOTES_API_TOKEN_HASHES": json.dumps([entry]),
        }
        with patch.dict(os.environ, environment, clear=False):
            auth = LocalAuth(config())

        principal = auth.authenticate(request_for(), raw_token)

        self.assertEqual(principal.kind, "api-token")
        self.assertEqual(principal.scopes, frozenset({NOTES_READ}))

    def test_cross_site_cookie_mutation_is_rejected(self) -> None:
        with patch.dict(os.environ, self.environment, clear=False):
            auth = LocalAuth(config())
            token = auth.login(Login(username="tom", password=self.password))
        request = request_for(
            method="PATCH",
            headers=[(b"sec-fetch-site", b"cross-site")],
        )
        request._cookies = {"lamanotes_session": token.access_token}

        with self.assertRaises(HTTPException) as raised:
            auth.authenticate(request, None)

        self.assertEqual(raised.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
