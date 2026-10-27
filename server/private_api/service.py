import hashlib
import math
import re
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import HTTPException
from bs4 import BeautifulSoup

from attachments.file_system.file_system import FileSystemAttachments
from notes.identity import read_note_id, with_note_id
from notes.models import Note, NoteCreate, NoteUpdate
from publications.metadata import (
    PUBLICATION_FILE_LOCK,
    strip_publication_metadata,
)

from .store import PrivateStore, fingerprint, missing, opaque_id


class PrivateService:
    def __init__(
        self,
        notes,
        owner_id="personal-owner",
        public_origin="https://notes.thuber.org",
    ):
        self.notes = notes
        self.root = Path(notes.storage_path).resolve()
        self.store = PrivateStore(self.root, owner_id)
        self.public_origin = public_origin.rstrip("/")

    def resolve(self, note_id):
        matches = []
        for path in self.root.glob("*.html"):
            if path.is_symlink():
                continue
            try:
                if read_note_id(path.read_text(encoding="utf-8")) == note_id:
                    matches.append(path.stem)
            except (UnicodeError, ValueError):
                continue
        if len(matches) != 1:
            missing()
        return self.notes.get(matches[0])

    def read_note(self, actor, note_id):
        if actor is not None:
            self.store.get_allowed(actor, note_id, "note")
        elif not self.store.object(note_id):
            missing()
        note = self.resolve(note_id)
        context = self.notes.get_context(note.title)
        return self.store.envelope(
            noteId=note_id,
            title=note.title,
            content=note.content,
            format=note.format,
            version=note.version,
            url=self.public_origin + "/n/" + note_id,
            researchId=context.research_id,
        )

    def context(self, actor, note_id):
        note = self.read_note(actor, note_id)
        context = self.notes.get_context(note["title"]).model_dump(
            by_alias=True
        )
        return {**context, **{k: v for k, v in note.items() if k != "content"}}

    def index(self, actor, term=""):
        result = []
        for obj in self.store.objects("note"):
            if not self.store.allowed(actor, obj):
                continue
            try:
                note = self.read_note(actor, obj["id"])
                context = self.notes.get_context(note["title"])
            except HTTPException:
                continue
            text = context.text
            query = term.casefold().strip()
            haystack = (note["title"] + "\n" + text).casefold()
            if query and query not in haystack:
                continue
            item = self.notes._index_entry_from_context(context).model_dump(
                by_alias=True
            )
            item.update({k: v for k, v in note.items() if k != "content"})
            if query:
                match = text.casefold().find(query)
                start = max(0, match - 60)
                end = start + 220
                item["snippet"] = text[start:end]
            result.append(item)
        result.sort(key=lambda item: item["title"].casefold())
        return result

    def enroll(self, request):
        with PUBLICATION_FILE_LOCK:
            path = Path(self.notes._existing_path_from_title(request.title))
            if path.is_symlink() or path.resolve().parent != self.root:
                missing()
            note = self.notes.get(request.title)
            if note.format != "html":
                raise HTTPException(
                    422, "Enroll an HTML note; legacy Markdown is unchanged."
                )
            if note.version != request.expected_version:
                raise HTTPException(
                    409, "Note changed. Reload before enrolling."
                )
            note_id = read_note_id(note.content)
            if not note_id:
                note_id = opaque_id("ln")
                content = with_note_id(note.content, note_id)
                self.notes._write_file(
                    self.notes._existing_path_from_title(note.title),
                    content,
                    overwrite=True,
                )
                self.notes._invalidate_semantic_index_cache()
            self.resolve(note_id)
            if self.store.object(note_id):
                self.store.activate(note_id, True)
            else:
                self.store.put_object(
                    note_id, "note", {"assetIds": [], "captureIds": []}
                )
            return self.read_note(None, note_id)

    def validate_assets_in_html(
        self, actor, content, asset_ids, allow_template=True
    ):
        # Imports cannot execute code or request unowned media.
        soup = BeautifulSoup(content, "html.parser")
        for template in soup.find_all("template"):
            markdown = template.get_text()
            if (
                not allow_template
                or template.get("data-lamanotes-work-markdown") is None
                or "![" in markdown
            ):
                raise HTTPException(
                    422, "Use passive HTML for private note media."
                )
            self.validate_assets_in_html(
                actor, markdown, asset_ids, allow_template=False
            )
        passive_tags = set(
            "html head body meta title article section div span p h1 h2 h3 h4 h5 h6 header footer main aside nav small strong b em i u s del mark sub sup br hr ul ol li dl dt dd table thead tbody tfoot tr th td caption colgroup col blockquote pre code kbd samp a img picture source figure figcaption audio video track details summary input label template svg g path circle ellipse rect line polyline polygon text tspan defs clippath mask pattern lineargradient radialgradient stop use symbol marker desc".split()
        )
        if any(
            element.name.lower() not in passive_tags
            for element in soup.find_all(True)
        ):
            raise HTTPException(
                422, "Use passive HTML and shared note styles."
            )
        if soup.find(
            [
                "script",
                "iframe",
                "object",
                "embed",
                "base",
                "form",
                "link",
                "style",
            ]
        ):
            raise HTTPException(
                422, "Use passive HTML and shared note styles."
            )
        allowed = set(asset_ids)
        for asset_id in allowed:
            self.store.get_allowed(actor, asset_id, "asset")
        for element in soup.find_all(True):
            for name, value in element.attrs.items():
                value = (
                    " ".join(value) if isinstance(value, list) else str(value)
                )
                if any(
                    not target.strip(" \t\r\n\"'").startswith("#")
                    for target in re.findall(r"url\(([^)]*)\)", value, re.I)
                ):
                    raise HTTPException(
                        422, "External SVG references are unavailable."
                    )
                if name.startswith("on") or name in {
                    "style",
                    "srcdoc",
                    "http-equiv",
                }:
                    raise HTTPException(
                        422, "Use passive HTML and shared note styles."
                    )
                if name in {"src", "poster", "srcset", "xlink:href"}:
                    if name == "xlink:href" and value.startswith("#"):
                        continue
                    found = re.fullmatch(
                        r"/api/private/v1/assets/(la-[a-f0-9]{32})/content",
                        value,
                    )
                    if not found or found.group(1) not in allowed:
                        raise HTTPException(
                            422,
                            "Media must reference an attached private asset.",
                        )
                if name == "href":
                    attached = re.fullmatch(
                        r"/api/private/v1/assets/(la-[a-f0-9]{32})/content",
                        value,
                    )
                    if (
                        element.name == "a"
                        and attached
                        and attached.group(1) in allowed
                    ):
                        continue
                    if not value.startswith("#") and (
                        element.name != "a"
                        or urlsplit(value).scheme
                        not in {"https", "http", "mailto"}
                    ):
                        raise HTTPException(422, "Unsupported link target.")

    def create_note(self, actor, request, key):
        payload = request.model_dump(by_alias=True)
        with PUBLICATION_FILE_LOCK:
            replay = self.store.replay(actor, "note", key, payload)
            if replay and self.store.object(replay):
                return self.read_note(actor, replay)
            supplied_id = read_note_id(request.content)
            if supplied_id != request.note_id:
                raise HTTPException(
                    422, "A preassigned noteId must match its HTML metadata."
                )
            assets = set(request.asset_ids)
            for capture_id in request.capture_ids:
                capture = self.store.get_allowed(actor, capture_id, "capture")
                assets.update(capture["payload"]["assetIds"])
            self.validate_assets_in_html(actor, request.content, assets)
            note_id = replay or request.note_id or opaque_id("ln")
            if not replay and (
                self.store.object(note_id)
                or self.store.reserved(note_id)
                or any(
                    note_id
                    in path.read_text(encoding="utf-8", errors="replace")
                    for path in self.root.glob("*.html")
                    if not path.is_symlink()
                )
            ):
                raise HTTPException(409, "Use a fresh note identity.")
            if strip_publication_metadata(request.content) != request.content:
                raise HTTPException(
                    422, "Private imports cannot carry publication metadata."
                )
            content = (
                with_note_id(request.content, note_id)
                .replace("\r\n", "\n")
                .replace("\r", "\n")
            )
            if actor and actor["jobId"]:
                context = self.notes._context_from_note(
                    Note(
                        title=request.title,
                        content=content,
                        format="html",
                        last_modified=0,
                    )
                )
                if context.research_id != actor["jobId"]:
                    raise HTTPException(
                        422, "The Research identity must match the bound job."
                    )
            if not replay:
                self.store.remember(actor, "note", key, payload, note_id)
            try:
                existing = self.resolve(note_id)
            except HTTPException:
                existing = None
            if existing:
                if (
                    existing.content != content
                    or existing.title != request.title
                ):
                    raise HTTPException(
                        409, "Interrupted creation requires review."
                    )
            else:
                self.notes.create(
                    NoteCreate(
                        title=request.title, content=content, format="html"
                    )
                )
            self.store.put_object(
                note_id,
                "note",
                {
                    "assetIds": sorted(assets),
                    "captureIds": request.capture_ids,
                },
                actor,
            )
            return self.read_note(actor, note_id)

    def update_note(self, actor, note_id, request):
        with PUBLICATION_FILE_LOCK:
            obj = self.store.get_allowed(actor, note_id, "note")
            note = self.resolve(note_id)
            if request.content is not None:
                self.validate_assets_in_html(
                    actor, request.content, obj["payload"]["assetIds"]
                )
            changes = {"expected_version": request.expected_version}
            if request.title is not None:
                changes["new_title"] = request.title
            if request.content is not None:
                changes["new_content"] = request.content
            self.notes.update(note.title, NoteUpdate(**changes))
            return self.read_note(actor, note_id)

    def create_capture(self, actor, request, key):
        payload = request.model_dump(by_alias=True)
        if (
            not request.text.strip()
            and not request.source_url
            and not request.asset_ids
        ):
            raise HTTPException(422, "Select text, a link or a file first.")
        with PUBLICATION_FILE_LOCK:
            replay = self.store.replay(actor, "capture", key, payload)
            if replay and self.store.object(replay):
                return self.read_capture(actor, replay)
            for asset_id in request.asset_ids:
                self.store.get_allowed(actor, asset_id, "asset")
            capture_id = replay or opaque_id("lc")
            if not replay:
                self.store.remember(actor, "capture", key, payload, capture_id)
            payload["sha256"] = fingerprint(payload)
            self.store.put_object(capture_id, "capture", payload, actor)
            return self.read_capture(actor, capture_id)

    def read_capture(self, actor, capture_id):
        obj = self.store.get_allowed(actor, capture_id, "capture")
        return self.store.envelope(captureId=capture_id, **obj["payload"])

    def asset(self, actor, asset_id):
        obj = self.store.get_allowed(actor, asset_id, "asset")
        path = self.store.assets / asset_id
        if not path.is_file() or path.is_symlink():
            missing()
        if (
            hashlib.sha256(path.read_bytes()).hexdigest()
            != obj["payload"]["sha256"]
        ):
            raise HTTPException(409, "Stored asset changed; review required.")
        return self.store.envelope(assetId=asset_id, **obj["payload"])

    def note_assets(self, actor, note_id):
        self.read_note(actor, note_id)
        obj = self.store.object(note_id)
        return self.store.envelope(
            items=[
                self.asset(actor, value)
                for value in obj["payload"]["assetIds"]
            ]
        )

    def attach_assets(self, actor, note_id, request):
        with PUBLICATION_FILE_LOCK:
            obj = self.store.get_allowed(actor, note_id, "note")
            note = self.resolve(note_id)
            if note.version != request.expected_version:
                raise HTTPException(
                    409, "Note changed. Reload before attaching."
                )
            asset_ids = set(obj["payload"]["assetIds"])
            for asset_id in request.asset_ids:
                self.store.get_allowed(actor, asset_id, "asset")
                asset_ids.add(asset_id)
            self.store.update_payload(
                note_id, {**obj["payload"], "assetIds": sorted(asset_ids)}
            )
            return self.note_assets(actor, note_id)

    @staticmethod
    def media_type(data, supplied):
        signatures = [
            (b"\x89PNG\r\n\x1a\n", "image/png"),
            (b"\xff\xd8\xff", "image/jpeg"),
            (b"GIF87a", "image/gif"),
            (b"GIF89a", "image/gif"),
            (b"%PDF-", "application/pdf"),
            (b"OggS", "audio/ogg"),
            (b"ID3", "audio/mpeg"),
            (b"fLaC", "audio/flac"),
        ]
        for magic, media in signatures:
            if data.startswith(magic):
                return media
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return "image/webp"
        if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
            return "audio/wav"
        if supplied == "audio/mp4" and len(data) >= 16 and data[4:8] == b"ftyp":
            return "audio/mp4"
        if supplied == "text/plain":
            data.decode("utf-8")
            return "text/plain"
        raise HTTPException(
            415,
            "Use PNG, JPEG, WebP, GIF, PDF, plain text or supported audio.",
        )

    def create_asset(
        self, actor, data, supplied, role, source_id, receipt, key
    ):
        if (not data and supplied != "text/plain") or len(data) > 20 * 1024 * 1024:
            raise HTTPException(413, "Select a file up to 20 MB.")
        media = self.media_type(data, supplied)
        digest = hashlib.sha256(data).hexdigest()
        width, height = FileSystemAttachments._image_dimensions(data)
        if media.startswith("image/") and (
            not width or not height or width * height > 40_000_000
        ):
            raise HTTPException(415, "Use a valid image up to 40 megapixels.")
        payload = {
            "role": role,
            "sourceAssetId": source_id,
            "sha256": digest,
            "mediaType": media,
            "size": len(data),
            "width": width,
            "height": height,
            "cropReceipt": receipt,
        }
        with PUBLICATION_FILE_LOCK:
            replay = self.store.replay(actor, "asset", key, payload)
            if replay and self.store.object(replay):
                return self.asset(actor, replay)
            if role == "derived":
                source = self.store.get_allowed(actor, source_id, "asset")
                self.asset(actor, source_id)
                if receipt:
                    self.validate_crop_receipt(
                        receipt, source_id, source["payload"], payload
                    )
            elif role != "source" or source_id or receipt:
                raise HTTPException(
                    422, "A source has no parent or crop receipt."
                )
            asset_id = replay or opaque_id("la")
            if not replay:
                self.store.remember(actor, "asset", key, payload, asset_id)
            path = self.store.assets / asset_id
            if path.exists():
                if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                    raise HTTPException(
                        409, "Interrupted asset requires review."
                    )
            else:
                with path.open("xb") as stream:
                    stream.write(data)
            path.chmod(0o600)
            self.store.put_object(asset_id, "asset", payload, actor)
            return self.asset(actor, asset_id)

    @staticmethod
    def validate_crop_receipt(receipt, source_id, source, output):
        allowed = {
            "schema",
            "source_system",
            "source_id",
            "output_name",
            "source_size_px",
            "crop_rect_px",
            "output_size_px",
            "target_size_cm",
            "print_dpi",
            "sha256_source",
            "sha256_output",
            "created_at",
        }
        if (
            not isinstance(receipt, dict)
            or set(receipt) - allowed
            or receipt.get("schema") != "lamaphotos.crop.v1"
            or receipt.get("source_system") != "lamanotes"
            or receipt.get("source_id") != source_id
            or receipt.get("sha256_source") != source["sha256"]
            or receipt.get("sha256_output") != output["sha256"]
        ):
            raise HTTPException(
                422, "Crop receipt does not match source and output."
            )
        filename = receipt.get("output_name", "")
        if (
            not isinstance(filename, str)
            or re.search(r"[/\\:]", filename)
            or len(filename) > 180
        ):
            raise HTTPException(
                422, "Crop receipt must not contain a local path."
            )
        for key, actual in (
            ("source_size_px", source),
            ("output_size_px", output),
        ):
            size = receipt.get(key, {})
            if (
                not isinstance(size, dict)
                or set(size) != {"width", "height"}
                or any(
                    type(size.get(axis)) is not int or size[axis] <= 0
                    for axis in ("width", "height")
                )
            ):
                raise HTTPException(
                    422, "Crop dimensions do not match the images."
                )
            measured = (actual.get("width"), actual.get("height"))
            accepted = {measured}
            if key == "source_size_px" and actual["mediaType"] == "image/jpeg":
                accepted.add(measured[::-1])
            if (size["width"], size["height"]) not in accepted:
                raise HTTPException(
                    422, "Crop dimensions do not match the images."
                )
        rect = receipt.get("crop_rect_px", {})
        if (
            not isinstance(rect, dict)
            or set(rect) != {"x", "y", "width", "height"}
            or any(type(rect[key]) is not int for key in rect)
            or rect["x"] < 0
            or rect["y"] < 0
            or rect["width"] <= 0
            or rect["height"] <= 0
            or rect["x"] + rect["width"] > receipt["source_size_px"]["width"]
            or rect["y"] + rect["height"] > receipt["source_size_px"]["height"]
        ):
            raise HTTPException(422, "Crop bounds are outside the source.")
        for key, fields in (
            ("target_size_cm", {"width", "height"}),
            ("print_dpi", {"horizontal", "vertical", "minimum"}),
        ):
            values = receipt.get(key, {})
            if (
                not isinstance(values, dict)
                or set(values) != fields
                or any(
                    type(value) not in {int, float}
                    or not math.isfinite(value)
                    or value <= 0
                    for value in values.values()
                )
            ):
                raise HTTPException(422, "Invalid print dimensions.")

    def check_references(self, actor, request):
        parent = None
        if request.parent:
            note = self.read_note(actor, request.parent.note_id)
            if note["version"] != request.parent.version or (
                request.parent.research_id
                and note["researchId"] != request.parent.research_id
            ):
                raise HTTPException(409, "Parent reference changed.")
            parent = request.parent.model_dump(by_alias=True)
        sources = []
        for source in request.sources:
            capture = self.read_capture(actor, source.capture_id)
            if capture["sha256"] != source.sha256:
                raise HTTPException(409, "Capture reference changed.")
            sources.append(source.model_dump(by_alias=True))
        return self.store.envelope(parent=parent, sources=sources)

    def result_reference(self, actor, request):
        note = self.read_note(actor, request.note_id)
        if (
            note["version"] != request.version
            or not request.research_id
            or note["researchId"] != request.research_id
            or (
                actor
                and actor["jobId"]
                and actor["jobId"] != request.research_id
            )
        ):
            raise HTTPException(
                409, "Result reference changed or does not match the job."
            )
        context = self.notes.get_context(note["title"])
        obj = self.store.get_allowed(actor, request.note_id, "note")
        manifest = [
            self.asset(actor, value)
            for value in sorted(obj["payload"]["assetIds"])
        ]
        return self.store.envelope(
            **{
                k: note[k]
                for k in ("noteId", "version", "researchId", "title", "url")
            },
            researchType=context.research_type,
            researchOrigin=context.research_origin,
            researchFreshness=context.research_freshness,
            parentResearchId=context.parent_research_id,
            htmlSha256=hashlib.sha256(
                note["content"]
                .replace("\r\n", "\n")
                .replace("\r", "\n")
                .encode("utf-8")
            ).hexdigest(),
            primaryResearchTopic=context.primary_research_topic,
            assetManifest=[
                {
                    k: asset[k]
                    for k in ("assetId", "sha256", "role", "sourceAssetId")
                }
                for asset in manifest
            ],
        )
