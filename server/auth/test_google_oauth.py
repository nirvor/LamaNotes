from __future__ import annotations

import asyncio
import base64
import hashlib
import unittest
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

from auth.google_oauth import (
    GoogleAuthError,
    GoogleIdentity,
    GoogleOAuthService,
)
from auth.models import Token


class FakeAuth:
    secret_key = "s" * 64

    def issue_session(self, remember_me: bool = True) -> Token:
        return Token(access_token="session-token", expires_in=3600)


def config() -> SimpleNamespace:
    return SimpleNamespace(
        google_client_id="client-id",
        google_client_secret="client-secret",
        google_allowed_email="owner@example.com",
        google_allowed_sub="",
        google_public_origin="https://notes.example",
        path_prefix="",
    )


class GoogleOAuthServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = GoogleOAuthService(config(), FakeAuth())
        self.verifier = "v" * 64
        digest = hashlib.sha256(self.verifier.encode("ascii")).digest()
        self.challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    def test_native_handoff_is_loopback_only_pkce_bound_and_single_use(
        self,
    ) -> None:
        url = self.service.authorization_url(
            flow="native",
            loopback_uri="http://127.0.0.1:43210/auth/google/callback",
            code_challenge=self.challenge,
            client_state="state_value_with_enough_entropy_123",
        )
        state = parse_qs(urlsplit(url).query)["state"][0]
        payload = self.service._decode_token(state, self.service.STATE_AUDIENCE)
        callback = {
            **payload,
            "identity": GoogleIdentity("google-subject", "owner@example.com"),
        }
        handoff = self.service.create_native_handoff(callback)

        token = self.service.exchange_native_handoff(
            handoff=handoff,
            verifier=self.verifier,
        )
        self.assertEqual(token.access_token, "session-token")
        with self.assertRaises(GoogleAuthError):
            self.service.exchange_native_handoff(
                handoff=handoff,
                verifier=self.verifier,
            )

    def test_native_handoff_rejects_non_loopback_callback(self) -> None:
        with self.assertRaises(GoogleAuthError):
            self.service.authorization_url(
                flow="native",
                loopback_uri="https://attacker.example/auth/google/callback",
                code_challenge=self.challenge,
                client_state="state_value_with_enough_entropy_123",
            )

    def test_callback_uses_signed_nonce_and_verified_identity(self) -> None:
        url = self.service.authorization_url(flow="web", next_path="/search")
        state = parse_qs(urlsplit(url).query)["state"][0]

        async def verified_identity(*, code: str, nonce: str) -> GoogleIdentity:
            self.assertEqual(code, "authorization-code")
            self.assertTrue(nonce)
            return GoogleIdentity("google-subject", "owner@example.com")

        self.service._exchange_and_verify = verified_identity
        payload = asyncio.run(
            self.service.finish_callback(code="authorization-code", state=state)
        )
        self.assertEqual(payload["flow"], "web")
        self.assertEqual(payload["next"], "/search")

    def test_identity_requires_exact_verified_email_and_nonce(self) -> None:
        valid_claims = {
            "iss": "https://accounts.google.com",
            "sub": "google-subject",
            "email": "OWNER@example.com",
            "email_verified": True,
            "nonce": "expected-nonce",
        }
        identity = self.service._identity_from_claims(
            valid_claims,
            "expected-nonce",
        )
        self.assertEqual(identity.email, "owner@example.com")

        invalid_claims = (
            {**valid_claims, "email": "other@example.com"},
            {**valid_claims, "email_verified": False},
            {**valid_claims, "nonce": "different-nonce"},
        )
        for claims in invalid_claims:
            with self.assertRaises(GoogleAuthError):
                self.service._identity_from_claims(claims, "expected-nonce")

    def test_identity_requires_bound_subject_after_bootstrap(self) -> None:
        bound_config = config()
        bound_config.google_allowed_sub = "bound-google-subject"
        service = GoogleOAuthService(bound_config, FakeAuth())
        claims = {
            "iss": "https://accounts.google.com",
            "sub": "bound-google-subject",
            "email": "owner@example.com",
            "email_verified": True,
            "nonce": "expected-nonce",
        }

        identity = service._identity_from_claims(claims, "expected-nonce")
        self.assertEqual(identity.subject, "bound-google-subject")
        with self.assertRaises(GoogleAuthError):
            service._identity_from_claims(
                {**claims, "sub": "different-google-subject"},
                "expected-nonce",
            )


if __name__ == "__main__":
    unittest.main()
