param(
  [Parameter(Mandatory = $true)][int]$ParentProcessId,
  [Parameter(Mandatory = $true)][string]$LegacyInstallDir,
  [Parameter(Mandatory = $true)][string]$InstallDir,
  [switch]$TestMode
)

$ErrorActionPreference = "Stop"
$AppName = "LamaNotes"
$LegacyAppName = "NirvNotes"
$ProgId = "LamaNotes.TextFile"
$LegacyProgId = "NirvNotes.TextFile"
$Extensions = @(".md", ".txt", ".cfg", ".ini", ".json", ".yaml", ".yml", ".toml", ".xml", ".log", ".csv", ".tex")
$LocalPrograms = [System.IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA "Programs")).TrimEnd("\")
$LegacyInstallDir = [System.IO.Path]::GetFullPath($LegacyInstallDir).TrimEnd("\")
$InstallDir = [System.IO.Path]::GetFullPath($InstallDir).TrimEnd("\")
$MigrationRoot = Join-Path $env:LOCALAPPDATA "LamaNotes\migration"
$LogPath = Join-Path $env:LOCALAPPDATA "LamaNotes\logs\product-migration.log"
$StageDir = Join-Path $LocalPrograms ".LamaNotes-migration-$PID"
$BackupDir = Join-Path $MigrationRoot "previous-target-$PID"
$ExePath = Join-Path $InstallDir "LamaNotes.exe"

New-Item -ItemType Directory -Path (Split-Path -Parent $LogPath) -Force | Out-Null
New-Item -ItemType Directory -Path $MigrationRoot -Force | Out-Null

function Write-MigrationLog([string]$Message) {
  Add-Content -LiteralPath $LogPath -Value ("{0} {1}" -f (Get-Date -Format "s"), $Message) -Encoding UTF8
}

function Assert-SafePaths {
  foreach ($Path in @($LegacyInstallDir, $InstallDir, $StageDir)) {
    if (-not $Path.StartsWith($LocalPrograms + "\", [System.StringComparison]::OrdinalIgnoreCase)) {
      throw "Migration paths must stay inside LOCALAPPDATA\Programs."
    }
  }
  if ((Split-Path -Leaf $LegacyInstallDir) -ine $LegacyAppName) {
    throw "Legacy source directory is not the expected application directory."
  }
  if ((Split-Path -Leaf $InstallDir) -ine $AppName) {
    throw "Migration target directory is not the expected application directory."
  }
  if ($LegacyInstallDir -ieq $InstallDir) {
    throw "Legacy source and LamaNotes target must differ."
  }
}

function Remove-RegistryPath([string]$Path) {
  if (Test-Path -LiteralPath $Path) {
    Remove-Item -LiteralPath $Path -Recurse -Force
  }
}

function New-Shortcut([string]$ShortcutPath, [string]$TargetPath) {
  New-Item -ItemType Directory -Path (Split-Path -Parent $ShortcutPath) -Force | Out-Null
  $Shell = New-Object -ComObject WScript.Shell
  $Shortcut = $Shell.CreateShortcut($ShortcutPath)
  $Shortcut.TargetPath = $TargetPath
  $Shortcut.WorkingDirectory = Split-Path -Parent $TargetPath
  $Shortcut.IconLocation = "$TargetPath,0"
  $Shortcut.Description = $AppName
  $Shortcut.Save()
}

function Register-Application {
  $AppKey = "HKCU:\Software\Classes\$ProgId"
  $ApplicationsKey = "HKCU:\Software\Classes\Applications\LamaNotes.exe"
  New-Item -Path "$AppKey\shell\open\command" -Force | Out-Null
  Set-Item -Path $AppKey -Value "Open with LamaNotes"
  New-ItemProperty -Path $AppKey -Name FriendlyTypeName -Value "LamaNotes text file" -PropertyType String -Force | Out-Null
  Set-Item -Path "$AppKey\shell\open\command" -Value "`"$ExePath`" `"%1`""
  New-Item -Path "$AppKey\DefaultIcon" -Force | Out-Null
  Set-Item -Path "$AppKey\DefaultIcon" -Value "`"$ExePath`",0"

  New-Item -Path "$ApplicationsKey\shell\open\command" -Force | Out-Null
  Set-Item -Path "$ApplicationsKey\shell\open\command" -Value "`"$ExePath`" `"%1`""
  New-Item -Path "$ApplicationsKey\SupportedTypes" -Force | Out-Null
  New-ItemProperty -Path $ApplicationsKey -Name ApplicationName -Value $AppName -PropertyType String -Force | Out-Null
  foreach ($Extension in $Extensions) {
    $OpenWithProgids = "HKCU:\Software\Classes\$Extension\OpenWithProgids"
    New-Item -Path $OpenWithProgids -Force | Out-Null
    New-ItemProperty -Path $OpenWithProgids -Name $ProgId -Value ([byte[]]@()) -PropertyType Binary -Force | Out-Null
    New-Item -Path "HKCU:\Software\Classes\$Extension\OpenWithList\LamaNotes.exe" -Force | Out-Null
    New-ItemProperty -Path "$ApplicationsKey\SupportedTypes" -Name $Extension -Value "" -PropertyType String -Force | Out-Null
  }

  $AppPathKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\App Paths\LamaNotes.exe"
  New-Item -Path $AppPathKey -Force | Out-Null
  Set-Item -Path $AppPathKey -Value $ExePath
  New-ItemProperty -Path $AppPathKey -Name Path -Value $InstallDir -PropertyType String -Force | Out-Null

  $UninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\LamaNotes"
  $UninstallScript = Join-Path $InstallDir "Uninstall-LamaNotes.ps1"
  New-Item -Path $UninstallKey -Force | Out-Null
  New-ItemProperty -Path $UninstallKey -Name DisplayName -Value $AppName -PropertyType String -Force | Out-Null
  New-ItemProperty -Path $UninstallKey -Name Publisher -Value $AppName -PropertyType String -Force | Out-Null
  New-ItemProperty -Path $UninstallKey -Name InstallLocation -Value $InstallDir -PropertyType String -Force | Out-Null
  New-ItemProperty -Path $UninstallKey -Name DisplayIcon -Value "$ExePath,0" -PropertyType String -Force | Out-Null
  New-ItemProperty -Path $UninstallKey -Name UninstallString -Value "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$UninstallScript`"" -PropertyType String -Force | Out-Null
  New-ItemProperty -Path $UninstallKey -Name NoModify -Value 1 -PropertyType DWord -Force | Out-Null
  New-ItemProperty -Path $UninstallKey -Name NoRepair -Value 1 -PropertyType DWord -Force | Out-Null
}

function Remove-LegacyRegistration {
  Remove-RegistryPath "HKCU:\Software\Classes\$LegacyProgId"
  Remove-RegistryPath "HKCU:\Software\Classes\Applications\NirvNotes.exe"
  Remove-RegistryPath "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\NirvNotes"
  Remove-RegistryPath "HKCU:\Software\Microsoft\Windows\CurrentVersion\App Paths\NirvNotes.exe"
  foreach ($Extension in $Extensions) {
    $OpenWithProgids = "HKCU:\Software\Classes\$Extension\OpenWithProgids"
    if (Test-Path -LiteralPath $OpenWithProgids) {
      Remove-ItemProperty -Path $OpenWithProgids -Name $LegacyProgId -ErrorAction SilentlyContinue
    }
    Remove-RegistryPath "HKCU:\Software\Classes\$Extension\OpenWithList\NirvNotes.exe"
  }
}

function Update-Shortcuts {
  $Desktop = [Environment]::GetFolderPath("Desktop")
  $StartMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
  Remove-Item -LiteralPath (Join-Path $Desktop "NirvNotes.lnk") -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath (Join-Path $StartMenu "NirvNotes.lnk") -Force -ErrorAction SilentlyContinue
  New-Shortcut (Join-Path $Desktop "LamaNotes.lnk") $ExePath
  New-Shortcut (Join-Path $StartMenu "LamaNotes.lnk") $ExePath

  $PinnedShortcut = Join-Path $env:APPDATA "Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar\NirvNotes.lnk"
  if (Test-Path -LiteralPath $PinnedShortcut) {
    New-Shortcut $PinnedShortcut $ExePath
  }
}

function Remove-DirectoryWithRetry([string]$Path) {
  for ($Attempt = 0; $Attempt -lt 12; $Attempt++) {
    Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction SilentlyContinue
    if (-not (Test-Path -LiteralPath $Path)) {
      return
    }
    Start-Sleep -Milliseconds 500
  }
  throw "Could not remove the previous application directory."
}

try {
  Assert-SafePaths
  Write-MigrationLog "Waiting for the previous desktop process."
  Wait-Process -Id $ParentProcessId -Timeout 20 -ErrorAction SilentlyContinue

  if (-not (Test-Path -LiteralPath (Join-Path $LegacyInstallDir "LamaNotes.exe") -PathType Leaf)) {
    throw "The migration package does not contain LamaNotes.exe."
  }

  Remove-Item -LiteralPath $StageDir -Recurse -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $BackupDir -Recurse -Force -ErrorAction SilentlyContinue
  New-Item -ItemType Directory -Path $StageDir -Force | Out-Null
  Copy-Item -Path (Join-Path $LegacyInstallDir "*") -Destination $StageDir -Recurse -Force
  Remove-Item -LiteralPath (Join-Path $StageDir "NirvNotes.exe") -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath (Join-Path $StageDir "Uninstall-NirvNotes.ps1") -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath (Join-Path $StageDir "install-info.json") -Force -ErrorAction SilentlyContinue

  if (-not (Test-Path -LiteralPath (Join-Path $StageDir "LamaNotes.exe") -PathType Leaf)) {
    throw "The staged LamaNotes executable is missing."
  }
  if (-not (Test-Path -LiteralPath (Join-Path $StageDir "_internal\client-version.json") -PathType Leaf)) {
    throw "The staged LamaNotes runtime is incomplete."
  }

  if (Test-Path -LiteralPath $InstallDir) {
    New-Item -ItemType Directory -Path (Split-Path -Parent $BackupDir) -Force | Out-Null
    Move-Item -LiteralPath $InstallDir -Destination $BackupDir
  }
  Move-Item -LiteralPath $StageDir -Destination $InstallDir

  [ordered]@{
    app = $AppName
    migratedAt = (Get-Date).ToString("s")
    installDir = $InstallDir
    serverUrl = "https://notes.thuber.org"
    startMenuShortcut = $true
    desktopShortcut = $true
    fileAssociations = $true
  } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $InstallDir "install-info.json") -Encoding UTF8

  if (-not $TestMode) {
    Register-Application
    Remove-LegacyRegistration
    Update-Shortcuts

    $Process = Start-Process -FilePath $ExePath -PassThru
    Start-Sleep -Seconds 3
    if ($Process.HasExited -and $Process.ExitCode -ne 0) {
      throw "LamaNotes did not start after migration."
    }
  }

  Remove-DirectoryWithRetry $LegacyInstallDir
  Remove-Item -LiteralPath $BackupDir -Recurse -Force -ErrorAction SilentlyContinue
  Write-MigrationLog "Product migration completed."
} catch {
  Write-MigrationLog "Product migration failed: $($_.Exception.Message)"
  if (-not (Test-Path -LiteralPath $InstallDir) -and (Test-Path -LiteralPath $BackupDir)) {
    Move-Item -LiteralPath $BackupDir -Destination $InstallDir -ErrorAction SilentlyContinue
  }
  exit 1
}
