from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from pathlib import Path

from .metadata import atomic_write_text
from .normalizer import PublicProjection


class PublicationStagingStore:
    def __init__(self, storage_path: str) -> None:
        self.root = (
            Path(storage_path).resolve() / ".lamanotes-publish"
        ).resolve()
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)

    def save_projection(
        self,
        *,
        source_id: str,
        title: str,
        source_modified: float,
        requested_slug: str | None,
        projection: PublicProjection,
    ) -> dict:
        directory = self._directory(
            source_id, projection.content_hash, create=True
        )
        assets_directory = directory / "assets"
        assets_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        manifest = projection.manifest(source_id, requested_slug)
        record = {
            "schemaVersion": 1,
            "sourceId": source_id,
            "title": title,
            "sourceModified": source_modified,
            "contentHash": projection.content_hash,
            "requestedSlug": requested_slug,
            "manifest": manifest,
            "operationId": None,
            "startedAt": None,
            "lastError": None,
            "updatedAt": time.time(),
        }
        for asset in projection.assets:
            self._atomic_write_bytes(
                assets_directory / asset.file_name, asset.content
            )
        atomic_write_text(
            directory / "record.json",
            json.dumps(record, ensure_ascii=False, separators=(",", ":")),
        )
        return record

    def set_operation(
        self,
        source_id: str,
        content_hash: str,
        operation_id: str,
        started_at: str,
    ) -> dict:
        record = self.load(source_id, content_hash)
        record["operationId"] = operation_id
        record["startedAt"] = started_at
        record["lastError"] = None
        record["updatedAt"] = time.time()
        self._save_record(record)
        return record

    def set_error(
        self, source_id: str, content_hash: str, error: dict
    ) -> dict:
        record = self.load(source_id, content_hash)
        record["lastError"] = {
            "code": str(error.get("code") or "consumer_unavailable"),
            "detail": str(error.get("detail") or "Publishing failed."),
            "field": error.get("field"),
            "retryable": bool(error.get("retryable")),
            "requestId": error.get("requestId"),
        }
        record["updatedAt"] = time.time()
        self._save_record(record)
        return record

    def load(self, source_id: str, content_hash: str) -> dict:
        path = self._directory(source_id, content_hash) / "record.json"
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raise FileNotFoundError(content_hash)
        if (
            record.get("sourceId") != source_id
            or record.get("contentHash") != content_hash
            or record.get("schemaVersion") != 1
        ):
            raise ValueError("invalid_stage")
        return record

    def asset_bytes(self, record: dict, asset_id: str) -> bytes:
        asset = next(
            (
                item
                for item in record.get("manifest", {}).get("assets", [])
                if item.get("assetId") == asset_id
            ),
            None,
        )
        if not asset:
            raise FileNotFoundError(asset_id)
        path = (
            self._directory(record["sourceId"], record["contentHash"])
            / "assets"
            / str(asset["fileName"])
        ).resolve()
        expected_root = (
            self._directory(record["sourceId"], record["contentHash"])
            / "assets"
        ).resolve()
        if path.parent != expected_root or not path.is_file():
            raise FileNotFoundError(asset_id)
        content = path.read_bytes()
        if len(content) != asset.get("byteLength"):
            raise ValueError("asset_mismatch")
        return content

    def list_records(self) -> list[dict]:
        records = []
        for path in self.root.glob("*/*/record.json"):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
                if record.get("schemaVersion") == 1:
                    records.append(record)
            except (OSError, json.JSONDecodeError):
                continue
        return records

    def latest_record(self, source_id: str) -> dict | None:
        records = [
            record
            for record in self.list_records()
            if record.get("sourceId") == source_id
        ]
        return max(
            records,
            key=lambda record: float(record.get("updatedAt") or 0),
            default=None,
        )

    def remove(self, source_id: str, content_hash: str) -> None:
        directory = self._directory(source_id, content_hash)
        shutil.rmtree(directory, ignore_errors=True)
        source_directory = directory.parent
        try:
            source_directory.rmdir()
        except OSError:
            pass

    def remove_expired(self, maximum_age_seconds: int = 48 * 60 * 60) -> None:
        cutoff = time.time() - maximum_age_seconds
        for record in self.list_records():
            if float(record.get("updatedAt") or 0) < cutoff:
                self.remove(record["sourceId"], record["contentHash"])

    def _directory(
        self, source_id: str, content_hash: str, *, create: bool = False
    ) -> Path:
        if not self._safe_identifier(source_id):
            raise ValueError("invalid_source_id")
        digest = str(content_hash).removeprefix("sha256:")
        if len(digest) != 64 or any(
            character not in "0123456789abcdef" for character in digest
        ):
            raise ValueError("invalid_content_hash")
        path = (self.root / source_id / digest).resolve()
        if self.root not in path.parents:
            raise ValueError("invalid_stage_path")
        if create:
            path.mkdir(mode=0o700, parents=True, exist_ok=True)
        return path

    @staticmethod
    def _safe_identifier(value: str) -> bool:
        return bool(value) and all(
            character.isalnum() or character in "-_" for character in value
        )

    def _save_record(self, record: dict) -> None:
        directory = self._directory(
            record["sourceId"], record["contentHash"], create=True
        )
        atomic_write_text(
            directory / "record.json",
            json.dumps(record, ensure_ascii=False, separators=(",", ":")),
        )

    @staticmethod
    def _atomic_write_bytes(path: Path, content: bytes) -> None:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
        )
        try:
            with os.fdopen(descriptor, "wb") as file:
                file.write(content)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary_name, path)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
