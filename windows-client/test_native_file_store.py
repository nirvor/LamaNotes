from __future__ import annotations

import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from unittest.mock import Mock, patch
from pathlib import Path
from urllib import error, parse, request

from nirvnotes_client import (
    ALLOWED_EXTENSIONS,
    SHARD_PATHW,
    CredentialStore,
    NativeFileStore,
    NirvNotesApi,
    add_to_windows_recent_documents,
    paths_from_native_drop_event,
    register_native_file_drop,
    start_local_proxy,
    updater_process_creation_flags,
    validate_windows_update_archive,
)


class NirvNotesApiTests(unittest.TestCase):
    def test_window_title_is_compact_and_native(self) -> None:
        store = NativeFileStore()
        try:
            api = NirvNotesApi(
                store,
                [],
                "https://notes.example",
                "https://notes.example",
            )
            api._window = Mock()

            result = api.set_window_title("  sample.csv  ")

            self.assertTrue(result["updated"])
            api._window.set_title.assert_called_once_with(
                "NirvNotes - sample.csv",
            )
        finally:
            store.close()

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
                result = api.open_external_url("https://pages.thuber.org/example/")
            self.assertTrue(result["opened"])
            startfile.assert_called_once_with("https://pages.thuber.org/example/")
        finally:
            store.close()

    @unittest.skipUnless(sys.platform == "win32", "Windows DPAPI only")
    def test_auth_token_is_user_bound_and_source_bound(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            credential_path = Path(directory) / "credential.bin"
            store = CredentialStore(
                "https://notes.example",
                path=credential_path,
            )

            self.assertTrue(store.set_token("secret-session-token"))
            self.assertEqual(store.get_token(), "secret-session-token")
            self.assertNotIn(
                b"secret-session-token",
                credential_path.read_bytes(),
            )
            self.assertEqual(
                CredentialStore(
                    "https://other.example",
                    path=credential_path,
                ).get_token(),
                "",
            )

            store.clear()
            self.assertFalse(credential_path.exists())

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

    def test_google_login_uses_system_browser_pkce_and_dpapi_store(
        self,
    ) -> None:
        class MemoryCredentialStore:
            token = ""

            def set_token(self, token: str) -> bool:
                self.token = token
                return True

        class ExchangeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self) -> bytes:
                return b'{"access_token":"native-session-token"}'

        store = NativeFileStore()
        credential_store = MemoryCredentialStore()
        try:
            api = NirvNotesApi(
                store,
                [],
                "http://127.0.0.1:31992",
                "https://notes.example",
                credential_store=credential_store,
            )
            api.set_google_handoff_port(45678)
            api._window = Mock()
            with patch("nirvnotes_client.os.startfile") as startfile:
                opened = api.start_google_login()

            self.assertTrue(opened["opened"])
            login_url = startfile.call_args.args[0]
            query = parse.parse_qs(parse.urlsplit(login_url).query)
            self.assertEqual(query["flow"], ["native"])
            self.assertEqual(
                query["loopback"],
                ["http://127.0.0.1:45678/auth/google/callback"],
            )
            self.assertEqual(len(query["code_challenge"][0]), 43)

            with patch(
                "nirvnotes_client.request.urlopen",
                return_value=ExchangeResponse(),
            ):
                completed = api.complete_google_login(
                    "short-lived-handoff",
                    query["client_state"][0],
                )

            self.assertTrue(completed["ok"])
            self.assertEqual(credential_store.token, "native-session-token")
            api._window.load_url.assert_called_once_with("http://127.0.0.1:31992/")
        finally:
            store.close()


