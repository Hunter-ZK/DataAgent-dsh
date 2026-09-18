[CmdletBinding()]
param(
    [string]$DshHome = "",
    [switch]$SkipDependencyInstall,
    [switch]$ResetProfile
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$isWindowsHost = $env:OS -eq "Windows_NT"

# DeepSeek Harness resolves its home as: explicit/DSH_HOME -> ~/.dsh.
# Use the same default so a later direct `dsh --profile dataagent` invocation
# resolves the exact profile created here.
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

$dshDir = Join-Path $repoRoot "dsh"
$guardDir = Join-Path $repoRoot "guard-plugin"
$profilePatch = Join-Path $repoRoot "dsh/profile/cordis.patch.yml"
$profileDir = Join-Path $DshHome "profiles/dataagent"
$profilePackage = Join-Path $profileDir "package.json"
$dshBin = if ($isWindowsHost) {
    Join-Path $dshDir "node_modules/.bin/dsh.cmd"
} else {
    Join-Path $dshDir "node_modules/.bin/dsh"
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][scriptblock]$Command
    )
    Write-Host "==> $Label"
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

function Remove-StaleProfile {
    param([Parameter(Mandatory = $true)][string]$Reason)
    if (Test-Path $profileDir) {
        Write-Host "==> $Reason" -ForegroundColor Yellow
        Write-Host "    Removing stale local profile: $profileDir"
        Remove-Item -Recurse -Force $profileDir
    }
}

function Test-ProfileLoadable {
    if (-not (Test-Path $profilePackage)) {
        return $false
    }

    $probeOut = Join-Path ([System.IO.Path]::GetTempPath()) "dataagent-profile-probe.out"
    $probeErr = Join-Path ([System.IO.Path]::GetTempPath()) "dataagent-profile-probe.err"
    Remove-Item $probeOut, $probeErr -Force -ErrorAction SilentlyContinue

    & $dshBin --profile dataagent --dump-default-config 1> $probeOut 2> $probeErr
    $ok = $LASTEXITCODE -eq 0
    if (-not $ok -and (Test-Path $probeErr)) {
        Write-Host "Existing profile failed dsh loadability probe:" -ForegroundColor Yellow
        Get-Content $probeErr | Write-Host
    }
    return $ok
}

if (-not $SkipDependencyInstall) {
    Push-Location $dshDir
    try {
        Invoke-Checked "Install pinned DeepSeek Harness dependencies" { npm ci --no-audit --no-fund }
    }
    finally {
        Pop-Location
    }

    Push-Location $guardDir
    try {
        Invoke-Checked "Install Agent3 Guard dependencies" { npm ci --no-audit --no-fund }
        Invoke-Checked "Build Agent3 Guard" { npm run build }
    }
    finally {
        Pop-Location
    }
}

if (-not (Test-Path $dshBin)) {
    throw "DeepSeek Harness executable was not found at $dshBin. Run this script without -SkipDependencyInstall first."
}

if ($ResetProfile) {
    Remove-StaleProfile "Reset requested."
}

New-Item -ItemType Directory -Force -Path $DshHome | Out-Null

Push-Location $repoRoot
try {
    # A directory alone is NOT a valid dsh profile. Official custom profile
    # initialization writes package.json; residual directories must be removed
    # because dsh deliberately refuses to initialize into an existing directory.
    if ((Test-Path $profileDir) -and -not (Test-Path $profilePackage)) {
        Remove-StaleProfile "Detected an incomplete DataAgent profile directory (missing package.json)."
    }
    elseif (Test-Path $profilePackage) {
        if (-not (Test-ProfileLoadable)) {
            Remove-StaleProfile "Detected a DataAgent profile that exists on disk but cannot be loaded by dsh."
        }
    }

    if (-not (Test-Path $profilePackage)) {
        Invoke-Checked "Initialize custom dsh profile 'dataagent' from shipped web profile" {
            & $dshBin --profile dataagent --from-default-profile web --dump-config | Out-Null
        }
    }
    else {
        Write-Host "==> Reusing verified local dsh profile: $profileDir"
    }

    $guardInstalled = $false
    if (Test-Path $profilePackage) {
        try {
            $profileJson = Get-Content $profilePackage -Raw | ConvertFrom-Json
            $dependencyNames = @()
            if ($null -ne $profileJson.dependencies) {
                $dependencyNames += $profileJson.dependencies.PSObject.Properties.Name
            }
            if ($null -ne $profileJson.devDependencies) {
                $dependencyNames += $profileJson.devDependencies.PSObject.Properties.Name
            }
            $guardInstalled = $dependencyNames -contains "@hunter-zk/agent3-guard"
        }
        catch {
            Remove-StaleProfile "DataAgent profile package.json is unreadable."
            Invoke-Checked "Reinitialize custom dsh profile 'dataagent'" {
                & $dshBin --profile dataagent --from-default-profile web --dump-config | Out-Null
            }
        }
    }

    if (-not $guardInstalled) {
        Invoke-Checked "Install local Agent3 Guard bundle into dataagent profile" {
            & $dshBin plugin --profile dataagent add $guardDir
        }
    }
    else {
        Write-Host "==> Agent3 Guard bundle already installed"
    }

    if (-not (Test-Path $profilePatch)) {
        throw "Repository profile patch not found: $profilePatch"
    }

    Copy-Item $profilePatch (Join-Path $profileDir "cordis.patch.yml") -Force
    Write-Host "==> Applied repository DataAgent profile patch"

    $configOut = Join-Path ([System.IO.Path]::GetTempPath()) "dataagent-effective-config.txt"
    $configErr = Join-Path ([System.IO.Path]::GetTempPath()) "dataagent-config.err"
    Remove-Item $configOut, $configErr -Force -ErrorAction SilentlyContinue

    & $dshBin --profile dataagent --dump-config 1> $configOut 2> $configErr
    if ($LASTEXITCODE -ne 0) {
        if (Test-Path $configErr) { Get-Content $configErr | Write-Host }
        throw "DataAgent profile validation failed with exit code $LASTEXITCODE"
    }

    $stderrText = if (Test-Path $configErr) { Get-Content $configErr -Raw } else { "" }
    if ($stderrText -match "(?i)unmatched|not found|failed to resolve|does not exist") {
        Write-Host $stderrText
        throw "DataAgent profile contains unresolved configuration."
    }

    $configText = Get-Content $configOut -Raw
    foreach ($required in @("deepseek-official", "mcp-agent3", "agent3-guard", "dataagent-query")) {
        if ($configText -notmatch [regex]::Escape($required)) {
            throw "DataAgent profile validation did not find required component: $required"
        }
    }

    if ($configText -match "127\.0\.0\.1:8100|deepseek-v3-local|LOCAL_LLM_KEY") {
        throw "DataAgent profile still contains the retired local-LLM configuration."
    }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "DataAgent dsh profile is ready." -ForegroundColor Green
Write-Host "DSH_HOME=$DshHome"
Write-Host "Profile: dataagent"
Write-Host "LLM provider: deepseek-official"
Write-Host "LLM model: deepseek-flash"
Write-Host ""
Write-Host "Next:"
Write-Host '  1. Set $env:DEEPSEEK_API_KEY = "sk-..." (or configure DeepSeek in Harness Settings > Models).'
Write-Host '  2. Start Agent3 MCP in another terminal: $env:AGENT3_MCP_POC_MODE="1"; python -m agent3.adapters.mcp.server'
Write-Host '  3. Start Harness with: .\scripts\start_dataagent.ps1'
Write-Host '     (Direct dsh also works because this script uses the official ~/.dsh home by default.)'
