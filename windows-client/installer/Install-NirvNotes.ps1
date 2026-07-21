param(
  [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "Programs\NirvNotes"),
  [string]$ServerUrl = "https://notes.thuber.org",
  [switch]$NoStartMenuShortcut,
  [switch]$NoDesktopShortcut,
  [switch]$NoFileAssociations,
  [switch]$NoLaunch,
  [switch]$SkipConnectivityCheck
)

$ErrorActionPreference = "Stop"

$AppName = "NirvNotes"
$ProgId = "NirvNotes.TextFile"
$Extensions = @(".md", ".txt", ".cfg", ".ini", ".json", ".yaml", ".yml", ".toml", ".xml", ".log", ".csv", ".tex")
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PackageVersion = "Win11 client"
$PackageManifestPath = Join-Path $ScriptRoot "installer-manifest.json"
if (Test-Path -LiteralPath $PackageManifestPath) {
  try {
    $PackageManifest = Get-Content -LiteralPath $PackageManifestPath -Raw | ConvertFrom-Json
    if ($PackageManifest.version) {
      $PackageVersion = [string]$PackageManifest.version
    }
  } catch {
    $PackageVersion = "Win11 client"
  }
}

function Write-Step([string]$Text) {
  Write-Host ""
  Write-Host "== $Text ==" -ForegroundColor Cyan
}

function Write-Ok([string]$Text) {
  Write-Host "OK  $Text" -ForegroundColor Green
}

function Write-Warn([string]$Text) {
  Write-Host "WARN $Text" -ForegroundColor Yellow
}

function Get-FullPath([string]$Path) {
  return [System.IO.Path]::GetFullPath($Path)
}

