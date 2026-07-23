from __future__ import annotations

import base64
import binascii
import json
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

UPDATE_SIGNATURE_ALGORITHM = "ed25519"
UPDATE_SIGNED_FIELDS = (
    "version",
    "commit",
    "file",
    "sha256",
    "size",
    "publishedAt",
)


def canonical_update_manifest(manifest: dict[str, Any]) -> bytes:
    if any(manifest.get(field) in (None, "") for field in UPDATE_SIGNED_FIELDS):
        raise ValueError("Windows update manifest cannot be signed completely.")
    payload = {field: manifest[field] for field in UPDATE_SIGNED_FIELDS}
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def verify_update_manifest_signature(
    manifest: dict[str, Any],
    encoded_public_key: str,
) -> bool:
    public_key_value = str(encoded_public_key or "").strip()
    if not public_key_value:
        return False
    if manifest.get("signatureAlgorithm") != UPDATE_SIGNATURE_ALGORITHM:
        raise ValueError("Windows update signature algorithm is invalid.")

    try:
        public_key_bytes = base64.b64decode(public_key_value, validate=True)
        signature = base64.b64decode(
            str(manifest.get("signature", "")),
            validate=True,
        )
        public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        public_key.verify(signature, canonical_update_manifest(manifest))
    except (
        binascii.Error,
        InvalidSignature,
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError("Windows update manifest signature is invalid.") from exc
    return True
