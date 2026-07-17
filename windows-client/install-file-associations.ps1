param(
  [Parameter(Mandatory = $true)]
  [string]$ExePath
)

$ErrorActionPreference = "Stop"
$ResolvedExe = (Resolve-Path $ExePath).Path
$ProgId = "NirvNotes.TextFile"
$AppKey = "HKCU:\Software\Classes\$ProgId"
$CommandKey = "$AppKey\shell\open\command"
$IconKey = "$AppKey\DefaultIcon"

New-Item -Path $AppKey -Force | Out-Null
Set-Item -Path $AppKey -Value "Open with NirvNotes"
New-Item -Path $CommandKey -Force | Out-Null
Set-Item -Path $CommandKey -Value "`"$ResolvedExe`" `"%1`""
New-Item -Path $IconKey -Force | Out-Null
Set-Item -Path $IconKey -Value "`"$ResolvedExe`",0"

foreach ($Extension in ".md", ".txt", ".cfg", ".ini", ".json", ".yaml", ".yml", ".toml", ".xml", ".log") {
  $ExtensionKey = "HKCU:\Software\Classes\$Extension\OpenWithProgids"
  New-Item -Path $ExtensionKey -Force | Out-Null
  New-ItemProperty -Path $ExtensionKey -Name $ProgId -Value ([byte[]]@()) -PropertyType Binary -Force | Out-Null
}

Write-Host "Registered NirvNotes as an Open With app for supported text and configuration files."
Write-Host "Windows may still require Settings > Apps > Default apps once to make it the default."
