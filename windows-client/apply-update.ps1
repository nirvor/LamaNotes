param(
  [Parameter(Mandatory = $true)][int]$ParentProcessId,
  [Parameter(Mandatory = $true)][string]$PackagePath,
  [Parameter(Mandatory = $true)][string]$InstallDir,
  [Parameter(Mandatory = $true)][string]$ExpectedSha256,
  [Parameter(Mandatory = $true)][string]$Version
)

$ErrorActionPreference = "Stop"
$UpdateRoot = Join-Path $env:LOCALAPPDATA "NirvNotes\updates"
$LogPath = Join-Path $UpdateRoot "apply-update.log"
$StageDir = Join-Path $UpdateRoot "stage"
$BackupDir = Join-Path $UpdateRoot "previous-app"
$InstalledExe = Join-Path $InstallDir "NirvNotes.exe"

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

function Restore-PreviousApp {
  $PreviousExe = Join-Path $BackupDir "NirvNotes.exe"
  $PreviousInternal = Join-Path $BackupDir "_internal"
  if (Test-Path -LiteralPath $PreviousExe) {
    Copy-Item -LiteralPath $PreviousExe -Destination (Join-Path $InstallDir "NirvNotes.exe") -Force
  }
  if (Test-Path -LiteralPath $PreviousInternal) {
    Copy-Item -LiteralPath $PreviousInternal -Destination (Join-Path $InstallDir "_internal") -Recurse -Force
  }
}

try {
  Assert-SafePaths
  Write-UpdateLog "Waiting for NirvNotes process $ParentProcessId."
  Wait-Process -Id $ParentProcessId -ErrorAction SilentlyContinue

  $OtherInstances = @(
    Get-CimInstance Win32_Process -Filter "Name = 'NirvNotes.exe'" -ErrorAction SilentlyContinue |
      Where-Object {
        $_.ExecutablePath -and
        [System.IO.Path]::GetFullPath($_.ExecutablePath) -ieq [System.IO.Path]::GetFullPath($InstalledExe)
      }
  )
  if ($OtherInstances.Count -gt 0) {
    Write-UpdateLog "Closing $($OtherInstances.Count) additional NirvNotes window(s)."
    foreach ($Process in $OtherInstances) {
      Stop-Process -Id $Process.ProcessId -Force -ErrorAction SilentlyContinue
      Wait-Process -Id $Process.ProcessId -Timeout 10 -ErrorAction SilentlyContinue
    }
  }

  $ActualHash = (Get-FileHash -LiteralPath $PackagePath -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($ActualHash -ne $ExpectedSha256.ToLowerInvariant()) {
    throw "Downloaded package hash does not match the update manifest."
  }

  Remove-Item -LiteralPath $StageDir -Recurse -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $BackupDir -Recurse -Force -ErrorAction SilentlyContinue
  New-Item -ItemType Directory -Path $StageDir -Force | Out-Null
  New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
  Expand-Archive -LiteralPath $PackagePath -DestinationPath $StageDir -Force

  $NewApp = Join-Path $StageDir "app"
  $NewExe = Join-Path $NewApp "NirvNotes.exe"
  if (-not (Test-Path -LiteralPath $NewExe)) {
    throw "The update package does not contain app\NirvNotes.exe."
  }

  $InstalledInternal = Join-Path $InstallDir "_internal"
  if (Test-Path -LiteralPath $InstalledExe) {
    Copy-Item -LiteralPath $InstalledExe -Destination $BackupDir -Force
  }
  if (Test-Path -LiteralPath $InstalledInternal) {
    Copy-Item -LiteralPath $InstalledInternal -Destination $BackupDir -Recurse -Force
  }

  try {
    Remove-Item -LiteralPath $InstalledExe -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $InstalledInternal -Recurse -Force -ErrorAction SilentlyContinue
    Copy-Item -Path (Join-Path $NewApp "*") -Destination $InstallDir -Recurse -Force
  } catch {
    Write-UpdateLog "Install failed. Restoring previous app."
    Remove-Item -LiteralPath $InstalledExe -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $InstalledInternal -Recurse -Force -ErrorAction SilentlyContinue
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
  Write-UpdateLog "Updated NirvNotes to $Version."
  Start-Process -FilePath $InstalledExe
} catch {
  Write-UpdateLog "Update failed: $($_.Exception.Message)"
  if (Test-Path -LiteralPath (Join-Path $InstallDir "NirvNotes.exe")) {
    Start-Process -FilePath (Join-Path $InstallDir "NirvNotes.exe")
  }
  exit 1
}
