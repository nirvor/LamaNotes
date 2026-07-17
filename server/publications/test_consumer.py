import json
import unittest

import httpx

from .consumer import PublicationConsumer
from .errors import PublicationError


class PublicationConsumerTests(unittest.TestCase):
    def test_contract_requests_use_bearer_idempotency_and_asset_hash(self):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if request.method == "POST" and request.url.path.endswith(
                "/nirvnotes-publications"
            ):
                return httpx.Response(
                    202,
                    json={
                        "operationId": "op_1",
                        "status": "awaiting-assets",
                        "missingAssets": [],
                    },
                )
            if request.method == "PUT":
                return httpx.Response(204)
            if request.method == "POST" and request.url.path.endswith(
                "/finalize"
            ):
                return httpx.Response(
                    202, json={"operationId": "op_1", "status": "deploying"}
                )
            return httpx.Response(
                200, json={"operationId": "op_1", "status": "verifying"}
            )

        consumer = PublicationConsumer(
            "https://pages.example/api/nirvnotes-publications",
            "server-only-token",
            transport=httpx.MockTransport(handler),
        )
        manifest = {
            "source": {"id": "source-id"},
            "content": {"contentHash": "sha256:" + "a" * 64},
        }
        consumer.begin(manifest)
        consumer.upload(
            "/api/nirvnotes-publications/op_1/assets/asset_1",
            {
                "contentType": "image/png",
                "sha256": "sha256:" + "b" * 64,
            },
            b"png",
        )
        consumer.finalize("op_1", "sha256:" + "a" * 64)
        consumer.status("op_1")

        self.assertTrue(
            all(
                request.headers["authorization"] == "Bearer server-only-token"
                for request in requests
            )
        )
        self.assertEqual(
            requests[0].headers["idempotency-key"],
            "source-id:sha256:" + "a" * 64,
        )
        self.assertEqual(requests[1].headers["x-content-sha256"], "b" * 64)
        self.assertEqual(
            json.loads(requests[2].content),
            {"contentHash": "sha256:" + "a" * 64},
        )

    def test_invalid_upload_origin_is_rejected_before_network(self):
        consumer = PublicationConsumer(
            "https://pages.example/api/nirvnotes-publications", "token"
        )
        with self.assertRaises(PublicationError) as raised:
            consumer.upload(
                "https://elsewhere.example/upload",
                {"contentType": "image/png", "sha256": "sha256:" + "a" * 64},
                b"data",
            )
        self.assertEqual(raised.exception.code, "consumer_unavailable")

    def test_consumer_error_cannot_echo_server_token(self):
        token = "server-only-token-value"

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                401,
                json={
                    "code": "publisher_unauthorized",
                    "detail": f"Rejected {token}",
                },
            )

        consumer = PublicationConsumer(
            "https://pages.example/api/nirvnotes-publications",
            token,
            transport=httpx.MockTransport(handler),
        )
        with self.assertRaises(PublicationError) as raised:
            consumer.begin(
                {
                    "source": {"id": "source-id"},
                    "content": {"contentHash": "sha256:" + "a" * 64},
                }
            )
        self.assertNotIn(token, raised.exception.detail)
        self.assertIn("[redacted]", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()
