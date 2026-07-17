import json
import re
from pathlib import Path
from typing import List, Literal

from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import api_messages
from attachments.base import BaseAttachments
from attachments.models import AttachmentCreateResponse
from auth.base import BaseAuth
from auth.models import Login, Token
from global_config import AuthType, GlobalConfig, GlobalConfigResponseModel
from helpers import replace_base_href
from notes.base import BaseNotes
from notes.models import (
    Note,
    NoteContext,
    NoteCreate,
    NoteIndexEntry,
    NoteUpdate,
    SearchResult,
)
from publications.errors import PublicationError
from publications.models import PublicationStart, PublicationStateResponse
from publications.service import PublicationService

global_config = GlobalConfig()
auth: BaseAuth = global_config.load_auth()
note_storage: BaseNotes = global_config.load_note_storage()
attachment_storage: BaseAttachments = global_config.load_attachment_storage()
publication_service = PublicationService(
    storage_path=note_storage.storage_path,
    base_url=global_config.publish_base_url,
    token=global_config.publish_token,
    public_base_url=global_config.public_base_url,
    timeout_seconds=global_config.publish_timeout_seconds,
)
auth_deps = [Depends(auth.authenticate)] if auth else []
router = APIRouter()
app = FastAPI(
    docs_url=global_config.path_prefix + "/docs",
    openapi_url=global_config.path_prefix + "/openapi.json",
)
replace_base_href("client/dist/index.html", global_config.path_prefix)


@app.on_event("startup")
def resume_pending_publications():
    publication_service.resume_pending()


HASHED_ASSET_RE = re.compile(
    r"/assets/.+-[A-Za-z0-9_-]{8,}\.(?:css|ico|js|otf|png|svg|ttf|webp|woff2?)$",
    re.IGNORECASE,
)
FONT_ASSET_RE = re.compile(
    r"/assets/fonts/.+\.(?:otf|ttf|woff2?)$",
    re.IGNORECASE,
)


@app.middleware("http")
async def add_static_cache_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path

    if HASHED_ASSET_RE.search(path):
        response.headers["Cache-Control"] = (
            "public, max-age=31536000, immutable"
        )
    elif FONT_ASSET_RE.search(path):
        response.headers.setdefault(
            "Cache-Control",
            "public, max-age=2592000",
        )

    return response


# region UI
@router.get("/", include_in_schema=False)
@router.get("/login", include_in_schema=False)
@router.get("/search", include_in_schema=False)
@router.get("/new", include_in_schema=False)
@router.get("/open-file", include_in_schema=False)
@router.get("/note/{title}", include_in_schema=False)
def root(title: str = ""):
    with open("client/dist/index.html", "r", encoding="utf-8") as f:
        html = f.read()
    return HTMLResponse(content=html)


# endregion


# region Windows client updates
def load_windows_update_manifest():
    if not global_config.windows_update_dir:
        raise HTTPException(404, "Windows client updates are not configured.")

    update_root = Path(global_config.windows_update_dir).resolve()
    manifest_path = update_root / "NirvNotes-update.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        raise HTTPException(404, "No Windows client update is available.")

    filename = Path(str(manifest.get("file", ""))).name
    package_path = (update_root / filename).resolve()
    if (
        not filename
        or update_root not in package_path.parents
        or not package_path.is_file()
    ):
        raise HTTPException(404, "The Windows client package is unavailable.")

    required_fields = ("version", "commit", "sha256", "size")
    if any(not manifest.get(field) for field in required_fields):
        raise HTTPException(500, "The Windows client manifest is incomplete.")

    return manifest, package_path


@router.get("/api/windows-client-update", include_in_schema=False)
def get_windows_client_update():
    manifest, _ = load_windows_update_manifest()
    response = dict(manifest)
    response["downloadUrl"] = (
        f"{global_config.path_prefix}/api/windows-client-update/download"
    )
    return JSONResponse(
        content=response,
        headers={"Cache-Control": "no-store"},
    )


@router.get("/api/windows-client-update/download", include_in_schema=False)
def download_windows_client_update():
    manifest, package_path = load_windows_update_manifest()
    return FileResponse(
        package_path,
        media_type="application/zip",
        filename=manifest["file"],
        headers={"Cache-Control": "no-store"},
    )


# endregion


# region Auth
if global_config.auth_type not in [AuthType.NONE, AuthType.READ_ONLY]:

    @router.post("/api/token", response_model=Token)
    def token(data: Login):
        try:
            return auth.login(data)
        except ValueError:
            raise HTTPException(
                status_code=401, detail=api_messages.login_failed
            )


@router.get("/api/auth-check", dependencies=auth_deps)
def auth_check() -> str:
    """A lightweight endpoint that simply returns 'OK' if the user is
    authenticated."""
    return "OK"


# endregion


# region Notes
# Get Note
@router.get(
    "/api/notes/{title}",
    dependencies=auth_deps,
    response_model=Note,
)
def get_note(title: str):
    """Get a specific note."""
    try:
        return note_storage.get(title)
    except ValueError:
        raise HTTPException(
            status_code=400, detail=api_messages.invalid_note_title
        )
    except FileNotFoundError:
        raise HTTPException(404, api_messages.note_not_found)


@router.get(
    "/api/notes/{title}/context",
    dependencies=auth_deps,
    response_model=NoteContext,
)
def get_note_context(title: str):
    """Get a structured, LLM-friendly context export for a specific note."""
    try:
        return note_storage.get_context(title)
    except ValueError:
        raise HTTPException(
            status_code=400, detail=api_messages.invalid_note_title
        )
    except FileNotFoundError:
        raise HTTPException(404, api_messages.note_not_found)


