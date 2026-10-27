import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from android_updates import update_router


class AndroidUpdateTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.payloads = {}
        for label, package, version, code, route in (
            ('LamaDroid', 'org.thuber.lamadroid', '0.5.0', 9, '/api/android-client-update'),
            ('LamaShare', 'org.thuber.lamashare', '0.1.0', 1, '/api/android-share-client-update'),
        ):
            content = (label + ' synthetic APK fixture').encode()
            filename = label + '-' + version + '.apk'
            (self.root / filename).write_bytes(content)
            self.payloads[label] = dict(schema=1, package=package, versionName=version,
                versionCode=code, downloadPath=route+'/download', file=filename,
                size=len(content), sha256=hashlib.sha256(content).hexdigest())
            self.write_manifest(label)
        app = FastAPI()
        app.include_router(update_router(folder.name))
        self.client = TestClient(app)

    def write_manifest(self, label):
        # Signature verification remains with the pinned native updater.
        envelope = {'payload':base64.b64encode(json.dumps(self.payloads[label]).encode()).decode(),
                    'signature':'synthetic-client-signature'}
        (self.root / (label+'-update.json')).write_text(json.dumps(envelope))
        return envelope

    def test_both_private_feeds_and_downloads_stay_independent(self):
        private = {'Host':'racknerd-31fcf0d.tail38b5b3.ts.net:8092'}
        for label, route in (('LamaDroid','/api/android-client-update'), ('LamaShare','/api/android-share-client-update')):
            response = self.client.get(route, headers=private)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), self.write_manifest(label))
            self.assertEqual(response.headers['cache-control'], 'no-store')
            apk = self.client.get(route+'/download', headers=private)
            self.assertEqual(apk.content, (self.root/self.payloads[label]['file']).read_bytes())
            self.assertIn(self.payloads[label]['file'], apk.headers['content-disposition'])
            self.assertEqual(apk.headers['x-content-type-options'], 'nosniff')
        self.assertEqual(self.client.get('/api/android-client-update?product=share').json(), self.write_manifest('LamaDroid'))

    def test_public_hostname_gets_404_for_all_four_routes(self):
        for base in ('/api/android-client-update','/api/android-share-client-update'):
            for suffix in ('','/download'):
                self.assertEqual(self.client.get(base+suffix, headers={'Host':'notes.thuber.org'}).status_code,404)

    def test_share_rejects_wrong_package_download_path_and_droid_filename(self):
        original = dict(self.payloads['LamaShare'])
        for changed in ({'package':'org.thuber.lamadroid'},
                        {'downloadPath':'/api/android-client-update/download'},
                        {'downloadPath':'https://other.example/app.apk'},
                        {'file':'LamaDroid-0.5.0.apk'},
                        {'file':'../LamaShare-0.1.0.apk'}):
            self.payloads['LamaShare'] = {**original,**changed}
            self.write_manifest('LamaShare')
            self.assertEqual(self.client.get('/api/android-share-client-update').status_code,404)
            self.assertEqual(self.client.get('/api/android-share-client-update/download').status_code,404)
            self.assertEqual(self.client.get('/api/android-client-update').status_code,200)

    def test_corrupt_or_missing_share_apk_does_not_affect_droid(self):
        path = self.root/self.payloads['LamaShare']['file']
        path.write_bytes(b'corrupted fixture')
        self.assertEqual(self.client.get('/api/android-share-client-update/download').status_code,404)
        path.unlink()
        self.assertEqual(self.client.get('/api/android-share-client-update').status_code,404)
        self.assertEqual(self.client.get('/api/android-client-update').status_code,200)

    def test_share_manifest_cannot_increase_the_apk_size_bound(self):
        self.payloads['LamaShare']['size'] = 33 * 1024 * 1024
        self.write_manifest('LamaShare')
        self.assertEqual(self.client.get('/api/android-share-client-update').status_code,404)


if __name__ == '__main__':
    unittest.main()
