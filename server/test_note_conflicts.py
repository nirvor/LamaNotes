import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from notes.errors import NoteConflictError
from notes.file_system.file_system import FileSystemNotes
from notes.models import Note, NoteUpdate


class NoteConflictTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name, "Example.md")
        self.path.write_text("First", encoding="utf-8")
        self.notes = object.__new__(FileSystemNotes)
        self.notes.storage_path = self.directory.name
        self.notes._invalidate_semantic_index_cache = Mock()
        self.notes._write_file = lambda path, content, overwrite=False: Path(path).write_text(content, encoding="utf-8")

    def test_two_editors_cannot_overwrite_each_other(self):
        first = self.notes.get("Example")
        second = self.notes.get("Example")
        saved = self.notes.update("Example", NoteUpdate(new_content="Second", expected_version=first.version))
        self.assertNotEqual(saved.version, first.version)
        with self.assertRaises(NoteConflictError):
            self.notes.update("Example", NoteUpdate(new_content="Stale", expected_version=second.version))
        self.assertEqual(self.path.read_text(encoding="utf-8"), "Second")

    def test_conflict_precedes_rename(self):
        original = self.notes.get("Example")
        self.path.write_text("External", encoding="utf-8")
        with self.assertRaises(NoteConflictError):
            self.notes.update("Example", NoteUpdate(new_title="Renamed", expected_version=original.version))
        self.assertTrue(self.path.exists())
        self.assertFalse(Path(self.directory.name, "Renamed.md").exists())

    def test_explicit_retry_uses_the_reviewed_revision(self):
        latest = self.notes.get("Example")
        saved = self.notes.update("Example", NoteUpdate(new_content="", expected_version=latest.version))
        self.assertEqual(saved.content, "")
        self.assertEqual(saved.version, self.notes.get("Example").version)

    def test_version_is_derived_and_format_sensitive(self):
        first = Note(title="Example", content="same", format="html", last_modified=1)
        second = Note(title="Example", content="same", format="markdown", last_modified=1)
        self.assertNotEqual(first.version, second.version)
        self.assertEqual(len(first.version), 64)
