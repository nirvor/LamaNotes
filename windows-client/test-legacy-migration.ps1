$ErrorActionPreference = "Stop"
$OriginalLocalAppData = $env:LOCALAPPDATA
$TestRoot = Join-Path $env:TEMP ("lamanotes-migration-test-" + [guid]::NewGuid().ToString("N"))

try {
  $env:LOCALAPPDATA = $TestRoot
  $LegacyDir = Join-Path $TestRoot "Programs\NirvNotes"
  $InstallDir = Join-Path $TestRoot "Programs\LamaNotes"
  New-Item -ItemType Directory -Path (Join-Path $LegacyDir "_internal") -Force | Out-Null
  Copy-Item "$env:WINDIR\System32\where.exe" (Join-Path $LegacyDir "LamaNotes.exe")
  Copy-Item "$env:WINDIR\System32\where.exe" (Join-Path $LegacyDir "NirvNotes.exe")
  Set-Content -LiteralPath (Join-Path $LegacyDir "_internal\client-version.json") -Value "{}" -Encoding UTF8
  Set-Content -LiteralPath (Join-Path $LegacyDir "Uninstall-LamaNotes.ps1") -Value "# test" -Encoding UTF8
  Set-Content -LiteralPath (Join-Path $LegacyDir "Uninstall-NirvNotes.ps1") -Value "# old" -Encoding UTF8

  & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "migrate-legacy-install.ps1") `
    -ParentProcessId 999999 `
    -LegacyInstallDir $LegacyDir `
    -InstallDir $InstallDir `
    -TestMode
  if ($LASTEXITCODE -ne 0) {
    throw "Migration script exited with code $LASTEXITCODE."
  }
  if (Test-Path -LiteralPath $LegacyDir) {
    throw "Legacy directory remains after migration."
  }
  if (-not (Test-Path -LiteralPath (Join-Path $InstallDir "LamaNotes.exe") -PathType Leaf)) {
    throw "Migrated executable is missing."
  }
  if (Test-Path -LiteralPath (Join-Path $InstallDir "NirvNotes.exe")) {
    throw "Legacy update alias remains after migration."
  }
  if (Test-Path -LiteralPath (Join-Path $InstallDir "Uninstall-NirvNotes.ps1")) {
    throw "Legacy uninstaller remains after migration."
  }

  Write-Host "Legacy product migration test passed."
} finally {
  $env:LOCALAPPDATA = $OriginalLocalAppData
  Remove-Item -LiteralPath $TestRoot -Recurse -Force -ErrorAction SilentlyContinue
}
