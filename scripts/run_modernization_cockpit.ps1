# =============================================================================
# Modernization Cockpit Orchestration Launcher (PowerShell)
# =============================================================================

$ErrorActionPreference = "Continue"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "   ENTERPRISE LEGACY MODERNIZATION FACTORY — COCKPIT LAUNCHER        " -ForegroundColor Cyan
Write-Host "=====================================================================" -ForegroundColor Cyan

# 1. Check Docker / Neo4j
Write-Host "[1/3] Checking Neo4j Graph Database status..." -ForegroundColor Yellow
$dockerRunning = $false
try {
    $null = docker info 2>$null
    if ($LASTEXITCODE -eq 0) {
        $dockerRunning = $true
    }
} catch {
    $dockerRunning = $false
}

if ($dockerRunning) {
    Write-Host "       Docker detected. Starting Neo4j container..." -ForegroundColor Green
    docker-compose up -d neo4j
} else {
    Write-Host "       Docker daemon not running or not found." -ForegroundColor DarkYellow
    Write-Host "       Running FastAPI Control Plane in resilient MOCK_MODE." -ForegroundColor DarkYellow
}

# 2. Start FastAPI Backend in background job
Write-Host "[2/3] Launching FastAPI Control Plane on http://localhost:8000..." -ForegroundColor Yellow
$env:PYTHONPATH = "$RepoRoot\modules\pipeline-core"
$env:MOCK_MODE = "true"
$env:MOCK_JIRA = "true"

$backendJob = Start-Job -ScriptBlock {
    param($root)
    $env:PYTHONPATH = "$root\modules\pipeline-core"
    $env:MOCK_MODE = "true"
    $env:MOCK_JIRA = "true"
    Set-Location "$root\modules\pipeline-core"
    python -m uvicorn api.server:app --host 0.0.0.0 --port 8000
} -ArgumentList $RepoRoot

Start-Sleep -Seconds 2

# 3. Start Vite UI
Write-Host "[3/3] Launching Modernization Wizard UI on http://localhost:5173..." -ForegroundColor Yellow
Write-Host ""
Write-Host "=====================================================================" -ForegroundColor Green
Write-Host " Modernization Cockpit is LIVE!" -ForegroundColor Green
Write-Host " • Cockpit UI:              http://localhost:5173" -ForegroundColor Cyan
Write-Host " • API Control Plane:       http://localhost:8000" -ForegroundColor Cyan
Write-Host " • API Interactive Docs:    http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "=====================================================================" -ForegroundColor Green
Write-Host " Press [Ctrl+C] to stop UI and background server." -ForegroundColor Gray

try {
    Set-Location "$RepoRoot\apps\wizard-ui"
    npm run dev -- --host 0.0.0.0 --port 5173
} finally {
    Write-Host "`nStopping backend job..." -ForegroundColor Yellow
    Stop-Job -Job $backendJob -ErrorAction SilentlyContinue
    Remove-Job -Job $backendJob -ErrorAction SilentlyContinue
    Write-Host "Services stopped." -ForegroundColor Green
}
