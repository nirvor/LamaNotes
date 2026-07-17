param(
  [string]$Url = "https://racknerd-31fcf0d.tail38b5b3.ts.net:8092",
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
  (Join-Path $PSScriptRoot "nirvnotes_client.py"),
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