class NativeShellIntegrationTests(unittest.TestCase):
    def test_windows_update_archive_requires_all_webview_runtimes(self) -> None:
        required = (
            "app/NirvNotes.exe",
            "app/_internal/client-version.json",
            "app/_internal/webview/lib/runtimes/win-arm64/native/WebView2Loader.dll",
            "app/_internal/webview/lib/runtimes/win-x64/native/WebView2Loader.dll",
            "app/_internal/webview/lib/runtimes/win-x86/native/WebView2Loader.dll",
        )
        with tempfile.TemporaryDirectory() as directory:
            complete = Path(directory) / "complete.zip"
            with zipfile.ZipFile(complete, "w") as archive:
                for name in required:
                    archive.writestr(name, b"payload")

            validate_windows_update_archive(complete)

            incomplete = Path(directory) / "incomplete.zip"
            with zipfile.ZipFile(incomplete, "w") as archive:
                for name in required:
                    if "win-arm64" not in name:
                        archive.writestr(name, b"payload")

            with self.assertRaisesRegex(ValueError, "win-arm64"):
                validate_windows_update_archive(incomplete)

            malformed = Path(directory) / "malformed.zip"
            malformed.write_bytes(b"not a zip")
            with self.assertRaisesRegex(ValueError, "valid ZIP"):
                validate_windows_update_archive(malformed)

    def test_drop_event_returns_unique_full_paths(self) -> None:
        event = {
            "dataTransfer": {
                "files": [
                    {"name": "alpha.md", "pywebviewFullPath": "C:/work/alpha.md"},
                    {"name": "alpha.md", "pywebviewFullPath": "C:/work/alpha.md"},
                    {"name": "missing.txt"},
                    {"name": "beta.csv", "pywebviewFullPath": "C:/work/beta.csv"},
                ]
            }
        }

        self.assertEqual(
            paths_from_native_drop_event(event),
            ["C:/work/alpha.md", "C:/work/beta.csv"],
        )

    def test_windows_recent_document_uses_shell_api(self) -> None:
        class RecentFunction:
            argtypes = None
            restype = None

            def __init__(self) -> None:
                self.calls = []

            def __call__(self, *args) -> None:
                self.calls.append(args)

        recent_function = RecentFunction()
        shell = Mock(SHAddToRecentDocs=recent_function)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.md"
            path.write_text("# Sample\n", encoding="utf-8")

            added = add_to_windows_recent_documents(
                path,
                shell32=shell,
                platform="win32",
            )

        self.assertTrue(added)
        self.assertEqual(len(recent_function.calls), 1)
        self.assertEqual(recent_function.calls[0][0], SHARD_PATHW)

    def test_windows_recent_document_is_noop_elsewhere(self) -> None:
        self.assertFalse(
            add_to_windows_recent_documents(
                "sample.md",
                shell32=Mock(),
                platform="linux",
            )
        )

    def test_native_drop_opens_only_the_first_file_in_current_window(self) -> None:
        class CapturingEvent:
            def __init__(self) -> None:
                self.items = []

            def __iadd__(self, item):
                self.items.append(item)
                return self

        loaded = CapturingEvent()
        dropped = CapturingEvent()
        window = Mock()
        window.events.loaded = loaded
        window.dom.document.events.drop = dropped
        api = Mock()
        api.open_external_paths.return_value = 1

        register_native_file_drop(window, api, "http://127.0.0.1:31992")
        loaded.items[0]()
        dropped.items[0].callback(
            {
                "dataTransfer": {
                    "files": [
                        {"pywebviewFullPath": "C:/work/first.md"},
                        {"pywebviewFullPath": "C:/work/second.txt"},
                    ]
                }
            }
        )

        api.open_external_paths.assert_called_once_with(
            ["C:/work/first.md"],
            "http://127.0.0.1:31992",
        )


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

    def test_csv_and_tex_are_opened_as_raw_source(self) -> None:
        csv_path = self.root / "measurements.csv"
        tex_path = self.root / "formula.tex"
        csv_path.write_text("name,value\nalpha,3.5\n", encoding="utf-8")
        tex_path.write_text("\\\\section{Result}\n", encoding="utf-8")

        csv_payload, tex_payload = self.store.payloads_for_paths(
            [str(csv_path), str(tex_path)]
        )

        self.assertIn(".csv", ALLOWED_EXTENSIONS)
        self.assertIn(".tex", ALLOWED_EXTENSIONS)
        self.assertEqual(csv_payload["type"], "text/csv")
        self.assertEqual(csv_payload["content"], "name,value\nalpha,3.5\n")
        self.assertEqual(tex_payload["type"], "application/x-tex")
        self.assertEqual(tex_payload["content"], "\\\\section{Result}\n")

    def test_opened_file_is_forwarded_to_windows_recents(self) -> None:
        path = self.root / "recent.md"
        path.write_text("# Recent\n", encoding="utf-8")

        with patch(
            "nirvnotes_client.add_to_windows_recent_documents"
        ) as add_recent:
            payloads = self.store.payloads_for_paths(
                [str(path)],
                record_recent=True,
            )

        self.assertEqual(len(payloads), 1)
        add_recent.assert_called_once_with(path)

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
