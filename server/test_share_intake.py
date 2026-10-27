import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import test_private_api
from android_updates import update_router
from notes.models import NoteUpdate


class ShareIntakeTests(unittest.TestCase):
    setUp = test_private_api.PrivateApiTests.setUp
    post = test_private_api.PrivateApiTests.post
    get = test_private_api.PrivateApiTests.get
    cap = test_private_api.PrivateApiTests.cap
    stored_capability = test_private_api.PrivateApiTests.stored_capability
    def test_selected_note_access_is_scoped_and_replay_safe(self):
        headers, grant = self.cap(['notes:read', 'references:read', 'capabilities:delegate'], note_ids=[])
        self.assertEqual(self.get('/notes/' + self.note['noteId'], headers).status_code, 404)
        ticket = self.post('/research-intakes', {'noteId': self.note['noteId'], 'expectedVersion': self.note['version']}).json()['ticket']
        self.assertEqual(self.get('/notes/' + self.note['noteId'], headers).status_code, 404)
        response = self.post('/research-intakes/consume', {'ticket': ticket}, headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['parent']['noteId'], self.note['noteId'])
        self.assertIsNone(response.json()['parent']['researchId'])
        self.assertEqual(response.json()['selectedNote'], {
            key: self.note[key] for key in ('noteId', 'version', 'title')
        })
        self.assertEqual(self.post('/research-intakes/consume', {'ticket': ticket}, headers).status_code, 200)
        self.assertEqual(self.get('/notes/' + self.note['noteId'], headers).status_code, 200)
        other_headers, _ = self.cap(['notes:read', 'references:read', 'capabilities:delegate'], note_ids=[])
        self.assertEqual(self.post('/research-intakes/consume', {'ticket': ticket}, other_headers).status_code, 409)
        self.assertEqual(self.get('/notes/' + self.note['noteId'], other_headers).status_code, 404)
        saved = json.loads(self.stored_capability(grant['capabilityId'])['payload'])
        self.assertEqual(saved['noteIds'], [self.note['noteId']])
        self.assertEqual(set(saved['scopes']), {'notes:read','references:read','capabilities:delegate'})

    def test_changed_note_expired_ticket_and_non_owner_are_rejected(self):
        headers, _ = self.cap(['notes:read', 'references:read', 'capabilities:delegate'], note_ids=[])
        body = {'noteId': self.note['noteId'], 'expectedVersion': self.note['version']}
        self.assertEqual(self.post('/research-intakes', body, headers).status_code, 403)
        self.assertEqual(self.post('/research-intakes', {**body, 'expectedVersion':'0'*64}).status_code, 409)
        ticket = self.post('/research-intakes', body).json()['ticket']
        with self.service.store.connect() as db:
            db.execute('UPDATE research_intakes SET expires_at=0')
        self.assertEqual(self.post('/research-intakes/consume', {'ticket':ticket}, headers).status_code, 410)

    def test_verifier_can_select_for_its_worker_without_gaining_note_read_scope(self):
        reader, _ = self.cap(['notes:read', 'references:read', 'capabilities:delegate'], note_ids=[])
        verifier, grant = self.cap(['references:read','capabilities:delegate'], note_ids=[])
        ticket = self.post('/research-intakes', {'noteId':self.note['noteId'],'expectedVersion':self.note['version']}).json()['ticket']
        result = self.post('/research-intakes/consume', {'ticket':ticket}, verifier)
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(self.get('/notes/'+self.note['noteId'],reader).status_code,200)
        self.assertEqual(self.get('/notes/'+self.note['noteId'],verifier).status_code,403)
        saved = json.loads(self.stored_capability(grant['capabilityId'])['payload'])
        self.assertNotIn('notes:read',saved['scopes'])

    def test_intake_title_uses_the_same_current_note_version(self):
        headers, _ = self.cap(['notes:read', 'references:read', 'capabilities:delegate'], note_ids=[])
        ticket = self.post('/research-intakes', {
            'noteId': self.note['noteId'], 'expectedVersion': self.note['version'],
        }).json()['ticket']
        self.notes.update(self.note['title'], NoteUpdate(
            new_title='Renamed selected fixture', new_content='<p>Updated fixture</p>',
        ))
        stale = self.post('/research-intakes/consume', {'ticket': ticket}, headers)
        self.assertEqual(stale.status_code, 409, stale.text)
        self.assertNotIn('selectedNote', stale.json())
        current = self.service.read_note(None, self.note['noteId'])
        ticket = self.post('/research-intakes', {
            'noteId': current['noteId'], 'expectedVersion': current['version'],
        }).json()['ticket']
        response = self.post('/research-intakes/consume', {'ticket': ticket}, headers)
        self.assertEqual(response.status_code, 200, response.text)
        selected = response.json()['selectedNote']
        self.assertEqual(selected, {key: current[key] for key in ('noteId', 'version', 'title')})
        self.assertEqual(selected['version'], response.json()['parent']['version'])
        self.assertNotEqual(selected['version'], self.note['version'])
        self.assertNotIn('content', response.json())


def test_android_feed_does_not_serve_missing_corrupt_or_path_escaped_packages():
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        app = FastAPI(); app.include_router(update_router(folder)); client = TestClient(app)
        assert client.get('/api/android-client-update').status_code == 404
        apk = root/'LamaDroid-0.2.0.apk'; apk.write_bytes(b'synthetic fixture')
        data = {'schema':1,'package':'org.thuber.lamadroid','versionName':'0.2.0','versionCode':2,
                'downloadPath':'/api/android-client-update/download',
                'file':apk.name,'size':apk.stat().st_size,'sha256':hashlib.sha256(apk.read_bytes()).hexdigest()}
        def manifest():
            (root/'LamaDroid-update.json').write_text(json.dumps({'payload':base64.b64encode(json.dumps(data).encode()).decode(),'signature':'fixture'}))
        manifest()
        assert client.get('/api/android-client-update').status_code == 200
        assert client.get('/api/android-client-update', headers={'host':'notes.thuber.org'}).status_code == 404
        assert client.get('/api/android-client-update/download', headers={'host':'notes.thuber.org'}).status_code == 404
        assert client.get('/api/android-client-update/download').content == apk.read_bytes()
        data['file'] = '../LamaDroid-0.2.0.apk'; manifest()
        assert client.get('/api/android-client-update/download').status_code == 404
        data['file'] = apk.name; data['sha256'] = '0'*64; manifest()
        assert client.get('/api/android-client-update/download').status_code == 404


class AndroidFeedTests(unittest.TestCase):
    def test_guarded_packages(self):
        test_android_feed_does_not_serve_missing_corrupt_or_path_escaped_packages()
