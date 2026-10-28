import hashlib
import json
import struct
import zlib
import logging
import os
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from auth.models import AuthPrincipal
from notes.file_system.file_system import FileSystemNotes
from notes.models import NoteCreate, NoteUpdate
from private_api.routes import create_router
from private_api.service import PrivateService
from private_api.middleware import PrivateRequestLimit
from notes.identity import with_note_id


class OwnerAuth:
    def authenticate(self, request, token):
        if token == "synthetic-owner":
            return AuthPrincipal("owner", "session", frozenset())
        if token == "legacy-service":
            return AuthPrincipal(
                "legacy", "api-token", frozenset({"notes:read"})
            )
        raise HTTPException(401, "Login required.")


class PrivateApiTests(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        with patch.dict(os.environ, {"LAMANOTES_PATH": self.temp.name}):
            self.notes = FileSystemNotes()
        self.service = PrivateService(self.notes)
        app = FastAPI()
        app.add_middleware(PrivateRequestLimit)
        app.include_router(create_router(self.service, OwnerAuth()))
        self.client = TestClient(app)
        self.owner = {"Authorization": "Bearer synthetic-owner"}
        self.prefix = "/api/private/v1"
        self.personal = self.notes.create(
            NoteCreate(title="Private fixture", content="<p>green apples</p>")
        )
        self.work = self.notes.create(
            NoteCreate(
                title="Excluded fixture",
                content="<p>forbidden-project-secret green apples</p>",
            )
        )
        self.note = self.post(
            "/grants/notes",
            {
                "title": self.personal.title,
                "expectedVersion": self.personal.version,
                "personal": True,
            },
        ).json()

    def post(self, path, body, headers=None, key="fixture-key-0001"):
        return self.client.post(
            self.prefix + path,
            json=body,
            headers={**(headers or self.owner), "Idempotency-Key": key},
        )

    def cap(self, scopes=None, note_ids=None, **extra):
        response = self.post(
            "/capabilities",
            {
                "clientId": "test-client",
                "scopes": scopes or ["notes:read"],
                "noteIds": (
                    note_ids if note_ids is not None else [self.note["noteId"]]
                ),
                **extra,
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        value = response.json()
        return {"Authorization": "Bearer " + value["token"]}, value

    def get(self, path, headers=None):
        return self.client.get(
            self.prefix + path, headers=headers or self.owner
        )

    def stored_capability(self, capability_id):
        with self.service.store.connect() as db:
            return dict(db.execute(
                "SELECT * FROM capabilities WHERE id=?", (capability_id,)
            ).fetchone())

    def alter_capability(self, capability_id, **changes):
        row = self.stored_capability(capability_id)
        payload = json.loads(row["payload"])
        payload.update(changes)
        with self.service.store.connect() as db:
            db.execute("UPDATE capabilities SET payload=? WHERE id=?",
                       (json.dumps(payload), capability_id))

    def child_capability(self, headers, expires_in=120):
        response = self.post("/capabilities/delegate", {
            "clientId": "test-client", "jobId": "lr-" + "e" * 32,
            "scopes": ["notes:read", "capabilities:delegate"],
            "noteIds": [self.note["noteId"]], "expiresIn": expires_in,
        }, headers)
        self.assertEqual(response.status_code, 201, response.text)
        value = response.json()
        return {"Authorization": "Bearer " + value["token"]}, value

    def test_owner_renewal_keeps_identity_objects_and_jobless_receipts(self):
        capture_body = {"kind": "text", "text": "Renewal fixture",
                        "provenance": {"channel": "codex"}}
        owner_capture = self.post("/captures", capture_body).json()
        headers, cap = self.cap([
            "notes:read", "notes:create", "captures:read", "captures:create",
            "assets:read", "assets:create",
        ], expiresIn=60, captureIds=[owner_capture["captureId"]])
        path = "/capabilities/" + cap["capabilityId"] + "/renew"
        capture = self.post("/captures", capture_body, headers).json()
        asset = self.upload(headers).json()
        note_body = {"title": "Renewal note", "content": "<p>Fixture</p>"}
        note = self.post("/notes", note_body, headers).json()
        before = self.stored_capability(cap["capabilityId"])
        with self.service.store.connect() as db:
            objects = list(db.execute("SELECT * FROM objects"))
            receipts = list(db.execute("SELECT * FROM receipts"))
        now = cap["expiresAt"] + 1
        with patch("private_api.store.time.time", return_value=now):
            self.assertEqual(self.get("/index", headers).status_code, 401)
            response = self.post(path, {"expiresIn": 600})
            self.assertEqual(response.status_code, 200, response.text)
            value = response.json()
            self.assertEqual(response.headers["cache-control"], "no-store")
            self.assertNotIn("token", value)
            self.assertNotIn("digest", value)
            self.assertEqual(value, {
                **{k: v for k, v in cap.items() if k != "token"},
                "expiresAt": now + 600, "revoked": False,
            })
            self.assertEqual(self.get("/index", headers).json()["total"], 2)
            self.assertEqual(self.post("/captures", capture_body, headers).json()["captureId"], capture["captureId"])
            self.assertEqual(self.post("/notes", note_body, headers).json()["noteId"], note["noteId"])
            self.assertEqual(self.upload(headers).json()["assetId"], asset["assetId"])
            self.assertEqual(self.get("/assets/" + asset["assetId"] + "/content", headers).content, b"private source")
        after = self.stored_capability(cap["capabilityId"])
        self.assertEqual(after["digest"], before["digest"])
        self.assertEqual(after["revoked"], before["revoked"])
        self.assertEqual(json.loads(after["payload"]), {**json.loads(before["payload"]), "expiresAt": now + 600})
        with self.service.store.connect() as db:
            self.assertEqual(list(db.execute("SELECT * FROM objects")), objects)
            self.assertEqual(list(db.execute("SELECT * FROM receipts")), receipts)

    def test_renewal_requires_owner_not_target_parent_or_service(self):
        parent_headers, _ = self.cap(["notes:read", "capabilities:delegate"], expiresIn=600)
        headers, cap = self.child_capability(parent_headers)
        path = self.prefix + "/capabilities/" + cap["capabilityId"] + "/renew"
        before = self.stored_capability(cap["capabilityId"])
        for auth, status in (({}, 401), ({"Authorization": "Bearer legacy-service"}, 403),
                             (headers, 403), (parent_headers, 403)):
            response = self.client.post(path, json={"expiresIn": 300}, headers=auth)
            self.assertEqual(response.status_code, status, response.text)
        self.assertEqual(self.stored_capability(cap["capabilityId"]), before)

    def test_renewal_rejects_unknown_ids_invalid_ttl_and_extra_fields(self):
        _, cap = self.cap()
        path = "/capabilities/" + cap["capabilityId"] + "/renew"
        before = self.stored_capability(cap["capabilityId"])
        bodies = [{}, *[{"expiresIn": ttl} for ttl in (59, 2592001, True, "600", 60.5)]]
        for field, value in (("scopes", ["notes:create"]), ("noteIds", []),
                             ("clientId", "other"), ("jobId", None), ("parentId", None)):
            bodies.append({"expiresIn": 600, field: value})
        for body in bodies:
            with self.subTest(body=body):
                self.assertEqual(self.post(path, body).status_code, 422)
        self.assertEqual(self.post("/capabilities/lg-" + "0" * 32 + "/renew", {"expiresIn": 600}).status_code, 404)
        self.assertEqual(self.stored_capability(cap["capabilityId"]), before)

    def test_renewal_never_shortens_and_repeated_requests_are_safe(self):
        now = int(time.time())
        with patch("private_api.store.time.time", return_value=now):
            _, cap = self.cap(expiresIn=600)
            path = "/capabilities/" + cap["capabilityId"] + "/renew"
            before = self.stored_capability(cap["capabilityId"])
            for _ in range(2):
                response = self.post(path, {"expiresIn": 60})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["expiresAt"], now + 600)
            self.assertEqual(self.stored_capability(cap["capabilityId"]), before)
            self.assertEqual(self.post(path, {"expiresIn": 2592000}).json()["expiresAt"], now + 2592000)
            self.assertEqual(self.post(path, {"expiresIn": 60}).json()["expiresAt"], now + 2592000)

    def test_revoked_target_cannot_be_renewed_even_after_expiry(self):
        headers, cap = self.cap(expiresIn=60)
        base = "/capabilities/" + cap["capabilityId"]
        self.client.delete(self.prefix + base, headers=self.owner)
        before = self.stored_capability(cap["capabilityId"])
        with patch("private_api.store.time.time", return_value=cap["expiresAt"] + 1):
            response = self.post(base + "/renew", {"expiresIn": 600})
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()["detail"]["code"], "capability-revoked")
            self.assertEqual(self.get("/index", headers).status_code, 401)
        self.assertEqual(self.stored_capability(cap["capabilityId"]), before)

    def test_child_renewal_preserves_ancestry_and_respects_parent_expiry(self):
        parent_headers, parent = self.cap(["notes:read", "capabilities:delegate"], expiresIn=600)
        headers, child = self.child_capability(parent_headers)
        path = "/capabilities/" + child["capabilityId"] + "/renew"
        before = self.stored_capability(child["capabilityId"])
        response = self.post(path, {"expiresIn": 700})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"]["code"], "capability-parent-expiry")
        self.assertEqual(self.stored_capability(child["capabilityId"]), before)
        now = child["expiresAt"] + 1
        with patch("private_api.store.time.time", return_value=now):
            self.assertEqual(self.get("/index", headers).status_code, 401)
            response = self.post(path, {"expiresIn": 180})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["parentId"], parent["capabilityId"])
            self.assertEqual(response.json()["jobId"], child["jobId"])
            self.assertEqual(response.json()["expiresAt"], now + 180)
            self.assertEqual(self.get("/index", headers).status_code, 200)
        self.assertEqual(self.stored_capability(child["capabilityId"])["digest"], before["digest"])

    def test_renewal_checks_all_ancestors_and_rejects_broken_chains(self):
        for state in ("revoked", "expired", "missing", "cycle", "expiry-bound"):
            with self.subTest(state=state):
                parent_headers, parent = self.cap(["notes:read", "capabilities:delegate"], expiresIn=900)
                middle_headers, middle = self.child_capability(parent_headers, 600)
                _, child = self.child_capability(middle_headers, 120)
                parent_id = parent["capabilityId"]
                before = self.stored_capability(child["capabilityId"])
                if state == "revoked":
                    self.client.delete(self.prefix + "/capabilities/" + parent_id, headers=self.owner)
                elif state == "expired":
                    self.alter_capability(parent_id, expiresAt=int(time.time()) - 1)
                elif state == "missing":
                    with self.service.store.connect() as db:
                        db.execute("DELETE FROM capabilities WHERE id=?", (parent_id,))
                elif state == "cycle":
                    self.alter_capability(parent_id, parentId=child["capabilityId"])
                else:
                    self.alter_capability(parent_id, expiresAt=int(time.time()) + 150)
                response = self.post("/capabilities/" + child["capabilityId"] + "/renew", {"expiresIn": 180})
                self.assertEqual(response.status_code, 409, response.text)
                expected = "capability-parent-expiry" if state == "expiry-bound" else "capability-ancestor-unavailable"
                self.assertEqual(response.json()["detail"]["code"], expected)
                self.assertEqual(self.stored_capability(child["capabilityId"]), before)

    def test_renewal_rejects_over_depth_chain(self):
        caps = [self.cap(expiresIn=600)[1] for _ in range(10)]
        for child, parent in zip(caps, caps[1:]):
            self.alter_capability(child["capabilityId"], parentId=parent["capabilityId"])
        response = self.post("/capabilities/" + caps[0]["capabilityId"] + "/renew", {"expiresIn": 60})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"]["code"], "capability-ancestor-unavailable")

    def test_renewal_does_not_restore_object_grants_or_extend_children_and_readers(self):
        headers, parent = self.cap(["notes:read", "assets:read", "capabilities:delegate"], expiresIn=600)
        child_headers, child = self.child_capability(headers, 60)
        reader = self.client.post("https://testserver" + self.prefix + "/reader-session",
                                  headers=headers, json={"noteId": self.note["noteId"], "expiresIn": 30})
        self.assertEqual(reader.status_code, 200, reader.text)
        with self.service.store.connect() as db:
            readers = list(db.execute("SELECT * FROM reader_sessions"))
        child_before = self.stored_capability(child["capabilityId"])
        self.client.delete(self.prefix + "/grants/" + self.note["noteId"], headers=self.owner)
        with patch("private_api.store.time.time", return_value=parent["expiresAt"] + 1):
            response = self.post("/capabilities/" + parent["capabilityId"] + "/renew", {"expiresIn": 600})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(self.get("/index", headers).json()["total"], 0)
            self.assertEqual(self.get("/index", child_headers).status_code, 401)
        self.assertFalse(self.service.store.object(self.note["noteId"])["active"])
        self.assertEqual(self.stored_capability(child["capabilityId"]), child_before)
        with self.service.store.connect() as db:
            self.assertEqual(list(db.execute("SELECT * FROM reader_sessions")), readers)

    def test_concurrent_renewals_keep_longest_expiry_and_revocation_wins(self):
        now = int(time.time())
        with patch("private_api.store.time.time", return_value=now):
            headers, cap = self.cap(expiresIn=60)
            base = "/capabilities/" + cap["capabilityId"]
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda ttl: self.post(base + "/renew", {"expiresIn": ttl}), (600, 1800)))
            self.assertEqual([result.status_code for result in results], [200, 200])
            self.assertEqual(self.service.store.capability(cap["capabilityId"])["expiresAt"], now + 1800)
            with ThreadPoolExecutor(max_workers=2) as pool:
                renewal = pool.submit(self.post, base + "/renew", {"expiresIn": 2400})
                revoke = pool.submit(self.client.delete, self.prefix + base, headers=self.owner)
                self.assertIn(renewal.result().status_code, (200, 409))
                self.assertEqual(revoke.result().status_code, 204)
            self.assertTrue(self.service.store.capability(cap["capabilityId"])["revoked"])
            self.assertEqual(self.get("/index", headers).status_code, 401)

    def test_private_index_search_and_context_never_expose_other_notes(self):
        headers, _ = self.cap()
        for path in [
            "/index",
            "/search?term=green",
            "/notes/" + self.note["noteId"] + "/context",
        ]:
            response = self.get(path, headers)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertNotIn("Excluded", response.text)
            self.assertNotIn("forbidden-project", response.text)
        self.assertEqual(self.get("/index", headers).json()["total"], 1)
        self.assertEqual(
            self.get("/search?term=forbidden", headers).json()["total"], 0
        )

    def test_no_automatic_personal_enrollment_or_broad_service_auth(self):
        headers, _ = self.cap(note_ids=[])
        self.assertEqual(self.get("/index", headers).json()["items"], [])
        self.assertEqual(
            self.get(
                "/index", {"Authorization": "Bearer legacy-service"}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.get("/notes/ln-" + "0" * 32, headers).status_code, 404
        )
        self.assertEqual(
            self.get("/notes/" + self.note["noteId"], headers).status_code, 404
        )
        self.assertEqual(
            self.post(
                "/grants/notes",
                {
                    "title": self.work.title,
                    "expectedVersion": self.work.version,
                    "personal": True,
                },
                headers,
            ).status_code,
            403,
        )

    def test_expired_and_revoked_parent_invalidate_children(self):
        headers, parent = self.cap(
            ["notes:read", "capabilities:delegate"], expiresIn=600
        )
        child = self.post(
            "/capabilities/delegate",
            {
                "clientId": "test-client",
                "jobId": "lr-" + "a" * 32,
                "scopes": ["notes:read"],
                "noteIds": [self.note["noteId"]],
                "expiresIn": 120,
            },
            headers,
        ).json()
        child_headers = {"Authorization": "Bearer " + child["token"]}
        self.assertEqual(self.get("/index", child_headers).status_code, 200)
        revoked = self.client.delete(
            self.prefix + "/capabilities/" + parent["capabilityId"],
            headers=self.owner,
        )
        self.assertEqual(revoked.status_code, 204)
        self.assertEqual(self.get("/index", child_headers).status_code, 401)
        headers, value = self.cap(expiresIn=60)
        with patch(
            "private_api.store.time.time", return_value=time.time() + 61
        ):
            self.assertEqual(self.get("/index", headers).status_code, 401)

    def test_delegation_cannot_widen_client_scopes_objects_or_expiry(self):
        headers, _ = self.cap(
            ["notes:read", "capabilities:delegate"], note_ids=[], expiresIn=600
        )
        base = {
            "clientId": "test-client",
            "scopes": ["notes:read"],
            "expiresIn": 60,
        }
        for change in [
            {"clientId": "other"},
            {"scopes": ["notes:create"]},
            {"expiresIn": 601},
            {"noteIds": [self.note["noteId"]]},
        ]:
            response = self.post(
                "/capabilities/delegate", {**base, **change}, headers
            )
            self.assertIn(response.status_code, {403, 404}, response.text)

    def test_generic_identity_survives_legacy_rename_and_edit(self):
        self.notes.update(
            self.personal.title,
            NoteUpdate(new_title="Renamed", new_content="<p>changed</p>"),
        )
        result = self.get("/notes/" + self.note["noteId"]).json()
        self.assertEqual(result["title"], "Renamed")
        self.assertEqual(result["noteId"], self.note["noteId"])
        self.assertIn("/n/ln-", result["url"])
        with self.assertRaises(ValueError):
            self.notes.update(
                "Renamed",
                NoteUpdate(
                    new_content='<meta name="lamanotes-note-id" content="ln-'
                    + "f" * 32
                    + '"><p>bad</p>'
                ),
            )
        self.assertEqual(
            self.get("/notes/" + self.note["noteId"]).json()["title"],
            "Renamed",
        )

    def test_integration_writes_require_current_version(self):
        headers, _ = self.cap(["notes:read", "notes:update"])
        url = self.prefix + "/notes/" + self.note["noteId"]
        self.assertEqual(
            self.client.patch(
                url, headers=headers, json={"content": "<p>x</p>"}
            ).status_code,
            422,
        )
        first = self.client.patch(
            url,
            headers=headers,
            json={
                "content": "<p>new</p>",
                "expectedVersion": self.note["version"],
            },
        )
        self.assertEqual(first.status_code, 200, first.text)
        conflict = self.client.patch(
            url,
            headers=headers,
            json={
                "title": "Must not rename",
                "expectedVersion": self.note["version"],
            },
        )
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(
            self.get("/notes/" + self.note["noteId"]).json()["title"],
            self.personal.title,
        )

    def test_enrollment_is_explicit_and_stale_enrollment_fails(self):
        self.notes.update(
            self.work.title, NoteUpdate(new_content="<p>later</p>")
        )
        result = self.post(
            "/grants/notes",
            {
                "title": self.work.title,
                "expectedVersion": self.work.version,
                "personal": True,
            },
        )
        self.assertEqual(result.status_code, 409)
        self.assertIsNone(self.notes.get(self.work.title).note_id)
        result = self.post(
            "/grants/notes",
            {
                "title": self.work.title,
                "expectedVersion": self.work.version,
                "personal": False,
            },
        )
        self.assertEqual(result.status_code, 422)

    def test_capture_replay_and_reference_validation(self):
        headers, _ = self.cap(
            ["captures:create", "captures:read", "references:read"],
            note_ids=[],
        )
        body = {
            "kind": "link",
            "sourceUrl": "https://example.org/article",
            "text": "Selected private source",
            "provenance": {"channel": "web"},
        }
        first = self.post("/captures", body, headers)
        self.assertEqual(first.status_code, 201, first.text)
        capture = first.json()
        self.assertEqual(
            self.post("/captures", body, headers).json()["captureId"],
            capture["captureId"],
        )
        self.assertEqual(
            self.post(
                "/captures", {**body, "text": "changed"}, headers
            ).status_code,
            409,
        )
        refs = {
            "sources": [
                {
                    "captureId": capture["captureId"],
                    "sha256": capture["sha256"],
                }
            ]
        }
        self.assertEqual(
            self.post("/references/check", refs, headers).status_code, 200
        )
        refs["sources"][0]["sha256"] = "0" * 64
        self.assertEqual(
            self.post("/references/check", refs, headers).status_code, 409
        )
        other, _ = self.cap(["captures:read"], note_ids=[], clientId="other")
        self.assertEqual(
            self.get("/captures/" + capture["captureId"], other).status_code,
            404,
        )

    def upload(self, headers, data=b"private source", **fields):
        return self.client.post(
            self.prefix + "/assets",
            headers={
                **headers,
                "Idempotency-Key": fields.pop("key", "asset-key-00001"),
            },
            files={
                "file": (
                    "fixture.txt",
                    data,
                    fields.pop("media", "text/plain"),
                )
            },
            data=fields,
        )

    def test_pdf_download_filename_on_private_and_reader_routes(self):
        headers, _ = self.cap(
            ["assets:create", "assets:read", "notes:create", "notes:read"],
            note_ids=[],
        )
        data = b"%PDF-1.4\n% synthetic download fixture\n%%EOF\n"
        # The validated signature, not the upload filename or claimed MIME,
        # determines the extension, including for existing extensionless assets.
        asset = self.upload(headers, data, media="text/plain").json()
        asset_id = asset["assetId"]
        self.assertEqual(asset["mediaType"], "application/pdf")
        self.assertTrue((self.service.store.assets / asset_id).is_file())
        path = "/assets/" + asset_id + "/content"
        note = self.post(
            "/notes",
            {
                "title": "PDF download fixture",
                "content": f'<a href="{self.prefix}{path}" download="Report.pdf">PDF</a>',
                "assetIds": [asset_id],
            },
            headers,
        ).json()
        reader = self.post(
            "/reader-session",
            {"noteId": note["noteId"], "expiresIn": 60},
            headers,
        ).json()["readerUrl"]
        responses = [
            self.get(path, headers),
            self.get(path),
            self.client.get(reader + path),
        ]
        for response in responses:
            with self.subTest(url=str(response.request.url)):
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.content, data)
                self.assertEqual(
                    response.headers["content-type"], "application/pdf"
                )
                self.assertEqual(
                    response.headers["content-disposition"],
                    f'attachment; filename="{asset_id}.pdf"',
                )
                self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(self.get("/assets/" + asset_id, headers).json(), asset)

    def test_non_pdf_asset_disposition_is_unchanged(self):
        asset = self.upload(self.owner).json()
        response = self.get("/assets/" + asset["assetId"] + "/content")
        self.assertEqual(
            response.headers["content-disposition"],
            f'attachment; filename="{asset["assetId"]}"',
        )
        self.assertEqual(response.content, b"private source")

    def test_assets_are_grant_filtered_and_sources_are_immutable(self):
        headers, _ = self.cap(["assets:create", "assets:read"], note_ids=[])
        source = self.upload(headers).json()
        original_hash = source["sha256"]
        derived = self.upload(
            headers,
            b"cropped source",
            role="derived",
            sourceAssetId=source["assetId"],
            key="asset-key-00002",
        )
        self.assertEqual(derived.status_code, 201, derived.text)
        self.assertEqual(
            self.get("/assets/" + source["assetId"], headers).json()["sha256"],
            original_hash,
        )
        other, _ = self.cap(
            ["assets:read", "assets:create"], note_ids=[], clientId="other"
        )
        self.assertEqual(
            self.get(
                "/assets/" + source["assetId"] + "/content", other
            ).status_code,
            404,
        )
        self.assertEqual(
            self.upload(
                other, role="derived", sourceAssetId=source["assetId"]
            ).status_code,
            404,
        )
        original = b"<svg><script>alert(1)</script></svg>"
        uploaded = self.upload(headers, original, media="image/svg+xml", key="svg-original-0001")
        self.assertEqual(uploaded.status_code, 201)
        response = self.get("/assets/" + uploaded.json()["assetId"] + "/content", headers)
        self.assertEqual(response.content, original)
        self.assertTrue(response.headers["content-disposition"].startswith("attachment;"))
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")

    def test_revoke_note_removes_linked_asset_access(self):
        asset = self.upload(self.owner).json()
        note = self.post(
            "/notes",
            {
                "title": "Image fixture",
                "content": "<p>image</p>",
                "assetIds": [asset["assetId"]],
            },
            key="image-note-01",
        ).json()
        headers, _ = self.cap(
            ["notes:read", "assets:read"], note_ids=[note["noteId"]]
        )
        self.assertEqual(
            self.get(
                "/assets/" + asset["assetId"] + "/content", headers
            ).status_code,
            200,
        )
        self.client.delete(
            self.prefix + "/grants/" + note["noteId"], headers=self.owner
        )
        self.assertEqual(
            self.get(
                "/assets/" + asset["assetId"] + "/content", headers
            ).status_code,
            404,
        )
        self.assertEqual(
            self.get("/notes/" + note["noteId"], headers).status_code, 404
        )
        self.assertEqual(
            self.get("/notes/" + note["noteId"], self.owner).status_code, 200
        )

    def test_job_bound_result_verifier_gets_only_matching_creation(self):
        job = "lr-" + "a" * 32
        worker, _ = self.cap(["notes:create"], note_ids=[], jobId=job)
        verifier, _ = self.cap(["references:read"], note_ids=[], jobId=job)
        content = (
            '<html><head><meta name="lamanotes-research-id" '
            f'content="{job}"></head><body><p>Result</p>'
            "<p>#research #r-fixture</p></body></html>"
        )
        response = self.post(
            "/notes", {"title": "Job result", "content": content}, worker
        )
        self.assertEqual(response.status_code, 201, response.text)
        note = response.json()
        result = self.post(
            "/references/result",
            {
                "noteId": note["noteId"],
                "version": note["version"],
                "researchId": job,
            },
            verifier,
        )
        self.assertEqual(result.status_code, 200, result.text)
        self.assertNotIn("content", result.json())
        self.assertEqual(
            result.json()["htmlSha256"],
            hashlib.sha256(note["content"].encode()).hexdigest(),
        )
        other, _ = self.cap(
            ["references:read"], note_ids=[], jobId="lr-" + "b" * 32
        )
        self.assertEqual(
            self.post(
                "/references/result",
                {
                    "noteId": note["noteId"],
                    "version": note["version"],
                    "researchId": job,
                },
                other,
            ).status_code,
            404,
        )

    def test_private_html_rejects_hidden_requests_and_active_content(self):
        for content in [
            "<img src=https://example.org/track>",
            '<meta http-equiv="refresh" content="0;url=https://example.org">',
            '<a href="javascript:alert(1)">x</a>',
            '<svg><use href="https://example.org/image"></use></svg>',
        ]:
            result = self.post(
                "/notes", {"title": "Rejected", "content": content}
            )
            self.assertEqual(result.status_code, 422, result.text)

    def test_idempotent_note_creation(self):
        body = {"title": "New fixture", "content": "<p>Private result</p>"}
        first = self.post("/notes", body).json()
        second = self.post("/notes", body).json()
        self.assertEqual(first["noteId"], second["noteId"])
        self.assertEqual(
            self.post(
                "/notes", {**body, "content": "<p>different</p>"}
            ).status_code,
            409,
        )

    def test_preassigned_identity_preserves_html_hash_and_rejects_reuse(self):
        note_id = "ln-" + "8" * 32
        content = with_note_id(
            "<html><head></head><body><p>Fixture</p></body></html>", note_id
        )
        body = {
            "noteId": note_id,
            "title": "Exact fixture",
            "content": content,
        }
        response = self.post("/notes", body)
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["content"], content)
        self.assertEqual(self.post("/notes", body).json()["noteId"], note_id)
        self.assertEqual(
            self.post("/notes", body, key="different-key").status_code, 409
        )
        self.assertEqual(
            self.post(
                "/notes",
                {**body, "noteId": "ln-" + "9" * 32},
                key="mismatch-key",
            ).status_code,
            422,
        )

    def test_interrupted_note_creation_replays_reserved_identity(self):
        body = {
            "title": "Interrupted fixture",
            "content": "<p>Recover this</p>",
        }
        with patch.object(
            self.service.store,
            "put_object",
            side_effect=RuntimeError("simulated crash"),
        ):
            with self.assertRaises(RuntimeError):
                self.post("/notes", body)
        existing = self.notes.get(body["title"])
        response = self.post("/notes", body)
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["noteId"], existing.note_id)
        self.assertEqual(
            len(list(self.service.root.glob("Interrupted fixture.html"))), 1
        )

    def test_interrupted_capture_and_asset_replay(self):
        body = {
            "kind": "text",
            "text": "Recover capture",
            "provenance": {"channel": "web"},
        }
        with patch.object(
            self.service.store,
            "put_object",
            side_effect=RuntimeError("simulated crash"),
        ):
            for action in [
                lambda: self.post("/captures", body),
                lambda: self.upload(self.owner),
            ]:
                with self.assertRaises(RuntimeError):
                    action()
        self.assertEqual(self.post("/captures", body).status_code, 201)
        self.assertEqual(self.upload(self.owner).status_code, 201)
        self.assertEqual(len(list(self.service.store.assets.iterdir())), 1)

    def test_asset_integrity_and_version_checked_note_association(self):
        asset = self.upload(self.owner).json()
        path = "/notes/" + self.note["noteId"] + "/assets"
        self.assertEqual(
            self.post(
                path,
                {"assetIds": [asset["assetId"]], "expectedVersion": "0" * 64},
            ).status_code,
            409,
        )
        self.assertEqual(
            self.post(
                path,
                {
                    "assetIds": [asset["assetId"]],
                    "expectedVersion": self.note["version"],
                },
            ).status_code,
            200,
        )
        (self.service.store.assets / asset["assetId"]).write_bytes(
            b"tampered fixture"
        )
        self.assertEqual(
            self.get("/assets/" + asset["assetId"] + "/content").status_code,
            409,
        )

    def test_crop_receipt_geometry_and_hashes(self):
        def png(size):
            def chunk(kind, value):
                return (
                    struct.pack(">I", len(value))
                    + kind
                    + value
                    + struct.pack(">I", zlib.crc32(kind + value))
                )

            width, height = size
            header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
            rows = (b"\0" + b"\0\0\xff" * width) * height
            return (
                b"\x89PNG\r\n\x1a\n"
                + chunk(b"IHDR", header)
                + chunk(b"IDAT", zlib.compress(rows))
                + chunk(b"IEND", b"")
            )

        source_bytes, cropped = png((20, 10)), png((10, 5))
        source = self.upload(
            self.owner, source_bytes, media="image/png"
        ).json()
        receipt = {
            "schema": "lamaphotos.crop.v1",
            "source_system": "lamanotes",
            "source_id": source["assetId"],
            "source_size_px": {"width": 20, "height": 10},
            "output_size_px": {"width": 10, "height": 5},
            "crop_rect_px": {"x": 2, "y": 1, "width": 10, "height": 5},
            "target_size_cm": {"width": 10, "height": 5},
            "print_dpi": {"horizontal": 100, "vertical": 100, "minimum": 100},
            "created_at": "2026-09-08T12:00:00Z",
            "sha256_source": source["sha256"],
            "sha256_output": hashlib.sha256(cropped).hexdigest(),
        }
        for index, change in enumerate(
            [
                {"sha256_output": "0" * 64},
                {"crop_rect_px": {"x": 19, "y": 0, "width": 10, "height": 5}},
                {"output_name": "C:/private/file.png"},
            ]
        ):
            response = self.upload(
                self.owner,
                cropped,
                role="derived",
                sourceAssetId=source["assetId"],
                media="image/png",
                cropReceipt=json.dumps({**receipt, **change}),
                key=f"bad-receipt-{index}",
            )
            self.assertEqual(response.status_code, 422, response.text)
        response = self.upload(
            self.owner,
            cropped,
            role="derived",
            sourceAssetId=source["assetId"],
            media="image/png",
            cropReceipt=json.dumps(receipt),
            key="valid-receipt",
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(
            self.get("/assets/" + source["assetId"] + "/content").content,
            source_bytes,
        )
        oriented = {**source, "mediaType": "image/jpeg"}
        transposed = {
            **receipt,
            "source_size_px": {"width": 10, "height": 20},
            "crop_rect_px": {"x": 0, "y": 0, "width": 10, "height": 5},
        }
        self.service.validate_crop_receipt(
            transposed, source["assetId"], oriented, response.json()
        )

    def test_reader_cookie_is_single_note_and_cannot_use_private_or_legacy_auth(
        self,
    ):
        headers, capability = self.cap(["notes:read", "assets:read"])
        result = self.post(
            "/reader-session",
            {"noteId": self.note["noteId"], "expiresIn": 60},
            headers,
        )
        self.assertEqual(result.status_code, 200, result.text)
        self.assertIn("HttpOnly", result.headers["set-cookie"])
        path = result.json()["readerUrl"]
        document = self.client.get(path + "/document")
        self.assertEqual(document.status_code, 200, document.text)
        self.assertEqual(document.headers["cache-control"], "no-store")
        self.assertEqual(
            self.client.get(self.prefix + "/index").status_code, 401
        )
        self.assertEqual(
            self.client.get(
                self.prefix + "/reader/ln-" + "0" * 32 + "/document"
            ).status_code,
            401,
        )
        self.client.delete(
            self.prefix + "/capabilities/" + capability["capabilityId"],
            headers=self.owner,
        )
        self.assertEqual(self.client.get(path + "/document").status_code, 401)

    def test_real_owner_auth_rejects_private_capability_on_legacy_routes(self):
        from auth.local.local import LocalAuth
        from starlette.requests import Request

        auth = object.__new__(LocalAuth)
        auth.secret_key = "synthetic-test-only-key"
        auth.accept_legacy_tokens = False
        headers, _ = self.cap()
        request = Request({"type": "http", "method": "GET", "headers": []})
        with self.assertRaises(HTTPException) as caught:
            auth.authenticate(request, headers["Authorization"][7:])
        self.assertEqual(caught.exception.status_code, 401)

    def test_body_limit_precedes_validation(self):
        result = self.client.post(
            self.prefix + "/captures",
            content=b" " * (8 * 1024 * 1024 + 1),
            headers=self.owner,
        )
        self.assertEqual(result.status_code, 413)

    def test_job_replay_survives_capability_rotation(self):
        job = "lr-" + "d" * 32
        body = {
            "title": "Rotated job fixture",
            "content": f'<meta name="lamanotes-research-id" content="{job}"><p>Result</p><p>#research #r-fixture</p>',
        }
        first, first_cap = self.cap(["notes:create"], note_ids=[], jobId=job)
        created = self.post("/notes", body, first)
        self.assertEqual(created.status_code, 201, created.text)
        self.client.delete(
            self.prefix + "/capabilities/" + first_cap["capabilityId"],
            headers=self.owner,
        )
        second, _ = self.cap(["notes:create"], note_ids=[], jobId=job)
        replay = self.post("/notes", body, second)
        self.assertEqual(replay.status_code, 201, replay.text)
        self.assertEqual(created.json()["noteId"], replay.json()["noteId"])

    def test_reader_does_not_inherit_other_asset_grants_and_expires(self):
        asset = self.upload(self.owner).json()
        other = self.post(
            "/notes",
            {
                "title": "Other media fixture",
                "content": "<p>Other</p>",
                "assetIds": [asset["assetId"]],
            },
        ).json()
        headers, _ = self.cap(
            ["notes:read", "assets:read"],
            note_ids=[self.note["noteId"], other["noteId"]],
        )
        response = self.post(
            "/reader-session",
            {"noteId": self.note["noteId"], "expiresIn": 30},
            headers,
        )
        path = response.json()["readerUrl"]
        self.assertEqual(
            self.client.get(
                path + "/assets/" + asset["assetId"] + "/content"
            ).status_code,
            404,
        )
        with patch(
            "private_api.store.time.time", return_value=time.time() + 31
        ):
            self.assertEqual(
                self.client.get(path + "/document").status_code, 401
            )

    def test_passive_svg_fragments_and_png_picture_pairs(self):
        asset = self.upload(self.owner).json()
        url = "/api/private/v1/assets/" + asset["assetId"] + "/content"
        content = f'<picture><source media="(prefers-color-scheme: dark)" srcset="{url}"><img src="{url}" alt="fixture"></picture><svg><defs><linearGradient id="a"><stop offset="0" /></linearGradient></defs><rect fill="url(#a)" width="10" height="10"/></svg>'
        response = self.post(
            "/notes",
            {
                "title": "Passive fixture",
                "content": content,
                "assetIds": [asset["assetId"]],
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        for forbidden in [
            '<svg><animate attributeName="href" to="https://example.org"/></svg>',
            '<svg><rect fill="url(https://example.org/image)"/></svg>',
        ]:
            response = self.post(
                "/notes",
                {"title": "Bad SVG fixture", "content": forbidden},
                key="forbidden-svg",
            )
            self.assertEqual(response.status_code, 422)

    def test_work_templates_cannot_hide_active_html_or_external_media(self):
        for source in [
            "&lt;script&gt;alert(1)&lt;/script&gt;",
            "![image](https://example.org/track)",
            '&lt;img src="https://example.org/track"&gt;',
        ]:
            content = f'<article data-lamanotes-note-kind="work"><template data-lamanotes-work-markdown>{source}</template><p>Work text</p></article>'
            response = self.post(
                "/notes",
                {"title": "Work template fixture", "content": content},
            )
            self.assertEqual(response.status_code, 422, response.text)
