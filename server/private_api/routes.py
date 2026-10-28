import json
import os
import re
import time
import hashlib
import secrets
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import FileResponse, HTMLResponse

from notes.errors import NoteConflictError
from .media import image_preview

from .models import (
    AttachAssets,
    CapabilityCreate,
    CapabilityRenew,
    FocusSourceRefresh,
    CaptureCreate,
    Enroll,
    ParentReference,
    PrivateNoteCreate,
    PrivateNoteUpdate,
    ReferenceCheck,
    ReferenceContent,
    ReferenceContext,
    ResearchReference,
    ReaderSession,
    ResearchIntake,
    ResearchIntakeConsume,
)
from .store import missing


def create_router(service, auth):
    router = APIRouter(prefix="/api/private/v1")
    store = service.store

    def principal(request: Request):
        header = request.headers.get("authorization", "")
        token = header[7:] if header.lower().startswith("bearer ") else None
        if token and token.startswith("lmp_"):
            return store.authenticate(token)
        if not auth:
            raise HTTPException(401, "Owner login required.")
        owner = auth.authenticate(request, token)
        if owner.kind != "session":
            raise HTTPException(
                403, "Use an owner session or a private capability."
            )
        return None

    def owner(actor=Depends(principal)):
        if actor is not None:
            raise HTTPException(403, "Owner session required.")
        return actor

    def scope(value):
        def check(actor=Depends(principal)):
            store.require(actor, value)
            return actor

        return check

    def idempotency(key: str = Header(alias="Idempotency-Key")):
        if not re.fullmatch(r"[A-Za-z0-9_-]{8,128}", key):
            raise HTTPException(422, "Use an opaque idempotency key.")
        return key

    @router.post("/research-intakes")
    def research_intake(data: ResearchIntake, request: Request, _=Depends(owner)):
        origin = request.headers.get("origin")
        if origin and origin != service.public_origin:
            raise HTTPException(403, "Open this selection in LamaNotes.")
        store.get_allowed(None, data.note_id, 'note')
        note = service.read_note(None, data.note_id)
        if note["version"] != data.expected_version:
            raise HTTPException(409, "The note changed. Open its current version.")
        token = secrets.token_urlsafe(32)
        with store.connect() as db:
            db.execute("DELETE FROM research_intakes WHERE expires_at<?", (int(time.time()),))
            db.execute("INSERT INTO research_intakes(digest,note_id,version,expires_at) VALUES(?,?,?,?)",
                       (hashlib.sha256(token.encode()).hexdigest(), data.note_id,
                        data.expected_version, int(time.time()) + 900))
        return {"ticket": token}

    @router.post("/research-intakes/consume")
    def consume_research_intake(data: ResearchIntakeConsume, actor=Depends(scope("references:read"))):
        if actor is None or actor.get("jobId") or actor.get("parentId"):
            raise HTTPException(403, "Use the existing Research integration.")
        store.require(actor, "capabilities:delegate")
        digest = hashlib.sha256(data.ticket.encode()).hexdigest()
        with store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM research_intakes WHERE digest=?", (digest,)).fetchone()
            if not row or row["expires_at"] <= time.time():
                raise HTTPException(410, "This selection expired. Open it again from LamaNotes.")
            if row["consumed_by"] and row["consumed_by"] != actor["capabilityId"]:
                raise HTTPException(409, "This selection was already opened elsewhere.")
            store.get_allowed(None, row['note_id'], 'note')
            note = service.read_note(None, row["note_id"])
            if note["version"] != row["version"]:
                raise HTTPException(409, "The selected note changed. Select its current version.")
            current = store.capability(actor["capabilityId"], db)
            store.validate_chain(current)
            roots = []
            for candidate in db.execute('SELECT id,payload FROM capabilities WHERE revoked=0').fetchall():
                grant = json.loads(candidate['payload'])
                if (grant['clientId'] == actor['clientId'] and not grant.get('parentId')
                    and not grant.get('jobId') and grant['expiresAt'] > time.time()
                    and {'notes:read','references:read'} & set(grant['scopes'])):
                    roots.append((candidate['id'],grant))
            if not any('notes:read' in grant['scopes'] for _,grant in roots):
                raise HTTPException(503, 'The Research note reader is unavailable.')
            for identifier, grant in roots:
                grant['noteIds'] = sorted(set(grant['noteIds']) | {note['noteId']})
                db.execute('UPDATE capabilities SET payload=? WHERE id=?', (json.dumps(grant),identifier))
            db.execute("UPDATE research_intakes SET consumed_by=? WHERE digest=?",
                       (actor["capabilityId"], digest))
        return {
            "parent": {"noteId": note["noteId"], "version": note["version"],
                       "researchId": note.get("researchId")},
            "selectedNote": {key: note[key] for key in ("noteId", "version", "title")},
        }

    @router.post("/reader-session")
    def reader_session(
        data: ReaderSession,
        request: Request,
        response: Response,
        actor=Depends(principal),
    ):
        if request.url.scheme != "https" and request.url.hostname not in {
            "localhost",
            "127.0.0.1",
            "testserver",
        }:
            raise HTTPException(400, "Reader sessions require HTTPS.")
        service.read_note(actor, data.note_id)
        token, expires = store.create_reader(
            actor, data.note_id, data.expires_in
        )
        path = request.url.path.rsplit("/", 1)[0] + "/reader/" + data.note_id
        response.set_cookie(
            "lamanotes_private_reader",
            token,
            max_age=max(1, expires - int(time.time())),
            httponly=True,
            secure=request.url.scheme == "https",
            samesite="strict",
            path=path,
        )
        response.headers["Cache-Control"] = "no-store"
        return store.envelope(
            readerUrl=path, expiresAt=expires, noteId=data.note_id
        )

    def reader_actor(note_id: str, request: Request):
        return store.reader(
            request.cookies.get("lamanotes_private_reader"), note_id
        )

    @router.get("/reader/{note_id}", response_class=HTMLResponse)
    def reader_page(
        note_id: str, request: Request, actor=Depends(reader_actor)
    ):
        service.read_note(actor, note_id)
        html = Path("client/dist/private-reader.html").read_text(
            encoding="utf-8"
        )
        base = request.url.path.split("/api/private/v1/", 1)[0] + "/"
        html = html.replace('<base href="/"', '<base href="' + base + '"')
        reader = str(request.url).split("?", 1)[0].rstrip("/") + "/"
        return HTMLResponse(
            html,
            headers={
                "Cache-Control": "no-store",
                "Referrer-Policy": "no-referrer",
                "Content-Security-Policy": (
                    "default-src 'none'; script-src 'self'; "
                    "style-src 'self' 'unsafe-inline'; font-src 'self' data:; "
                    f"img-src {reader}assets/ blob: data:; "
                    f"media-src {reader}assets/ blob:; connect-src {reader}; "
                    "base-uri 'self'; form-action 'none'; frame-ancestors 'none'"
                ),
            },
        )

    @router.get("/reader/{note_id}/document")
    def reader_document(note_id: str, actor=Depends(reader_actor)):
        note = service.read_note(actor, note_id)
        # Enrollment can include owner-authored HTML. The isolated renderer
        # accepts the same passive subset as private publication.
        obj = store.get_allowed(actor, note_id, "note")
        service.validate_assets_in_html(
            actor, note["content"], obj["payload"]["assetIds"]
        )
        return note

    @router.get("/reader/{note_id}/assets/{asset_id}/content")
    def reader_asset(note_id: str, asset_id: str, actor=Depends(reader_actor)):
        obj = store.get_allowed(actor, note_id, "note")
        if asset_id not in obj["payload"]["assetIds"]:
            missing()
        return asset_response(actor, asset_id)

    @router.get("/settings")
    def settings(_=Depends(owner)):
        crop = os.environ.get("LAMANOTES_PRIVATE_CROP_ORIGIN", "").strip()
        parsed = urlsplit(crop)
        if crop and (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            crop = ""
        return store.envelope(cropOrigin=crop)

    @router.get("/capabilities")
    def capabilities(_=Depends(owner)):
        return store.envelope(items=store.list_capabilities())

    @router.post("/capabilities", status_code=201)
    @router.post("/capabilities/delegate", status_code=201)
    def create_capability(
        data: CapabilityCreate, response: Response, actor=Depends(principal)
    ):
        response.headers["Cache-Control"] = "no-store"
        return store.create_capability(actor, data)

    @router.delete("/capabilities/{capability_id}", status_code=204)
    def revoke_capability(capability_id: str, actor=Depends(principal)):
        store.revoke_capability(actor, capability_id)

    @router.post("/capabilities/{capability_id}/renew")
    def renew_capability(
        capability_id: str,
        data: CapabilityRenew,
        response: Response,
        _=Depends(owner),
    ):
        response.headers["Cache-Control"] = "no-store"
        return store.renew_capability(capability_id, data.expires_in)

    @router.post("/integrations/focus/refresh")
    def refresh_focus_integration(data: FocusSourceRefresh, response: Response, _=Depends(owner)):
        from .focus_source import refresh_focus_source
        response.headers["Cache-Control"] = "no-store"
        return store.envelope(**refresh_focus_source(store))

    @router.post("/grants/notes")
    def enroll(data: Enroll, _=Depends(owner)):
        try:
            return service.enroll(data)
        except FileNotFoundError:
            missing()
        except ValueError:
            raise HTTPException(422, "Cannot enroll this note.")

    @router.delete("/grants/{object_id}", status_code=204)
    def revoke_object(object_id: str, _=Depends(owner)):
        if not store.object(object_id):
            missing()
        store.activate(object_id, False)

    @router.get("/notes/resolve")
    def resolve_research(
        research_id: str = Query(
            alias="researchId", pattern=r"^lr-[a-f0-9]{32}$"
        ),
        actor=Depends(scope("notes:read")),
    ):
        matches = [
            entry
            for entry in service.index(actor)
            if entry["researchId"] == research_id
        ]
        if len(matches) != 1:
            missing()
        return service.read_note(actor, matches[0]["noteId"])

    @router.get("/index")
    def index(actor=Depends(scope("notes:read"))):
        items = service.index(actor)
        return store.envelope(items=items, total=len(items))

    @router.get("/search")
    def search(
        term: str = Query(min_length=1, max_length=100),
        actor=Depends(scope("notes:read")),
    ):
        items = service.index(actor, term)
        return store.envelope(items=items, total=len(items))

    @router.get("/notes/{note_id}")
    def get_note(note_id: str, actor=Depends(scope("notes:read"))):
        return service.read_note(actor, note_id)

    @router.get("/notes/{note_id}/context")
    def context(note_id: str, actor=Depends(scope("notes:read"))):
        return service.context(actor, note_id)

    @router.get("/notes/{note_id}/assets")
    def note_assets(note_id: str, actor=Depends(scope("notes:read"))):
        store.require(actor, "assets:read")
        return service.note_assets(actor, note_id)

    @router.post("/notes/{note_id}/assets")
    def attach_assets(
        note_id: str, data: AttachAssets, actor=Depends(scope("notes:update"))
    ):
        return service.attach_assets(actor, note_id, data)

    @router.post("/notes", status_code=201)
    def create_note(
        data: PrivateNoteCreate,
        actor=Depends(scope("notes:create")),
        key=Depends(idempotency),
    ):
        try:
            return service.create_note(actor, data, key)
        except (FileExistsError, ValueError):
            raise HTTPException(
                422,
                "Cannot create this note. Use a distinct title and passive HTML.",
            )

    @router.patch("/notes/{note_id}")
    def update_note(
        note_id: str,
        data: PrivateNoteUpdate,
        actor=Depends(scope("notes:update")),
    ):
        try:
            return service.update_note(actor, note_id, data)
        except NoteConflictError:
            raise HTTPException(
                409,
                {
                    "code": "note-conflict",
                    "message": "Note changed; reload before editing.",
                },
            )
        except (ValueError, FileExistsError):
            raise HTTPException(422, "Cannot apply this note change.")

    @router.post("/captures", status_code=201)
    def create_capture(
        data: CaptureCreate,
        actor=Depends(scope("captures:create")),
        key=Depends(idempotency),
    ):
        return service.create_capture(actor, data, key)

    @router.get("/captures/{capture_id}")
    def get_capture(capture_id: str, actor=Depends(scope("captures:read"))):
        return service.read_capture(actor, capture_id)

    @router.get("/assets/{asset_id}")
    def get_asset(asset_id: str, actor=Depends(scope("assets:read"))):
        return service.asset(actor, asset_id)

    @router.get("/assets/{asset_id}/content")
    def get_asset_content(asset_id: str, actor=Depends(scope("assets:read"))):
        return asset_response(actor, asset_id)

    def asset_response(actor, asset_id):
        asset = service.asset(actor, asset_id)
        path = store.assets / asset_id
        if not path.is_file() or path.is_symlink():
            missing()
        media = asset["mediaType"]
        disposition = "inline" if image_preview(asset) else "attachment"
        # Storage keys have no extension. The response filename takes priority
        # over an HTML download attribute, including for existing PDF assets.
        filename = asset_id + {"application/pdf": ".pdf", "video/mp4": ".mp4", "video/webm": ".webm"}.get(media, "")
        return FileResponse(
            path,
            media_type=media,
            filename=filename,
            content_disposition_type=disposition,
            headers={
                "Cache-Control": "no-store",
                "Content-Security-Policy": "default-src 'none'; sandbox",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @router.post("/assets", status_code=201)
    async def create_asset(
        file: UploadFile = File(),
        role: str = Form(default="source"),
        source_asset_id: str | None = Form(
            default=None, alias="sourceAssetId"
        ),
        crop_receipt: str | None = Form(default=None, alias="cropReceipt"),
        actor=Depends(scope("assets:create")),
        key=Depends(idempotency),
    ):
        data = await file.read(20 * 1024 * 1024 + 1)
        try:
            receipt = json.loads(crop_receipt) if crop_receipt else None
            return service.create_asset(
                actor,
                data,
                file.content_type,
                role,
                source_asset_id,
                receipt,
                key,
            )
        except (UnicodeError, json.JSONDecodeError, ValueError):
            raise HTTPException(422, "Cannot import this file or receipt.")
        finally:
            await file.close()

    @router.post("/references/check")
    def references(
        data: ReferenceCheck, actor=Depends(scope("references:read"))
    ):
        return service.check_references(actor, data)

    @router.post("/references/resolve")
    def reference_resolve(
        data: ResearchReference, actor=Depends(scope("references:read"))
    ):
        matches = [
            entry
            for entry in service.index(actor)
            if entry["researchId"] == data.research_id
        ]
        if len(matches) != 1:
            missing()
        note = matches[0]
        return store.envelope(
            **{key: note[key] for key in ("noteId", "version", "researchId")}
        )

    @router.post("/references/context")
    def selected_context(
        data: ReferenceContext, actor=Depends(scope("references:read"))
    ):
        from .references import reference_context

        return reference_context(service, actor, data)

    @router.post("/references/content")
    def selected_content(
        data: ReferenceContent, actor=Depends(scope("references:read"))
    ):
        from .references import reference_content

        asset, content = reference_content(service, actor, data)
        extension = {
            "application/pdf": ".pdf",
            "text/plain": ".txt",
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/webp": ".webp",
            "image/gif": ".gif",
            "audio/ogg": ".ogg",
            "audio/mpeg": ".mp3",
            "audio/flac": ".flac",
            "audio/wav": ".wav",
            "audio/mp4": ".m4a",
        }.get(asset["mediaType"], "")
        return Response(
            content,
            media_type=asset["mediaType"],
            headers={
                "Cache-Control": "no-store",
                "Content-Disposition": f'attachment; filename="{data.asset_id}{extension}"',
                "Content-Security-Policy": "default-src 'none'; sandbox",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @router.post("/references/result")
    def result(data: ParentReference, actor=Depends(scope("references:read"))):
        return service.result_reference(actor, data)

    return router
