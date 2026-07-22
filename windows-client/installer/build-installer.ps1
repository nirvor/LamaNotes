param(
  [string]$Version = "",
  [switch]$SkipAppBuild
)

$ErrorActionPreference = "Stop"

$InstallerRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$WindowsClientRoot = Split-Path -Parent $InstallerRoot
$RepoRoot = Split-Path -Parent $WindowsClientRoot
$ArtifactsDir = Join-Path $InstallerRoot "artifacts"
$BuildDir = Join-Path $InstallerRoot "build"
$StageDir = Join-Path $BuildDir "LamaNotes-win11"
$AppDist = Join-Path $WindowsClientRoot "dist\LamaNotes"

function Write-Step([string]$Text) {
  Write-Host ""
  Write-Host "== $Text ==" -ForegroundColor Cyan
}

function Get-GitValue([string]$ArgsLine) {
  try {
    $Value = & git $ArgsLine.Split(" ") 2>$null
    if ($LASTEXITCODE -eq 0) {
      return ($Value | Select-Object -First 1)
    }
  } catch {
    return ""
  }
  return ""
}

Push-Location $RepoRoot
try {
  if (-not $Version) {
    $Version = Get-GitValue "rev-parse --short HEAD"
    if (-not $Version) {
      $Version = Get-Date -Format "yyyyMMdd-HHmmss"
    }
  }

  $Commit = Get-GitValue "rev-parse HEAD"

  if (-not $SkipAppBuild) {
    Write-Step "Building Windows app"
    & (Join-Path $WindowsClientRoot "build.ps1") -Version $Version -Commit $Commit
  }

  if (!(Test-Path (Join-Path $AppDist "LamaNotes.exe"))) {
    throw "Missing app build at $AppDist. Run windows-client\build.ps1 first."
  }

  Write-Step "Staging installer package"
  Remove-Item -LiteralPath $StageDir -Recurse -Force -ErrorAction SilentlyContinue
  New-Item -ItemType Directory -Path (Join-Path $StageDir "app") -Force | Out-Null
  New-Item -ItemType Directory -Path $ArtifactsDir -Force | Out-Null

  foreach ($StaleFile in Get-ChildItem -Path $ArtifactsDir -File -Filter "LamaNotes-Setup-*.exe" -ErrorAction SilentlyContinue) {
    Remove-Item -LiteralPath $StaleFile.FullName -Force
  }
  foreach ($StaleFile in Get-ChildItem -Path $ArtifactsDir -File -Filter "LamaNotes-win11-*.zip" -ErrorAction SilentlyContinue) {
    Remove-Item -LiteralPath $StaleFile.FullName -Force
  }
  foreach ($StaleFile in Get-ChildItem -Path $ArtifactsDir -File -Filter "NirvNotes-*" -ErrorAction SilentlyContinue) {
    Remove-Item -LiteralPath $StaleFile.FullName -Force
  }
  foreach ($AccidentalExtract in @(
    "app",
    "Install-LamaNotes.cmd",
    "Install-LamaNotes.ps1",
    "Uninstall-LamaNotes.ps1",
    "README.md",
    "installer-manifest.json"
  )) {
    Remove-Item -LiteralPath (Join-Path $ArtifactsDir $AccidentalExtract) -Recurse -Force -ErrorAction SilentlyContinue
  }

  Copy-Item -Path (Join-Path $AppDist "*") -Destination (Join-Path $StageDir "app") -Recurse -Force
  Copy-Item -LiteralPath (Join-Path $AppDist "LamaNotes.exe") -Destination (Join-Path $StageDir "app\NirvNotes.exe") -Force
  Copy-Item -LiteralPath (Join-Path $InstallerRoot "Uninstall-LamaNotes.ps1") -Destination (Join-Path $StageDir "app") -Force
  Copy-Item -Path (Join-Path $InstallerRoot "Install-LamaNotes.ps1") -Destination $StageDir -Force
  Copy-Item -Path (Join-Path $InstallerRoot "Install-LamaNotes.cmd") -Destination $StageDir -Force
  Copy-Item -Path (Join-Path $InstallerRoot "Uninstall-LamaNotes.ps1") -Destination $StageDir -Force
  Copy-Item -Path (Join-Path $InstallerRoot "README.md") -Destination $StageDir -Force

  $Manifest = [ordered]@{
    name = "LamaNotes Win11 installer"
    version = $Version
    commit = $Commit
    builtAt = (Get-Date).ToString("s")
    defaultServerUrl = "https://notes.thuber.org"
    installCommand = "Install-LamaNotes.cmd"
    legacyUpdateBridge = $true
  }
  $Manifest | ConvertTo-Json | Set-Content -Path (Join-Path $StageDir "installer-manifest.json") -Encoding UTF8

  Write-Step "Writing ZIP"
  $ZipPath = Join-Path $ArtifactsDir "LamaNotes-win11-$Version.zip"
  Remove-Item -LiteralPath $ZipPath -Force -ErrorAction SilentlyContinue
  Compress-Archive -Path (Join-Path $StageDir "*") -DestinationPath $ZipPath -Force
  Write-Host $ZipPath

  $PackageHash = (Get-FileHash -LiteralPath $ZipPath -Algorithm SHA256).Hash.ToLowerInvariant()
  $PackageInfo = Get-Item -LiteralPath $ZipPath
  $UpdateManifest = [ordered]@{
    version = $Version
    commit = $Commit
    file = $PackageInfo.Name
    sha256 = $PackageHash
    size = $PackageInfo.Length
    publishedAt = (Get-Date).ToString("s")
  }
  $UpdateManifest | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $ArtifactsDir "LamaNotes-update.json") -Encoding UTF8

  Write-Step "Done"
  Get-ChildItem $ArtifactsDir | Sort-Object LastWriteTime -Descending | Select-Object Name,Length,LastWriteTime
} finally {
  Pop-Location
}
