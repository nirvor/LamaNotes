"""One explicit LamaShare action appends to the bound Quicknotes note."""
import hashlib
import json
import os
import re
from html import escape
from typing import Literal
from urllib.parse import quote
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import Field, field_validator
from starlette.concurrency import run_in_threadpool

from notes.errors import NoteConflictError
from notes.models import NoteUpdate
from private_api.models import StrictModel
from private_api.media import editable_text, image_preview
from private_api.store import canonical, fingerprint
from publications.metadata import PUBLICATION_FILE_LOCK
from quicknotes import MAX_NOTE_CHARS, Quicknotes, _Document, _sync_directory, append_fragments, literal_markdown, timestamp
from share_import import MAX_BYTES, NO_STORE, ShareCapture, ShareExport, bounded_response, fail, parse_export

INTENT = "quicknotes.append"
BINDING = "share-quicknotes-target"
RECEIPT = "share-quicknotes-append"
MARKER = "lamanotes-share-quicknote"


class IntakeRequest(StrictModel):
    ticket: str = Field(pattern=r"^lsq_[A-Za-z0-9_-]{43}$")


class QuicknotesExport(ShareExport):
    intent: Literal["quicknotes.append"]
    operation_id: str = Field(pattern=r"^[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12}$")

    @field_validator("operation_id")
    @classmethod
    def operation_uuid(cls, value):
        return str(UUID(value))

    def payload(self):
        return {"intent": self.intent, "operationId": self.operation_id,
                "item": self.item.model_dump(by_alias=True)}


def receipt(db, operation, key, digest):
    row = db.execute("SELECT fingerprint,object_id FROM receipts WHERE actor='owner' AND operation=? AND key=?",
                     (operation, key)).fetchone()
    if row and row["fingerprint"] != digest:
        fail(409, "This Quicknotes action was already used for different content.")
    return json.loads(row["object_id"]) if row else None


def remember(db, operation, key, digest, value):
    db.execute("INSERT INTO receipts VALUES('owner',?,?,?,?)", (operation, key, digest, canonical(value)))


def entry_fragments(item, assets, entry_id=None, originals=None):
    stamp = timestamp(item.created_at)
    anchor = f' id="quicknote-{entry_id}"' if entry_id else ''
    visible = [f'<hr class="lamanote-share-separator"{anchor}>', '<p><small>' + stamp + '</small></p>']
    markdown = ([f'<span id="quicknote-{entry_id}" data-lamanotes-share-anchor></span>'] if entry_id else [])
    markdown.extend(["---", f"<small>{stamp}</small>"])
    for text in (item.title, item.text, item.annotation):
        if text:
            normalized = text.replace("\r\n", "\n").replace("\r", "\n")
            visible.append('<p>' + escape(normalized, quote=False).replace('\n', '<br>') + '</p>')
            markdown.append(literal_markdown(normalized))
    if item.url:
        url = quote(item.url, safe=":/?#[]@!$&'*+,;=%")
        visible.append('<p><a href="' + escape(url, quote=True) + '">' + escape(item.url) + '</a></p>')
        markdown.append('[' + literal_markdown(item.url) + '](' + url + ')')
    for index, (file, asset) in enumerate(zip(item.files, assets, strict=True)):
        url = '/api/private/v1/assets/' + asset['assetId'] + '/content'
        name = escape(file.name, quote=True)
        if image_preview(asset):
            visible.append(f'<p><img src="{url}" alt="{name}" loading="lazy"></p>')
            markdown.append('![' + literal_markdown(file.name) + '](' + url + ')')
        visible.append(f'<p><a href="{url}" download>{name}</a></p>')
        markdown.append('[' + literal_markdown(file.name) + '](' + url + ')')
        media = asset['mediaType']
        text = (editable_text(originals[index], MAX_NOTE_CHARS)
                if originals is not None and media != 'application/pdf'
                and not media.startswith(('image/', 'audio/', 'video/')) else None)
        if text is not None:
            language = {'py':'python','js':'javascript','ts':'typescript','ps1':'powershell',
                        'json':'json','md':'markdown','sh':'bash','yml':'yaml','yaml':'yaml'}.get(file.name.rsplit('.',1)[-1].lower(), 'text')
            fence = '`' * max(3, max((len(value) + 1 for value in re.findall(r'`+', text)), default=3))
            markdown.append(fence + language + '\n' + text + '\n' + fence)
            visible.append(f'<pre><code class="language-{language}">' + escape(text, quote=False) + '</code></pre>')
    return ''.join(visible), '\n\n'.join(markdown)


