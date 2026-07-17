from __future__ import annotations

import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from pathlib import Path
from urllib import error, request

from nirvnotes_client import (
    ALLOWED_EXTENSIONS,
    NativeFileStore,
    NirvNotesApi,
    start_local_proxy,
    updater_process_creation_flags,
)


class NirvNotesApiTests(unittest.TestCase):
    def test_external_public_url_opens_in_system_browser(self) -> None:
        store = NativeFileStore()
        try:
            api = NirvNotesApi(
                store,
                [],
                "https://notes.example",
                "https://notes.example",
            )
            with patch("nirvnotes_client.os.startfile") as startfile:
                result = api.open_external_url(
                    "https://pages.thuber.org/example/"
                )
            self.assertTrue(result["opened"])
            startfile.assert_called_once_with(
                "https://pages.thuber.org/example/"
            )
        finally:
            store.close()

    def test_external_url_rejects_non_https(self) -> None:
        store = NativeFileStore()
        try:
            api = NirvNotesApi(
                store,
                [],
                "https://notes.example",
                "https://notes.example",
            )
            with patch("nirvnotes_client.os.startfile") as startfile:
                result = api.open_external_url("file:///C:/private.txt")
            self.assertFalse(result["opened"])
            startfile.assert_not_called()
        finally:
            store.close()


class NativeFileStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.store = NativeFileStore()

    def tearDown(self) -> None:
        self.store.close()
        self.temporary_directory.cleanup()

    def test_atomic_save_preserves_utf8_bom_and_crlf(self) -> None:
        path = self.root / "sample.md"
        path.write_bytes(b"\xef\xbb\xbfalpha\r\nbeta\r\n")

        payload = self.store.payloads_for_paths([str(path)])[0]
        self.assertEqual(payload["content"], "alpha\nbeta\n")
        self.assertEqual(payload["encoding"], "UTF-8 BOM")
        self.assertEqual(payload["lineEnding"], "CRLF")

        saved = self.store.save(
            payload["id"],
            "alpha\nbeta\ngamma\n",
            payload["version"],
        )

        self.assertTrue(saved["ok"])
        self.assertEqual(
            path.read_bytes(),
            b"\xef\xbb\xbfalpha\r\nbeta\r\ngamma\r\n",
        )
        self.assertFalse(list(self.root.glob(f".{path.name}.*.tmp")))

    def test_save_detects_external_version_conflict(self) -> None:
        path = self.root / "sample.ini"
        path.write_text("value=one\n", encoding="utf-8")
        payload = self.store.payloads_for_paths([str(path)])[0]

        path.write_text("value=external\n", encoding="utf-8")
        conflict = self.store.save(
            payload["id"],
            "value=mine\n",
            payload["version"],
        )

        self.assertTrue(conflict["conflict"])
        self.assertEqual(conflict["external"]["content"], "value=external\n")
        self.assertEqual(path.read_text(encoding="utf-8"), "value=external\n")

        saved = self.store.save(
            payload["id"],
            "value=mine\n",
            payload["version"],
            force=True,
        )
        self.assertTrue(saved["ok"])
        self.assertEqual(path.read_text(encoding="utf-8"), "value=mine\n")

    def test_native_watcher_reports_external_change_and_delete(self) -> None:
        path = self.root / "sample.txt"
        path.write_text("first\n", encoding="utf-8")
        payload = self.store.payloads_for_paths([str(path)])[0]

        path.write_text("second\n", encoding="utf-8")
        changed = self._wait_for_change(payload["id"])
        self.assertEqual(changed["content"], "second\n")
        self.assertFalse(changed["deleted"])

        path.unlink()
        deleted = self._wait_for_change(payload["id"])
        self.assertTrue(deleted["deleted"])

    def test_structured_text_formats_are_opened_as_raw_source(self) -> None:
        path = self.root / "service.yaml"
        path.write_text("enabled: true\n", encoding="utf-8")

        payload = self.store.payloads_for_paths([str(path)])[0]

        self.assertIn(".yaml", ALLOWED_EXTENSIONS)
        self.assertEqual(payload["extension"], "yaml")
        self.assertEqual(payload["type"], "application/yaml")
        self.assertEqual(payload["content"], "enabled: true\n")

    def _wait_for_change(self, file_id: str) -> dict:
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            for change in self.store.poll_changes():
                if change["id"] == file_id:
                    return change
            time.sleep(0.05)
        self.fail("Native watcher did not report the expected change.")


class LocalProxyTests(unittest.TestCase):
    def test_offline_response_is_marked_and_subsequent_call_is_fast(self) -> None:
        local_url, server = start_local_proxy("http://127.0.0.1:1", 0)
        try:
            with self.assertRaises(error.HTTPError) as first_error:
                request.urlopen(f"{local_url}/api/config", timeout=3)
            self.assertEqual(first_error.exception.code, 502)
            self.assertEqual(
                first_error.exception.headers.get("X-NirvNotes-Upstream"),
                "offline",
            )

            started = time.monotonic()
            with self.assertRaises(error.HTTPError):
                request.urlopen(f"{local_url}/api/config", timeout=3)
            self.assertLess(time.monotonic() - started, 0.25)
        finally:
            server.shutdown()
            server.server_close()


class ClientUpdaterTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "Windows process flags only")
    def test_updater_flags_do_not_combine_detached_and_no_window(self) -> None:
        flags = updater_process_creation_flags()

        self.assertTrue(flags & subprocess.CREATE_NEW_PROCESS_GROUP)
        self.assertTrue(flags & subprocess.CREATE_NO_WINDOW)
        self.assertFalse(flags & subprocess.DETACHED_PROCESS)


if __name__ == "__main__":
    unittest.main()
