from __future__ import annotations

from typing import Literal

from pydantic import Field

from helpers import CustomBaseModel

PublicationState = Literal[
    "ineligible",
    "unpublished",
    "preparing",
    "uploading-assets",
    "deploying",
    "verifying",
    "current",
    "stale",
    "failed-unpublished",
    "failed-update",
]


class PublicationStart(CustomBaseModel):
    requested_slug: str | None = Field(None, max_length=80)
    expected_last_modified: float


class PublicationOperation(CustomBaseModel):
    id: str
    content_hash: str
    started_at: str
    retry_after_ms: int = 2000
    phase: str | None = None


class PublicationProblem(CustomBaseModel):
    code: str
    detail: str
    field: str | None = None
    retryable: bool = False
    request_id: str | None = None


class PublicationStateResponse(CustomBaseModel):
    eligible: bool
    state: PublicationState
    source_id: str | None = None
    suggested_slug: str | None = None
    canonical_slug: str | None = None
    canonical_url: str | None = None
    publication_id: str | None = None
    current_content_hash: str | None = None
    published_content_hash: str | None = None
    published_at: str | None = None
    last_modified: float | None = None
    operation: PublicationOperation | None = None
    error: PublicationProblem | None = None
