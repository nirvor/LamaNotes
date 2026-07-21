param(
  [Parameter(Mandatory = $true)][int]$ParentProcessId,
  [Parameter(Mandatory = $true)][string]$PackagePath,
  [Parameter(Mandatory = $true)][string]$InstallDir,
  [Parameter(Mandatory = $true)][string]$ExpectedSha256,
  [Parameter(Mandatory = $true)][string]$Version,
  [switch]$SkipLaunch
)

$ErrorActionPreference = "Stop"
$UpdateRoot = Join-Path $env:LOCALAPPDATA "NirvNotes\updates"
$LogPath = Join-Path $UpdateRoot "apply-update.log"
$SafeVersion = $Version -replace "[^A-Za-z0-9._-]", "_"
$SessionKey = "$SafeVersion-$ParentProcessId-$PID"
$StageDir = Join-Path $UpdateRoot "stage-$SessionKey"
$BackupDir = Join-Path $UpdateRoot "previous-app-$SessionKey"
$NextAppDir = Join-Path $UpdateRoot "next-app-$SessionKey"
$InstalledExe = Join-Path $InstallDir "NirvNotes.exe"
$InstalledInternal = Join-Path $InstallDir "_internal"

New-Item -ItemType Directory -Path $UpdateRoot -Force | Out-Null

function Write-UpdateLog([string]$Message) {
  $Line = "{0} {1}" -f (Get-Date -Format "s"), $Message
  Add-Content -LiteralPath $LogPath -Value $Line -Encoding UTF8
}

