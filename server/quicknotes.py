"""Owner-only, retry-safe writing into the existing Quicknotes note."""
import json
import os
import re
import string
from datetime import datetime
from html import escape, unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import Field, field_validator

from auth.scopes import NOTES_WRITE
from notes.errors import NoteConflictError
from notes.identity import read_note_id
from notes.models import NoteUpdate
from private_api.models import StrictModel
from private_api.store import fingerprint
from publications.metadata import PUBLICATION_FILE_LOCK

ENTRY_META = "lamanotes-quicknote-entry"
OPERATION = "quicknotes-entry"
MAX_NOTE_CHARS = 2_000_000
NO_STORE = {"Cache-Control": "no-store", "Vary": "Authorization, Cookie"}
VOID_TAGS = frozenset("area base br col embed hr img input link meta param source track wbr".split())


def problem(code, message, status=409):
    raise HTTPException(status, {"code": code, "message": message}, headers=NO_STORE)


class QuicknoteEntry(StrictModel):
    note_id: Annotated[str, Field(pattern=r"^ln-[a-f0-9]{32}$")]
    entry_id: Annotated[str, Field(pattern=r"^[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12}$")]
    text: Annotated[str, Field(strict=True, min_length=1, max_length=10000)]
    captured_at: Annotated[str, Field(strict=True, min_length=20, max_length=64)]

    @field_validator("entry_id")
    @classmethod
    def valid_entry_id(cls, value):
        return str(UUID(value))

    @field_validator("text")
    @classmethod
    def valid_text(cls, value):
        if not value.strip() or "\0" in value:
            raise ValueError("Enter some writing text.")
        value.encode("utf-8")
        return value.replace("\r\n", "\n").replace("\r", "\n")

    @field_validator("captured_at")
    @classmethod
    def valid_capture_time(cls, value):
        if not re.match(r"^\d{4}-\d{2}-\d{2}T", value):
            raise ValueError("Use an ISO timestamp with a time zone.")
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("Use an ISO timestamp with a time zone.")
        try:
            parsed.astimezone(ZoneInfo("Europe/Berlin"))
        except OverflowError:
            raise ValueError("Use a valid ISO timestamp.")
        return value


class _Document(HTMLParser):
    def __init__(self, content):
        super().__init__(convert_charrefs=False)
        self.content, self.nodes, self.stack = content, [], []
        self.lines = [0] + [match.end() for match in re.finditer("\n", content)]
        self.feed(content)
        self.close()

    def source_offset(self):
        line, column = self.getpos()
        return self.lines[line - 1] + column

    def handle_starttag(self, tag, attrs):
        start = self.source_offset()
        node = {"tag": tag, "attrs": dict(attrs), "start": start,
                "inner": start + len(self.get_starttag_text()),
                "close": None, "end": None, "parent": self.stack[-1] if self.stack else None}
        self.nodes.append(node)
        if tag not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            node = self.stack.pop()
            node["close"] = node["end"] = node["inner"]

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            node = self.stack[index]
            if node["tag"] == tag:
                node["close"] = self.source_offset()
                node["end"] = self.content.index(">", node["close"]) + 1
                del self.stack[index:]
                return

    def capture_markers(self, entry_id, name=ENTRY_META):
        values = []
        for node in self.nodes:
            attrs = node["attrs"]
            if node["tag"] == "meta" and attrs.get("name") == name:
                value = attrs.get("content", "")
                if value.split(":", 1)[0] == entry_id:
                    values.append(value)
        return values


def literal_markdown(text):
    return re.sub("([" + re.escape(string.punctuation) + "])", r"\\\1", text).replace("\n", "  \n")


def timestamp(captured_at):
    moment = datetime.fromisoformat(captured_at.replace("Z", "+00:00")).astimezone(ZoneInfo("Europe/Berlin"))
    month = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()[moment.month - 1]
    return f"{moment.day} {month} {moment.year}, {moment:%H:%M}"