function Assert-SafeInstallDir([string]$Path) {
  $FullPath = Get-FullPath $Path
  $Forbidden = @(
    [System.IO.Path]::GetPathRoot($FullPath),
    [Environment]::GetFolderPath("UserProfile"),
    $env:LOCALAPPDATA,
    $env:APPDATA,
    [Environment]::GetFolderPath("Desktop")
  ) | Where-Object { $_ }

  foreach ($Item in $Forbidden) {
    if ($FullPath.TrimEnd("\") -ieq (Get-FullPath $Item).TrimEnd("\")) {
      throw "Refusing to install into unsafe directory: $FullPath"
    }
  }

  return $FullPath
}

function Get-AppSourceDir {
  $PackageSource = Join-Path $ScriptRoot "app"
  if (Test-Path (Join-Path $PackageSource "NirvNotes.exe")) {
    return (Resolve-Path $PackageSource).Path
  }

  $RepoSource = Join-Path (Split-Path $ScriptRoot -Parent) "dist\NirvNotes"
  if (Test-Path (Join-Path $RepoSource "NirvNotes.exe")) {
    return (Resolve-Path $RepoSource).Path
  }

  throw "Could not find packaged NirvNotes app. Expected app\NirvNotes.exe next to this installer."
}

function Stop-RunningApp {
  $Processes = Get-Process -Name "NirvNotes" -ErrorAction SilentlyContinue
  if ($Processes) {
    $Processes | Stop-Process -Force
    Start-Sleep -Seconds 2
    Write-Ok "Stopped running NirvNotes instance."
  }
}

function Copy-AppFiles(
  [string]$SourceDir,
  [string]$TargetDir,
  [bool]$InstallStartMenuShortcut,
  [bool]$InstallDesktopShortcut,
  [bool]$InstallFileAssociations
) {
  if (Test-Path $TargetDir) {
    Remove-Item -LiteralPath $TargetDir -Recurse -Force
  }

  New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
  Copy-Item -Path (Join-Path $SourceDir "*") -Destination $TargetDir -Recurse -Force
  Copy-Item -Path (Join-Path $ScriptRoot "Uninstall-NirvNotes.ps1") -Destination $TargetDir -Force

  $InstallInfo = [ordered]@{
    app = $AppName
    version = $PackageVersion
    serverUrl = $ServerUrl
    installedAt = (Get-Date).ToString("s")
    installDir = $TargetDir
    startMenuShortcut = $InstallStartMenuShortcut
    desktopShortcut = $InstallDesktopShortcut
    fileAssociations = $InstallFileAssociations
  }
  $InstallInfo | ConvertTo-Json | Set-Content -Path (Join-Path $TargetDir "install-info.json") -Encoding UTF8
}

function New-Shortcut([string]$ShortcutPath, [string]$TargetPath) {
  $Parent = Split-Path -Parent $ShortcutPath
  New-Item -ItemType Directory -Path $Parent -Force | Out-Null
  $Shell = New-Object -ComObject WScript.Shell
  $Shortcut = $Shell.CreateShortcut($ShortcutPath)
  $Shortcut.TargetPath = $TargetPath
  $Shortcut.WorkingDirectory = Split-Path -Parent $TargetPath
  $Shortcut.IconLocation = "$TargetPath,0"
  $Shortcut.Description = "NirvNotes"
  $Shortcut.Save()
}

function Register-FileAssociations([string]$ExePath) {
  $AppKey = "HKCU:\Software\Classes\$ProgId"
  $CommandKey = "$AppKey\shell\open\command"
  $IconKey = "$AppKey\DefaultIcon"
  $ApplicationsKey = "HKCU:\Software\Classes\Applications\NirvNotes.exe"

  New-Item -Path $AppKey -Force | Out-Null
  Set-Item -Path $AppKey -Value "Open with NirvNotes"
  New-ItemProperty -Path $AppKey -Name "FriendlyTypeName" -Value "NirvNotes text file" -PropertyType String -Force | Out-Null

  New-Item -Path $CommandKey -Force | Out-Null
  Set-Item -Path $CommandKey -Value "`"$ExePath`" `"%1`""
  New-Item -Path $IconKey -Force | Out-Null
  Set-Item -Path $IconKey -Value "`"$ExePath`",0"

  New-Item -Path "$ApplicationsKey\shell\open\command" -Force | Out-Null
  Set-Item -Path "$ApplicationsKey\shell\open\command" -Value "`"$ExePath`" `"%1`""
  New-Item -Path "$ApplicationsKey\SupportedTypes" -Force | Out-Null
  New-ItemProperty -Path $ApplicationsKey -Name "ApplicationName" -Value "NirvNotes" -PropertyType String -Force | Out-Null

  foreach ($Extension in $Extensions) {
    $ExtensionKey = "HKCU:\Software\Classes\$Extension\OpenWithProgids"
    New-Item -Path $ExtensionKey -Force | Out-Null
    New-ItemProperty -Path $ExtensionKey -Name $ProgId -Value ([byte[]]@()) -PropertyType Binary -Force | Out-Null

    $OpenWithListKey = "HKCU:\Software\Classes\$Extension\OpenWithList\NirvNotes.exe"
    New-Item -Path $OpenWithListKey -Force | Out-Null

    New-ItemProperty -Path "$ApplicationsKey\SupportedTypes" -Name $Extension -Value "" -PropertyType String -Force | Out-Null
  }
}

function Register-Uninstaller([string]$ExePath, [string]$TargetDir) {
  $UninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\NirvNotes"
  $UninstallScript = Join-Path $TargetDir "Uninstall-NirvNotes.ps1"
  $UninstallCommand = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$UninstallScript`""
  $EstimatedSize = [int](([System.IO.Directory]::EnumerateFiles($TargetDir, "*", "AllDirectories") |
    ForEach-Object { (Get-Item $_).Length } |
    Measure-Object -Sum).Sum / 1KB)

  New-Item -Path $UninstallKey -Force | Out-Null
  New-ItemProperty -Path $UninstallKey -Name "DisplayName" -Value "NirvNotes" -PropertyType String -Force | Out-Null
  New-ItemProperty -Path $UninstallKey -Name "DisplayVersion" -Value $PackageVersion -PropertyType String -Force | Out-Null
  New-ItemProperty -Path $UninstallKey -Name "Publisher" -Value "NirvNotes" -PropertyType String -Force | Out-Null
  New-ItemProperty -Path $UninstallKey -Name "InstallLocation" -Value $TargetDir -PropertyType String -Force | Out-Null
  New-ItemProperty -Path $UninstallKey -Name "DisplayIcon" -Value "$ExePath,0" -PropertyType String -Force | Out-Null
  New-ItemProperty -Path $UninstallKey -Name "UninstallString" -Value $UninstallCommand -PropertyType String -Force | Out-Null
  New-ItemProperty -Path $UninstallKey -Name "NoModify" -Value 1 -PropertyType DWord -Force | Out-Null
  New-ItemProperty -Path $UninstallKey -Name "NoRepair" -Value 1 -PropertyType DWord -Force | Out-Null
  New-ItemProperty -Path $UninstallKey -Name "EstimatedSize" -Value $EstimatedSize -PropertyType DWord -Force | Out-Null
}

function Register-AppPath([string]$ExePath, [string]$TargetDir) {
  $AppPathKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\App Paths\NirvNotes.exe"
  New-Item -Path $AppPathKey -Force | Out-Null
  Set-Item -Path $AppPathKey -Value $ExePath
  New-ItemProperty -Path $AppPathKey -Name "Path" -Value $TargetDir -PropertyType String -Force | Out-Null
}

function Test-Connectivity {
  if ($SkipConnectivityCheck) {
    Write-Warn "Skipped cloud connectivity check."
    return
  }

  Write-Step "Connectivity check"
  $HealthUrl = $ServerUrl.TrimEnd("/") + "/health"
  try {
    $Health = & curl.exe -s -S --max-time 8 $HealthUrl 2>$null
    if ($LASTEXITCODE -eq 0 -and $Health -match "OK") {
      Write-Ok "NirvNotes cloud endpoint reachable over HTTPS."
    } else {
      Write-Warn "Cloud endpoint did not return OK from $HealthUrl."
    }
  } catch {
    Write-Warn "Could not reach $HealthUrl. Install continues; check the network before first login."
  }
}

$InstallDir = Assert-SafeInstallDir $InstallDir
$AppSource = Get-AppSourceDir
$ExePath = Join-Path $InstallDir "NirvNotes.exe"

Write-Step "Installing NirvNotes"
Write-Host "Source: $AppSource"
Write-Host "Target: $InstallDir"

Stop-RunningApp
Copy-AppFiles `
  -SourceDir $AppSource `
  -TargetDir $InstallDir `
  -InstallStartMenuShortcut (-not $NoStartMenuShortcut) `
  -InstallDesktopShortcut (-not $NoDesktopShortcut) `
  -InstallFileAssociations (-not $NoFileAssociations)
Write-Ok "Copied app files."

$StartMenuShortcut = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\NirvNotes.lnk"
if (-not $NoStartMenuShortcut) {
  New-Shortcut -ShortcutPath $StartMenuShortcut -TargetPath $ExePath
  Write-Ok "Created Start Menu shortcut."
}

if (-not $NoDesktopShortcut) {
  $DesktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "NirvNotes.lnk"
  New-Shortcut -ShortcutPath $DesktopShortcut -TargetPath $ExePath
  Write-Ok "Created Desktop shortcut."
}

if (-not $NoFileAssociations) {
  Register-FileAssociations -ExePath $ExePath
  Write-Ok "Registered supported text and configuration formats as Open With targets."
}

Register-Uninstaller -ExePath $ExePath -TargetDir $InstallDir
Register-AppPath -ExePath $ExePath -TargetDir $InstallDir
Write-Ok "Registered Windows app metadata and uninstaller."

Test-Connectivity

if (-not $NoLaunch) {
  Start-Process -FilePath $ExePath
  Write-Ok "Started NirvNotes."
}

Write-Step "Done"
Write-Host "NirvNotes is installed for this Windows user."
Write-Host "If Windows asks for the default app once, choose NirvNotes for the wanted text/config format."
