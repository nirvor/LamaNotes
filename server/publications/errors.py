from __future__ import annotations


class PublicationError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        detail: str,
        *,
        field: str | None = None,
        retryable: bool = False,
        request_id: str | None = None,
    ) -> None:
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail
        self.field = field
        self.retryable = retryable
        self.request_id = request_id

    def problem(self) -> dict:
        return {
            "type": (
                "https://pages.thuber.org/problems/"
                + self.code.replace("_", "-")
            ),
            "title": self._title(),
            "status": self.status,
            "code": self.code,
            "detail": self.detail,
            **({"field": self.field} if self.field else {}),
            "retryable": self.retryable,
            **({"requestId": self.request_id} if self.request_id else {}),
        }

    def _title(self) -> str:
        return {
            "asset_mismatch": "Asset does not match",
            "asset_missing": "Asset is missing",
            "asset_too_large": "Asset is too large",
            "consumer_unavailable": "Publishing is unavailable",
            "deploy_failed": "Public deployment failed",
            "invalid_request": "Invalid publication request",
            "invalid_slug": "Invalid URL name",
            "note_changed": "Note changed",
            "publication_busy": "Publication already in progress",
            "publication_too_large": "Publication is too large",
            "publisher_forbidden": "Publisher is not allowed",
            "publisher_unauthorized": "Publisher is not authorized",
            "public_asset_verification_failed": (
                "Public asset verification failed"
            ),
            "runtime_component": "Interactive component is not publishable",
            "slug_conflict": "Slug already in use",
            "slug_locked": "Published URL is fixed",
            "unsafe_public_content": "Public content is unsafe",
            "verification_timeout": "Public verification timed out",
        }.get(self.code, "Publishing failed")
