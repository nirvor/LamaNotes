param(
  [Parameter(Mandatory = $true)]
  [ValidateScript({ Test-Path -LiteralPath $_ -PathType Leaf })]
  [string]$ExePath,
  [ValidateRange(1, 30)]
  [int]$Runs = 5,
  [ValidateSet("Cold", "Warm")]
  [string]$Profile = "Warm",
  [ValidateRange(5, 60)]
  [int]$TimeoutSeconds = 20,
  [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
$ResolvedExe = (Resolve-Path -LiteralPath $ExePath).Path
$BenchmarkRoot = Join-Path $env:TEMP "LamaNotes-startup-benchmark-$PID"
$SharedProfile = Join-Path $BenchmarkRoot "profile"
$OriginalLocalAppData = $env:LOCALAPPDATA
$StartedProcesses = [System.Collections.Generic.List[System.Diagnostics.Process]]::new()

function Get-Percentile {
  param(
    [double[]]$Values,
    [double]$Percentile
  )
  $Sorted = @($Values | Sort-Object)
  $Index = [Math]::Floor(($Sorted.Count - 1) * $Percentile)
  return [Math]::Round($Sorted[$Index], 1)
}

function Stop-BenchmarkProcess {
  param([System.Diagnostics.Process]$Process)
  if ($Process.HasExited) {
    return
  }
  $null = $Process.CloseMainWindow()
  if (-not $Process.WaitForExit(5000)) {
    Stop-Process -Id $Process.Id -Force
    $Process.WaitForExit(5000)
  }
}

New-Item -ItemType Directory -Path $BenchmarkRoot | Out-Null
$Results = @()

try {
  for ($Run = 1; $Run -le $Runs; $Run += 1) {
    $ProfileRoot = if ($Profile -eq "Warm") {
      $SharedProfile
    } else {
      Join-Path $BenchmarkRoot "profile-$Run"
    }
    New-Item -ItemType Directory -Path $ProfileRoot -Force | Out-Null
    $LogPath = Join-Path $ProfileRoot "LamaNotes\logs\lamanotes-client.log"
    $ExistingReadyLines = if (Test-Path -LiteralPath $LogPath) {
      @(Select-String -LiteralPath $LogPath -Pattern "client ready phase=editor").Count
    } else {
      0
    }

    $env:LOCALAPPDATA = $ProfileRoot
    $Route = "/open-file?new=1&draft=benchmark-$Run"
    $Process = Start-Process `
      -FilePath $ResolvedExe `
      -ArgumentList @("--proxy-port", "0", "--route", $Route) `
      -PassThru
    $StartedProcesses.Add($Process)
    $env:LOCALAPPDATA = $OriginalLocalAppData

    $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $ReadyLine = $null
    while ((Get-Date) -lt $Deadline) {
      if ($Process.HasExited) {
        throw "LamaNotes exited before the editor-ready signal in run $Run."
      }
      if (Test-Path -LiteralPath $LogPath) {
        $ReadyLines = @(
          Select-String -LiteralPath $LogPath -Pattern "client ready phase=editor"
        )
        if ($ReadyLines.Count -gt $ExistingReadyLines) {
          $ReadyLine = $ReadyLines[-1].Line
          break
        }
      }
      Start-Sleep -Milliseconds 50
    }
    if (-not $ReadyLine) {
      throw "LamaNotes did not report editor-ready within $TimeoutSeconds seconds."
    }

    $Match = [regex]::Match(
      $ReadyLine,
      "browser_ms=(?<browser>\d+).*route_ms=(?<route>\d+).*native_ms=(?<native>\d+)"
    )
    if (-not $Match.Success) {
      throw "Could not parse the editor-ready metric in run $Run."
    }
    $Process.Refresh()
    $Results += [pscustomobject]@{
      run = $Run
      nativeMs = [int]$Match.Groups["native"].Value
      browserMs = [int]$Match.Groups["browser"].Value
      routeMs = [int]$Match.Groups["route"].Value
      workingSetMb = [Math]::Round($Process.WorkingSet64 / 1MB, 1)
    }
    Stop-BenchmarkProcess -Process $Process
  }

  $Report = [ordered]@{
    executable = $ResolvedExe
    profile = $Profile.ToLowerInvariant()
    runs = $Runs
    measuredAt = (Get-Date).ToUniversalTime().ToString("o")
    summary = [ordered]@{
      nativeMedianMs = Get-Percentile $Results.nativeMs 0.5
      nativeP95Ms = Get-Percentile $Results.nativeMs 0.95
      browserMedianMs = Get-Percentile $Results.browserMs 0.5
      routeMedianMs = Get-Percentile $Results.routeMs 0.5
      workingSetMedianMb = Get-Percentile $Results.workingSetMb 0.5
    }
    samples = $Results
  }

  $Results | Format-Table -AutoSize
  $Report.summary | Format-List
  if ($OutputPath) {
    $ResolvedOutput = [IO.Path]::GetFullPath($OutputPath)
    $OutputDirectory = Split-Path -Parent $ResolvedOutput
    if ($OutputDirectory) {
      New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
    }
    $Report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ResolvedOutput
    Write-Host "JSON report: $ResolvedOutput"
  }
} finally {
  $env:LOCALAPPDATA = $OriginalLocalAppData
  foreach ($Process in $StartedProcesses) {
    Stop-BenchmarkProcess -Process $Process
  }
  $ResolvedBenchmarkRoot = [IO.Path]::GetFullPath($BenchmarkRoot)
  $ResolvedTempRoot = [IO.Path]::GetFullPath($env:TEMP).TrimEnd("\")
  if (
    $ResolvedBenchmarkRoot.StartsWith(
      "$ResolvedTempRoot\LamaNotes-startup-benchmark-",
      [StringComparison]::OrdinalIgnoreCase
    ) -and
    [IO.Directory]::Exists($ResolvedBenchmarkRoot)
  ) {
    [IO.Directory]::Delete($ResolvedBenchmarkRoot, $true)
  }
}
