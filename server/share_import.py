"""Owner-confirmed import of one bounded LamaShare export."""
import hashlib
import re
from datetime import datetime, timezone
from html import escape

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import Field, field_validator, model_validator
from starlette.concurrency import run_in_threadpool

from auth.scopes import NOTES_WRITE
from private_api.models import CaptureCreate, PrivateNoteCreate, StrictModel, validate_source_url
from private_api.media import image_preview
from publications.metadata import PUBLICATION_FILE_LOCK

SHARE_ORIGIN = "http://nirvstart:8080"
MAX_BYTES = 20 * 1024 * 1024
OPAQUE = r"^[A-Za-z0-9_-]{32}$"
NO_STORE = {"Cache-Control": "no-store", "Vary": "Authorization, Cookie"}


def fail(status, message):
    raise HTTPException(status, message, headers=NO_STORE)


def utc(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
            raise ValueError
        return parsed
    except (ValueError, AttributeError, OverflowError):
        raise ValueError("Use a UTC ISO timestamp.") from None


class ImportRequest(StrictModel):
    ticket: str = Field(pattern=r"^lst_[A-Za-z0-9_-]{43}$")


class ShareSource(StrictModel):
    platform: str = Field(pattern=r"^(android|web)$")
    package: str = Field(strict=True, max_length=180, pattern=r"^[^\x00-\x1f\x7f]*$")
    received_at: str = Field(strict=True, min_length=20, max_length=40)

    _time = field_validator("received_at")(lambda value: (utc(value), value)[1])


class ShareFile(StrictModel):
    id: str = Field(pattern=OPAQUE)
    name: str = Field(strict=True, min_length=1, max_length=180, pattern=r"^[^/\\\x00-\x1f\x7f]+$")
    mime: str
    size: int = Field(strict=True, ge=0, le=MAX_BYTES)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    uploaded: bool = Field(strict=True)

    @model_validator(mode="after")
    def valid_file(self):
        if not self.uploaded or not self.name.strip() or self.name in {".", ".."}:
            raise ValueError("Use a complete file.")
        return self


class ShareItem(StrictModel):
    id: str = Field(pattern=OPAQUE)
    title: str = Field(strict=True, max_length=180)
    text: str = Field(strict=True, max_length=100000)
    url: str = Field(strict=True, max_length=4000)
    annotation: str = Field(strict=True, max_length=100000)
    source: ShareSource | None = None
    files: list[ShareFile] = Field(max_length=10)
    ready: bool = Field(strict=True)
    created_at: str = Field(strict=True, min_length=20, max_length=40)

    _time = field_validator("created_at")(lambda value: (utc(value), value)[1])

    @field_validator("url")
    @classmethod
    def source_url(cls, value):
        if value:
            validate_source_url(value)
            if re.search(r"[\s\\\x00-\x1f\x7f]", value):
                raise ValueError("Invalid source URL.")
        return value

    @model_validator(mode="after")
    def bounded_item(self):
        if (not self.ready or sum(file.size for file in self.files) > MAX_BYTES
            or len({file.id for file in self.files}) != len(self.files)
            or not self.files and not any(v.strip() for v in (self.title, self.text, self.url, self.annotation))):
            raise ValueError("Use a complete bounded Share item.")
        return self


class ShareExport(StrictModel):
    item: ShareItem
    file_token: str = Field(pattern=r"^lse_[A-Za-z0-9_-]{43}$")
    expires_at: str = Field(strict=True, min_length=20, max_length=40)

    @field_validator("expires_at")
    @classmethod
    def valid_expiry(cls, value):
        remaining = (utc(value) - datetime.now(timezone.utc)).total_seconds()
        if remaining <= 0 or remaining > 610:
            raise ValueError("The Share export is expired or invalid.")
        return value


class ShareCapture(CaptureCreate):
    share: ShareItem


async def bounded_response(client, method, path, *, limit, **kwargs):
    # Callers supply only fixed paths and validated opaque file IDs.
    async with client.stream(method, SHARE_ORIGIN + path, **kwargs) as response:
        if response.status_code in {401, 403, 404, 410}:
            fail(410, "This Share export expired. Open Save to Notes again in LamaShare.")
        if response.status_code != 200:
            fail(502, "LamaShare could not provide this item. Please try again.")
        if response.headers.get("content-encoding", "identity") != "identity":
            fail(502, "LamaShare returned an unsupported file response.")
        chunks, size = [], 0
        async for chunk in response.aiter_raw():
            size += len(chunk)
            if size > limit:
                fail(413, "The Share export exceeds its size limit.")
            chunks.append(chunk)
        return b"".join(chunks), response.headers.get("content-type", "").split(";")[0].strip().lower()


class ShareImporter:
    def __init__(self, service, transport=None):
        self.service = service
        self.transport = transport

    def replay(self, item):
        payload = item.model_dump(by_alias=True)
        key = "share-" + item.id
        note_id = self.service.store.replay(None, "lamashare-import", key, payload)
        if note_id:
            try:
                return self.service.read_note(None, note_id)
            except HTTPException as error:
                if error.status_code == 404:
                    fail(409, "This item was already imported, but its note is unavailable. Your original remains in LamaShare.")
                raise
        return None

    async def import_ticket(self, ticket):
        try:
            async with httpx.AsyncClient(transport=self.transport, trust_env=False, follow_redirects=False,
                    timeout=httpx.Timeout(30, connect=8), headers={"Accept-Encoding": "identity"}) as client:
                raw, media = await bounded_response(client, "POST", "/api/share/v1/notes-export",
                    limit=2 * 1024 * 1024, json={"ticket": ticket})
                if media != "application/json":
                    fail(502, "LamaShare returned an invalid export.")
                export = ShareExport.model_validate_json(raw)
                replay = await run_in_threadpool(self.replay, export.item)
                if replay:
                    return replay
                files = []
                for file in export.item.files:
                    data, media = await bounded_response(client, "GET", "/api/share/v1/notes-export/files/" + file.id,
                        limit=file.size, headers={"Authorization": "Bearer " + export.file_token})
                    if (len(data) != file.size
                        or hashlib.sha256(data).hexdigest() != file.sha256):
                        fail(422, "A shared file could not be verified. The original remains in LamaShare.")
                    files.append(data)
        except httpx.HTTPError:
            fail(502, "LamaShare is unavailable. Your item remains on the VPS. Please try again.")
        except (ValueError, UnicodeError):
            fail(422, "This Share export could not be verified. The original remains in LamaShare.")
        return await run_in_threadpool(self.finish, export.item, files)

    def title(self, item, note_key):
        with self.service.store.connect() as db:
            row = db.execute("SELECT object_id FROM receipts WHERE actor='owner' AND operation='note' AND key=?", (note_key,)).fetchone()
        if row:
            try:
                return self.service.resolve(row["object_id"]).title
            except HTTPException:
                pass
        suggested = item.title or item.text.split("\n")[0] or (item.files[0].name if item.files else "Shared note")
        title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', ' ', suggested).strip().rstrip(".")[:180] or "Shared note"
        taken = {path.stem.casefold() for path in self.service.root.glob("*.html")}
        if title.casefold() in taken:
            title = title[:140] + " - " + item.id
        return title

    def finish(self, item, files):
        with PUBLICATION_FILE_LOCK:
            existing = self.replay(item)
            if existing:
                return existing
            key = "share-" + item.id
            assets = [self.service.create_asset(None, data, file.mime, "source", None, None, key + "-" + file.id)
                      for file, data in zip(item.files, files, strict=True)]
            kind = ("image" if item.files[0].mime.startswith("image/") else "audio" if item.files[0].mime.startswith("audio/") else "file") if item.files else "link" if item.url else "text"
            capture = self.service.create_capture(None, ShareCapture(kind=kind,
                text=item.text or item.annotation or item.title, source_url=item.url or None,
                asset_ids=[asset["assetId"] for asset in assets], share=item,
                provenance={"channel": "android-share" if item.source and item.source.platform == "android" else "web",
                            "description": "LamaShare import. Source metadata is unverified.",
                            "capturedAt": item.created_at}), key + "-capture")
            title = self.title(item, key + "-note")
            content = note_html(item, assets)
            try:
                note = self.service.create_note(None, PrivateNoteCreate(title=title, content=content,
                    capture_ids=[capture["captureId"]], asset_ids=[asset["assetId"] for asset in assets]), key + "-note")
            except ValueError:
                fail(409, "The note title is already in use. Your original remains in LamaShare.")
            self.service.store.remember(None, "lamashare-import", key, item.model_dump(by_alias=True), note["noteId"])
            return note


def note_html(item, assets):
    parts = ['<!doctype html><html><head><meta charset="utf-8"><meta name="lamanotes-tags" content="shared"></head>',
             '<body><article class="lamanote lamanote-article">']
    if item.title:
        parts.append('<h1>' + escape(item.title) + '</h1>')
    for text in (item.text, item.annotation):
        if text:
            parts.append('<p>' + escape(text).replace('\n', '<br>') + '</p>')
    if item.url:
        parts.append('<p><a href="' + escape(item.url, quote=True) + '">' + escape(item.url) + '</a></p>')
    for file, asset in zip(item.files, assets, strict=True):
        url = '/api/private/v1/assets/' + asset['assetId'] + '/content'
        name = escape(file.name, quote=True)
        if image_preview(asset):
            parts.append(f'<figure class="lamanote-media"><img src="{url}" alt="{name}"><figcaption><a href="{url}" download>{name}</a></figcaption></figure>')
        elif asset['mediaType'].startswith('audio/'):
            parts.append(f'<figure class="lamanote-media"><audio controls preload="metadata" src="{url}"></audio><figcaption>{name}</figcaption></figure>')
        else:
            parts.append(f'<p><a href="{url}" download>{name}</a></p>')
    parts.append('<p class="lamanote-tags">#shared</p></article></body></html>')
    return ''.join(parts)


class ShareImportRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handle(request):
            try:
                return await original(request)
            except RequestValidationError:
                fail(422, "Open a valid Save to Notes handoff from LamaShare.")
        return handle


def create_router(service, auth, read_only=False, transport=None):
    router = APIRouter(prefix="/api/private/v1/share-import", route_class=ShareImportRoute)
    importer = ShareImporter(service, transport)

    def owner(request: Request):
        if not auth or read_only:
            fail(401, "An owner writing session is required.")
        header = request.headers.get("authorization", "")
        token = header[7:] if header.lower().startswith("bearer ") else None
        principal = auth.authenticate(request, token)
        if principal.kind != "session" or NOTES_WRITE not in principal.scopes:
            fail(403, "An owner writing session is required.")
        if request.headers.get("origin") != service.public_origin or request.headers.get("x-lamanotes-share") != "1":
            fail(403, "Open this import in LamaNotes.")

    @router.post("", dependencies=[Depends(owner)])
    async def import_share(data: ImportRequest):
        note = await importer.import_ticket(data.ticket)
        return {key: note[key] for key in ("noteId", "title", "url", "version")}

    return router
