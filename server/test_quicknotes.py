import json
import logging
import os
import re
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from html import unescape
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from bs4 import BeautifulSoup
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth.local import LocalAuth
from auth.scopes import ALL_SCOPES, NOTES_READ
from global_config import AuthType
from notes.errors import NoteConflictError
from notes.file_system.file_system import FileSystemNotes
from notes.identity import read_note_id
from notes.models import NoteCreate, NoteUpdate
from private_api.models import CapabilityCreate, Enroll
from private_api.service import PrivateService
from quicknotes import ENTRY_META, create_router

IDENTITY = "ln-" + "a" * 32
LEGACY = f'''<!doctype html><html lang="de"><head>
<meta charset="utf-8"><meta name="lamanotes-note-id" content="{IDENTITY}">
<meta name="lamanotes-tags" content="pinned,private"><meta name="custom-origin" content="keep me"><title>Quicknotes</title>
</head><body><article class="flatnote flatnote-migrated">
<p class="flatnote-kicker">Pinned Scratch Note</p><h1>Quicknotes</h1>
<p>Previous <strong>useful writing</strong> and <a href="https://example.org/old">link</a>.</p>
<ul><li>Old list item</li></ul><p>#private</p>
</article></body></html>'''
TEXT_MODE = f'''<!doctype html><html lang="de"><head>
<meta name="lamanotes-note-id" content="{IDENTITY}"><meta name="custom-origin" content="keep me">
<meta name="lamanotes-tags" content="pinned,private"><meta name="lamanotes-editor" content="markdown"><title>Quicknotes</title>
</head><body><article class="lamanote lamanote-article" data-lamanotes-editor="markdown">
<h1>Quicknotes</h1><section class="lamanote-text-body"><p>Previous writing.</p><p>#private</p></section>
<template data-lamanotes-text-markdown>Previous writing.\n\n#private</template></article></body></html>'''


