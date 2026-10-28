import hashlib

from fastapi import HTTPException

from publications.metadata import PUBLICATION_FILE_LOCK

from .store import missing
from .media import SHARE_MAX_BYTES

MAX_CONTEXT_BYTES = 2 * 1024 * 1024
MAX_ASSET_BYTES = SHARE_MAX_BYTES
ASSET_FIELDS = (
    "assetId",
    "sha256",
    "mediaType",
    "size",
    "width",
    "height",
    "role",
    "sourceAssetId",
)


def selected_actor(service, actor, parent, sources):
    if not actor or not actor.get("parentId") or not actor.get("jobId"):
        raise HTTPException(
            403, "Use a delegated job-bound reference capability."
        )
    service.store.require(actor, "references:read")
    service.store.validate_chain(actor)
    if parent and parent.note_id not in actor["noteIds"]:
        missing()
    if any(source.capture_id not in actor["captureIds"] for source in sources):
        missing()


def selected_objects(service, actor, parent, sources):
    selected_actor(service, actor, parent, sources)
    note = None
    if parent:
        note = service.read_note(actor, parent.note_id)
        if note["version"] != parent.version or (
            parent.research_id and note["researchId"] != parent.research_id
        ):
            raise HTTPException(409, "Parent reference changed.")
    captures = []
    for source in sources:
        capture = service.read_capture(actor, source.capture_id)
        if capture["sha256"] != source.sha256:
            raise HTTPException(409, "Capture reference changed.")
        captures.append(capture)
    return note, captures


def asset_metadata(service, actor, asset_id):
    path = service.store.assets / asset_id
    if not path.is_file() or path.is_symlink():
        missing()
    if path.stat().st_size > MAX_ASSET_BYTES:
        raise HTTPException(413, "Selected original exceeds 100 MB (100,000,000 bytes).")
    asset = service.asset(actor, asset_id)
    if asset["size"] != path.stat().st_size:
        raise HTTPException(409, "Stored asset changed; review required.")
    return {key: asset[key] for key in ASSET_FIELDS}


def reference_context(service, actor, request):
    with PUBLICATION_FILE_LOCK:
        note, captures = selected_objects(
            service, actor, request.parent, request.sources
        )
        text_size = len((note["content"] if note else "").encode("utf-8"))
        text_size += sum(
            len(source["text"].encode("utf-8")) for source in captures
        )
        if text_size > MAX_CONTEXT_BYTES:
            raise HTTPException(413, "Selected context exceeds 2 MB of text.")
        if note:
            obj = service.store.get_allowed(actor, note["noteId"], "note")
            note = {
                key: note[key]
                for key in (
                    "noteId",
                    "version",
                    "researchId",
                    "title",
                    "url",
                    "content",
                    "format",
                )
            }
            note["assets"] = [
                asset_metadata(service, actor, asset_id)
                for asset_id in sorted(obj["payload"]["assetIds"])
            ]
        selected_sources = []
        for capture in captures:
            selected_sources.append(
                {
                    key: capture[key]
                    for key in (
                        "captureId",
                        "sha256",
                        "kind",
                        "text",
                        "sourceUrl",
                        "provenance",
                    )
                }
            )
            selected_sources[-1]["assets"] = [
                asset_metadata(service, actor, asset_id)
                for asset_id in sorted(capture["assetIds"])
            ]
        return service.store.envelope(parent=note, sources=selected_sources)


def reference_content(service, actor, request):
    sources = [request.source] if request.source else []
    with PUBLICATION_FILE_LOCK:
        note, captures = selected_objects(
            service, actor, request.parent, sources
        )
        if note:
            obj = service.store.get_allowed(actor, note["noteId"], "note")
            attached = obj["payload"]["assetIds"]
        else:
            attached = captures[0]["assetIds"]
        if request.asset_id not in attached:
            missing()
        asset = asset_metadata(service, actor, request.asset_id)
        content = (service.store.assets / request.asset_id).read_bytes()
        if (
            len(content) != asset["size"]
            or hashlib.sha256(content).hexdigest() != asset["sha256"]
        ):
            raise HTTPException(409, "Stored asset changed; review required.")
        return asset, content
