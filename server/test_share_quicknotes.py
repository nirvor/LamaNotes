import copy
import base64
import hashlib
import json
import logging
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI
from fastapi.testclient import TestClient

from notes.errors import NoteConflictError
from notes.file_system.file_system import FileSystemNotes
from notes.models import NoteCreate, NoteUpdate
from private_api.middleware import PrivateRequestLimit
from private_api.models import CapabilityCreate, Enroll
from private_api.service import PrivateService
from quicknotes import Quicknotes, QuicknoteEntry
from share_quicknotes import MARKER, RECEIPT, create_router
from test_quicknotes import IDENTITY, LEGACY, TEXT_MODE

PNG = bytes.fromhex('89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489'
                    '0000000b49444154789c636000020000050001a5f645400000000049454e44ae426082')


class ShareQuicknotesTests(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        with patch.dict(os.environ, {'LAMANOTES_PATH': str(self.root)}):
            self.notes = FileSystemNotes()
        self.service = PrivateService(self.notes)
        note = self.notes.create(NoteCreate(title='Quicknotes', content=TEXT_MODE))
        self.service.enroll(Enroll(title=note.title, expected_version=note.version, personal=True))
        self.binding = self.service.store.root / 'focus-quicknotes.json'
        self.binding.write_text(json.dumps({'noteId': IDENTITY, 'capabilityId': 'lg-' + 'b' * 32}))
        now = datetime.now(timezone.utc)
        self.data = PNG
        self.item = {'id': 'i' * 32, 'title': 'A shared photo',
            'text': '<script>literal</script>\n#not-a-tag\n*not bold*',
            'url': 'https://example.org/a(b)?x=1&y=2', 'annotation': 'Keep this annotation.',
            'source': {'platform': 'android', 'package': 'example.camera', 'receivedAt': now.isoformat()},
            'createdAt': now.isoformat(), 'ready': True,
            'files': [{'id': 'f' * 32, 'name': 'PXL_[original].png', 'mime': 'image/png',
                'size': len(self.data), 'sha256': hashlib.sha256(self.data).hexdigest(), 'uploaded': True}]}
        self.export = {'intent': 'quicknotes.append', 'operationId': str(uuid4()), 'item': self.item,
            'fileToken': 'lse_' + 's' * 43, 'expiresAt': (now + timedelta(minutes=9)).isoformat()}
        self.calls = []
        self.file_failure = False
        self.redirect = False
        self.client = self.make_client()

    def handler(self, request):
        self.calls.append(request)
        self.assertEqual(str(request.url).split('/api/')[0], 'http://nirvstart:8080')
        self.assertNotIn('cookie', request.headers)
        if request.method == 'POST':
            self.assertEqual(request.url.path, '/api/share/v1/quicknotes-export')
            self.assertNotIn('authorization', request.headers)
            if self.redirect:
                return httpx.Response(302, headers={'location': 'https://outside.invalid/'}, stream=httpx.ByteStream(b''))
            return httpx.Response(200, headers={'content-type': 'application/json'},
                                  stream=httpx.ByteStream(json.dumps(self.export).encode()))
        self.assertEqual(request.url.path, '/api/share/v1/notes-export/files/' + 'f' * 32)
        self.assertEqual(request.headers['authorization'], 'Bearer ' + self.export['fileToken'])
        return httpx.Response(503 if self.file_failure else 200,
            headers={'content-type': self.item['files'][0]['mime']}, stream=httpx.ByteStream(self.data))

    def make_client(self, enabled=True, host='http://lamanotes:8080'):
        app = FastAPI()
        app.add_middleware(PrivateRequestLimit)
        app.include_router(create_router(self.service, enabled, transport=httpx.MockTransport(self.handler)))
        return TestClient(app, base_url=host)

    def post(self, client=None, **kwargs):
        kwargs.setdefault('json', {'ticket': 'lsq_' + 't' * 43})
        return (client or self.client).post('/api/share-intake/v1/quicknotes', **kwargs)

    def source(self):
        return self.notes.get('Quicknotes').content

    def test_photo_appends_both_sources_keeps_originals_and_does_not_create_a_library_note(self):
        before = self.source()
        capability = self.service.store.create_capability(None, CapabilityCreate(client_id='focus-quicknotes',
            scopes=['notes:read'], note_ids=[IDENTITY]))
        grants = self.service.store.list_capabilities()
        result = self.post()
        self.assertEqual(result.status_code, 200, result.text)
        saved = result.json()
        self.assertEqual(set(saved), {'operationId','itemId','appendId','version','assetCount','duplicate','saved','noteId','openUrl','editUrl'})
        self.assertEqual(saved['appendId'], self.export['operationId'])
        self.assertTrue(saved['saved'])
        self.assertFalse(saved['duplicate'])
        self.assertEqual(saved['assetCount'], 1)
        self.assertEqual(result.headers['cache-control'], 'no-store')
        self.assertNotIn('Previous writing', result.text)
        doc = BeautifulSoup(self.source(), 'html.parser')
        source = unescape(doc.select_one('template[data-lamanotes-text-markdown]').decode_contents())
        self.assertTrue(source.startswith('Previous writing.\n\n#private\n\n<span id="quicknote-' + self.export['operationId']))
        self.assertEqual(saved['noteId'], IDENTITY)
        self.assertEqual(saved['openUrl'], 'https://notes.thuber.org/n/' + IDENTITY + '?entry=' + self.export['operationId'])
        self.assertEqual(saved['editUrl'], saved['openUrl'] + '&edit=1')
        self.assertIn(r'\#not\-a\-tag', source)
        self.assertIn('![PXL', source)
        self.assertIn('a%28b%29?x=1&y=2', source)
        self.assertTrue(doc.select_one('hr.lamanote-share-separator'))
        self.assertFalse(doc.select('script'))
        self.assertEqual(doc.select_one('.lamanote-text-body a')['href'], 'https://example.org/a%28b%29?x=1&y=2')
        asset = self.service.store.objects('asset')[0]
        self.assertEqual((self.service.store.assets / asset['id']).read_bytes(), PNG)
        note = self.service.store.object(IDENTITY)
        self.assertEqual(note['payload']['assetIds'], [asset['id']])
        capture = self.service.store.objects('capture')[0]
        self.assertEqual(capture['payload']['share'], self.item)
        self.assertEqual(note['payload']['captureIds'], [capture['id']])
        self.assertEqual(len(self.service.store.objects('note')), 1)
        self.assertEqual(len(list(self.root.glob('*.html'))), 1)
        self.assertEqual(self.service.store.list_capabilities(), grants)
        self.assertEqual(self.service.store.authenticate(capability['token'])['scopes'], ['notes:read'])
        self.assertEqual(doc.select_one('meta[name="lamanotes-tags"]')['content'], 'pinned,private')
        self.assertIn('keep me', self.source())
        self.assertIn('Previous writing.', before)

    def test_retries_new_ticket_and_owner_edits_return_receipt_without_reappending(self):
        first = self.post().json()
        current = self.notes.get('Quicknotes')
        edited = current.content.replace('Previous writing.', 'Owner edited this.')
        self.notes.update(current.title, NoteUpdate(new_content=edited, expected_version=current.version))
        self.export['fileToken'] = 'lse_' + 'n' * 43
        response = self.post(json={'ticket': 'lsq_' + 'n' * 43})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {**first, 'duplicate': True})
        self.assertEqual(self.source(), edited)
        self.assertEqual(sum(call.method == 'GET' for call in self.calls), 1)
        self.item['annotation'] = 'Changed input under the same operation'
        self.assertEqual(self.post().status_code, 409)
        self.assertEqual(self.source(), edited)

    def test_existing_media_and_capture_associations_are_preserved(self):
        old = self.service.create_asset(None, b'Original prior attachment', 'text/plain', 'source', None, None, 'prior-file')
        obj = self.service.store.object(IDENTITY)
        self.service.store.update_payload(IDENTITY, {**obj['payload'], 'assetIds':[old['assetId']],
            'captureIds':['lc-'+'e'*32], 'keep':'existing metadata'})
        response = self.post()
        self.assertEqual(response.status_code, 200, response.text)
        current = self.service.store.object(IDENTITY)['payload']
        self.assertIn(old['assetId'], current['assetIds'])
        self.assertEqual(len(current['assetIds']), 2)
        self.assertIn('lc-'+'e'*32, current['captureIds'])
        self.assertEqual(current['keep'], 'existing metadata')
        self.assertEqual((self.service.store.assets / old['assetId']).read_bytes(), b'Original prior attachment')

    def test_interruption_after_file_commit_recovers_metadata_and_receipt_once(self):
        from share_quicknotes import remember
        def interrupt(db, operation, key, digest, value):
            if operation == RECEIPT:
                raise OSError('synthetic receipt interruption')
            return remember(db, operation, key, digest, value)
        with patch('share_quicknotes.remember', side_effect=interrupt), self.assertRaises(OSError):
            self.post()
        once = self.source()
        self.assertTrue(BeautifulSoup(once, 'html.parser').select_one('meta[name="' + MARKER + '"]'))
        self.assertEqual(self.service.store.object(IDENTITY)['payload']['assetIds'], [])
        replay = self.post()
        self.assertEqual(replay.status_code, 200, replay.text)
        self.assertTrue(replay.json()['duplicate'])
        self.assertEqual(self.source(), once)
        self.assertEqual(len(self.service.store.object(IDENTITY)['payload']['assetIds']), 1)

    def test_parallel_identical_and_distinct_operations_preserve_every_entry(self):
        # Distinct operation IDs are carried by item-scoped export responses.
        exports = {}
        for index in range(4):
            value = copy.deepcopy(self.export)
            value['operationId'] = str(uuid4())
            value['item']['text'] = 'Concurrent writing ' + str(index)
            exports['lsq_' + str(index) * 43] = value
        original = self.handler
        def dispatch(request):
            if request.method == 'POST':
                value = exports[json.loads(request.content)['ticket']]
                return httpx.Response(200, headers={'content-type':'application/json'},
                                      stream=httpx.ByteStream(json.dumps(value).encode()))
            return original(request)
        app = FastAPI()
        app.include_router(create_router(self.service, transport=httpx.MockTransport(dispatch)))
        with TestClient(app, base_url='http://lamanotes:8080') as client, ThreadPoolExecutor(max_workers=8) as pool:
            tickets = list(exports) * 2
            responses = list(pool.map(lambda ticket: self.post(client, json={'ticket':ticket}), tickets))
        self.assertTrue(all(response.status_code == 200 for response in responses))
        self.assertEqual(sum(not response.json()['duplicate'] for response in responses), 4)
        doc = BeautifulSoup(self.source(), 'html.parser')
        self.assertEqual(len(doc.select('meta[name="' + MARKER + '"]')), 4)
        self.assertEqual(len(doc.select('hr.lamanote-share-separator')), 4)
        self.assertEqual(len(self.service.store.object(IDENTITY)['payload']['assetIds']), 4)

    def test_stale_editor_cannot_overwrite_append_and_cas_conflict_can_retry(self):
        stale = self.notes.get('Quicknotes')
        with patch.object(self.notes, 'update', side_effect=NoteConflictError('synthetic race')):
            response = self.post()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.source(), stale.content)
        self.assertEqual(self.post().status_code, 200)
        with self.assertRaises(NoteConflictError):
            self.notes.update('Quicknotes', NoteUpdate(new_content=stale.content, expected_version=stale.version))

    def test_binding_change_during_file_retry_cannot_redirect_action(self):
        self.file_failure = True
        self.assertEqual(self.post().status_code, 502)
        other_id = 'ln-' + 'e' * 32
        other = self.notes.create(NoteCreate(title='Other scratch', content=TEXT_MODE.replace(IDENTITY, other_id)))
        self.service.enroll(Enroll(title=other.title, expected_version=other.version, personal=True))
        self.binding.write_text(json.dumps({'noteId': other_id}))
        self.file_failure = False
        self.assertEqual(self.post().status_code, 409)
        self.assertEqual(self.source(), TEXT_MODE)
        self.assertEqual(self.notes.get(other.title).content, other.content)

    def test_legacy_note_stays_writable_after_share_and_preserves_its_original_bytes(self):
        current = self.notes.get('Quicknotes')
        self.notes.update(current.title, NoteUpdate(new_content=LEGACY, expected_version=current.version))
        self.assertEqual(self.post().status_code, 200)
        doc = BeautifulSoup(self.source(), 'html.parser')
        section = doc.select_one('section[data-lamanotes-share-entry]')
        self.assertTrue(section.select_one('template[data-lamanotes-share-markdown]'))
        source = self.source()
        start = source.index('<section data-lamanotes-share-entry=')
        end = source.index('</section>', start) + len('</section>')
        stripped = source[:start] + source[end:]
        import re
        stripped = re.sub(r'<meta name="lamanotes-share-quicknote"[^>]*>', '', stripped)
        self.assertEqual(stripped, LEGACY)
        entry = QuicknoteEntry(noteId=IDENTITY, entryId=str(uuid4()), text='Another quick thought',
                               capturedAt=self.item['createdAt'])
        self.assertFalse(Quicknotes(self.notes, self.service).append(entry)['duplicate'])
        self.assertIn('Another quick thought', self.source())

    def test_invalid_authority_never_fetches_a_share_export(self):
        for ticket in ('lst_' + 'a'*43, 'lse_' + 'a'*43, 'lsq_private-invalid'):
            result = self.post(json={'ticket':ticket})
            self.assertEqual(result.status_code, 422)
            self.assertNotIn(ticket, result.text)
        for headers in ({'Origin':'https://notes.thuber.org'}, {'Cookie':'owner=unused'}, {'Authorization':'Bearer owner'}):
            self.assertEqual(self.post(headers=headers).status_code, 404)
        self.assertEqual(self.post(self.make_client(host='https://notes.thuber.org')).status_code, 404)
        self.assertEqual(self.post(self.make_client(enabled=False)).status_code, 403)
        self.assertEqual(self.post(json={'ticket':'lsq_'+'a'*43, 'noteId':IDENTITY}).status_code, 422)
        self.assertEqual(self.calls, [])

    def test_wrong_intent_expiry_hash_and_redirect_never_append(self):
        before = self.source()
        self.export['intent'] = 'library.import'
        self.assertEqual(self.post().status_code, 422)
        self.export['intent'] = 'quicknotes.append'
        expiry = self.export['expiresAt']
        self.export['expiresAt'] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        self.assertEqual(self.post().status_code, 422)
        self.export['expiresAt'] = expiry
        self.item['files'][0]['sha256'] = '0' * 64
        self.assertEqual(self.post().status_code, 422)
        self.redirect = True
        self.assertEqual(self.post().status_code, 502)
        self.assertEqual(self.source(), before)
        self.assertEqual(self.service.store.objects('asset'), [])

    def test_missing_binding_never_creates_or_selects_a_replacement(self):
        self.binding.unlink()
        before = self.source()
        self.assertEqual(self.post().status_code, 409)
        self.assertEqual(self.source(), before)
        self.assertEqual(len(list(self.root.glob('*.html'))), 1)

    def test_code_file_is_editable_as_inert_fenced_text_and_original_stays_exact(self):
        self.data = b'print("hello")\r\n```\r\n<script>never run</script>\r\n'
        self.item['files'][0].update(name='example.py', mime='text/plain', size=len(self.data), sha256=hashlib.sha256(self.data).hexdigest())
        response = self.post()
        self.assertEqual(response.status_code, 200, response.text)
        doc = BeautifulSoup(self.source(), 'html.parser')
        source = unescape(doc.select_one('template[data-lamanotes-text-markdown]').decode_contents())
        self.assertIn('````python\nprint("hello")\n```\n<script>never run</script>\n\n````', source)
        self.assertEqual(doc.select_one('pre > code').get_text(), self.data.decode().replace('\r\n','\n'))
        self.assertFalse(doc.select('script'))
        asset = self.service.store.objects('asset')[0]
        self.assertEqual((self.service.store.assets / asset['id']).read_bytes(), self.data)

    def test_video_originals_are_private_file_links_and_gif_keeps_its_image_path(self):
        fixtures = [('video/mp4','clip.mp4',b'\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isommp42'),
                    ('video/webm','clip.webm',b'\x1a\x45\xdf\xa3\x8b\x42\x82\x84webm\x18\x53\x80\x67'),
                    ('image/gif','motion.gif',base64.b64decode('R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=='))]
        for mime,name,data in fixtures:
            with self.subTest(mime=mime):
                self.export['operationId'] = str(uuid4())
                self.data = data
                self.item['files'][0].update(name=name,mime=mime,size=len(data),sha256=hashlib.sha256(data).hexdigest())
                result = self.post()
                self.assertEqual(result.status_code,200,result.text)
                assets = self.service.store.objects('asset')
                asset = next(asset for asset in assets if asset['payload']['sha256'] == hashlib.sha256(data).hexdigest())
                self.assertEqual((self.service.store.assets/asset['id']).read_bytes(),data)
                doc = BeautifulSoup(self.source(),'html.parser')
                url = '/api/private/v1/assets/' + asset['id'] + '/content'
                self.assertFalse(doc.select('video'))
                self.assertTrue(doc.select_one(('img[src="' if mime=='image/gif' else 'a[href="') + url + '"]'))
        self.assertEqual(len(list(self.root.glob('*.html'))),1)

    def test_text_link_only_and_empty_plain_file_keep_payloads_and_limits(self):
        self.item['files'] = []
        self.assertEqual(self.post().json()['assetCount'], 0)
        self.item['files'] = [{'id':'f'*32, 'name':'empty.txt', 'mime':'text/plain',
                              'size':0, 'sha256':hashlib.sha256(b'').hexdigest(), 'uploaded':True}]
        self.export['operationId'] = str(uuid4())
        self.data = b''
        self.assertEqual(self.post().json()['assetCount'], 1)
        self.assertEqual((self.service.store.assets / self.service.store.objects('asset')[0]['id']).read_bytes(), b'')
        self.assertEqual(self.post(content=b'x'*1025, headers={'Content-Type':'application/json'}).status_code, 413)

    def test_arbitrary_originals_and_invalid_previews_are_saved_exactly_and_replayed(self):
        fixtures = [('archive.bin', 'application/x-custom', b'\x00\xfforiginal'),
                    ('unusual.png', 'image/png', b'\x00\xffunusual image header'),
                    ('invalid.txt', 'text/plain', b'\xff\xfeinvalid utf8'),
                    ('empty.dat', '', b'')]
        for name, mime, data in fixtures:
            with self.subTest(name=name):
                self.export['operationId'] = str(uuid4())
                self.data = data
                self.item['files'][0].update(name=name, mime=mime, size=len(data), sha256=hashlib.sha256(data).hexdigest())
                response = self.post()
                self.assertEqual(response.status_code, 200, response.text)
                asset = next(asset for asset in self.service.store.objects('asset')
                             if asset['payload']['sha256'] == hashlib.sha256(data).hexdigest())
                self.assertEqual((self.service.store.assets / asset['id']).read_bytes(), data)
                doc = BeautifulSoup(self.source(), 'html.parser')
                self.assertTrue(doc.select_one('a[href="/api/private/v1/assets/' + asset['id'] + '/content"]'))
                self.assertFalse(doc.select('img,script'))
                before = self.source()
                self.assertTrue(self.post().json()['duplicate'])
                self.assertEqual(self.source(), before)

    def test_mime_metadata_or_preview_errors_do_not_block_originals(self):
        self.item['files'][0]['mime'] = 'application/octet-stream'
        with patch('private_api.service.FileSystemAttachments._image_dimensions', side_effect=ValueError('preview failed')):
            response = self.post()
        self.assertEqual(response.status_code, 200, response.text)
        asset = self.service.store.objects('asset')[0]
        self.assertEqual((self.service.store.assets / asset['id']).read_bytes(), PNG)
        self.assertFalse(BeautifulSoup(self.source(), 'html.parser').select('img'))

    def test_readable_code_with_generic_mime_is_editable_but_large_text_stays_attached(self):
        for name, data in [('source.py', b'print("hello")\n'), ('large.txt', b'a' * 1_000_000)]:
            with self.subTest(name=name):
                self.export['operationId'] = str(uuid4())
                self.data = data
                self.item['files'][0].update(name=name, mime='application/octet-stream', size=len(data), sha256=hashlib.sha256(data).hexdigest())
                response = self.post()
                self.assertEqual(response.status_code, 200, response.text)
                asset = next(asset for asset in self.service.store.objects('asset')
                             if asset['payload']['sha256'] == hashlib.sha256(data).hexdigest())
                self.assertEqual((self.service.store.assets / asset['id']).read_bytes(), data)
        self.assertIn('print("hello")', self.source())
        self.assertNotIn('a' * 1000, self.source())


if __name__ == '__main__':
    unittest.main()
