param(
  [string]$InstallDir = (Split-Path -Parent $MyInvocation.MyCommand.Path),
  [switch]$RemoveUserData
)

$ErrorActionPreference = "Stop"

$ProgId = "LamaNotes.TextFile"
$Extensions = @(".md", ".txt", ".cfg", ".ini", ".json", ".yaml", ".yml", ".toml", ".xml", ".log", ".csv", ".tex")

function Write-Step([string]$Text) {
  Write-Host ""
  Write-Host "== $Text ==" -ForegroundColor Cyan
}

function Remove-IfExists([string]$Path) {
  if (Test-Path $Path) {
    Remove-Item -LiteralPath $Path -Force -Recurse
  }
}

function Remove-RegistryPath([string]$Path) {
  if (Test-Path $Path) {
    Remove-Item -Path $Path -Recurse -Force
  }
}

function Unregister-FileAssociations {
  Remove-RegistryPath "HKCU:\Software\Classes\$ProgId"
  Remove-RegistryPath "HKCU:\Software\Classes\Applications\LamaNotes.exe"

  foreach ($Extension in $Extensions) {
    $OpenWithProgids = "HKCU:\Software\Classes\$Extension\OpenWithProgids"
    if (Test-Path $OpenWithProgids) {
      Remove-ItemProperty -Path $OpenWithProgids -Name $ProgId -ErrorAction SilentlyContinue
    }

    Remove-RegistryPath "HKCU:\Software\Classes\$Extension\OpenWithList\LamaNotes.exe"
  }
}

$InstallInfoPath = Join-Path $InstallDir "install-info.json"
$ShouldUnregisterFileAssociations = $true
$ShouldRemoveStartMenuShortcut = $true
$ShouldRemoveDesktopShortcut = $true
if (Test-Path $InstallInfoPath) {
  try {
    $InstallInfo = Get-Content -Path $InstallInfoPath -Raw | ConvertFrom-Json
    if ($InstallInfo.fileAssociations -eq $false) {
      $ShouldUnregisterFileAssociations = $false
    }
    if ($InstallInfo.startMenuShortcut -eq $false) {
      $ShouldRemoveStartMenuShortcut = $false
    }
    if ($InstallInfo.desktopShortcut -eq $false) {
      $ShouldRemoveDesktopShortcut = $false
    }
  } catch {
    $ShouldUnregisterFileAssociations = $true
    $ShouldRemoveStartMenuShortcut = $true
    $ShouldRemoveDesktopShortcut = $true
  }
}

Write-Step "Uninstalling LamaNotes"

Get-Process -Name "LamaNotes" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 1

if ($ShouldRemoveStartMenuShortcut) {
  Remove-IfExists (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\LamaNotes.lnk")
}
if ($ShouldRemoveDesktopShortcut) {
  Remove-IfExists (Join-Path ([Environment]::GetFolderPath("Desktop")) "LamaNotes.lnk")
}

if ($ShouldUnregisterFileAssociations) {
  Unregister-FileAssociations
}
Remove-RegistryPath "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\LamaNotes"
Remove-RegistryPath "HKCU:\Software\Microsoft\Windows\CurrentVersion\App Paths\LamaNotes.exe"

if ($RemoveUserData) {
  Remove-IfExists (Join-Path $env:LOCALAPPDATA "LamaNotes\WebView2")
  Remove-IfExists (Join-Path $env:LOCALAPPDATA "LamaNotes\window-state.json")
}

$FullInstallDir = [System.IO.Path]::GetFullPath($InstallDir)
if (Test-Path $FullInstallDir) {
  $Command = "timeout /t 2 /nobreak >nul & rmdir /s /q `"$FullInstallDir`""
  Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $Command -WindowStyle Hidden
}

Write-Host "LamaNotes uninstall requested. Program files will be removed after this window closes."
if (-not $RemoveUserData) {
  Write-Host "WebView2 login/session data was kept. Use -RemoveUserData to remove it too."
}
