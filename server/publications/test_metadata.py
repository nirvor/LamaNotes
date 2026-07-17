import tempfile
import unittest
import uuid
from pathlib import Path

from notes.file_system.file_system import FileSystemNotes
from notes.models import NoteCreate, NoteUpdate

from .metadata import (
    PUBLICATION_ID,
    SOURCE_ID,
    PublicationMetadataStore,
    inject_publication_metadata,
    parse_publication_metadata,
)


class PublicationMetadataTests(unittest.TestCase):
    def test_source_id_is_stable_and_duplicate_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Test.html"
            path.write_text(
                "<html><body><p>Safe note.</p></body></html>", encoding="utf-8"
            )
            store = PublicationMetadataStore(directory)

            _, content, modified, metadata = store.ensure_source_id(
                "Test", path.stat().st_mtime
            )

            self.assertEqual(uuid.UUID(metadata.source_id).version, 4)
            _, content_again, modified_again, metadata_again = (
                store.ensure_source_id("Test", modified)
            )
            self.assertEqual(metadata_again.source_id, metadata.source_id)
            self.assertEqual(content_again, content)
            self.assertEqual(modified_again, modified)

            (Path(directory) / "Copy.html").write_text(
                content, encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "duplicate_source_id"):
                store.ensure_source_id("Test", modified)

    def test_expected_modification_time_prevents_stale_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Test.html"
            path.write_text("<p>One</p>", encoding="utf-8")
            store = PublicationMetadataStore(directory)

            with self.assertRaisesRegex(ValueError, "note_changed"):
                store.ensure_source_id("Test", path.stat().st_mtime - 10)

    def test_editor_preserves_authoritative_metadata_and_strips_forged_values(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            notes = object.__new__(FileSystemNotes)
            notes.storage_path = directory
            forged = inject_publication_metadata(
                "<p>Created</p>",
                {SOURCE_ID: str(uuid.uuid4()), PUBLICATION_ID: "pub_forged"},
            )

            created = notes.create(
                NoteCreate(title="Created", content=forged, format="html")
            )
            self.assertIsNone(
                parse_publication_metadata(created.content).source_id
            )

            source_id = str(uuid.uuid4())
            existing = inject_publication_metadata(
                "<p>Before</p>",
                {SOURCE_ID: source_id, PUBLICATION_ID: "pub_real"},
            )
            (Path(directory) / "Existing.html").write_text(
                existing, encoding="utf-8"
            )
            incoming = inject_publication_metadata(
                "<p>After</p>",
                {SOURCE_ID: str(uuid.uuid4()), PUBLICATION_ID: "pub_forged"},
            )

            updated = notes.update(
                "Existing", NoteUpdate(new_content=incoming)
            )
            metadata = parse_publication_metadata(updated.content)
            self.assertEqual(metadata.source_id, source_id)
            self.assertEqual(metadata.publication_id, "pub_real")
            self.assertIn("After", updated.content)
            self.assertNotIn("pub_forged", updated.content)


if __name__ == "__main__":
    unittest.main()
