param(
  [string]$Name = "NirvNotes",
  [string]$Version = "",
  [string]$Commit = ""
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Venv = Join-Path $PSScriptRoot ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"
$Icon = Join-Path $Root "client\assets\favicon.ico"
$Entry = Join-Path $PSScriptRoot "nirvnotes_client.py"
$Dist = Join-Path $PSScriptRoot "dist"
$Build = Join-Path $PSScriptRoot "build"
$UpdaterScript = Join-Path $PSScriptRoot "apply-update.ps1"
$ClientDist = Join-Path $Root "client\dist"
$MetadataDir = Join-Path $env:TEMP "NirvNotes-build-metadata-$PID"
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

New-Item -ItemType Directory -Path $MetadataDir -Force | Out-Null
[ordered]@{
  version = $Version
  commit = $Commit
  builtAt = (Get-Date).ToString("s")
} | ConvertTo-Json | Set-Content -LiteralPath $VersionMetadata -Encoding UTF8

Get-CimInstance Win32_Process |
  Where-Object {
    $_.Name -eq "NirvNotes.exe" -or
    ($_.Name -eq "msedgewebview2.exe" -and $_.CommandLine -like "*NirvNotes.exe*")
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
    --add-data "$Icon;client\assets" `
    --add-data "$ClientDist;client\dist" `
    --add-data "$VersionMetadata;." `
    --add-data "$UpdaterScript;." `
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
