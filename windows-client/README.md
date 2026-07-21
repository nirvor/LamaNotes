# NirvNotes Windows Client

Native Windows shell for NirvNotes. Android stays the normal PWA. The Windows
client bundles the complete UI locally and only sends note/API/media requests
to the VPS. It therefore starts and opens local files even when Tailscale or the
VPS is unavailable.

## Run locally

```powershell
powershell -ExecutionPolicy Bypass -File windows-client\run.ps1
```

Open one or more local text files:

```powershell
powershell -ExecutionPolicy Bypass -File windows-client\run.ps1 -Files README.md
```

## Build executable

```powershell
powershell -ExecutionPolicy Bypass -File windows-client\build.ps1
```

The executable is written to:

```text
windows-client\dist\NirvNotes\NirvNotes.exe
```

## Register as Open With app

```powershell
powershell -ExecutionPolicy Bypass -File windows-client\install-file-associations.ps1 -ExePath windows-client\dist\NirvNotes\NirvNotes.exe
```

Windows 11 may still require one manual default-app confirmation for a newly
associated text/config format. That is normal; the script registers the app cleanly
but does not fight Windows UserChoice protection.

## Behavior

- Serves the bundled NirvNotes UI from a local loopback server.
- Proxies only dynamic API, attachment, and note-asset requests to the live VPS.
- Keeps the shell and local file editor usable while the VPS is offline.
- Uses persistent WebView2 storage under `%LOCALAPPDATA%\NirvNotes\WebView2`.
- Writes startup diagnostics to `%LOCALAPPDATA%\NirvNotes\logs`.
- Opens `.md`, `.txt`, `.cfg`, `.ini`, `.json`, `.yaml/.yml`, `.toml`, `.xml`,
  and `.log` from Windows or the native menu.
- Uses one compact CodeMirror editor with line numbers, syntax color, search,
  keyboard undo/redo, and exact raw-source copy.
- Preserves UTF-8 BOM, Windows-1252, LF/CRLF, cursor, scroll, open files, edit
  mode, and the last window position.
- Watches local files natively, reloads clean files automatically, and shows a
  compact compare/reload/overwrite choice when both versions changed.
- Saves edited external files atomically back to their original path.
- Does not import external files into the VPS note folder.
- Supports multiple independent windows. A second app launch gets its own local
  proxy port, and `New Window` opens the current NirvNotes route natively.
- Starts Google login in the normal system browser. The server returns a
  short-lived PKCE-bound handoff to the app's loopback listener; the resulting
  NirvNotes token is protected with Windows DPAPI and is never placed in the
  embedded browser URL.

## Updates

An installed release checks the NirvNotes server for a newer Windows package.
When one is available, `Update NirvNotes` appears in the normal app menu. The
client downloads the ZIP, verifies its SHA-256 hash and size, backs up the
current installation, replaces it, and restarts. A failed replacement is rolled
back automatically.

The first updater-capable release still needs one normal installer run. Later
releases can use the in-app update action. The server reads the update manifest
and package from `NIRVNOTES_WINDOWS_UPDATE_DIR`.
