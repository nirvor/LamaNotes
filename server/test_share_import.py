import hashlib
import json
import logging
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from auth.models import AuthPrincipal
from auth.scopes import NOTES_WRITE
from notes.file_system.file_system import FileSystemNotes
from private_api.middleware import PrivateRequestLimit
from private_api.service import PrivateService
from share_import import create_router


class OwnerAuth:
    def authenticate(self, request, token):
        if token == "owner-fixture":
            return AuthPrincipal("owner", "session", frozenset({NOTES_WRITE}))
        if token:
            return AuthPrincipal("service", "api-token", frozenset({NOTES_WRITE}))
        raise HTTPException(401, "Login required.")


class ShareImportTests(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        with patch.dict(os.environ, {"LAMANOTES_PATH": temp.name}):
            self.service = PrivateService(FileSystemNotes())
        self.data = b"<script>inert original</script>\n"
        now = datetime.now(timezone.utc)
        self.item = {"id": "i" * 32, "title": 'Shared: original title',
            "text": '<script>never execute</script>\nSecond line',
            "url": 'https://example.org/source?x=1&y=2', "annotation": 'Keep <raw> annotation',
            "source": {"platform": "android", "package": "example.unverified", "receivedAt": now.isoformat()},
            "files": [{"id": "f" * 32, "name": "original.html.txt", "mime": "text/plain",
                       "size": len(self.data), "sha256": hashlib.sha256(self.data).hexdigest(), "uploaded": True}],
            "ready": True, "createdAt": now.isoformat()}
        self.export = {"item": self.item, "fileToken": "lse_" + "s" * 43,
                       "expiresAt": (now + timedelta(minutes=9)).isoformat()}
        self.calls = []
        self.redirect = False

        def handler(request):
            self.calls.append(request)
            self.assertEqual(str(request.url).split('/api/')[0], "http://nirvstart:8080")
            self.assertNotIn("cookie", request.headers)
            if request.method == 'POST':
                self.assertEqual(request.url.path, '/api/share/v1/notes-export')
                self.assertNotIn('authorization', request.headers)
                if self.redirect:
                    return httpx.Response(302, headers={"location": "https://other.example/secret"}, stream=httpx.ByteStream(b''))
                data = json.dumps(self.export).encode()
                return httpx.Response(200, headers={"content-type": "application/json"}, stream=httpx.ByteStream(data))
            self.assertEqual(request.url.path, '/api/share/v1/notes-export/files/' + 'f' * 32)
            self.assertEqual(request.headers['authorization'], 'Bearer ' + self.export['fileToken'])
            return httpx.Response(200, headers={"content-type": "text/plain; charset=utf-8"}, stream=httpx.ByteStream(self.data))

        app = FastAPI()
        app.add_middleware(PrivateRequestLimit)
        app.include_router(create_router(self.service, OwnerAuth(), transport=httpx.MockTransport(handler)))
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer owner-fixture", "Origin": "https://notes.thuber.org", "X-LamaNotes-Share": "1"}

    def post(self, headers=None, ticket=None):
        return self.client.post('/api/private/v1/share-import', headers=headers or self.headers,
                                json={"ticket": ticket or "lst_" + "t" * 43})

    def test_owner_import_is_passive_preserves_originals_and_replays_across_new_tickets(self):
        response = self.post()
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(response.headers['cache-control'], 'no-store')
        note = self.service.read_note(None, result['noteId'])
        self.assertIn('&lt;script&gt;never execute&lt;/script&gt;', note['content'])
        self.assertNotIn('<script>', note['content'])
        self.assertEqual(self.service.notes.get_context(note['title']).tags, ['shared'])
        capture = self.service.store.objects('capture')[0]['payload']
        self.assertEqual(capture['share'], self.item)
        asset = self.service.store.objects('asset')[0]
        self.assertEqual((self.service.store.assets / asset['id']).read_bytes(), self.data)
        self.assertEqual(self.post(ticket='lst_' + 'n'*43).json(), result)
        self.assertEqual(len(self.service.store.objects('note')), 1)
        self.assertEqual(len(self.service.store.objects('capture')), 1)
        self.assertEqual(len(self.service.store.objects('asset')), 1)
        self.assertEqual(len([r for r in self.calls if r.method == 'GET']), 1)

    def test_owner_session_and_same_origin_csrf_are_required_before_any_export_call(self):
        for headers, status in [({'Origin':'https://notes.thuber.org','X-LamaNotes-Share':'1'},401),
                ({**self.headers,'Authorization':'Bearer lms_'+'x'*43},403),
                ({**self.headers,'Authorization':'Bearer lmp_'+'x'*43},403),
                ({**self.headers,'Origin':'https://other.example'},403),
                ({k:v for k,v in self.headers.items() if k!='X-LamaNotes-Share'},403)]:
            self.assertEqual(self.post(headers).status_code, status)
        self.assertEqual(self.calls, [])

    def test_hash_mismatch_and_redirect_never_create_a_note(self):
        self.item['files'][0]['sha256'] = '0'*64
        self.assertEqual(self.post().status_code, 422)
        self.assertEqual(self.service.store.objects(), [])
        self.redirect = True
        self.assertEqual(self.post().status_code, 502)
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(self.service.store.objects(), [])

    def test_oversize_and_unsafe_file_ids_are_rejected_before_file_fetch(self):
        self.item['files'][0]['id'] = '../outside'
        self.assertEqual(self.post().status_code, 422)
        self.item['files'][0]['id'] = 'f'*32
        self.item['files'][0]['size'] = 21 * 1024 * 1024
        self.assertEqual(self.post().status_code, 422)
        self.assertTrue(all(request.method == 'POST' for request in self.calls))
        self.assertEqual(self.service.store.objects(), [])

    def test_expired_export_and_changed_item_identity_are_not_replayed_silently(self):
        saved = self.post().json()
        self.item['annotation'] = 'Unexpected changed input'
        self.assertEqual(self.post().status_code, 409)
        self.export['expiresAt'] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        self.assertEqual(self.post().status_code, 422)
        self.assertEqual(len(self.service.store.objects('note')), 1)
        self.assertEqual(self.service.read_note(None, saved['noteId'])['noteId'], saved['noteId'])

    def test_original_empty_text_file_is_kept(self):
        self.data = b''
        self.item['files'][0].update(size=0, sha256=hashlib.sha256(b'').hexdigest())
        response = self.post()
        self.assertEqual(response.status_code, 200, response.text)
        asset = self.service.store.objects('asset')[0]
        self.assertEqual((self.service.store.assets / asset['id']).read_bytes(), b'')

    def test_invalid_ticket_has_a_plain_error_without_reflecting_the_secret(self):
        response = self.post(ticket='lst_private-invalid-fixture')
        self.assertEqual(response.status_code, 422)
        self.assertIsInstance(response.json()['detail'], str)
        self.assertNotIn('lst_private-invalid-fixture', response.text)
        self.assertEqual(self.calls, [])


if __name__ == '__main__':
    unittest.main()