class QuicknotesTests(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.configuration = SimpleNamespace(auth_type=AuthType.PASSWORD, password_login_enabled=False,
            session_expiry_hours=12, remember_expiry_days=30, accept_legacy_tokens=False,
            session_cookie_name="lamanotes_session")
        with patch.dict(os.environ, {"LAMANOTES_PATH": str(self.root), "LAMANOTES_USERNAME": "fixture-owner",
                "LAMANOTES_SECRET_KEY": "synthetic-owner-fixture-key-" * 4, "LAMANOTES_API_TOKEN_HASHES": "[]"}):
            self.notes = FileSystemNotes()
            self.auth = LocalAuth(self.configuration)
        self.owner_token = self.auth.issue_session().access_token
        self.owner = {"Authorization": "Bearer " + self.owner_token}
        self.private = PrivateService(self.notes)
        note = self.notes.create(NoteCreate(title="Quicknotes", content=LEGACY))
        self.private.enroll(Enroll(title="Quicknotes", expected_version=note.version, personal=True))
        self.binding = self.private.store.root / "focus-quicknotes.json"
        self.bind(IDENTITY)
        self.client = self.make_client()

    def make_client(self, auth=True, read_only=False):
        app = FastAPI()
        app.include_router(create_router(self.notes, self.private, self.auth if auth else None, read_only))
        return TestClient(app)

    def bind(self, note_id):
        self.binding.write_text(json.dumps({"noteId": note_id, "capabilityId": "lg-" + "b" * 32}), encoding="utf-8")

    def entry(self, text="Writing from the phone", **changes):
        body = {"entryId": str(uuid4()), "noteId": IDENTITY, "text": text, "capturedAt": "2026-10-26T07:30:00.000Z"}
        return {**body, **changes}

    def post(self, body, client=None, headers=None):
        return (client or self.client).post("/api/quicknotes/entries", json=body,
                                          headers=self.owner if headers is None else headers)

    def source(self):
        return self.notes.get("Quicknotes").content

    def test_owner_target_contract_and_legacy_append_keep_identity_metadata_and_prior_content(self):
        response = self.client.get("/api/quicknotes", headers=self.owner)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"noteId": IDENTITY, "title": "Quicknotes"})
        self.assertEqual(response.headers["cache-control"], "no-store")
        before = self.source()
        entry = self.entry("A thought\nSecond line, with #private in a sentence")
        saved = self.post(entry)
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(set(saved.json()), {"entryId", "noteId", "title", "version", "duplicate"})
        self.assertFalse(saved.json()["duplicate"])
        self.assertEqual(saved.headers["cache-control"], "no-store")
        self.assertEqual(saved.json()["noteId"], IDENTITY)
        self.assertEqual(saved.json()["version"], self.notes.get("Quicknotes").version)
        source = self.source()
        doc = BeautifulSoup(source, "html.parser")
        self.assertEqual(doc.find("meta", {"name": "custom-origin"})["content"], "keep me")
        self.assertEqual(doc.find("meta", {"name": "lamanotes-tags"})["content"], "pinned,private")
        capture = doc.select_one("[data-lamanotes-quicknote-entry]")
        self.assertEqual(capture.select_one("[data-lamanotes-quicknote-text]").get_text(), entry["text"])
        self.assertEqual(capture.small.get_text(), "26 Oct 2026, 08:30")
        capture.extract()
        markers = doc.find_all("meta", {"name": ENTRY_META})
        self.assertEqual(len(markers), 1)
        self.assertTrue(markers[0]["content"].startswith(entry["entryId"] + ":"))
        # Appending has no rewrite pass over the original document.
        stripped = re.sub(r'<meta name="lamanotes-quicknote-entry"[^>]*>', "", source)
        start = stripped.index('<p data-lamanotes-quicknote-entry=')
        end = stripped.index("</p>", start) + len("</p>")
        self.assertEqual(stripped[:start] + stripped[end:], before)
        self.assertEqual(read_note_id(source), IDENTITY)
        self.assertEqual(self.notes.get_context("Quicknotes").tags, ["pinned", "private"])

    def test_text_mode_updates_visible_and_canonical_literal_text_without_injecting_tags(self):
        current = self.notes.get("Quicknotes")
        self.notes.update("Quicknotes", NoteUpdate(new_content=TEXT_MODE, expected_version=current.version))
        text = '#work\n*bold* [link](javascript:alert(1))\n<script>x</script> & </template>'
        response = self.post(self.entry(text))
        self.assertEqual(response.status_code, 200)
        doc = BeautifulSoup(self.source(), "html.parser")
        self.assertEqual(len(doc.select("template[data-lamanotes-text-markdown]")), 1)
        self.assertFalse(doc.body.find_all("script"))
        self.assertFalse(doc.body.find_all("a"))
        self.assertEqual(doc.select_one("[data-lamanotes-quicknote-text]").get_text(), text)
        canonical = doc.select_one("template[data-lamanotes-text-markdown]").decode_contents()
        canonical = unescape(canonical)
        self.assertTrue(canonical.startswith("Previous writing.\n\n#private\n\n<small>26 Oct 2026, 08:30</small>  \n"))
        self.assertIn(r"\#work" + "  \n" + r"\*bold\*", canonical)
        self.assertIn(r"\[link\]\(javascript\:alert\(1\)\)", canonical)
        self.assertEqual(doc.find("meta", {"name": "lamanotes-tags"})["content"], "pinned,private")
        context = self.notes.get_context("Quicknotes")
        self.assertEqual(context.tags, ["pinned", "private"])
        self.assertEqual(context.text.count("bold"), 1)

    def test_lost_response_retry_and_restart_do_not_duplicate(self):
        entry = self.entry()
        first = self.post(entry).json()
        source = self.source()
        replay = self.post(entry, client=self.make_client()).json()
        self.assertTrue(replay["duplicate"])
        self.assertEqual({key: value for key, value in replay.items() if key != "duplicate"},
                         {key: value for key, value in first.items() if key != "duplicate"})
        self.assertEqual(self.source(), source)

    def test_marker_recovers_save_before_sqlite_receipt_and_payload_mismatch_is_a_conflict(self):
        entry = self.entry()
        with patch("quicknotes._remember", side_effect=OSError("synthetic interruption")):
            with self.assertRaises(OSError):
                self.post(entry)
        once = self.source()
        conflict = self.post({**entry, "text": "Different writing"})
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.json()["detail"]["code"], "quicknotes-entry-conflict")
        replay = self.post(entry)
        self.assertEqual(replay.status_code, 200)
        self.assertTrue(replay.json()["duplicate"])
        self.assertEqual(self.source(), once)

    def test_sqlite_receipt_survives_editor_removing_marker_and_never_expires(self):
        entry = self.entry()
        self.assertEqual(self.post(entry).status_code, 200)
        current = self.notes.get("Quicknotes")
        edited = re.sub(r'<meta name="lamanotes-quicknote-entry"[^>]*>', "", current.content).replace("Old list item", "User edited list item")
        self.notes.update("Quicknotes", NoteUpdate(new_content=edited, expected_version=current.version))
        response = self.post(entry)
        self.assertTrue(response.json()["duplicate"])
        self.assertEqual(self.source(), edited)
        changed = self.post({**entry, "capturedAt": "2026-10-26T07:31:00.000Z"})
        self.assertEqual(changed.status_code, 409)
        self.assertEqual(changed.json()["detail"]["code"], "quicknotes-entry-conflict")

    def test_concurrent_requests_append_each_distinct_entry_once(self):
        entries = [self.entry("Concurrent thought " + str(index)) for index in range(8)]
        requests = entries + entries
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(self.post, requests))
        self.assertTrue(all(result.status_code == 200 for result in results))
        self.assertEqual(sum(not result.json()["duplicate"] for result in results), len(entries))
        doc = BeautifulSoup(self.source(), "html.parser")
        self.assertEqual(len(doc.select("[data-lamanotes-quicknote-entry]")), len(entries))
        self.assertEqual({node.get_text() for node in doc.select("[data-lamanotes-quicknote-text]")},
                         {entry["text"] for entry in entries})

    def test_full_editor_cas_cannot_overwrite_a_capture_and_append_uses_latest_writing(self):
        stale = self.notes.get("Quicknotes")
        self.assertEqual(self.post(self.entry()).status_code, 200)
        with self.assertRaises(NoteConflictError):
            self.notes.update("Quicknotes", NoteUpdate(new_content=LEGACY, expected_version=stale.version))
        current = self.notes.get("Quicknotes")
        self.notes.update("Quicknotes", NoteUpdate(new_content=current.content.replace("Old list item", "New edited list item"),
                                                   expected_version=current.version))
        self.assertEqual(self.post(self.entry("Next fresh entry")).status_code, 200)
        self.assertIn("New edited list item", self.source())
        self.assertIn("Next fresh entry", self.source())

    def test_cas_conflict_does_not_remember_or_change_the_entry(self):
        entry = self.entry()
        before = self.source()
        with patch.object(self.notes, "update", side_effect=NoteConflictError("synthetic conflict")):
            conflict = self.post(entry)
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.json()["detail"]["code"], "note-conflict")
        self.assertEqual(self.source(), before)
        response = self.post(entry)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["duplicate"])

    def test_explicit_target_mismatch_and_binding_failures_never_fall_back_or_write(self):
        before = self.source()
        mismatch = self.post(self.entry(noteId="ln-" + "c" * 32))
        self.assertEqual(mismatch.status_code, 409)
        self.assertEqual(mismatch.json()["detail"]["code"], "quicknotes-target-changed")
        self.assertNotIn("Previous", mismatch.text)
        for invalid in ("invalid", json.dumps({"noteId": "ln-" + "c" * 32}), json.dumps({"noteId": "#private"})):
            self.binding.write_text(invalid)
            response = self.post(self.entry())
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()["detail"]["code"], "quicknotes-unavailable")
            self.assertEqual(self.source(), before)
        self.bind(IDENTITY)
        self.private.store.activate(IDENTITY, False)
        self.assertEqual(self.post(self.entry()).status_code, 409)
        self.assertEqual(self.source(), before)

    def test_delayed_entry_cannot_follow_a_changed_valid_source_binding(self):
        queued = self.entry()
        other_id = "ln-" + "e" * 32
        other = self.notes.create(NoteCreate(title="Selected personal scratch", content=LEGACY.replace(IDENTITY, other_id)))
        self.private.enroll(Enroll(title=other.title, expected_version=other.version, personal=True))
        self.bind(other_id)
        target = self.client.get("/api/quicknotes", headers=self.owner)
        self.assertEqual(target.json(), {"noteId": other_id, "title": other.title})
        response = self.post(queued)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"]["code"], "quicknotes-target-changed")
        self.assertNotIn(queued["text"], self.source())
        self.assertNotIn(queued["text"], self.notes.get(other.title).content)

    def test_capture_keeps_the_existing_read_grant_and_flat_library(self):
        capability = self.private.store.create_capability(None, CapabilityCreate(client_id="focus-quicknotes",
            scopes=["notes:read"], note_ids=[IDENTITY]))
        self.binding.write_text(json.dumps({"noteId": IDENTITY, "capabilityId": capability["capabilityId"]}))
        before = self.private.store.list_capabilities()
        paths = sorted(path.name for path in self.root.glob("*.html"))
        self.assertEqual(self.post(self.entry()).status_code, 200)
        self.assertEqual(self.private.store.list_capabilities(), before)
        self.assertEqual(sorted(path.name for path in self.root.glob("*.html")), paths)
        actor = self.private.store.authenticate(capability["token"])
        self.assertEqual(actor["scopes"], ["notes:read"])
        self.assertEqual(actor["noteIds"], [IDENTITY])

    def test_bound_identity_survives_rename_and_unbound_fallback_requires_existing_stable_id(self):
        current = self.notes.get("Quicknotes")
        self.notes.update("Quicknotes", NoteUpdate(new_title="Renamed personal scratch", expected_version=current.version))
        target = self.client.get("/api/quicknotes", headers=self.owner)
        self.assertEqual(target.json(), {"noteId": IDENTITY, "title": "Renamed personal scratch"})
        self.assertEqual(self.post(self.entry()).json()["title"], "Renamed personal scratch")
        self.binding.unlink()
        self.assertEqual(self.client.get("/api/quicknotes", headers=self.owner).status_code, 409)
        self.notes.create(NoteCreate(title="Quicknotes", content=LEGACY.replace(IDENTITY, "ln-" + "d" * 32)))
        self.assertEqual(self.client.get("/api/quicknotes", headers=self.owner).json()["noteId"], "ln-" + "d" * 32)
        self.notes.delete("Quicknotes")
        self.notes.create(NoteCreate(title="Quicknotes", content=re.sub(r'<meta name="lamanotes-note-id"[^>]*>', "", LEGACY)))
        self.assertEqual(self.client.get("/api/quicknotes", headers=self.owner).status_code, 409)
        self.assertIsNone(read_note_id(self.source()))

    def test_work_note_and_unsupported_document_are_not_capture_targets(self):
        current = self.notes.get("Quicknotes")
        work = current.content.replace("<title>", '<meta name="lamanotes-note-kind" content="work"><title>')
        self.notes.update("Quicknotes", NoteUpdate(new_content=work, expected_version=current.version))
        self.assertEqual(self.post(self.entry()).status_code, 409)
        self.assertEqual(self.source(), work)
        current = self.notes.get("Quicknotes")
        self.notes.update("Quicknotes", NoteUpdate(new_content=LEGACY.replace("flatnote-migrated", "ordinary-research"),
                                                   expected_version=current.version))
        response = self.post(self.entry())
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"]["code"], "quicknotes-format")

    def test_owner_session_scope_is_required_and_focus_read_capability_stays_read_only(self):
        read_session = self.auth._create_access_token(subject="fixture-owner", scopes=frozenset({NOTES_READ}), expiry=timedelta(hours=1))
        service_token = self.auth._create_access_token(subject="fixture-owner", scopes=ALL_SCOPES, expiry=timedelta(hours=1))
        capability = self.private.store.create_capability(None, CapabilityCreate(client_id="focus-quicknotes", scopes=["notes:read"], note_ids=[IDENTITY]))
        for headers, status in (({}, 401), ({"Authorization": "Bearer " + read_session}, 403),
                                ({"Authorization": "Bearer " + capability["token"]}, 403)):
            self.assertEqual(self.post(self.entry(), headers=headers).status_code, status)
            self.assertEqual(self.client.get("/api/quicknotes", headers=headers).status_code, status)
        actor = self.private.store.authenticate(capability["token"])
        self.assertEqual(self.private.read_note(actor, IDENTITY)["noteId"], IDENTITY)
        with patch.object(self.auth, "authenticate", return_value=SimpleNamespace(kind="api-token", scopes=ALL_SCOPES)):
            self.assertEqual(self.post(self.entry(), headers={"Authorization": "Bearer " + service_token}).status_code, 403)
        self.assertEqual(self.post(self.entry(), client=self.make_client(auth=False)).status_code, 401)
        self.assertEqual(self.post(self.entry(), client=self.make_client(read_only=True)).status_code, 403)

    def test_cookie_session_obeys_existing_cross_site_guard_and_loopback_owner_works(self):
        client = self.make_client()
        client.cookies.set("lamanotes_session", self.owner_token)
        self.assertEqual(self.post(self.entry(), client=client, headers={}).status_code, 200)
        self.assertEqual(self.post(self.entry(), client=client, headers={"Sec-Fetch-Site": "cross-site"}).status_code, 401)
        self.assertEqual(self.post(self.entry(), headers={**self.owner, "Origin": "http://127.0.0.1:41987"}).status_code, 200)

    def test_input_validation_and_note_limit_leave_source_unchanged(self):
        before = self.source()
        for change in ({"entryId": "not-a-uuid"}, {"noteId": "#private"}, {"text": ""}, {"text": " "},
                       {"text": "a" * 10001}, {"text": "bad\0text"}, {"capturedAt": "yesterday"},
                       {"capturedAt": "2026-10-26T08:30:00"}, {"noteId": None}, {"other": True}):
            with self.subTest(change=change):
                self.assertEqual(self.post(self.entry(**change)).status_code, 422)
                self.assertEqual(self.source(), before)
        with patch("quicknotes.MAX_NOTE_CHARS", len(before) + 5):
            response = self.post(self.entry())
        self.assertEqual(response.status_code, 413)
        self.assertEqual(self.source(), before)


if __name__ == "__main__":
    unittest.main()
