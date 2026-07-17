from __future__ import annotations

import html
import os
import re
import tempfile
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup

from helpers import is_valid_filename

SOURCE_ID = "nirvnotes-source-id"
PUBLICATION_ID = "nirvnotes-publication-id"
PUBLICATION_SLUG = "nirvnotes-publication-slug"
PUBLICATION_URL = "nirvnotes-publication-url"
PUBLISHED_HASH = "nirvnotes-published-content-hash"
PUBLISHED_AT = "nirvnotes-published-at"
OPERATION_ID = "nirvnotes-publish-operation-id"
OPERATION_HASH = "nirvnotes-publish-operation-hash"
OPERATION_STARTED_AT = "nirvnotes-publish-started-at"

PUBLICATION_META_NAMES = (
    SOURCE_ID,
    PUBLICATION_ID,
    PUBLICATION_SLUG,
    PUBLICATION_URL,
    PUBLISHED_HASH,
    PUBLISHED_AT,
    OPERATION_ID,
    OPERATION_HASH,
    OPERATION_STARTED_AT,
)
PUBLICATION_META_SET = set(PUBLICATION_META_NAMES)
PUBLICATION_FILE_LOCK = threading.RLock()
META_TAG_RE = re.compile(r"<meta\b[^>]*>", re.IGNORECASE)
ATTRIBUTE_RE_TEMPLATE = (
    r"\b{attribute}\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s>]+))"
)


@dataclass(frozen=True)
class PublicationMetadata:
    source_id: str | None = None
    publication_id: str | None = None
    canonical_slug: str | None = None
    canonical_url: str | None = None
    published_content_hash: str | None = None
    published_at: str | None = None
    operation_id: str | None = None
    operation_hash: str | None = None
    operation_started_at: str | None = None

    @property
    def is_published(self) -> bool:
        return bool(
            self.publication_id
            and self.canonical_slug
            and self.canonical_url
            and self.published_content_hash
        )

    @property
    def is_pending(self) -> bool:
        return bool(self.operation_id and self.operation_hash)

    def as_values(self) -> dict[str, str]:
        values = {
            SOURCE_ID: self.source_id,
            PUBLICATION_ID: self.publication_id,
            PUBLICATION_SLUG: self.canonical_slug,
            PUBLICATION_URL: self.canonical_url,
            PUBLISHED_HASH: self.published_content_hash,
            PUBLISHED_AT: self.published_at,
            OPERATION_ID: self.operation_id,
            OPERATION_HASH: self.operation_hash,
            OPERATION_STARTED_AT: self.operation_started_at,
        }
        return {key: value for key, value in values.items() if value}


def parse_publication_metadata(content: str) -> PublicationMetadata:
    soup = BeautifulSoup(content or "", "html.parser")
    values: dict[str, str] = {}
    for meta in soup.find_all("meta"):
        name = str(meta.get("name") or "").strip().lower()
        if name in PUBLICATION_META_SET:
            values[name] = str(meta.get("content") or "").strip()
    return PublicationMetadata(
        source_id=values.get(SOURCE_ID),
        publication_id=values.get(PUBLICATION_ID),
        canonical_slug=values.get(PUBLICATION_SLUG),
        canonical_url=values.get(PUBLICATION_URL),
        published_content_hash=values.get(PUBLISHED_HASH),
        published_at=values.get(PUBLISHED_AT),
        operation_id=values.get(OPERATION_ID),
        operation_hash=values.get(OPERATION_HASH),
        operation_started_at=values.get(OPERATION_STARTED_AT),
    )


def _attribute_value(markup: str, attribute: str) -> str:
    pattern = re.compile(
        ATTRIBUTE_RE_TEMPLATE.format(attribute=re.escape(attribute)),
        re.IGNORECASE,
    )
    match = pattern.search(markup)
    if not match:
        return ""
    return html.unescape(
        next(value for value in match.groups() if value is not None)
    )


def strip_publication_metadata(content: str) -> str:
    def replace(markup: re.Match) -> str:
        name = _attribute_value(markup.group(0), "name").strip().lower()
        return "" if name in PUBLICATION_META_SET else markup.group(0)

    return META_TAG_RE.sub(replace, content or "")


def inject_publication_metadata(content: str, values: dict[str, str]) -> str:
    stripped = strip_publication_metadata(content)
    ordered = [
        (name, values.get(name))
        for name in PUBLICATION_META_NAMES
        if values.get(name)
    ]
    if not ordered:
        return stripped

    meta_markup = "\n".join(
        f'    <meta name="{name}" content="{html.escape(value, quote=True)}">'
        for name, value in ordered
    )
    if re.search(r"</head\s*>", stripped, re.IGNORECASE):
        return re.sub(
            r"</head\s*>",
            f"{meta_markup}\n  </head>",
            stripped,
            count=1,
            flags=re.IGNORECASE,
        )
    html_open = re.search(r"<html\b[^>]*>", stripped, re.IGNORECASE)
    if html_open:
        position = html_open.end()
        return (
            stripped[:position]
            + f"\n  <head>\n{meta_markup}\n  </head>"
            + stripped[position:]
        )
    return f"<head>\n{meta_markup}\n</head>\n{stripped}"


