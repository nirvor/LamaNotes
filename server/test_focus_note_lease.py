import json
import logging
import os
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from notes.file_system.file_system import FileSystemNotes
from notes.models import NoteCreate
from private_api.routes import create_router
from private_api.service import PrivateService
from test_private_api import OwnerAuth


class FocusNoteLeaseTests(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        with patch.dict(os.environ, {"LAMANOTES_PATH": temporary.name}):
            notes = FileSystemNotes()
        self.service = PrivateService(notes)
        self.store = self.service.store
        app = FastAPI()
        app.include_router(create_router(self.service, OwnerAuth()))
        self.client = TestClient(app)
        self.owner = {"Authorization": "Bearer synthetic-owner"}
        self.prefix = "/api/private/v1"
        self.note_ids = []
        for title in ("Quicknotes fixture", "Other private fixture"):
            note = notes.create(NoteCreate(title=title, content="<p>private fixture text</p>"))
            response = self.client.post(self.prefix + "/grants/notes", headers=self.owner,
                json={"title": title, "expectedVersion": note.version, "personal": True})
            self.assertEqual(response.status_code, 200)
            self.note_ids.append(response.json()["noteId"])
        self.note_id = self.note_ids[0]

    def capability(self, **changes):
        body = {"clientId": "focus-quicknotes", "scopes": ["notes:read"], "noteIds": [self.note_id], "expiresIn": 60}
        body.update(changes)
        response = self.client.post(self.prefix + "/capabilities", headers=self.owner, json=body)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def bind(self, capability, note_id=None):
        (self.store.root / "focus-quicknotes.json").write_text(json.dumps({"noteId": note_id or self.note_id,
            "capabilityId": capability["capabilityId"]}))

    def refresh(self, headers=None, body=None):
        return self.client.post(self.prefix + "/integrations/focus/refresh", headers=headers or self.owner,
                                json={} if body is None else body)

    def expire(self, capability, when):
        identifier = capability["capabilityId"]
        value = {key: value for key, value in self.store.capability(identifier).items() if key != "revoked"}
        value["expiresAt"] = when
        with self.store.connect() as db:
            db.execute("UPDATE capabilities SET payload=? WHERE id=?", (json.dumps(value), identifier))

    def test_renewal_only_changes_bound_expiry_and_keeps_same_read_only_token(self):
        selected = self.capability()
        unrelated = self.capability(clientId="another-reader", noteIds=[self.note_ids[1]])
        self.bind(selected)
        before = self.store.list_capabilities()
        now = int(time.time())
        response = self.refresh()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertTrue(response.json()["connected"] and response.json()["renewed"])
        self.assertLessEqual(abs(response.json()["expiresAt"] - now - 30 * 86400), 2)
        self.assertNotIn(selected["token"], response.text)
        after = self.store.list_capabilities()
        for old, new in zip(before, after):
            if old["capabilityId"] == selected["capabilityId"]:
                self.assertEqual({k: v for k, v in old.items() if k != "expiresAt"}, {k: v for k, v in new.items() if k != "expiresAt"})
            else:
                self.assertEqual(old, new)
        second = self.refresh().json()
        self.assertFalse(second["renewed"])
        self.assertEqual(second["expiresAt"], response.json()["expiresAt"])
        reader = {"Authorization": "Bearer " + selected["token"]}
        self.assertEqual(self.client.get(self.prefix + "/notes/" + self.note_id, headers=reader).status_code, 200)
        self.assertEqual(self.client.get(self.prefix + "/notes/" + self.note_ids[1], headers=reader).status_code, 404)
        self.assertEqual(self.client.get(self.prefix + "/index", headers=reader).json()["total"], 1)
        self.assertEqual(self.store.capability(unrelated["capabilityId"])["noteIds"], [self.note_ids[1]])
        current = self.client.get(self.prefix + "/notes/" + self.note_id, headers=reader).json()
        updated = self.client.patch(self.prefix + "/notes/" + self.note_id, headers=self.owner,
            json={"expectedVersion": current["version"], "content": "<p>fresh selected text</p>"})
        self.assertEqual(updated.status_code, 200)
        fresh = self.client.get(self.prefix + "/notes/" + self.note_id + "/context", headers=reader).json()
        self.assertEqual(fresh["noteId"], self.note_id)
        self.assertNotEqual(fresh["version"], current["version"])
        self.assertIn("fresh selected text", fresh["text"])

    def test_expired_lease_needs_owner_use_to_restore_same_selected_token(self):
        selected = self.capability()
        self.bind(selected)
        self.expire(selected, int(time.time()) - 1)
        reader = {"Authorization": "Bearer " + selected["token"]}
        self.assertEqual(self.client.get(self.prefix + "/notes/" + self.note_id, headers=reader).status_code, 401)
        self.assertTrue(self.refresh().json()["renewed"])
        self.assertEqual(self.client.get(self.prefix + "/notes/" + self.note_id, headers=reader).status_code, 200)

    def test_owner_auth_is_required_including_windows_loopback_origin(self):
        selected = self.capability()
        self.bind(selected)
        before = self.store.capability(selected["capabilityId"])
        reader = {"Authorization": "Bearer " + selected["token"]}
        loopback = {"Origin": "http://127.0.0.1:41987"}
        self.assertEqual(self.refresh(headers={**reader, **loopback}).status_code, 403)
        self.assertEqual(self.refresh(headers={"Authorization": "Bearer legacy-service"}).status_code, 403)
        self.assertEqual(self.client.post(self.prefix + "/integrations/focus/refresh", headers=loopback, json={}).status_code, 401)
        self.assertEqual(self.refresh(body={"noteId": self.note_ids[1]}).status_code, 422)
        self.assertEqual(self.store.capability(selected["capabilityId"]), before)
        response = self.refresh(headers={**self.owner, **loopback})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["connected"] and response.json()["renewed"])

    def test_revoked_capability_or_enrollment_never_revives(self):
        selected = self.capability()
        self.bind(selected)
        self.store.revoke_capability(None, selected["capabilityId"])
        before = self.store.capability(selected["capabilityId"])
        self.assertFalse(self.refresh().json()["connected"])
        self.assertEqual(self.store.capability(selected["capabilityId"]), before)
        selected = self.capability()
        self.bind(selected)
        self.store.activate(self.note_id, False)
        before = self.store.capability(selected["capabilityId"])
        self.assertFalse(self.refresh().json()["connected"])
        self.assertEqual(self.store.capability(selected["capabilityId"]), before)

    def test_binding_cannot_renew_broader_or_unrelated_capabilities(self):
        for change in ({"clientId": "lama-private"}, {"scopes": ["notes:read", "notes:update"]},
                       {"noteIds": self.note_ids}, {"noteIds": [self.note_ids[1]]}):
            with self.subTest(change=change):
                selected = self.capability(**change)
                self.bind(selected)
                before = self.store.capability(selected["capabilityId"])
                self.assertFalse(self.refresh().json()["connected"])
                self.assertEqual(self.store.capability(selected["capabilityId"]), before)

    def test_missing_or_invalid_fixed_binding_is_quiet(self):
        self.assertFalse(self.refresh().json()["connected"])
        binding = self.store.root / "focus-quicknotes.json"
        binding.write_text("invalid")
        self.assertFalse(self.refresh().json()["connected"])
        binding.write_text(json.dumps({"noteId": "#private", "capabilityId": "lg-" + "1" * 32}))
        self.assertFalse(self.refresh().json()["connected"])


if __name__ == "__main__":
    unittest.main()
