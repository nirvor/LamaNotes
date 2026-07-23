from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

WINDOWS_CLIENT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WINDOWS_CLIENT_ROOT))

from update_manifest import (  # noqa: E402
    UPDATE_SIGNATURE_ALGORITHM,
    canonical_update_manifest,
)


def load_private_key(path: Path) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("The update signing key must be an Ed25519 private key.")
    return key


def encoded_public_key(private_key: Ed25519PrivateKey) -> str:
    raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return base64.b64encode(raw).decode("ascii")


def sign_manifest(manifest_path: Path, private_key: Ed25519PrivateKey) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    signature = private_key.sign(canonical_update_manifest(manifest))
    manifest["signatureAlgorithm"] = UPDATE_SIGNATURE_ALGORITHM
    manifest["signature"] = base64.b64encode(signature).decode("ascii")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=("public-key", "sign"),
    )
    parser.add_argument(
        "--private-key",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--manifest",
        type=Path,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    private_key = load_private_key(args.private_key)
    if args.command == "public-key":
        print(encoded_public_key(private_key))
        return
    if not args.manifest:
        raise ValueError("--manifest is required when signing.")
    sign_manifest(args.manifest, private_key)


if __name__ == "__main__":
    main()
