[CmdletBinding()]
param(
    [string]$DshHome = "",
    [switch]$NoOpen
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$isWindowsHost = $env:OS -eq "Windows_NT"

if ([string]::IsNullOrWhiteSpace($DshHome)) {
    if (-not [string]::IsNullOrWhiteSpace($env:DSH_HOME)) {
        $DshHome = $env:DSH_HOME
    }
    elseif ($isWindowsHost -and -not [string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
        $DshHome = Join-Path $env:LOCALAPPDATA "DataAgent-dsh\dsh-home"
    }
    else {
        $DshHome = Join-Path $HOME ".dataagent-dsh/dsh-home"
    }
}

$DshHome = [System.IO.Path]::GetFullPath($DshHome)
$env:DSH_HOME = $DshHome
$env:DSH_TELEMETRY_MODE = "DISABLED"

$profileDir = Join-Path $DshHome "profiles/dataagent"
if (-not (Test-Path $profileDir)) {
    Write-Host "DataAgent profile is not initialized yet; running bootstrap first..." -ForegroundColor Yellow
    & (Join-Path $PSScriptRoot "setup_dataagent.ps1") -DshHome $DshHome
    if ($LASTEXITCODE -ne 0) {
        throw "DataAgent profile bootstrap failed."
    }
}

if ([string]::IsNullOrWhiteSpace($env:DEEPSEEK_API_KEY)) {
    Write-Warning "DEEPSEEK_API_KEY is not set in this terminal. Harness can still start, but model calls require either this environment variable or a DeepSeek key saved in Settings > Models."
}

$dshBin = if ($isWindowsHost) {
    Join-Path $repoRoot "dsh/node_modules/.bin/dsh.cmd"
} else {
    Join-Path $repoRoot "dsh/node_modules/.bin/dsh"
}
if (-not (Test-Path $dshBin)) {
    throw "DeepSeek Harness executable was not found at $dshBin. Run scripts/setup_dataagent.ps1 first."
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