@router.get(
    "/api/notes/{title}/publication",
    dependencies=auth_deps,
    response_model=PublicationStateResponse,
)
def get_note_publication(title: str):
    """Return authoritative public publication state for a Library note."""
    try:
        return publication_service.get_state(title)
    except ValueError:
        raise HTTPException(
            status_code=400, detail=api_messages.invalid_note_title
        )


if global_config.auth_type != AuthType.READ_ONLY:

    # Create Note
    @router.post(
        "/api/notes",
        dependencies=auth_deps,
        response_model=Note,
    )
    def post_note(note: NoteCreate):
        """Create a new note."""
        try:
            return note_storage.create(note)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=api_messages.invalid_note_title,
            )
        except FileExistsError:
            raise HTTPException(
                status_code=409, detail=api_messages.note_exists
            )

    # Update Note
    @router.patch(
        "/api/notes/{title}",
        dependencies=auth_deps,
        response_model=Note,
    )
    def patch_note(title: str, data: NoteUpdate):
        try:
            return note_storage.update(title, data)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=api_messages.invalid_note_title,
            )
        except FileExistsError:
            raise HTTPException(
                status_code=409, detail=api_messages.note_exists
            )
        except FileNotFoundError:
            raise HTTPException(404, api_messages.note_not_found)

    @router.post(
        "/api/notes/{title}/publication",
        dependencies=auth_deps,
        response_model=PublicationStateResponse,
        status_code=202,
    )
    def publish_note(title: str, data: PublicationStart):
        """Start or resume an explicit public publication."""
        try:
            result = publication_service.start(title, data)
        except FileNotFoundError:
            raise HTTPException(404, api_messages.note_not_found)
        except PublicationError as error:
            return JSONResponse(
                status_code=error.status,
                content=error.problem(),
                media_type="application/problem+json",
                headers={"Cache-Control": "no-store"},
            )
        except ValueError:
            raise HTTPException(
                status_code=400, detail=api_messages.invalid_note_title
            )
        status_code = 200 if result.state == "current" else 202
        return JSONResponse(
            status_code=status_code,
            content=jsonable_encoder(result, by_alias=True),
            headers={"Cache-Control": "no-store"},
        )

    # Delete Note
    @router.delete(
        "/api/notes/{title}",
        dependencies=auth_deps,
        response_model=None,
    )
    def delete_note(title: str):
        try:
            note_storage.delete(title)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=api_messages.invalid_note_title,
            )
        except FileNotFoundError:
            raise HTTPException(404, api_messages.note_not_found)


# endregion


# region Search
@router.get(
    "/api/search",
    dependencies=auth_deps,
    response_model=List[SearchResult],
)
def search(
    term: str,
    sort: Literal["score", "title", "lastModified"] = "score",
    order: Literal["asc", "desc"] = "desc",
    limit: int = None,
):
    """Perform a full text search on all notes."""
    if sort == "lastModified":
        sort = "last_modified"
    return note_storage.search(term, sort=sort, order=order, limit=limit)


@router.get(
    "/api/tags",
    dependencies=auth_deps,
    response_model=List[str],
)
def get_tags():
    """Get a list of all indexed tags."""
    return note_storage.get_tags()


@router.get(
    "/api/index",
    dependencies=auth_deps,
    response_model=List[NoteIndexEntry],
)
def get_semantic_index():
    """Get a compact semantic index of all notes."""
    return note_storage.get_semantic_index()


# endregion


# region Config
@router.get("/api/config", response_model=GlobalConfigResponseModel)
def get_config():
    """Retrieve server-side config required for the UI."""
    return GlobalConfigResponseModel(
        auth_type=global_config.auth_type,
        quick_access_hide=global_config.quick_access_hide,
        quick_access_title=global_config.quick_access_title,
        quick_access_term=global_config.quick_access_term,
        quick_access_sort=global_config.quick_access_sort,
        quick_access_limit=global_config.quick_access_limit,
    )


# endregion


# region Attachments
# Get Attachment
@router.get(
    "/api/attachments/{filename}",
    dependencies=auth_deps,
)
# Include a secondary route used to create relative URLs that can be used
# outside the context of flatnotes (e.g. "/attachments/image.jpg").
@router.get(
    "/attachments/{filename}",
    dependencies=auth_deps,
    include_in_schema=False,
)
def get_attachment(filename: str):
    """Download an attachment."""
    try:
        return attachment_storage.get(filename)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=api_messages.invalid_attachment_filename,
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=404, detail=api_messages.attachment_not_found
        )


if global_config.auth_type != AuthType.READ_ONLY:

    # Create Attachment
    @router.post(
        "/api/attachments",
        dependencies=auth_deps,
        response_model=AttachmentCreateResponse,
    )
    def post_attachment(file: UploadFile):
        """Upload an attachment."""
        try:
            return attachment_storage.create(file)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=api_messages.invalid_attachment_filename,
            )
        except FileExistsError:
            raise HTTPException(409, api_messages.attachment_exists)


# endregion


# region Healthcheck
@router.get("/health")
def healthcheck() -> str:
    """A lightweight endpoint that simply returns 'OK' to indicate the server
    is running."""
    return "OK"


# endregion

app.include_router(router, prefix=global_config.path_prefix)
app.mount(
    global_config.path_prefix,
    StaticFiles(directory="client/dist"),
    name="dist",
)
