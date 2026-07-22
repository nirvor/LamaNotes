# LamaNotes Windows Client

Native Windows shell for LamaNotes. Android stays the normal PWA. The Windows
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
windows-client\dist\LamaNotes\LamaNotes.exe
```

## Register as Open With app

```powershell
powershell -ExecutionPolicy Bypass -File windows-client\install-file-associations.ps1 -ExePath windows-client\dist\LamaNotes\LamaNotes.exe
```

Windows 11 may still require one manual default-app confirmation for a newly
associated text/config format. That is normal; the script registers the app cleanly
but does not fight Windows UserChoice protection.

## Behavior

- Serves the bundled LamaNotes UI from a local loopback server.
- Proxies only dynamic API, attachment, and note-asset requests to the live VPS.
- Keeps the shell and local file editor usable while the VPS is offline.
- Uses persistent WebView2 storage under `%LOCALAPPDATA%\LamaNotes\WebView2`.
- Writes startup diagnostics to `%LOCALAPPDATA%\LamaNotes\logs`.
- Opens `.md`, `.txt`, `.cfg`, `.ini`, `.json`, `.yaml/.yml`, `.toml`, `.xml`,
  `.log`, `.csv`, and `.tex` from Windows, the native menu, or by dropping one
  file into the current window.
- Adds successfully opened local files to the normal Windows recent-document
  history used by the taskbar Jump List.
- Uses one compact CodeMirror editor with optional line numbers, syntax color,
  search, keyboard undo/redo, and exact raw-source copy.
- Avoids expensive rich rendering for unusually large files while keeping the
  complete raw source available in edit mode.
- Preserves UTF-8 BOM, Windows-1252, LF/CRLF, cursor, scroll, open files, edit
  mode, and the last window position.
- Watches local files natively, reloads clean files automatically, and shows a
  compact compare/reload/overwrite choice when both versions changed.
- Saves edited external files atomically back to their original path.
- Does not import external files into the VPS note folder.
- Supports multiple independent windows. A second app launch gets its own local
  proxy port, and `New Window` opens the current LamaNotes route natively.
- Starts Google login in the normal system browser. The server returns a
  short-lived PKCE-bound handoff to the app's loopback listener; the resulting
  LamaNotes token is protected with Windows DPAPI and is never placed in the
  embedded browser URL.

## Updates

An installed release checks the LamaNotes server for a newer Windows package.
When one is available, `Update LamaNotes` appears in the normal app menu. The
client downloads the ZIP, verifies its SHA-256 hash and size, backs up the
current installation, replaces it, and restarts. A failed replacement is rolled
back automatically.

The first updater-capable release still needs one normal installer run. Later
releases can use the in-app update action. The server reads the update manifest
and package from `LAMANOTES_WINDOWS_UPDATE_DIR`.