class QuicknotesIntake:
    def __init__(self, service, transport=None):
        self.service, self.transport = service, transport
        self.quicknotes = Quicknotes(service.notes, service)

    def links(self, result, note_id, duplicate):
        url = self.service.public_origin + '/n/' + note_id + '?entry=' + result['appendId']
        return {**result, 'duplicate': duplicate, 'noteId': note_id, 'openUrl': url, 'editUrl': url + '&edit=1'}

    def bind(self, export):
        digest = fingerprint(export.payload())
        with PUBLICATION_FILE_LOCK, self.service.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            saved = receipt(db, RECEIPT, export.operation_id, digest)
            bound = receipt(db, BINDING, export.operation_id, digest)
            if saved:
                return self.links(saved, bound['noteId'], True)
            binding = self.service.store.root / 'focus-quicknotes.json'
            if not binding.is_file() or binding.is_symlink():
                fail(409, "The existing Quicknotes binding is unavailable.")
            note_id, _ = self.quicknotes.target()
            if bound and bound['noteId'] != note_id:
                fail(409, "The Quicknotes target changed. The action remains queued.")
            if not bound:
                remember(db, BINDING, export.operation_id, digest,
                         {"noteId": note_id, "operationId": export.operation_id})
        return None

    async def receive(self, ticket):
        try:
            async with httpx.AsyncClient(transport=self.transport, trust_env=False, follow_redirects=False,
                    timeout=httpx.Timeout(30, connect=8), headers={"Accept-Encoding": "identity"}) as client:
                raw, media = await bounded_response(client, 'POST', '/api/share/v1/quicknotes-export',
                    limit=2 * 1024 * 1024, json={"ticket": ticket})
                if media != 'application/json':
                    fail(502, "LamaShare returned an invalid Quicknotes export.")
                export = parse_export(raw, QuicknotesExport)
                saved = await run_in_threadpool(self.bind, export)
                if saved:
                    return saved
                files = []
                for file in export.item.files:
                    data, media = await bounded_response(client, 'GET', '/api/share/v1/notes-export/files/' + file.id,
                        limit=file.size, headers={"Authorization": "Bearer " + export.file_token})
                    if (len(data) != file.size
                        or hashlib.sha256(data).hexdigest() != file.sha256):
                        fail(422, "A shared file could not be verified. The action remains queued.")
                    files.append(data)
        except httpx.HTTPError:
            fail(502, "LamaShare is unavailable. The Quicknotes action remains queued.")
        except HTTPException as error:
            if error.status_code == 410:
                fail(410, "This Quicknotes export expired. Retry the same queued action.")
            raise
        except (ValueError, UnicodeError):
            fail(422, "The Quicknotes export could not be verified. The action remains queued.")
        return await run_in_threadpool(self.finish, export, files)

    def finish(self, export, files):
        with PUBLICATION_FILE_LOCK:
            saved = self.bind(export)
            if saved:
                return saved
            item, key = export.item, 'share-quicknotes-' + export.operation_id
            assets = [self.service.create_asset(None, data, file.mime, 'source', None, None, key + '-' + file.id,
                                               source_limit=MAX_BYTES)
                      for file, data in zip(item.files, files, strict=True)]
            for asset in assets:
                with (self.service.store.assets / asset['assetId']).open('rb') as stream:
                    os.fsync(stream.fileno())
            _sync_directory(self.service.store.assets)
            kind = ('image' if item.files[0].mime.startswith('image/') else
                    'audio' if item.files[0].mime.startswith('audio/') else 'file') if item.files else 'link' if item.url else 'text'
            capture = self.service.create_capture(None, ShareCapture(kind=kind,
                text=item.text or item.annotation or item.title, source_url=item.url or None,
                asset_ids=[asset['assetId'] for asset in assets], share=item,
                provenance={"channel": "android-share" if item.source and item.source.platform == 'android' else 'web',
                            "description": "Explicit LamaShare Quicknotes action. Source metadata is unverified.",
                            "capturedAt": item.created_at}), key + '-capture')
            digest = fingerprint(export.payload())
            with self.service.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                saved = receipt(db, RECEIPT, export.operation_id, digest)
                if saved:
                    bound = receipt(db, BINDING, export.operation_id, digest)
                    return self.links(saved, bound['noteId'], True)
                bound = receipt(db, BINDING, export.operation_id, digest)
                note_id, note = self.quicknotes.target()
                if not bound or bound['noteId'] != note_id:
                    fail(409, "The Quicknotes target changed. The action remains queued.")
                markers = _Document(note.content).capture_markers(export.operation_id, MARKER)
                if markers and markers != [export.operation_id + ':' + digest]:
                    fail(409, "The existing Quicknotes entry does not match this action.")
                obj = self.service.store.get_allowed(None, note_id, 'note')
                metadata = {**obj['payload'],
                    'assetIds': sorted(set(obj['payload'].get('assetIds', [])) | {asset['assetId'] for asset in assets}),
                    'captureIds': sorted(set(obj['payload'].get('captureIds', [])) | {capture['captureId']})}
                db.execute('UPDATE objects SET payload=? WHERE id=?', (canonical(metadata), note_id))
                if not markers:
                    visible, markdown = entry_fragments(item, assets, export.operation_id, files)
                    try:
                        content = append_fragments(note.content, export.operation_id, digest, visible, markdown,
                                                   marker_name=MARKER, shared=True)
                    except HTTPException as error:
                        if error.status_code != 413:
                            raise
                        visible, markdown = entry_fragments(item, assets, export.operation_id)
                        content = append_fragments(note.content, export.operation_id, digest, visible, markdown,
                                                   marker_name=MARKER, shared=True)
                    try:
                        note = self.service.notes.update(note.title, NoteUpdate(new_content=content, expected_version=note.version))
                    except NoteConflictError:
                        fail(409, "Quicknotes changed. Retry the same action.")
                    _sync_directory(self.service.root)
                result = {"operationId": export.operation_id, "itemId": item.id,
                          "appendId": export.operation_id, "version": note.version,
                          "assetCount": len(assets), "saved": True}
                remember(db, RECEIPT, export.operation_id, digest, result)
            return self.links(result, note_id, bool(markers))


class IntakeRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handle(request):
            try:
                return await original(request)
            except RequestValidationError:
                fail(422, "Use a valid item-scoped Quicknotes action.")
        return handle


def create_router(service, enabled=True, transport=None):
    router = APIRouter(prefix='/api/share-intake/v1', route_class=IntakeRoute)
    intake = QuicknotesIntake(service, transport)

    @router.post('/quicknotes')
    async def append(request: Request, data: IntakeRequest):
        if request.url.hostname != 'lamanotes' or any(name in request.headers for name in ('origin', 'cookie', 'authorization')):
            fail(404, "Not found.")
        if not enabled:
            fail(403, "Quicknotes writing is unavailable.")
        return await intake.receive(data.ticket)

    return router
