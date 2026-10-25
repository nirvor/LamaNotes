import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from android_updates import update_router


class AndroidCatalogTests(unittest.TestCase):
    def test_private_catalogue_and_content_addressed_artwork(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'lamaui'
            (root / 'assets').mkdir(parents=True)
            image = b'RIFF0000WEBP' + b'synthetic test image'
            digest = hashlib.sha256(image).hexdigest()
            art = {'sha256': digest, 'size': len(image)}
            payload = {'schema': 1, 'kind': 'lamaui-catalog', 'revision': 1,
                       'apps': [{'artwork': art, 'launcher': {'artwork': art}}]}
            envelope = {'payload': base64.b64encode(json.dumps(payload).encode()).decode(), 'signature': 'verified-by-client'}
            (root / 'current.json').write_text(json.dumps(envelope))
            (root / 'assets' / (digest + '.webp')).write_bytes(image)
            app = FastAPI()
            app.include_router(update_router(temporary))
            with TestClient(app) as client:
                assert client.get('/api/android-client-catalog').json() == envelope
                url = '/api/android-client-catalog/assets/' + digest + '.webp'
                assert client.get(url).content == image
                assert client.get('/api/android-client-catalog', headers={'host': 'notes.thuber.org'}).status_code == 404
                assert client.get(url, headers={'host': 'notes.thuber.org'}).status_code == 404
                assert client.get('/api/android-client-catalog/assets/' + 'a'*64 + '.webp').status_code == 404
                (root / 'assets' / (digest + '.webp')).write_bytes(b'corrupted image')
                assert client.get(url).status_code == 404
                (root / 'current.json').write_text('{}')
                assert client.get('/api/android-client-catalog').status_code == 404
