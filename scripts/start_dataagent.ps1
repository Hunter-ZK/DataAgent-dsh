[CmdletBinding()]
param(
    [string]$DshHome = "",
    [switch]$NoOpen
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$isWindowsHost = $env:OS -eq "Windows_NT"

# Match dsh's own resolution: DSH_HOME when explicitly provided, otherwise ~/.dsh.
if ([string]::IsNullOrWhiteSpace($DshHome)) {
    if (-not [string]::IsNullOrWhiteSpace($env:DSH_HOME)) {
        $DshHome = $env:DSH_HOME
    }
    else {
        $DshHome = Join-Path $HOME ".dsh"
    }
}

$DshHome = [System.IO.Path]::GetFullPath($DshHome)
$env:DSH_HOME = $DshHome
$env:DSH_TELEMETRY_MODE = "DISABLED"

$dshBin = if ($isWindowsHost) {
    Join-Path $repoRoot "dsh/node_modules/.bin/dsh.cmd"
} else {
    Join-Path $repoRoot "dsh/node_modules/.bin/dsh"
}

$setupScript = Join-Path $PSScriptRoot "setup_dataagent.ps1"

# Always run the idempotent bootstrap before launch. This deliberately repairs:
# - a missing profile;
# - a residual/incomplete profile directory;
# - a profile that exists on disk but dsh cannot load;
# - a missing local Guard bundle or stale repository patch.
if (Test-Path $dshBin) {
    & $setupScript -DshHome $DshHome -SkipDependencyInstall
}
else {
    & $setupScript -DshHome $DshHome
}
if (-not $?) {
    throw "DataAgent profile bootstrap failed."
}

if ([string]::IsNullOrWhiteSpace($env:DEEPSEEK_API_KEY)) {
    Write-Warning "DEEPSEEK_API_KEY is not set in this terminal. Harness can still start, but model calls require either this environment variable or a DeepSeek key saved in Settings > Models."
}

if (-not (Test-Path $dshBin)) {
    throw "DeepSeek Harness executable was not found at $dshBin after bootstrap."
}

Push-Location $repoRoot
try {
    Write-Host "Starting local DeepSeek Harness with profile 'dataagent'..." -ForegroundColor Green
    Write-Host "DSH_HOME=$DshHome"
    Write-Host "Model provider: deepseek-official"
    Write-Host "Agent3 MCP expected at: http://127.0.0.1:8900/mcp"

    if ($NoOpen) {
        & $dshBin --profile dataagent --no-open
    }
    else {
        & $dshBin --profile dataagent
    }
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
