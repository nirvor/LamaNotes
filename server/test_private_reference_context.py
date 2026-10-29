import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

import test_private_api as fixtures
from notes.models import NoteUpdate
from private_api.references import MAX_ASSET_BYTES


class ReferenceContextTests(unittest.TestCase):
    setUp = fixtures.PrivateApiTests.setUp
    post = fixtures.PrivateApiTests.post
    get = fixtures.PrivateApiTests.get
    cap = fixtures.PrivateApiTests.cap
    upload = fixtures.PrivateApiTests.upload

    def selected(self, note_ids=None, capture_ids=None, job=None):
        note_ids = [self.note["noteId"]] if note_ids is None else note_ids
        capture_ids = capture_ids or []
        root, _ = self.cap(
            ["references:read", "capabilities:delegate"],
            note_ids=note_ids,
            captureIds=capture_ids,
        )
        child = self.post(
            "/capabilities/delegate",
            {
                "clientId": "test-client",
                "jobId": job or "lr-" + "a" * 32,
                "scopes": ["references:read"],
                "expiresIn": 60,
                "noteIds": note_ids,
                "captureIds": capture_ids,
            },
            root,
        )
        self.assertEqual(child.status_code, 201, child.text)
        result = child.json()
        return {"Authorization": "Bearer " + result["token"]}, result, root

    def parent(self, note=None):
        note = note or self.note
        return {key: note[key] for key in ("noteId", "version", "researchId")}

    def test_scoped_original_export_accepts_100mb_and_rejects_one_byte_more(self):
        self.assertEqual(MAX_ASSET_BYTES, 100_000_000)
        data = b'\x00' * MAX_ASSET_BYTES
        asset = self.service.create_asset(None, data, 'application/octet-stream', 'source', None, None,
                                          'share-export-boundary', source_limit=MAX_ASSET_BYTES)
        capture = self.post('/captures', {'kind': 'file', 'text': 'Selected original',
            'assetIds': [asset['assetId']], 'provenance': {'channel': 'web'}}).json()
        headers, _, _ = self.selected(capture_ids=[capture['captureId']])
        source = {key: capture[key] for key in ('captureId', 'sha256')}
        context = self.post('/references/context', {'sources': [source]}, headers)
        self.assertEqual(context.status_code, 200, context.text)
        self.assertEqual(context.json()['sources'][0]['assets'][0]['size'], MAX_ASSET_BYTES)
        body = {'source': source, 'assetId': asset['assetId']}
        download = self.post('/references/content', body, headers)
        self.assertEqual(download.status_code, 200)
        self.assertEqual(len(download.content), MAX_ASSET_BYTES)
        self.assertEqual(hashlib.sha256(download.content).hexdigest(), asset['sha256'])
        self.assertTrue(download.headers['content-disposition'].startswith('attachment;'))
        self.assertEqual(download.headers['x-content-type-options'], 'nosniff')
        with (self.service.store.assets / asset['assetId']).open('ab') as stream:
            stream.write(b'\x00')
        response = self.post('/references/content', body, headers)
        self.assertEqual(response.status_code, 413)
        self.assertIn('100 MB', response.text)

    def test_original_export_reads_once_and_still_rejects_same_size_corruption(self):
        data = b'Private original fixture'
        asset = self.upload(self.owner, data).json()
        capture = self.post('/captures', {'kind': 'file', 'assetIds': [asset['assetId']],
                                         'provenance': {'channel': 'web'}}).json()
        headers, _, _ = self.selected(capture_ids=[capture['captureId']])
        source = {key: capture[key] for key in ('captureId', 'sha256')}
        body = {'source': source, 'assetId': asset['assetId']}
        path = self.service.store.assets / asset['assetId']
        original_read = Path.read_bytes
        reads = []
        def counted_read(target):
            if target == path:
                reads.append(target)
            return original_read(target)
        with patch.object(Path, 'read_bytes', counted_read):
            response = self.post('/references/content', body, headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, data)
        self.assertEqual(len(reads), 1)
        path.write_bytes(b'X' + data[1:])
        self.assertEqual(self.post('/references/content', body, headers).status_code, 409)
        self.assertEqual(self.post('/references/context', {'sources': [source]}, headers).status_code, 409)

    def test_selected_note_and_capture_with_real_asset_bytes(self):
        data = b"%PDF-1.7\nSelected fixture PDF\n"
        asset = self.upload(self.owner, data, media="application/pdf").json()
        capture = self.post(
            "/captures",
            {
                "kind": "file",
                "text": "Selected PDF",
                "assetIds": [asset["assetId"]],
                "provenance": {"channel": "web"},
            },
        ).json()
        headers, _, _ = self.selected(capture_ids=[capture["captureId"]])
        source = {key: capture[key] for key in ("captureId", "sha256")}
        response = self.post(
            "/references/context",
            {
                "parent": self.parent(),
                "sources": [source],
            },
            headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        value = response.json()
        self.assertEqual(value["parent"]["content"], self.note["content"])
        self.assertIsNone(value["parent"]["researchId"])
        self.assertEqual(value["sources"][0]["text"], "Selected PDF")
        self.assertEqual(
            value["sources"][0]["provenance"],
            {"channel": "web", "description": None, "capturedAt": None},
        )
        self.assertEqual(
            value["sources"][0]["assets"][0]["sha256"],
            hashlib.sha256(data).hexdigest(),
        )
        self.assertEqual(value["sources"][0]["assets"][0]["size"], len(data))
        self.assertEqual(response.headers["cache-control"], "no-store")
        download = self.post(
            "/references/content",
            {
                "source": source,
                "assetId": asset["assetId"],
            },
            headers,
        )
        self.assertEqual(download.status_code, 200, download.text)
        self.assertEqual(download.content, data)
        self.assertEqual(download.headers["content-type"], "application/pdf")
        self.assertEqual(
            download.headers["content-disposition"],
            f'attachment; filename="{asset["assetId"]}.pdf"',
        )
        self.assertEqual(download.headers["cache-control"], "no-store")
        self.assertEqual(download.headers["x-content-type-options"], "nosniff")
        self.assertEqual(self.get("/index", headers).status_code, 403)
        self.assertEqual(
            self.get("/notes/" + self.note["noteId"], headers).status_code, 403
        )
        self.assertEqual(
            self.get(
                "/assets/" + asset["assetId"] + "/content", headers
            ).status_code,
            403,
        )

    def test_owner_root_jobless_and_unscoped_tokens_cannot_read_context(self):
        selected, _, root = self.selected()
        job_root, _ = self.cap(["references:read"], jobId="lr-" + "b" * 32)
        jobless = self.post(
            "/capabilities/delegate",
            {
                "clientId": "test-client",
                "scopes": ["references:read"],
                "noteIds": [self.note["noteId"]],
                "expiresIn": 60,
            },
            root,
        ).json()
        unscoped, _ = self.cap(["notes:read"])
        body = {"parent": self.parent()}
        for headers in (
            self.owner,
            root,
            job_root,
            unscoped,
            {"Authorization": "Bearer " + jobless["token"]},
        ):
            self.assertEqual(
                self.post("/references/context", body, headers).status_code,
                403,
            )
        self.assertEqual(
            self.post(
                "/references/context",
                body,
                {"Authorization": "Bearer invalid"},
            ).status_code,
            401,
        )
        self.assertEqual(
            self.post("/references/context", body, selected).status_code, 200
        )

    def test_explicit_selection_does_not_inherit_job_peer_notes(self):
        job = "lr-" + "c" * 32
        creator, _ = self.cap(
            ["notes:create", "captures:create"], note_ids=[], jobId=job
        )
        response = self.post(
            "/notes",
            {
                "title": "Same-job private fixture",
                "content": '<html><head><meta name="lamanotes-research-id" content="'
                + job
                + '"></head><body><p>Private same-job text</p><p>#research #r-fixture</p></body></html>',
            },
            creator,
        )
        self.assertEqual(response.status_code, 201, response.text)
        created = response.json()
        capture = self.post(
            "/captures",
            {
                "kind": "text",
                "text": "Unselected same-job capture",
                "provenance": {"channel": "codex"},
            },
            creator,
        ).json()
        headers, _, _ = self.selected(note_ids=[], job=job)
        result = self.post(
            "/references/context", {"parent": self.parent(created)}, headers
        )
        self.assertEqual(result.status_code, 404, result.text)
        result = self.post(
            "/references/context",
            {
                "sources": [
                    {key: capture[key] for key in ("captureId", "sha256")}
                ],
            },
            headers,
        )
        self.assertEqual(result.status_code, 404, result.text)
        self.assertNotIn("Private same-job", result.text)

    def test_version_and_capture_hash_conflicts_return_no_content(self):
        capture = self.post(
            "/captures",
            {
                "kind": "text",
                "text": "Selected text",
                "provenance": {"channel": "web"},
            },
        ).json()
        headers, _, _ = self.selected(capture_ids=[capture["captureId"]])
        self.notes.update(
            self.note["title"], NoteUpdate(new_content="<p>Updated note</p>")
        )
        response = self.post(
            "/references/context", {"parent": self.parent()}, headers
        )
        self.assertEqual(response.status_code, 409, response.text)
        response = self.post(
            "/references/context",
            {
                "sources": [
                    {"captureId": capture["captureId"], "sha256": "0" * 64}
                ],
            },
            headers,
        )
        self.assertEqual(response.status_code, 409, response.text)
        self.assertNotIn("Selected text", response.text)

    def test_asset_must_be_attached_to_exact_selected_reference(self):
        selected_asset = self.upload(self.owner).json()
        other_asset = self.upload(
            self.owner, b"Other private fixture", key="other-asset-0001"
        ).json()
        capture = self.post(
            "/captures",
            {
                "kind": "file",
                "text": "Selected file",
                "assetIds": [selected_asset["assetId"]],
                "provenance": {"channel": "web"},
            },
        ).json()
        headers, _, _ = self.selected(capture_ids=[capture["captureId"]])
        source = {key: capture[key] for key in ("captureId", "sha256")}
        for body in (
            {"source": source, "assetId": other_asset["assetId"]},
            {"parent": self.parent(), "assetId": selected_asset["assetId"]},
        ):
            self.assertEqual(
                self.post("/references/content", body, headers).status_code,
                404,
            )
        path = self.service.store.assets / selected_asset["assetId"]
        path.write_bytes(b"Changed private fixture")
        response = self.post(
            "/references/context", {"sources": [source]}, headers
        )
        self.assertEqual(response.status_code, 409, response.text)
        response = self.post(
            "/references/content",
            {"source": source, "assetId": selected_asset["assetId"]},
            headers,
        )
        self.assertEqual(response.status_code, 409, response.text)
        self.assertNotIn("Changed private", response.text)

    def test_selected_note_attachment_and_enrollment_revocation(self):
        asset = self.upload(self.owner).json()
        note = self.post(
            "/notes",
            {
                "title": "Selected multimedia note",
                "content": "<p>Selected attachment</p>",
                "assetIds": [asset["assetId"]],
            },
        ).json()
        headers, _, _ = self.selected(note_ids=[note["noteId"]])
        parent = self.parent(note)
        response = self.post(
            "/references/context", {"parent": parent}, headers
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json()["parent"]["assets"][0]["assetId"], asset["assetId"]
        )
        body = {"parent": parent, "assetId": asset["assetId"]}
        self.assertEqual(
            self.post("/references/content", body, headers).content,
            b"private source",
        )
        self.client.delete(
            self.prefix + "/grants/" + note["noteId"], headers=self.owner
        )
        self.assertEqual(
            self.post(
                "/references/context", {"parent": parent}, headers
            ).status_code,
            404,
        )
        self.assertEqual(
            self.post("/references/content", body, headers).status_code, 404
        )

    def test_codex_result_keeps_canonical_origin_and_actual_asset_hash(self):
        job = "lr-" + "d" * 32
        creator, _ = self.cap(
            ["notes:create", "assets:create"], note_ids=[], jobId=job
        )
        verifier, _ = self.cap(["references:read"], note_ids=[], jobId=job)
        asset = self.upload(creator).json()
        content = (
            '<html><head><meta name="lamanotes-research-id" content="'
            + job
            + '">'
            '<meta name="lamanotes-research-origin" content="codex">'
            "</head><body><p>Codex result</p><p>#research #r-fixture</p></body></html>"
        )
        response = self.post(
            "/notes",
            {
                "title": "Canonical native result",
                "content": content,
                "assetIds": [asset["assetId"]],
            },
            creator,
        )
        self.assertEqual(response.status_code, 201, response.text)
        note = response.json()
        response = self.post("/references/result", self.parent(note), verifier)
        self.assertEqual(response.status_code, 200, response.text)
        value = response.json()
        self.assertEqual(value["researchOrigin"], "codex")
        self.assertEqual(
            value["url"], "https://notes.thuber.org/n/" + note["noteId"]
        )
        self.assertEqual(
            value["htmlSha256"],
            hashlib.sha256(note["content"].encode()).hexdigest(),
        )
        self.assertEqual(
            value["assetManifest"][0]["sha256"],
            hashlib.sha256(b"private source").hexdigest(),
        )
        (self.service.store.assets / asset["assetId"]).write_bytes(
            b"Corrupted fixture"
        )
        self.assertEqual(
            self.post(
                "/references/result", self.parent(note), verifier
            ).status_code,
            409,
        )

    def test_context_and_asset_bounds_do_not_silently_truncate(self):
        headers, _, _ = self.selected()
        with patch("private_api.references.MAX_CONTEXT_BYTES", 1):
            response = self.post(
                "/references/context", {"parent": self.parent()}, headers
            )
        self.assertEqual(response.status_code, 413, response.text)
        asset = self.upload(self.owner).json()
        capture = self.post(
            "/captures",
            {
                "kind": "file",
                "assetIds": [asset["assetId"]],
                "provenance": {"channel": "web"},
            },
        ).json()
        headers, _, _ = self.selected(capture_ids=[capture["captureId"]])
        source = {key: capture[key] for key in ("captureId", "sha256")}
        with patch("private_api.references.MAX_ASSET_BYTES", 1):
            response = self.post(
                "/references/content",
                {"source": source, "assetId": asset["assetId"]},
                headers,
            )
        self.assertEqual(response.status_code, 413, response.text)

    def test_revocation_expiry_and_source_shape_are_enforced(self):
        headers, child, root = self.selected()
        body = {"parent": self.parent()}
        with patch(
            "private_api.store.time.time", return_value=child["expiresAt"] + 1
        ):
            self.assertEqual(
                self.post("/references/context", body, headers).status_code,
                401,
            )
        response = self.client.delete(
            self.prefix + "/capabilities/" + child["parentId"],
            headers=self.owner,
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(
            self.post("/references/context", body, headers).status_code, 401
        )
        headers, _, _ = self.selected()
        for body in (
            {},
            {"parent": self.parent(), "sources": [], "allNotes": True},
        ):
            self.assertEqual(
                self.post("/references/context", body, headers).status_code,
                422,
            )
        asset_id = "la-" + "a" * 32
        for body in (
            {"assetId": asset_id},
            {
                "parent": self.parent(),
                "source": {"captureId": "lc-" + "a" * 32, "sha256": "a" * 64},
                "assetId": asset_id,
            },
        ):
            self.assertEqual(
                self.post("/references/content", body, headers).status_code,
                422,
            )