def append_content(content, entry, digest):
    stamp = timestamp(entry.captured_at)
    visible = (f'<p data-lamanotes-quicknote-entry="{entry.entry_id}">'
               f'<small>{stamp}</small><br>'
               '<span data-lamanotes-quicknote-text style="white-space:pre-wrap">'
               + escape(entry.text, quote=False) + "</span></p>")
    markdown = f"<small>{stamp}</small>  \n" + literal_markdown(entry.text)
    return append_fragments(content, entry.entry_id, digest, visible, markdown)


def append_fragments(content, entry_id, digest, visible, markdown, *, marker_name=ENTRY_META, shared=False):
    document = _Document(content)
    templates = [node for node in document.nodes if node["tag"] == "template"
                 and "data-lamanotes-text-markdown" in node["attrs"]]
    patches = []
    if templates:
        bodies = [node for node in document.nodes
                  if "lamanote-text-body" in node["attrs"].get("class", "").split()]
        if len(templates) != 1 or len(bodies) != 1 or templates[0]["close"] is None or bodies[0]["close"] is None:
            problem("quicknotes-format", "Open Quicknotes in its editor before adding writing here.")
        template = templates[0]
        if any(node["parent"] is template for node in document.nodes):
            problem("quicknotes-format", "Open Quicknotes in its editor before adding writing here.")
        previous = unescape(content[template["inner"]:template["close"]])
        addition = markdown + ("\n\n" if previous else "")
        patches.extend([(template["inner"], escape(addition, quote=False)),
                        (bodies[0]["inner"], visible)])
    else:
        roots = [node for node in document.nodes if node["tag"] == "article"
                 and {"flatnote-migrated", "lamanote-migrated"} & set(node["attrs"].get("class", "").split())]
        if len(roots) != 1 or roots[0]["close"] is None:
            problem("quicknotes-format", "Open Quicknotes in its writing editor first.")
        root = roots[0]
        legacy = BeautifulSoup(content[root["start"]:root["end"]], "html.parser")
        for fragment in legacy.select("section[data-lamanotes-share-entry]"):
            if len(fragment.select(":scope > template[data-lamanotes-share-markdown]")) == 1:
                fragment.decompose()
        kicker = legacy.select_one(".flatnote-kicker,.lamanote-kicker")
        if not kicker or kicker.get_text(strip=True).lower() != "pinned scratch note" or legacy.select_one(
                "audio,canvas,figure,iframe,img,math,object,pre,script,style,svg,table,template,video"):
            problem("quicknotes-format", "Open Quicknotes in its writing editor first.")
        if shared:
            visible = (f'<section data-lamanotes-share-entry="{entry_id}">' + visible
                       + '<template data-lamanotes-share-markdown>' + escape(markdown, quote=False)
                       + '</template></section>')
        entries = [node for node in document.nodes if node["parent"] is root
                   and ("data-lamanotes-quicknote-entry" in node["attrs"]
                        or "data-lamanotes-share-entry" in node["attrs"])]
        patches.append((entries[0]["start"] if entries else root["close"], visible))
    heads = [node for node in document.nodes if node["tag"] == "head"]
    if heads and (len(heads) != 1 or heads[0]["close"] is None):
        problem("quicknotes-format", "Quicknotes needs its original editor.")
    marker = f'<meta name="{marker_name}" content="{entry_id}:{digest}">'
    patches.append((heads[0]["close"] if heads else 0, marker))
    for position, addition in sorted(patches, reverse=True):
        content = content[:position] + addition + content[position:]
    if len(content) > MAX_NOTE_CHARS:
        problem("quicknotes-full", "Quicknotes is full. Open the note before adding more writing.", 413)
    return content


