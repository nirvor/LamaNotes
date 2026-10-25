import base64
import hashlib
import json
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse


def update_router(directory):
    router = APIRouter()

    def private_root(request):
        if request.url.hostname not in {'racknerd-31fcf0d.tail38b5b3.ts.net', 'testserver', 'localhost', '127.0.0.1'}:
            raise HTTPException(404, 'Android updates use the private Tailscale address.')
        if not directory:
            raise HTTPException(404, "Android updates are unavailable.")
        return Path(directory).resolve()

    def release(request):
        root = private_root(request)
        try:
            envelope = json.loads((root / "LamaDroid-update.json").read_text())
            manifest = json.loads(base64.b64decode(envelope["payload"], validate=True))
            filename = manifest["file"]
            if not re.fullmatch(r"LamaDroid-[0-9]+\.[0-9]+\.[0-9]+\.apk", filename):
                raise ValueError()
            package = root / filename
            if package.is_symlink() or not package.is_file() or package.stat().st_size != manifest["size"]:
                raise ValueError()
            if hashlib.sha256(package.read_bytes()).hexdigest() != manifest["sha256"]:
                raise ValueError()
            return envelope, package
        except (OSError, ValueError, KeyError, TypeError):
            raise HTTPException(404, "No verified Android update is available.") from None

    @router.get("/api/android-client-update", include_in_schema=False)
    def metadata(request: Request):
        envelope, _ = release(request)
        return JSONResponse(envelope, headers={"Cache-Control": "no-store"})

    @router.get("/api/android-client-update/download", include_in_schema=False)
    def download(request: Request):
        _, package = release(request)
        return FileResponse(package, filename=package.name,
                            media_type="application/vnd.android.package-archive",
                            headers={"Cache-Control": "no-store"})

    def catalogue(request):
        root = private_root(request) / 'lamaui'
        try:
            source = root / 'current.json'
            if source.is_symlink() or source.stat().st_size > 65536:
                raise ValueError()
            envelope = json.loads(source.read_text())
            raw = base64.b64decode(envelope['payload'], validate=True)
            data = json.loads(raw)
            if data['kind'] != 'lamaui-catalog' or data['schema'] != 1 or not 1 <= len(data['apps']) <= 40:
                raise ValueError()
            for app in data['apps']:
                for art in (app['artwork'], app['launcher']['artwork']):
                    if not re.fullmatch(r'[a-f0-9]{64}', art['sha256']) or not 16 <= art['size'] <= 524288:
                        raise ValueError()
            return root, envelope, data
        except (OSError, ValueError, KeyError, TypeError):
            raise HTTPException(404, 'No shared catalogue is available.') from None

    @router.get('/api/android-client-catalog', include_in_schema=False)
    def catalogue_metadata(request: Request):
        _, envelope, _ = catalogue(request)
        return JSONResponse(envelope, headers={'Cache-Control': 'no-store'})

    @router.get('/api/android-client-catalog/assets/{digest}.webp', include_in_schema=False)
    def catalogue_artwork(request: Request, digest: str):
        root, _, data = catalogue(request)
        if not re.fullmatch(r'[a-f0-9]{64}', digest):
            raise HTTPException(404)
        allowed = [art for app in data['apps'] for art in (app['artwork'], app['launcher']['artwork']) if art['sha256'] == digest]
        image = root / 'assets' / (digest + '.webp')
        if not allowed or image.is_symlink() or not image.is_file() or not 16 <= image.stat().st_size <= 524288:
            raise HTTPException(404)
        content = image.read_bytes()
        if len(content) != allowed[0]['size'] or hashlib.sha256(content).hexdigest() != digest:
            raise HTTPException(404)
        return FileResponse(image, media_type='image/webp', headers={'Cache-Control': 'private, max-age=31536000, immutable', 'X-Content-Type-Options': 'nosniff'})

    return router
