import base64
import hashlib
import json
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse


def update_router(directory):
    router = APIRouter()

    def release(request):
        if request.url.hostname not in {'racknerd-31fcf0d.tail38b5b3.ts.net', 'testserver', 'localhost', '127.0.0.1'}:
            raise HTTPException(404, 'Android updates use the private Tailscale address.')
        if not directory:
            raise HTTPException(404, "Android updates are unavailable.")
        root = Path(directory).resolve()
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

    return router
