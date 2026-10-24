from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator

from helpers import CustomBaseModel

NoteId = Annotated[str, Field(pattern=r"^ln-[a-f0-9]{32}$")]
CaptureId = Annotated[str, Field(pattern=r"^lc-[a-f0-9]{32}$")]
AssetId = Annotated[str, Field(pattern=r"^la-[a-f0-9]{32}$")]
Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Opaque = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")]


class StrictModel(CustomBaseModel):
    model_config = {**CustomBaseModel.model_config, "extra": "forbid"}


def validate_source_url(value):
    if value is None:
        return None
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("A source must be an HTTP(S) URL.")
    if parsed.username or parsed.password:
        raise ValueError("Source URLs cannot contain credentials.")
    return value


class CapabilityCreate(StrictModel):
    client_id: Opaque
    job_id: Annotated[str, Field(pattern=r"^lr-[a-f0-9]{32}$")] | None = None
    expires_in: int = Field(default=3600, ge=60, le=2592000)
    scopes: list[str] = Field(min_length=1, max_length=10)
    note_ids: list[NoteId] = Field(default_factory=list, max_length=200)
    capture_ids: list[CaptureId] = Field(default_factory=list, max_length=200)


class CapabilityRenew(StrictModel):
    expires_in: int = Field(strict=True, ge=60, le=2592000)


class Enroll(StrictModel):
    title: str = Field(min_length=1, max_length=180)
    expected_version: Hash
    personal: Literal[True]


class PrivateNoteCreate(StrictModel):
    note_id: NoteId | None = None
    title: str = Field(min_length=1, max_length=180)
    content: str = Field(max_length=2_000_000)
    capture_ids: list[CaptureId] = Field(default_factory=list, max_length=30)
    asset_ids: list[AssetId] = Field(default_factory=list, max_length=60)


class PrivateNoteUpdate(StrictModel):
    expected_version: Hash
    title: str | None = Field(default=None, min_length=1, max_length=180)
    content: str | None = Field(default=None, max_length=2_000_000)


class Provenance(StrictModel):
    channel: Literal[
        "web", "android-share", "windows", "telegram", "whatsapp", "codex"
    ]
    description: str | None = Field(default=None, max_length=500)
    captured_at: str | None = Field(default=None, max_length=40)


class CaptureCreate(StrictModel):
    kind: Literal["text", "link", "image", "file", "audio"]
    text: str = Field(default="", max_length=100_000)
    source_url: str | None = Field(default=None, max_length=4000)
    asset_ids: list[AssetId] = Field(default_factory=list, max_length=10)
    provenance: Provenance

    _url = field_validator("source_url")(validate_source_url)


class ParentReference(StrictModel):
    note_id: NoteId
    version: Hash
    research_id: Annotated[str, Field(pattern=r"^lr-[a-f0-9]{32}$")] | None = (
        None
    )


class CaptureReference(StrictModel):
    capture_id: CaptureId
    sha256: Hash


class ReferenceCheck(StrictModel):
    parent: ParentReference | None = None
    sources: list[CaptureReference] = Field(
        default_factory=list, max_length=30
    )


class ResearchReference(StrictModel):
    research_id: Annotated[str, Field(pattern=r"^lr-[a-f0-9]{32}$")]


class AttachAssets(StrictModel):
    expected_version: Hash
    asset_ids: list[AssetId] = Field(min_length=1, max_length=10)


class ReaderSession(StrictModel):
    note_id: NoteId
    expires_in: int = Field(default=120, ge=30, le=300)


class ResearchIntake(StrictModel):
    note_id: NoteId
    expected_version: Hash


class ResearchIntakeConsume(StrictModel):
    ticket: Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{43}$")]
