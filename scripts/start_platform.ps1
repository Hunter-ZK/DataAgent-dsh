param(
    [switch]$SkipInstall,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$runtimeDir = Join-Path $root ".runtime\local-acceptance"
$logDir = Join-Path $runtimeDir "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

if (-not $env:DEEPSEEK_API_KEY) {
    throw "DEEPSEEK_API_KEY is required for the real-LLM acceptance path. Set `$env:DEEPSEEK_API_KEY before running this script."
}

if (-not (Test-Path $venvPython)) {
    Write-Host "[DataAgent] Creating Python 3.14 virtual environment..."
    py -3.14 -m venv (Join-Path $root ".venv")
}

if (-not $SkipInstall) {
    Write-Host "[DataAgent] Installing Python platform + MCP dependencies..."
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -e "$root[platform,mcp]"

    Write-Host "[DataAgent] Installing web dependencies..."
    Push-Location (Join-Path $root "web")
    try {
        npm install --no-audit --no-fund
    }
    finally {
        Pop-Location
    }
}

# Local acceptance identity is explicit, loopback-only and never the production path.
$env:AGENT3_DEV_AUTH = "1"
$env:AGENT3_HOST = "127.0.0.1"
$env:AGENT3_PORT = "8080"
$env:AGENT3_DEV_PRINCIPAL = "local-pilot"
$env:AGENT3_DEV_ROLES = "analyst,pilot-region-user"
$env:AGENT3_DEV_DATA_SCOPES = "region_code=4403"
$env:AGENT3_DEV_SCOPE_VERSION = "local-1"
$env:AGENT3_MCP_POC_MODE = "1"
$env:DSH_TELEMETRY_MODE = "DISABLED"

Write-Host "[DataAgent] Starting local Agent3 MCP on 127.0.0.1:8900..."
$mcpOut = Join-Path $logDir "mcp.out.log"
$mcpErr = Join-Path $logDir "mcp.err.log"
$mcp = Start-Process -FilePath $venvPython -ArgumentList @("-m", "agent3.adapters.mcp.server") -WorkingDirectory $root -RedirectStandardOutput $mcpOut -RedirectStandardError $mcpErr -PassThru

Write-Host "[DataAgent] Starting agent3-api on 127.0.0.1:8080..."
$apiOut = Join-Path $logDir "api.out.log"
$apiErr = Join-Path $logDir "api.err.log"
$api = Start-Process -FilePath $venvPython -ArgumentList @("-m", "agent3_api.main") -WorkingDirectory $root -RedirectStandardOutput $apiOut -RedirectStandardError $apiErr -PassThru

try {
    $ready = $false
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Milliseconds 500
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/health" -TimeoutSec 2
            if ($health.ok) { $ready = $true; break }
        }
        catch { }
        if ($api.HasExited) {
            throw "agent3-api exited during startup. See $apiErr"
        }
        if ($mcp.HasExited) {
            throw "Agent3 MCP exited during startup. See $mcpErr"
        }
    }
    if (-not $ready) {
        throw "agent3-api did not become healthy. See $apiErr"
    }

    Write-Host ""
    Write-Host "DataAgent local acceptance environment is ready."
    Write-Host "  Web:  http://127.0.0.1:5173"
    Write-Host "  API:  http://127.0.0.1:8080/api/health"
    Write-Host "  MCP:  http://127.0.0.1:8900/mcp"
    Write-Host "  Logs: $logDir"
    Write-Host ""
    Write-Host "Press Ctrl+C to stop all local acceptance processes."

    if (-not $NoBrowser) {
        Start-Process "http://127.0.0.1:5173"
    }

    Push-Location (Join-Path $root "web")
    try {
        npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
    }
    finally {
        Pop-Location
    }
}
finally {
    foreach ($process in @($api, $mcp)) {
        if ($null -ne $process -and -not $process.HasExited) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
