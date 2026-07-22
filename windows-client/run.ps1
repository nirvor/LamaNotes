param(
  [string]$Url = "https://notes.thuber.org",
  [string[]]$Files = @(),
  [switch]$Debug
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Venv = Join-Path $PSScriptRoot ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"

if (!(Test-Path $Python)) {
  python -m venv $Venv
  & $Python -m pip install --upgrade pip
  & $Python -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")
}

$Args = @(
  (Join-Path $PSScriptRoot "lamanotes_client.py"),
  "--url",
  $Url
)

if ($Debug) {
  $Args += "--debug"
}

$Args += $Files
Push-Location $Root
try {
  & $Python @Args
} finally {
  Pop-Location
}
