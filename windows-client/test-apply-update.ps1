param(
  [string]$SourceApp = (Join-Path $PSScriptRoot "dist\NirvNotes")
)

$ErrorActionPreference = "Stop"
$TestId = [Guid]::NewGuid().ToString("N")
$InstallDir = Join-Path $env:LOCALAPPDATA "NirvNotesUpdaterTest-$TestId"
$PayloadRoot = Join-Path $env:TEMP "NirvNotesUpdaterPayload-$TestId"
$PackagePath = Join-Path $env:LOCALAPPDATA "NirvNotes\updates\updater-test-$TestId.zip"
$TestProcesses = @()

try {
  if (-not (Test-Path -LiteralPath (Join-Path $SourceApp "NirvNotes.exe"))) {
    throw "Build the Windows app before running this updater integration test."
  }

  New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
  New-Item -ItemType Directory -Path (Join-Path $PayloadRoot "app") -Force | Out-Null
  New-Item -ItemType Directory -Path (Split-Path -Parent $PackagePath) -Force | Out-Null
  Copy-Item -Path (Join-Path $SourceApp "*") -Destination $InstallDir -Recurse -Force
  Copy-Item -Path (Join-Path $SourceApp "*") -Destination (Join-Path $PayloadRoot "app") -Recurse -Force
  Copy-Item -LiteralPath (Join-Path $env:WINDIR "System32\ping.exe") -Destination (Join-Path $InstallDir "NirvNotes.exe") -Force
  $TestProcesses = @(
    Start-Process -FilePath (Join-Path $InstallDir "NirvNotes.exe") -ArgumentList "-t", "127.0.0.1" -WindowStyle Hidden -PassThru
    Start-Process -FilePath (Join-Path $InstallDir "NirvNotes.exe") -ArgumentList "-t", "127.0.0.1" -WindowStyle Hidden -PassThru
  )
  Set-Content -LiteralPath (Join-Path $PayloadRoot "app\_internal\client-version.json") -Value '{"version":"updater-integration-test"}' -Encoding UTF8
  Compress-Archive -Path (Join-Path $PayloadRoot "*") -DestinationPath $PackagePath -Force

  $Hash = (Get-FileHash -LiteralPath $PackagePath -Algorithm SHA256).Hash
  & (Join-Path $PSScriptRoot "apply-update.ps1") `
    -ParentProcessId 999999 `
    -PackagePath $PackagePath `
    -InstallDir $InstallDir `
    -ExpectedSha256 $Hash `
    -Version "updater-integration-test" `
    -SkipLaunch

  $Metadata = Get-Content -LiteralPath (Join-Path $InstallDir "_internal\client-version.json") -Raw
  if ($Metadata -notmatch "updater-integration-test") {
    throw "The staged payload was not installed."
  }
  foreach ($Architecture in @("win-arm64", "win-x64", "win-x86")) {
    $Loader = Join-Path $InstallDir "_internal\webview\lib\runtimes\$Architecture\native\WebView2Loader.dll"
    if (-not (Test-Path -LiteralPath $Loader -PathType Leaf)) {
      throw "The installed payload is missing $Architecture."
    }
  }
  foreach ($Process in $TestProcesses) {
    if (Get-Process -Id $Process.Id -ErrorAction SilentlyContinue) {
      throw "Updater left test process $($Process.Id) running."
    }
  }

  Write-Host "Updater integration test passed."
} finally {
  foreach ($Process in $TestProcesses) {
    Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
  }
  Remove-Item -LiteralPath $InstallDir -Recurse -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $PayloadRoot -Recurse -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $PackagePath -Force -ErrorAction SilentlyContinue
}