class Quicknotes:
    def __init__(self, notes, private_service):
        self.notes, self.private = notes, private_service
        self.store = private_service.store

    def target(self):
        binding = self.store.root / "focus-quicknotes.json"
        try:
            if binding.exists() or binding.is_symlink():
                if binding.is_symlink() or binding.stat().st_size > 4096:
                    raise ValueError()
                value = json.loads(binding.read_text(encoding="utf-8"))
                note_id = value["noteId"]
                if not isinstance(note_id, str) or not re.fullmatch(r"ln-[a-f0-9]{32}", note_id):
                    raise ValueError()
                obj = self.store.object(note_id)
                if not obj or obj["kind"] != "note" or not obj["active"]:
                    raise ValueError()
                note = self.private.resolve(note_id)
            else:
                path = Path(self.notes._existing_path_from_title("Quicknotes"))
                if path.is_symlink() or path.resolve().parent != self.private.root:
                    raise ValueError()
                note = self.notes.get("Quicknotes")
                note_id = read_note_id(note.content)
                if not note_id:
                    raise ValueError()
                # An existing identity must still resolve to this one exact file.
                if self.private.resolve(note_id).title != "Quicknotes":
                    raise ValueError()
            if note.format != "html" or self.notes.get_context(note.title).note_kind == "work":
                raise ValueError()
            return note_id, note
        except (OSError, ValueError, KeyError, TypeError, HTTPException):
            problem("quicknotes-unavailable", "Quicknotes is unavailable. Open the original note first.")

    def append(self, entry):
        with PUBLICATION_FILE_LOCK:
            note_id, note = self.target()
            if entry.note_id != note_id:
                problem("quicknotes-target-changed", "Quicknotes changed. Review the saved target before sending.")
            digest = fingerprint(entry.model_dump(by_alias=True))
            with self.store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute("SELECT fingerprint FROM receipts WHERE actor='owner' AND operation=? AND key=?",
                                 (OPERATION, entry.entry_id)).fetchone()
                if row:
                    if row["fingerprint"] != digest:
                        problem("quicknotes-entry-conflict", "This entry ID was already used for different writing.")
                    return self.result(entry, note, True)
                markers = _Document(note.content).capture_markers(entry.entry_id)
                if markers:
                    if markers != [entry.entry_id + ":" + digest]:
                        problem("quicknotes-entry-conflict", "This entry ID was already used for different writing.")
                    _remember(db, entry, digest)
                    return self.result(entry, note, True)
                content = append_content(note.content, entry, digest)
                try:
                    saved = self.notes.update(note.title, NoteUpdate(new_content=content, expected_version=note.version))
                except NoteConflictError:
                    problem("note-conflict", "Quicknotes changed. Please try sending again.")
                _sync_directory(self.private.root)
                _remember(db, entry, digest)
                return self.result(entry, saved, False)

    @staticmethod
    def result(entry, note, duplicate):
        return {"entryId": entry.entry_id, "noteId": entry.note_id, "title": note.title,
                "version": note.version, "duplicate": duplicate}


def _remember(db, entry, digest):
    db.execute("INSERT INTO receipts(actor,operation,key,fingerprint,object_id) VALUES('owner',?,?,?,?)",
               (OPERATION, entry.entry_id, digest, "quicknote:" + entry.entry_id))


def _sync_directory(root):
    if os.name == "nt":
        return
    descriptor = os.open(root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def create_router(notes, private_service, auth, read_only=False):
    router = APIRouter(prefix="/api/quicknotes")
    quicknotes = Quicknotes(notes, private_service)

    def owner(request: Request):
        if read_only:
            problem("owner-required", "An owner writing session is required.", 403)
        if not auth:
            problem("owner-required", "An owner writing session is required.", 401)
        header = request.headers.get("authorization", "")
        token = header[7:] if header.lower().startswith("bearer ") else None
        if token and token.startswith("lmp_"):
            problem("owner-required", "An owner writing session is required.", 403)
        principal = auth.authenticate(request, token)
        if principal.kind != "session" or NOTES_WRITE not in principal.scopes:
            problem("owner-required", "An owner writing session is required.", 403)

    @router.get("", dependencies=[Depends(owner)])
    def target(response: Response):
        with PUBLICATION_FILE_LOCK:
            note_id, note = quicknotes.target()
        response.headers.update(NO_STORE)
        return {"noteId": note_id, "title": note.title}

    @router.post("/entries", dependencies=[Depends(owner)])
    def append(entry: QuicknoteEntry, response: Response):
        result = quicknotes.append(entry)
        response.headers.update(NO_STORE)
        return result

    return router
