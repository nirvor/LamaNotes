# NirvNotes Win11 Installer

This package installs the NirvNotes desktop client for the current Windows user.
It does not need admin rights.

## Quick install

Extract the ZIP, then double-click:

```text
Install-NirvNotes.cmd
```

The installer copies the app to:

```text
%LOCALAPPDATA%\Programs\NirvNotes
```

It also creates Start Menu and Desktop shortcuts, registers NirvNotes as an
Open With app for the supported text and configuration formats, and adds a normal Windows
uninstaller entry.

This installer is required once for the updater-capable client. Future releases
appear as `Update NirvNotes` in the app menu and install without extracting a
new installer package manually.

## Cloud/backend behavior

The desktop shell and local editor are bundled with the app. VPS notes, search,
attachments, and media use the live RackNerd endpoint:

```text
https://notes.thuber.org
```

The Win11 client uses normal authenticated HTTPS and does not require Tailscale.
The installer performs a small connectivity check but does not fail when the
machine is offline. Local text and configuration files remain available without
the VPS.

## Command-line install

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Install-NirvNotes.ps1
```

Useful options:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Install-NirvNotes.ps1 -NoLaunch
powershell -NoProfile -ExecutionPolicy Bypass -File .\Install-NirvNotes.ps1 -NoStartMenuShortcut
powershell -NoProfile -ExecutionPolicy Bypass -File .\Install-NirvNotes.ps1 -NoDesktopShortcut
powershell -NoProfile -ExecutionPolicy Bypass -File .\Install-NirvNotes.ps1 -SkipConnectivityCheck
```

## Uninstall

Use Windows Settings > Apps > Installed apps > NirvNotes, or run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\Programs\NirvNotes\Uninstall-NirvNotes.ps1"
```

Uninstall keeps WebView2/login data by default. Use `-RemoveUserData` if you
want to remove the local browser profile too.
