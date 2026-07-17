import tempfile
import unittest
from pathlib import Path

from .errors import PublicationError
from .metadata import parse_publication_metadata, preserve_publication_metadata
from .models import PublicationStart
from .service import PublicationService


class FakeConsumer:
    def __init__(self):
        self.manifests = []
        self.uploads = []
        self.finalized = []

    def begin(self, manifest):
        self.manifests.append(manifest)
        return 202, {
            "operationId": "op_test",
            "status": "awaiting-assets",
            "missingAssets": [],
        }

    def upload(self, upload_path, asset, content):
        self.uploads.append((upload_path, asset, content))

    def finalize(self, operation_id, content_hash):
        self.finalized.append((operation_id, content_hash))
        manifest = self.manifests[-1]
        return 200, self.success(manifest)

    def status(self, operation_id):
        return 202, {"operationId": operation_id, "status": "deploying"}

    @staticmethod
    def success(manifest):
        source_id = manifest["source"]["id"]
        return {
            "operationId": "op_test",
            "status": "succeeded",
            "publicationId": "pub_test",
            "sourceId": source_id,
            "canonicalSlug": "safe-publication",
            "canonicalUrl": "https://pages.thuber.org/safe-publication/",
            "publishedContentHash": manifest["content"]["contentHash"],
            "publishedAt": "2026-07-15T12:00:00Z",
        }


class PublicationServiceTests(unittest.TestCase):
    def make_service(self, directory, consumer):
        service = PublicationService(
            storage_path=directory,
            base_url="https://pages.example/api/nirvnotes-publications",
            token="test-token",
            public_base_url="https://pages.thuber.org",
            consumer=consumer,
        )
        service.submit_advance = lambda *_args: None
        return service

    def test_first_publish_and_update_keep_identity_and_canonical_url(self):
        with tempfile.TemporaryDirectory() as directory:
            note_path = Path(directory) / "Safe.html"
            note_path.write_text(
                "<html><body><article><h1>Safe</h1><p>Version one.</p></article></body></html>",
                encoding="utf-8",
            )
            consumer = FakeConsumer()
            service = self.make_service(directory, consumer)
            try:
                started = service.start(
                    "Safe",
                    PublicationStart(
                        requested_slug="safe-publication",
                        expected_last_modified=note_path.stat().st_mtime,
                    ),
                )
                self.assertEqual(started.state, "uploading-assets")
                source_id = started.source_id
                self.assertEqual(
                    consumer.manifests[0]["page"]["requestedSlug"],
                    "safe-publication",
                )

                service._advance(source_id, started.current_content_hash)
                current = service.get_state("Safe", refresh_remote=False)
                self.assertEqual(current.state, "current")
                self.assertEqual(
                    current.canonical_url,
                    "https://pages.thuber.org/safe-publication/",
                )

                existing = note_path.read_text(encoding="utf-8")
                updated = preserve_publication_metadata(
                    existing,
                    "<html><body><article><h1>Safe</h1><p>Version two.</p></article></body></html>",
                )
                note_path.write_text(updated, encoding="utf-8")
                update_started = service.start(
                    "Safe",
                    PublicationStart(
                        expected_last_modified=note_path.stat().st_mtime
                    ),
                )
                self.assertEqual(update_started.source_id, source_id)
                self.assertNotIn(
                    "requestedSlug", consumer.manifests[-1]["page"]
                )
                service._advance(
                    source_id, update_started.current_content_hash
                )
                current = service.get_state("Safe", refresh_remote=False)
                self.assertEqual(current.state, "current")
                self.assertEqual(current.source_id, source_id)
                self.assertEqual(
                    current.canonical_url,
                    "https://pages.thuber.org/safe-publication/",
                )
                self.assertEqual(
                    parse_publication_metadata(
                        note_path.read_text(encoding="utf-8")
                    ).source_id,
                    source_id,
                )
            finally:
                service._executor.shutdown(wait=False, cancel_futures=True)

    def test_resume_skips_nonretryable_stage_and_resumes_pending_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            note_path = Path(directory) / "Safe.html"
            note_path.write_text("<p>Safe content.</p>", encoding="utf-8")
            service = self.make_service(directory, FakeConsumer())
            calls = []
            try:
                started = service.start(
                    "Safe",
                    PublicationStart(
                        requested_slug="safe",
                        expected_last_modified=note_path.stat().st_mtime,
                    ),
                )
                service.submit_advance = lambda *args: calls.append(args)
                service.resume_pending()
                self.assertEqual(
                    calls, [(started.source_id, started.current_content_hash)]
                )

                service.staging.set_error(
                    started.source_id,
                    started.current_content_hash,
                    {
                        "code": "unsafe_public_content",
                        "detail": "Unsafe content.",
                        "retryable": False,
                    },
                )
                calls.clear()
                service.resume_pending()
                self.assertEqual(calls, [])
            finally:
                service._executor.shutdown(wait=False, cancel_futures=True)

    def test_new_content_cannot_overtake_a_running_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            note_path = Path(directory) / "Safe.html"
            note_path.write_text("<p>Version one.</p>", encoding="utf-8")
            service = self.make_service(directory, FakeConsumer())
            try:
                service.start(
                    "Safe",
                    PublicationStart(
                        requested_slug="safe",
                        expected_last_modified=note_path.stat().st_mtime,
                    ),
                )
                existing = note_path.read_text(encoding="utf-8")
                note_path.write_text(
                    preserve_publication_metadata(
                        existing, "<p>Version two.</p>"
                    ),
                    encoding="utf-8",
                )

                with self.assertRaises(PublicationError) as raised:
                    service.start(
                        "Safe",
                        PublicationStart(
                            expected_last_modified=note_path.stat().st_mtime
                        ),
                    )
                self.assertEqual(raised.exception.code, "publication_busy")
            finally:
                service._executor.shutdown(wait=False, cancel_futures=True)


if __name__ == "__main__":
    unittest.main()
