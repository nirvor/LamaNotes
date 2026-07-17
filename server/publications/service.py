from __future__ import annotations

import re
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from logger import logger

from .consumer import PublicationConsumer
from .errors import PublicationError
from .metadata import PublicationMetadata, PublicationMetadataStore
from .models import (
    PublicationOperation,
    PublicationProblem,
    PublicationStart,
    PublicationStateResponse,
)
from .normalizer import PublicProjection, PublicProjectionBuilder
from .staging import PublicationStagingStore

SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
RESERVED_SLUGS = {"404", "api", "assets", "catalog", "guide", "pages"}
PENDING_STATE = {
    "awaiting-assets": "uploading-assets",
    "uploading-assets": "uploading-assets",
    "deploying": "deploying",
    "verifying": "verifying",
}
PROJECTION_CACHE_SECONDS = 10


class PublicationService:
    def __init__(
        self,
        *,
        storage_path: str,
        base_url: str,
        token: str,
        public_base_url: str = "https://pages.thuber.org",
        timeout_seconds: int = 20,
        consumer: PublicationConsumer | None = None,
    ) -> None:
        self.metadata = PublicationMetadataStore(storage_path)
        self.staging = PublicationStagingStore(storage_path)
        self.storage_path = storage_path
        self.timeout_seconds = timeout_seconds
        self.public_base_url = str(
            public_base_url or "https://pages.thuber.org"
        ).rstrip("/")
        self.enabled = bool(base_url and token)
        self.consumer = consumer
        if self.consumer is None and self.enabled:
            self.consumer = PublicationConsumer(
                base_url, token, timeout_seconds=timeout_seconds
            )
        self._executor = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="nirvnotes-publish"
        )
        self._active: set[tuple[str, str]] = set()
        self._active_lock = threading.Lock()
        self._projection_cache: OrderedDict[
            tuple[str, float], tuple[float, PublicProjection]
        ] = OrderedDict()
        self._projection_cache_lock = threading.Lock()

    def get_state(
        self, title: str, *, refresh_remote: bool = True
    ) -> PublicationStateResponse:
        try:
            _, content, modified, metadata = self.metadata.read(title)
        except FileNotFoundError:
            return PublicationStateResponse(eligible=False, state="ineligible")

        remote_status = None
        remote_error = None
        if metadata.is_pending and self.enabled and refresh_remote:
            try:
                _, remote_status = self.consumer.status(metadata.operation_id)
                if remote_status.get("status") == "succeeded":
                    title, modified, metadata = self._record_success(
                        remote_status
                    )
                    _, content, modified, metadata = self.metadata.read(title)
                elif remote_status.get("status") == "failed":
                    remote_error = self._problem_from_payload(
                        remote_status.get("error") or {}
                    )
                    self.metadata.clear_pending(metadata.source_id)
                    _, content, modified, metadata = self.metadata.read(title)
                elif remote_status.get("status") in {
                    "awaiting-assets",
                    "uploading-assets",
                }:
                    self.submit_advance(
                        metadata.source_id, metadata.operation_hash
                    )
            except PublicationError as error:
                remote_error = error

        projection = None
        projection_error = None
        try:
            projection = self._projection(title, content, modified)
        except PublicationError as error:
            projection_error = error

        if remote_error is None and metadata.source_id:
            staged = None
            try:
                if metadata.is_pending:
                    staged = self.staging.load(
                        metadata.source_id, metadata.operation_hash
                    )
                else:
                    staged = self.staging.latest_record(metadata.source_id)
            except (FileNotFoundError, ValueError):
                staged = None
            if (
                staged
                and staged.get("lastError")
                and (
                    projection is None
                    or staged.get("contentHash") == projection.content_hash
                )
            ):
                remote_error = self._problem_from_payload(staged["lastError"])

        if metadata.is_pending:
            raw_status = str(
                (remote_status or {}).get("status") or "preparing"
            )
            state = PENDING_STATE.get(raw_status, "preparing")
            return self._response(
                title,
                modified,
                metadata,
                projection,
                state,
                operation_payload=remote_status,
                error=remote_error or projection_error,
            )

        if metadata.is_published:
            state = (
                "current"
                if projection
                and projection.content_hash == metadata.published_content_hash
                else "stale"
            )
        else:
            state = "unpublished"
        if remote_error:
            state = (
                "failed-update"
                if metadata.is_published
                else "failed-unpublished"
            )
        return self._response(
            title,
            modified,
            metadata,
            projection,
            state,
            error=remote_error or projection_error,
        )

    def start(
        self, title: str, request: PublicationStart
    ) -> PublicationStateResponse:
        if not self.enabled or self.consumer is None:
            raise PublicationError(
                503,
                "consumer_unavailable",
                "Publishing is not configured on this NirvNotes server.",
                retryable=True,
            )
        try:
            _, content, modified, metadata = self.metadata.ensure_source_id(
                title, request.expected_last_modified
            )
        except ValueError as error:
            if str(error) == "note_changed":
                raise PublicationError(
                    409,
                    "note_changed",
                    "The note changed. Review it and confirm publishing again.",
                )
            if str(error) == "duplicate_source_id":
                raise PublicationError(
                    409,
                    "invalid_request",
                    "This note has a duplicate publication identity.",
                )
            raise

        projection = self._projection(title, content, modified, force=True)
        if metadata.is_pending:
            if metadata.operation_hash != projection.content_hash:
                raise PublicationError(
                    409,
                    "publication_busy",
                    "Wait for the current public update to finish.",
                    retryable=True,
                )
            self.submit_advance(metadata.source_id, projection.content_hash)
            return self._response(
                title,
                modified,
                metadata,
                projection,
                "preparing",
            )

        requested_slug = (
            request.requested_slug.strip() if request.requested_slug else None
        )
        if metadata.is_published:
            if requested_slug and requested_slug != metadata.canonical_slug:
                raise PublicationError(
                    409,
                    "slug_locked",
                    "This note already owns a fixed public URL.",
                    field="requestedSlug",
                )
            requested_slug = None
        else:
            self._validate_slug(requested_slug)

        record = self.staging.save_projection(
            source_id=metadata.source_id,
            title=title,
            source_modified=modified,
            requested_slug=requested_slug,
            projection=projection,
        )
        try:
            status_code, payload = self.consumer.begin(record["manifest"])
        except PublicationError as error:
            self.staging.set_error(
                metadata.source_id, projection.content_hash, error.problem()
            )
            raise
        if payload.get("status") == "succeeded" or status_code == 200:
            self._record_success(payload)
            self.staging.remove(metadata.source_id, projection.content_hash)
            return self.get_state(title, refresh_remote=False)

        operation_id = str(payload.get("operationId") or "")
        if not operation_id:
            raise PublicationError(
                502,
                "consumer_unavailable",
                "The publishing service returned no operation ID.",
                retryable=True,
            )
        started_at = (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )
        self.staging.set_operation(
            metadata.source_id,
            projection.content_hash,
            operation_id,
            started_at,
        )
        title, modified, metadata = self.metadata.update_pending(
            metadata.source_id,
            operation_id=operation_id,
            operation_hash=projection.content_hash,
            started_at=started_at,
        )
        self.submit_advance(metadata.source_id, projection.content_hash)
        return self._response(
            title,
            modified,
            metadata,
            projection,
            PENDING_STATE.get(str(payload.get("status")), "preparing"),
            operation_payload=payload,
        )

    def resume_pending(self) -> None:
        self.staging.remove_expired()
        records_by_source = {}
        for record in self.staging.list_records():
            source_id = str(record.get("sourceId") or "")
            if not source_id:
                continue
            records_by_source.setdefault(source_id, []).append(record)

        for source_id, records in records_by_source.items():
            try:
                _, _, modified, metadata = self.metadata.find_by_source_id(
                    source_id
                )
            except (FileNotFoundError, ValueError):
                continue
            candidates = (
                [
                    record
                    for record in records
                    if record.get("contentHash") == metadata.operation_hash
                ]
                if metadata.is_pending
                else records
            )
            if not candidates:
                continue
            record = max(
                candidates,
                key=lambda item: float(item.get("updatedAt") or 0),
            )
            content_hash = str(record.get("contentHash") or "")
            last_error = record.get("lastError") or {}
            matches_pending = (
                metadata.is_pending and metadata.operation_hash == content_hash
            )
            matches_unstarted = (
                not metadata.is_pending
                and record.get("operationId") is None
                and abs(modified - float(record.get("sourceModified") or 0))
                <= 0.001
            )
            if (
                content_hash
                and (matches_pending or matches_unstarted)
                and not (last_error and last_error.get("retryable") is False)
            ):
                self.submit_advance(source_id, content_hash)

    def submit_advance(self, source_id: str, content_hash: str) -> None:
        if not self.enabled or not source_id or not content_hash:
            return
        key = (source_id, content_hash)
        with self._active_lock:
            if key in self._active:
                return
            self._active.add(key)
        self._executor.submit(self._advance_job, key)

    def _advance_job(self, key: tuple[str, str]) -> None:
        source_id, content_hash = key
        try:
            self._advance(source_id, content_hash)
        except PublicationError as error:
            logger.warning("Publication %s paused: %s", source_id, error.code)
            try:
                self.staging.set_error(
                    source_id, content_hash, error.problem()
                )
            except (FileNotFoundError, ValueError):
                pass
            if not error.retryable:
                try:
                    _, _, _, metadata = self.metadata.find_by_source_id(
                        source_id
                    )
                    if metadata.operation_hash == content_hash:
                        self.metadata.clear_pending(source_id)
                except (FileNotFoundError, ValueError):
                    pass
        except Exception:
            logger.exception("Publication %s stopped unexpectedly", source_id)
            try:
                self.staging.set_error(
                    source_id,
                    content_hash,
                    PublicationError(
                        502,
                        "consumer_unavailable",
                        "Publishing stopped unexpectedly and will be retried.",
                        retryable=True,
                    ).problem(),
                )
            except (FileNotFoundError, ValueError):
                pass
        finally:
            with self._active_lock:
                self._active.discard(key)

    def _advance(self, source_id: str, content_hash: str) -> None:
        record = self.staging.load(source_id, content_hash)
        _, payload = self.consumer.begin(record["manifest"])
        if payload.get("status") == "succeeded":
            self._record_success(payload)
            self.staging.remove(source_id, content_hash)
            return
        if payload.get("status") == "failed":
            raise self._problem_from_payload(payload.get("error") or {})

        operation_id = str(
            payload.get("operationId") or record.get("operationId") or ""
        )
        if not operation_id:
            raise PublicationError(
                502,
                "consumer_unavailable",
                "The publishing operation has no ID.",
                retryable=True,
            )
        started_at = str(
            record.get("startedAt")
            or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )
        self.staging.set_operation(
            source_id, content_hash, operation_id, started_at
        )
        self.metadata.update_pending(
            source_id,
            operation_id=operation_id,
            operation_hash=content_hash,
            started_at=started_at,
        )

        for missing in payload.get("missingAssets") or []:
            asset_id = str(missing.get("assetId") or "")
            asset = next(
                (
                    item
                    for item in record["manifest"]["assets"]
                    if item["assetId"] == asset_id
                ),
                None,
            )
            if not asset:
                raise PublicationError(
                    422,
                    "asset_missing",
                    "The staged asset manifest is incomplete.",
                )
            content = self.staging.asset_bytes(record, asset_id)
            self.consumer.upload(
                str(missing.get("uploadPath") or ""), asset, content
            )

        if str(payload.get("status") or "") in {
            "awaiting-assets",
            "uploading-assets",
        }:
            _, payload = self.consumer.finalize(operation_id, content_hash)
        deadline = time.monotonic() + 20 * 60
        while time.monotonic() < deadline:
            status = str(payload.get("status") or "")
            if status == "succeeded":
                self._record_success(payload)
                self.staging.remove(source_id, content_hash)
                return
            if status == "failed":
                problem = self._problem_from_payload(
                    payload.get("error") or {}
                )
                self.metadata.clear_pending(source_id)
                self.staging.set_error(
                    source_id, content_hash, problem.problem()
                )
                raise problem
            delay_ms = max(
                1000, min(int(payload.get("retryAfterMs") or 3000), 10000)
            )
            time.sleep(delay_ms / 1000)
            _, payload = self.consumer.status(operation_id)
        raise PublicationError(
            504,
            "verification_timeout",
            "Public verification is still pending.",
            retryable=True,
        )

    def _record_success(
        self, payload: dict
    ) -> tuple[str, float, PublicationMetadata]:
        required = (
            "publicationId",
            "sourceId",
            "canonicalSlug",
            "canonicalUrl",
            "publishedContentHash",
            "publishedAt",
        )
        if any(not payload.get(key) for key in required):
            raise PublicationError(
                502,
                "consumer_unavailable",
                "The publishing service returned an incomplete success response.",
                retryable=True,
            )
        canonical_url = str(payload["canonicalUrl"])
        expected_prefix = f"{self.public_base_url}/"
        if not canonical_url.startswith(expected_prefix):
            raise PublicationError(
                502,
                "consumer_unavailable",
                "The publishing service returned an unexpected public URL.",
                retryable=True,
            )
        return self.metadata.update_success(
            str(payload["sourceId"]),
            publication_id=str(payload["publicationId"]),
            canonical_slug=str(payload["canonicalSlug"]),
            canonical_url=canonical_url,
            published_hash=str(payload["publishedContentHash"]),
            published_at=str(payload["publishedAt"]),
        )

    def _projection(
        self,
        title: str,
        content: str,
        modified: float,
        *,
        force: bool = False,
    ) -> PublicProjection:
        key = (title, modified)
        if not force:
            with self._projection_cache_lock:
                if key in self._projection_cache:
                    cached_at, cached_projection = self._projection_cache[key]
                    if time.monotonic() - cached_at < PROJECTION_CACHE_SECONDS:
                        self._projection_cache.move_to_end(key)
                        return cached_projection
                    self._projection_cache.pop(key, None)
        projection = PublicProjectionBuilder(
            self.storage_path, self.timeout_seconds
        ).build(title, content)
        with self._projection_cache_lock:
            self._projection_cache[key] = (time.monotonic(), projection)
            self._projection_cache.move_to_end(key)
            while len(self._projection_cache) > 16:
                self._projection_cache.popitem(last=False)
        return projection

    def _response(
        self,
        title: str,
        modified: float,
        metadata: PublicationMetadata,
        projection: PublicProjection | None,
        state: str,
        *,
        operation_payload: dict | None = None,
        error: PublicationError | None = None,
    ) -> PublicationStateResponse:
        operation = None
        if metadata.is_pending:
            operation = PublicationOperation(
                id=metadata.operation_id,
                content_hash=metadata.operation_hash,
                started_at=metadata.operation_started_at or "",
                retry_after_ms=int(
                    (operation_payload or {}).get("retryAfterMs") or 2000
                ),
                phase=(operation_payload or {}).get("phase"),
            )
        problem = None
        if error:
            problem = PublicationProblem(
                code=error.code,
                detail=error.detail,
                field=error.field,
                retryable=error.retryable,
                request_id=error.request_id,
            )
        return PublicationStateResponse(
            eligible=True,
            state=state,
            source_id=metadata.source_id,
            suggested_slug=(
                None
                if metadata.is_published
                else PublicProjectionBuilder.suggested_slug(title)
            ),
            canonical_slug=metadata.canonical_slug,
            canonical_url=metadata.canonical_url,
            publication_id=metadata.publication_id,
            current_content_hash=(
                projection.content_hash if projection else None
            ),
            published_content_hash=metadata.published_content_hash,
            published_at=metadata.published_at,
            last_modified=modified,
            operation=operation,
            error=problem,
        )

    @staticmethod
    def _validate_slug(slug: str | None) -> None:
        if (
            not slug
            or len(slug) > 80
            or not SLUG.fullmatch(slug)
            or slug in RESERVED_SLUGS
        ):
            raise PublicationError(
                400,
                "invalid_slug",
                "Use 1-80 lowercase letters, numbers, and single hyphens.",
                field="requestedSlug",
            )

    @staticmethod
    def _problem_from_payload(payload: dict) -> PublicationError:
        status = payload.get("status")
        status = (
            status if isinstance(status, int) and 400 <= status <= 599 else 503
        )
        return PublicationError(
            status,
            str(payload.get("code") or "consumer_unavailable"),
            str(payload.get("detail") or "Publishing failed."),
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