function Assert-SafePaths {
  $ResolvedInstall = [System.IO.Path]::GetFullPath($InstallDir).TrimEnd("\")
  $ResolvedLocalAppData = [System.IO.Path]::GetFullPath($env:LOCALAPPDATA).TrimEnd("\")
  $ResolvedPackage = [System.IO.Path]::GetFullPath($PackagePath)
  $ResolvedUpdateRoot = [System.IO.Path]::GetFullPath($UpdateRoot).TrimEnd("\")

  if (-not $ResolvedInstall.StartsWith($ResolvedLocalAppData + "\", [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Update target must stay inside LOCALAPPDATA."
  }
  if ($ResolvedInstall -ieq $ResolvedLocalAppData) {
    throw "Refusing to update the LOCALAPPDATA root."
  }
  if (-not $ResolvedPackage.StartsWith($ResolvedUpdateRoot + "\", [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Update package must stay inside the NirvNotes update directory."
  }
}

function Get-InstalledAppProcesses {
  $ResolvedExe = [System.IO.Path]::GetFullPath($InstalledExe)
  return @(
    Get-CimInstance Win32_Process -Filter "Name = 'NirvNotes.exe'" -ErrorAction SilentlyContinue |
      Where-Object {
        $_.ExecutablePath -and
        [System.IO.Path]::GetFullPath($_.ExecutablePath) -ieq $ResolvedExe
      }
  )
}

function Stop-InstalledAppProcesses {
  $Deadline = (Get-Date).AddSeconds(30)
  do {
    $Processes = @(Get-InstalledAppProcesses)
    if ($Processes.Count -eq 0) {
      return
    }

    Write-UpdateLog "Closing $($Processes.Count) remaining NirvNotes process(es)."
    foreach ($Process in $Processes) {
      Stop-Process -Id $Process.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Milliseconds 300
  } while ((Get-Date) -lt $Deadline)

  $Remaining = @(Get-InstalledAppProcesses)
  if ($Remaining.Count -gt 0) {
    throw "NirvNotes did not close completely before the update."
  }
}

function Get-RequiredAppFiles([string]$Root) {
  return @(
    (Join-Path $Root "NirvNotes.exe"),
    (Join-Path $Root "_internal\client-version.json"),
    (Join-Path $Root "_internal\webview\lib\runtimes\win-arm64\native\WebView2Loader.dll"),
    (Join-Path $Root "_internal\webview\lib\runtimes\win-x64\native\WebView2Loader.dll"),
    (Join-Path $Root "_internal\webview\lib\runtimes\win-x86\native\WebView2Loader.dll")
  )
}

function Assert-AppPayload([string]$Root, [string]$Label) {
  $Missing = @(Get-RequiredAppFiles $Root | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) })
  if ($Missing.Count -gt 0) {
    throw "$Label is incomplete: $($Missing -join ', ')"
  }
}

function Copy-AppContents([string]$Source, [string]$Destination) {
  New-Item -ItemType Directory -Path $Destination -Force | Out-Null
  Copy-Item -Path (Join-Path $Source "*") -Destination $Destination -Recurse -Force
}

function Restore-PreviousApp {
  Stop-InstalledAppProcesses
  Remove-Item -LiteralPath $InstalledExe -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $InstalledInternal -Recurse -Force -ErrorAction SilentlyContinue
  if (Test-Path -LiteralPath $BackupDir) {
    Copy-AppContents $BackupDir $InstallDir
    Assert-AppPayload $InstallDir "Restored NirvNotes app"
  }
}

try {
  Assert-SafePaths
  Write-UpdateLog "Waiting for NirvNotes process $ParentProcessId."
  Wait-Process -Id $ParentProcessId -Timeout 15 -ErrorAction SilentlyContinue
  Stop-InstalledAppProcesses

  $ActualHash = (Get-FileHash -LiteralPath $PackagePath -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($ActualHash -ne $ExpectedSha256.ToLowerInvariant()) {
    throw "Downloaded package hash does not match the update manifest."
  }

  Remove-Item -LiteralPath $StageDir -Recurse -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $BackupDir -Recurse -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $NextAppDir -Recurse -Force -ErrorAction SilentlyContinue
  New-Item -ItemType Directory -Path $StageDir -Force | Out-Null
  New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
  Expand-Archive -LiteralPath $PackagePath -DestinationPath $StageDir -Force

  $NewApp = Join-Path $StageDir "app"
  Assert-AppPayload $NewApp "Downloaded NirvNotes app"
  Copy-AppContents $NewApp $NextAppDir
  Assert-AppPayload $NextAppDir "Staged NirvNotes app"

  if (Test-Path -LiteralPath $InstalledExe) {
    Copy-Item -LiteralPath $InstalledExe -Destination $BackupDir -Force
  }
  if (Test-Path -LiteralPath $InstalledInternal) {
    New-Item -ItemType Directory -Path (Join-Path $BackupDir "_internal") -Force | Out-Null
    Copy-Item -Path (Join-Path $InstalledInternal "*") -Destination (Join-Path $BackupDir "_internal") -Recurse -Force
  }
  Assert-AppPayload $BackupDir "NirvNotes rollback backup"

  try {
    Remove-Item -LiteralPath $InstalledExe -Force
    Remove-Item -LiteralPath $InstalledInternal -Recurse -Force
    Copy-AppContents $NextAppDir $InstallDir
    Assert-AppPayload $InstallDir "Installed NirvNotes app"
  } catch {
    Write-UpdateLog "Install failed. Restoring previous app."
    Restore-PreviousApp
    throw
  }

  $InstallInfoPath = Join-Path $InstallDir "install-info.json"
  if (Test-Path -LiteralPath $InstallInfoPath) {
    try {
      $InstallInfo = Get-Content -LiteralPath $InstallInfoPath -Raw | ConvertFrom-Json
      $InstallInfo | Add-Member -NotePropertyName version -NotePropertyValue $Version -Force
      $InstallInfo | Add-Member -NotePropertyName updatedAt -NotePropertyValue (Get-Date).ToString("s") -Force
      $InstallInfo | ConvertTo-Json | Set-Content -LiteralPath $InstallInfoPath -Encoding UTF8
    } catch {
      Write-UpdateLog "Could not update install-info.json."
    }
  }

  $UninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\NirvNotes"
  if (Test-Path -LiteralPath $UninstallKey) {
    New-ItemProperty -Path $UninstallKey -Name DisplayVersion -Value $Version -PropertyType String -Force | Out-Null
  }

  Remove-Item -LiteralPath $BackupDir -Recurse -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $StageDir -Recurse -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $NextAppDir -Recurse -Force -ErrorAction SilentlyContinue
  Write-UpdateLog "Updated NirvNotes to $Version."
  if (-not $SkipLaunch) {
    Start-Process -FilePath $InstalledExe
  }
} catch {
  Write-UpdateLog "Update failed: $($_.Exception.Message)"
  if (-not $SkipLaunch) {
    try {
      Assert-AppPayload $InstallDir "Recoverable NirvNotes app"
      Start-Process -FilePath $InstalledExe
    } catch {
      Write-UpdateLog "NirvNotes was not restarted because its payload is incomplete."
    }
  }
  exit 1
}