def preserve_publication_metadata(existing: str, incoming: str) -> str:
    values = parse_publication_metadata(existing).as_values()
    return inject_publication_metadata(incoming, values)


def atomic_write_text(path: Path, content: str) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_name, path)
        try:
            directory_descriptor = os.open(str(path.parent), os.O_RDONLY)
        except OSError:
            directory_descriptor = None
        if directory_descriptor is not None:
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


class PublicationMetadataStore:
    def __init__(self, storage_path: str) -> None:
        self.storage_path = Path(storage_path).resolve()
        self._lock = PUBLICATION_FILE_LOCK

    def note_path(self, title: str) -> Path:
        is_valid_filename(title)
        path = (self.storage_path / f"{title}.html").resolve()
        if path.parent != self.storage_path or not path.is_file():
            raise FileNotFoundError(title)
        return path

    def read(self, title: str) -> tuple[Path, str, float, PublicationMetadata]:
        path = self.note_path(title)
        content = path.read_text(encoding="utf-8")
        return (
            path,
            content,
            path.stat().st_mtime,
            parse_publication_metadata(content),
        )

    def ensure_source_id(
        self, title: str, expected_last_modified: float
    ) -> tuple[Path, str, float, PublicationMetadata]:
        with self._lock:
            path, content, modified, metadata = self.read(title)
            if abs(modified - expected_last_modified) > 0.001:
                raise ValueError("note_changed")
            if metadata.source_id:
                self._raise_if_duplicate(metadata.source_id, path)
                return path, content, modified, metadata

            source_id = str(uuid.uuid4())
            updated = inject_publication_metadata(
                content, {SOURCE_ID: source_id}
            )
            atomic_write_text(path, updated)
            modified = path.stat().st_mtime
            return path, updated, modified, parse_publication_metadata(updated)

    def update_pending(
        self,
        source_id: str,
        *,
        operation_id: str,
        operation_hash: str,
        started_at: str,
    ) -> tuple[str, float, PublicationMetadata]:
        return self._mutate_source(
            source_id,
            {
                OPERATION_ID: operation_id,
                OPERATION_HASH: operation_hash,
                OPERATION_STARTED_AT: started_at,
            },
        )

    def update_success(
        self,
        source_id: str,
        *,
        publication_id: str,
        canonical_slug: str,
        canonical_url: str,
        published_hash: str,
        published_at: str,
    ) -> tuple[str, float, PublicationMetadata]:
        return self._mutate_source(
            source_id,
            {
                PUBLICATION_ID: publication_id,
                PUBLICATION_SLUG: canonical_slug,
                PUBLICATION_URL: canonical_url,
                PUBLISHED_HASH: published_hash,
                PUBLISHED_AT: published_at,
                OPERATION_ID: None,
                OPERATION_HASH: None,
                OPERATION_STARTED_AT: None,
            },
        )

    def clear_pending(
        self, source_id: str
    ) -> tuple[str, float, PublicationMetadata]:
        return self._mutate_source(
            source_id,
            {
                OPERATION_ID: None,
                OPERATION_HASH: None,
                OPERATION_STARTED_AT: None,
            },
        )

    def find_by_source_id(
        self, source_id: str
    ) -> tuple[Path, str, float, PublicationMetadata]:
        with self._lock:
            matches = []
            for path in self.storage_path.glob("*.html"):
                content = path.read_text(encoding="utf-8")
                metadata = parse_publication_metadata(content)
                if metadata.source_id == source_id:
                    matches.append(
                        (path, content, path.stat().st_mtime, metadata)
                    )
            if not matches:
                raise FileNotFoundError(source_id)
            if len(matches) > 1:
                raise ValueError("duplicate_source_id")
            return matches[0]

    def _mutate_source(
        self, source_id: str, changes: dict[str, str | None]
    ) -> tuple[str, float, PublicationMetadata]:
        with self._lock:
            path, content, _, metadata = self.find_by_source_id(source_id)
            values = metadata.as_values()
            for name, value in changes.items():
                if value:
                    values[name] = value
                else:
                    values.pop(name, None)
            updated = inject_publication_metadata(content, values)
            atomic_write_text(path, updated)
            return (
                path.stem,
                path.stat().st_mtime,
                parse_publication_metadata(updated),
            )

    def _raise_if_duplicate(self, source_id: str, expected: Path) -> None:
        for path in self.storage_path.glob("*.html"):
            if path.resolve() == expected.resolve():
                continue
            content = path.read_text(encoding="utf-8")
            if parse_publication_metadata(content).source_id == source_id:
                raise ValueError("duplicate_source_id")
