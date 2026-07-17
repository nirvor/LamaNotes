import os
import re
import struct
import urllib.parse
import hashlib
import mimetypes
import unicodedata

from fastapi import UploadFile
from fastapi.responses import FileResponse

from helpers import get_env, is_valid_filename

from ..base import BaseAttachments
from ..models import AttachmentCreateResponse


class FileSystemAttachments(BaseAttachments):
    def __init__(self):
        self.base_path = get_env("FLATNOTES_PATH", mandatory=True)
        if not os.path.exists(self.base_path):
            raise NotADirectoryError(
                f"'{self.base_path}' is not a valid directory."
            )
        self.storage_path = os.path.join(self.base_path, "attachments")
        os.makedirs(self.storage_path, exist_ok=True)

    def create(self, file: UploadFile) -> AttachmentCreateResponse:
        """Create a new attachment."""
        original_filename = os.path.basename(file.filename or "asset")
        content = file.file.read()
        digest = hashlib.sha256(content).hexdigest()
        filename = self._asset_filename(original_filename, digest, file.content_type)
        is_valid_filename(filename)
        filepath = os.path.join(self.storage_path, filename)
        reused = os.path.isfile(filepath)
        if not reused:
            self._save_bytes(filepath, content)
        width, height = self._image_dimensions(content)
        return AttachmentCreateResponse(
            filename=filename,
            url=self._url_for_filename(filename),
            original_filename=original_filename,
            content_type=file.content_type
            or mimetypes.guess_type(original_filename)[0],
            size=len(content),
            sha256=digest,
            reused=reused,
            width=width,
            height=height,
        )

    def get(self, filename: str) -> FileResponse:
        """Get a specific attachment."""
        is_valid_filename(filename)
        filepath = os.path.join(self.storage_path, filename)
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"'{filename}' not found.")
        return FileResponse(filepath)

    def _save_bytes(self, filepath: str, content: bytes):
        with open(filepath, "xb") as f:
            f.write(content)

    @staticmethod
    def _slugify(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value or "")
        ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-").lower()
        return slug or "asset"

    def _asset_filename(
        self, original_filename: str, digest: str, content_type: str | None
    ) -> str:
        name, ext = os.path.splitext(original_filename)
        ext = ext.lower()
        if not ext:
            ext = mimetypes.guess_extension(content_type or "") or ".bin"
        slug = self._slugify(name)
        return f"{slug}-{digest[:10]}{ext}"

    def _url_for_filename(self, filename: str) -> str:
        """Return the URL for the given filename."""
        return f"attachments/{urllib.parse.quote(filename)}"

    @staticmethod
    def _image_dimensions(content: bytes) -> tuple[int | None, int | None]:
        if len(content) >= 24 and content.startswith(b"\x89PNG\r\n\x1a\n"):
            width, height = struct.unpack(">II", content[16:24])
            return width, height

        if len(content) >= 10 and content[:6] in (b"GIF87a", b"GIF89a"):
            width, height = struct.unpack("<HH", content[6:10])
            return width, height

        if len(content) >= 4 and content[:2] == b"\xff\xd8":
            return FileSystemAttachments._jpeg_dimensions(content)

        if len(content) >= 30 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
            return FileSystemAttachments._webp_dimensions(content)

        return None, None

    @staticmethod
    def _jpeg_dimensions(content: bytes) -> tuple[int | None, int | None]:
        index = 2
        while index + 9 < len(content):
            if content[index] != 0xFF:
                index += 1
                continue
            marker = content[index + 1]
            index += 2
            if marker in (0xD8, 0xD9):
                continue
            if index + 2 > len(content):
                break
            length = int.from_bytes(content[index : index + 2], "big")
            if length < 2 or index + length > len(content):
                break
            if marker in {
                0xC0,
                0xC1,
                0xC2,
                0xC3,
                0xC5,
                0xC6,
                0xC7,
                0xC9,
                0xCA,
                0xCB,
                0xCD,
                0xCE,
                0xCF,
            }:
                height = int.from_bytes(content[index + 3 : index + 5], "big")
                width = int.from_bytes(content[index + 5 : index + 7], "big")
                return width, height
            index += length
        return None, None

    @staticmethod
    def _webp_dimensions(content: bytes) -> tuple[int | None, int | None]:
        chunk_type = content[12:16]
        if chunk_type == b"VP8X" and len(content) >= 30:
            width = int.from_bytes(content[24:27], "little") + 1
            height = int.from_bytes(content[27:30], "little") + 1
            return width, height

        if chunk_type == b"VP8 " and len(content) >= 30:
            width = int.from_bytes(content[26:28], "little") & 0x3FFF
            height = int.from_bytes(content[28:30], "little") & 0x3FFF
            return width, height

        if chunk_type == b"VP8L" and len(content) >= 25:
            bits = int.from_bytes(content[21:25], "little")
            width = (bits & 0x3FFF) + 1
            height = ((bits >> 14) & 0x3FFF) + 1
            return width, height

        return None, None
