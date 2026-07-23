param(
  [string]$Name = "LamaNotes",
  [string]$Version = "",
  [string]$Commit = "",
  [string]$UpdateSigningPublicKey = ""
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Venv = Join-Path $PSScriptRoot ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"
$Icon = Join-Path $PSScriptRoot "lamanotes.ico"
$Entry = Join-Path $PSScriptRoot "lamanotes_client.py"
$Dist = Join-Path $PSScriptRoot "dist"
$Build = Join-Path $PSScriptRoot "build"
$UpdaterScript = Join-Path $PSScriptRoot "apply-update.ps1"
$LegacyMigrationScript = Join-Path $PSScriptRoot "migrate-legacy-install.ps1"
$ClientDist = Join-Path $Root "client\dist"
$MetadataDir = Join-Path $env:TEMP "LamaNotes-build-metadata-$PID"
$VersionMetadata = Join-Path $MetadataDir "client-version.json"

if (-not $Commit) {
  $Commit = (& git -C $Root rev-parse HEAD 2>$null | Select-Object -First 1)
}
if (-not $Version) {
  $Version = (& git -C $Root rev-parse --short HEAD 2>$null | Select-Object -First 1)
}
if (-not $Version) {
  $Version = Get-Date -Format "yyyyMMdd-HHmmss"
}
$UpdateSigningPublicKey = $UpdateSigningPublicKey.Trim()
if (
  $UpdateSigningPublicKey -and
  $UpdateSigningPublicKey -notmatch "^[A-Za-z0-9+/]{43}=$"
) {
  throw "UpdateSigningPublicKey must be one base64-encoded Ed25519 public key."
}

New-Item -ItemType Directory -Path $MetadataDir -Force | Out-Null
[ordered]@{
  version = $Version
  commit = $Commit
  builtAt = (Get-Date).ToString("s")
  updateSigningPublicKey = $UpdateSigningPublicKey
} | ConvertTo-Json | Set-Content -LiteralPath $VersionMetadata -Encoding UTF8

$ResolvedDist = [System.IO.Path]::GetFullPath($Dist).TrimEnd("\") + "\"
Get-CimInstance Win32_Process |
  Where-Object {
    $ExecutablePath = if ($_.ExecutablePath) {
      [System.IO.Path]::GetFullPath($_.ExecutablePath)
    } else {
      ""
    }
    ($_.Name -in @("LamaNotes.exe", "NirvNotes.exe") -and $ExecutablePath.StartsWith(
      $ResolvedDist,
      [System.StringComparison]::OrdinalIgnoreCase
    )) -or
    ($_.Name -eq "msedgewebview2.exe" -and $_.CommandLine -like "*$ResolvedDist*")
  } |
  ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
  }
Start-Sleep -Seconds 2

if (!(Test-Path $Python)) {
  python -m venv $Venv
  & $Python -m pip install --upgrade pip
}

& $Python -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")

Push-Location $Root
try {
  & npm run build
} finally {
  Pop-Location
}
if (!(Test-Path (Join-Path $ClientDist "index.html"))) {
  throw "Frontend build finished but $ClientDist\index.html was not created."
}

if (Test-Path $Dist) {
  Remove-Item -LiteralPath $Dist -Recurse -Force
}
if (Test-Path $Build) {
  Remove-Item -LiteralPath $Build -Recurse -Force
}

Push-Location $Root
try {
  & $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name $Name `
    --icon $Icon `
    --distpath $Dist `
    --workpath $Build `
    --specpath $Build `
    --add-data "$Icon;." `
    --add-data "$ClientDist;client\dist" `
    --add-data "$VersionMetadata;." `
    --add-data "$UpdaterScript;." `
    --add-data "$LegacyMigrationScript;." `
    $Entry
} finally {
  Pop-Location
  Remove-Item -LiteralPath $MetadataDir -Recurse -Force -ErrorAction SilentlyContinue
}

$Exe = Join-Path $Dist "$Name\$Name.exe"
if (!(Test-Path $Exe)) {
  throw "Build finished but $Exe was not created."
}

Write-Host "Built $Exe"
