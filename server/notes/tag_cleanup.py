"""Preview or apply a version-guarded metadata plan during a coordinated release."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile

from .tag_policy import _TagDocument, replace_tag_metadata, rewrite_tag_metadata


def prepare(directory, changes):
    root = Path(directory).resolve(strict=True)
    rows = changes.get("notes", [])
    if changes.get("schema") not in {1, 2} or not isinstance(rows, list) or len(rows) > 200:
        raise ValueError("Use an explicit schema 1 or 2 metadata plan.")
    prepared = []
    seen = set()
    for row in rows:
        filename = row["filename"]
        if not isinstance(filename, str) or Path(filename).name != filename or "\\" in filename or not filename.endswith(".html") or filename.startswith(".") or filename in seen:
            raise ValueError("Use unique flat HTML note filenames.")
        seen.add(filename)
        path = root / filename
        if path.is_symlink() or path.resolve().parent != root or not path.is_file():
            raise ValueError("The note must be a regular file inside the Library.")
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if not re.fullmatch(r"[a-f0-9]{64}", row.get("sourceSha256", "")) or digest != row["sourceSha256"]:
            raise ValueError("The note changed after the metadata audit: " + filename)
        content = raw.decode("utf-8")
        document = _TagDocument(content)
        for field, names in (("researchId", {"lamanotes-research-id", "flatnotes-research-id"}), ("noteId", {"lamanotes-note-id", "flatnotes-note-id"})):
            if field in row and {value for _, value in document.identities(names)} != {row[field]}:
                raise ValueError("The planned note identity changed: " + filename)
        if changes["schema"] == 2:
            if not {"expectedTags", "tags", "expectedPrimaryTopic", "researchTopic"} <= row.keys():
                raise ValueError("An exact-set plan needs tag and Research topic guards.")
            result = replace_tag_metadata(content, row["tags"], expected_tags=row["expectedTags"],
                                          research_topic=row["researchTopic"], expected_primary_topic=row["expectedPrimaryTopic"])
        else:
            result = rewrite_tag_metadata(content, row["replacements"], expected_primary_topic=row.get("expectedPrimaryTopic"))
        prepared.append((path, raw, result.content.encode("utf-8"), result))
    return prepared


def atomic_replace(path, expected, updated):
    source_stat = path.stat()
    if hasattr(os, "getuid") and os.getuid() != source_stat.st_uid:
        raise ValueError("Run the cleanup as the existing note-file owner.")
    if path.is_symlink() or path.read_bytes() != expected:
        raise ValueError("The note changed before replacement: " + path.name)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".tag-cleanup-", suffix=".pending", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(updated)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(stat.S_IMODE(source_stat.st_mode))
        os.utime(temporary, ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns))
        if path.is_symlink() or path.read_bytes() != expected:
            raise ValueError("The note changed before replacement: " + path.name)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def run(directory, changes, *, apply=False):
    prepared = prepare(directory, changes)
    if apply:
        # Keep the writer stopped for the batch; per-file replacement is atomic.
        for path, expected, _, _ in prepared:
            if path.read_bytes() != expected:
                raise ValueError("The Library changed after preflight: " + path.name)
        for path, raw, updated, _ in prepared:
            if updated != raw:
                atomic_replace(path, raw, updated)
        if any(raw != updated for _, raw, updated, _ in prepared):
            rebuild_index(directory)
    return {"schema": changes["schema"], "applied": apply, "changedNotes": sum(raw != updated for _, raw, updated, _ in prepared),
            "preservesModificationTimes": True, "indexRebuilt": apply and any(raw != updated for _, raw, updated, _ in prepared),
            "notes": [{"filename": path.name, "sourceSha256": hashlib.sha256(raw).hexdigest(),
                       "resultSha256": hashlib.sha256(updated).hexdigest(), "previousTags": list(result.previous_tags),
                       "tags": list(result.tags), "changedSpans": len(result.changed_spans)} for path, raw, updated, result in prepared]}


def rebuild_index(directory):
    from .file_system.file_system import FileSystemNotes
    notes = object.__new__(FileSystemNotes)
    notes.storage_path = str(Path(directory).resolve(strict=True))
    notes.index = notes._load_index()
    try:
        notes._sync_index_with_retry(optimize=True, clean=True)
    finally:
        notes.index.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--changes", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.directory, json.loads(args.changes.read_text(encoding="utf-8-sig")), apply=args.apply), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
