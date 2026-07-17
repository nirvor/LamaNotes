from __future__ import annotations

import urllib.parse

import httpx

from .errors import PublicationError


class PublicationConsumer:
    def __init__(
        self,
        base_url: str,
        token: str,
        timeout_seconds: int = 20,
        transport=None,
    ) -> None:
        self.base_url = str(base_url or "").rstrip("/")
        self.token = str(token or "")
        self.timeout_seconds = max(2, min(int(timeout_seconds), 60))
        parsed = urllib.parse.urlparse(self.base_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("NIRVNOTES_PUBLISH_BASE_URL must use HTTPS.")
        self.origin = f"{parsed.scheme}://{parsed.netloc}"
        self._transport = transport

    def begin(self, manifest: dict) -> tuple[int, dict]:
        source_id = manifest["source"]["id"]
        content_hash = manifest["content"]["contentHash"]
        return self._json_request(
            "POST",
            self.base_url,
            json_body=manifest,
            headers={"Idempotency-Key": f"{source_id}:{content_hash}"},
        )

    def upload(self, upload_path: str, asset: dict, content: bytes) -> None:
        url = urllib.parse.urljoin(self.origin, upload_path)
        parsed = urllib.parse.urlparse(url)
        if (
            f"{parsed.scheme}://{parsed.netloc}" != self.origin
            or not parsed.path.startswith("/api/nirvnotes-publications/")
        ):
            raise PublicationError(
                502,
                "consumer_unavailable",
                "The publishing service returned an invalid asset path.",
                retryable=True,
            )
        response = self._request(
            "PUT",
            url,
            content=content,
            headers={
                "Content-Type": asset["contentType"],
                "Content-Length": str(len(content)),
                "X-Content-SHA256": asset["sha256"].removeprefix("sha256:"),
            },
        )
        if response.status_code != 204:
            self._raise_response(response)

    def finalize(
        self, operation_id: str, content_hash: str
    ) -> tuple[int, dict]:
        return self._json_request(
            "POST",
            f"{self.base_url}/{operation_id}/finalize",
            json_body={"contentHash": content_hash},
        )

    def status(self, operation_id: str) -> tuple[int, dict]:
        return self._json_request("GET", f"{self.base_url}/{operation_id}")

    def _json_request(
        self,
        method: str,
        url: str,
        *,
        json_body: dict | None = None,
        headers: dict | None = None,
    ) -> tuple[int, dict]:
        response = self._request(
            method, url, json=json_body, headers=headers or {}
        )
        if response.status_code >= 400:
            self._raise_response(response)
        try:
            payload = response.json()
        except ValueError:
            raise PublicationError(
                502,
                "consumer_unavailable",
                "The publishing service returned an invalid response.",
                retryable=True,
            )
        if not isinstance(payload, dict):
            raise PublicationError(
                502,
                "consumer_unavailable",
                "The publishing service returned an invalid response.",
                retryable=True,
            )
        return response.status_code, payload

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {self.token}"
        headers["Accept"] = "application/json"
        try:
            with httpx.Client(
                timeout=self.timeout_seconds,
                follow_redirects=False,
                trust_env=False,
                transport=self._transport,
            ) as client:
                return client.request(method, url, headers=headers, **kwargs)
        except httpx.HTTPError:
            raise PublicationError(
                502,
                "consumer_unavailable",
                "The publishing service is temporarily unavailable.",
                retryable=True,
            )

    def _raise_response(self, response: httpx.Response) -> None:
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        code = str(payload.get("code") or "consumer_unavailable")
        safe_codes = {
            "asset_mismatch",
            "asset_missing",
            "asset_too_large",
            "consumer_unavailable",
            "deploy_failed",
            "invalid_request",
            "invalid_slug",
            "publication_busy",
            "publication_too_large",
            "publisher_forbidden",
            "publisher_unauthorized",
            "public_asset_verification_failed",
            "runtime_component",
            "slug_conflict",
            "slug_locked",
            "unsafe_public_content",
            "verification_timeout",
        }
        if code not in safe_codes:
            code = "consumer_unavailable"
        detail = str(
            payload.get("detail")
            or "The publishing service could not complete the request."
        )[:500]
        if self.token:
            detail = detail.replace(self.token, "[redacted]")
        raise PublicationError(
            response.status_code if response.status_code >= 400 else 502,
            code,
            detail,
            field=(
                str(payload.get("field")) if payload.get("field") else None
            ),
            retryable=bool(payload.get("retryable")),
            request_id=(
                str(payload.get("requestId"))
                if payload.get("requestId")
                else None
            ),
        )
