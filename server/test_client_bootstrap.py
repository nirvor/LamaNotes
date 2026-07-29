import unittest
from types import SimpleNamespace

from client_bootstrap import ClientBootstrapResponse, client_config_response
from global_config import AuthType


class ClientBootstrapTests(unittest.TestCase):
    def test_safe_bootstrap_serializes_config_and_body_free_index(self) -> None:
        config = client_config_response(
            SimpleNamespace(
                auth_type=AuthType.PASSWORD,
                google_auth_enabled=True,
                password_login_enabled=False,
                quick_access_hide=False,
                quick_access_title="Pinned",
                quick_access_term="#pinned",
                quick_access_sort="lastModified",
                quick_access_limit=7,
            )
        )
        payload = ClientBootstrapResponse(
            config=config,
            index=[
                {
                    "title": "Example",
                    "lastModified": 1.0,
                    "format": "html",
                    "noteKind": "work",
                    "tags": ["pinned"],
                    "content": "must not leave the server",
                    "text": "must not leave the server",
                }
            ],
        ).model_dump(by_alias=True)

        self.assertEqual(payload["config"]["authType"], "password")
        self.assertEqual(payload["index"][0]["title"], "Example")
        self.assertNotIn("content", payload["index"][0])
        self.assertNotIn("text", payload["index"][0])


if __name__ == "__main__":
    unittest.main()
