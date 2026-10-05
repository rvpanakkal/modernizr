# =============================================================================
# run_mock_mode.ps1 -- Modernization Factory Mock Mode Single-Click Launcher
# =============================================================================
# Runs Java (LST Extractor), Python (FastAPI Control Plane), and UI (Vite React)
# in deterministic offline Mock Mode with zero external dependencies.
# =============================================================================

Param(
    [string]$SourceDir = "samples\legacy-banking-monolith\src\main\java",
    [switch]$SkipJava = $false,
    [int]$BackendPort = 8000,
    [int]$UiPort = 5173
)

$ErrorActionPreference = "Continue"
$RepoRoot = $PSScriptRoot
if (-not (Test-Path "$RepoRoot\modules\lst-extractor")) {
    $RepoRoot = Split-Path -Parent $PSScriptRoot
}
Set-Location $RepoRoot

Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "   ENTERPRISE LEGACY MODERNIZATION FACTORY -- MOCK MODE LAUNCHER     " -ForegroundColor Cyan
Write-Host "   (Running Java LST Extractor + Python FastAPI + React Cockpit UI)  " -ForegroundColor Cyan
Write-Host "=====================================================================" -ForegroundColor Cyan

# ── 1. JAVA MODULE: Run OpenRewrite LST Extractor ────────────────────────────
if (-not $SkipJava) {
    Write-Host "`n[1/3] Executing Java Module (modules/lst-extractor)..." -ForegroundColor Yellow
    $fatJar = Join-Path $RepoRoot "modules\lst-extractor\target\lst-extractor-1.0.0-SNAPSHOT.jar"
    $rawOutputDir = Join-Path $RepoRoot "artifacts\raw_lst"
    $rawOutputJson = Join-Path $rawOutputDir "metadata_extracted.json"
    New-Item -ItemType Directory -Path $rawOutputDir -Force | Out-Null

    if (-not (Test-Path $fatJar)) {
        Write-Host "       Building LST Extractor fat JAR via Maven..." -ForegroundColor DarkYellow
        & mvn clean package -f "$RepoRoot\modules\lst-extractor\pom.xml" -DskipTests
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Maven build failed for lst-extractor; using existing sample artifacts."
        }
    }

    if (Test-Path $fatJar) {
        $absSourceDir = Join-Path $RepoRoot $SourceDir
        Write-Host "       Extracting LST metadata from: $absSourceDir" -ForegroundColor Gray
        & java -jar "$fatJar" --source-dir "$absSourceDir" --output "$rawOutputJson"
        if ($LASTEXITCODE -eq 0 -and (Test-Path $rawOutputJson)) {
            Write-Host "  [OK] Java LST Extraction complete: $rawOutputJson" -ForegroundColor Green
        } else {
            Write-Warning "Java extraction exited with code $LASTEXITCODE; using existing sample artifacts."
        }
    }
} else {
    Write-Host "`n[1/3] Skipping Java Module extraction (-SkipJava specified)." -ForegroundColor DarkGray
}

# ── 2. PYTHON MODULE: Launch FastAPI Control Plane in Mock Mode ──────────────
Write-Host "`n[2/3] Launching Python Module (FastAPI on http://localhost:$BackendPort)..." -ForegroundColor Yellow
$backendJob = Start-Job -ScriptBlock {
    param($root, $port)
    $env:PYTHONPATH = "$root\modules\pipeline-core"
    $env:MOCK_MODE = "true"
    $env:MOCK_LLM = "true"
    $env:MOCK_JIRA = "true"
    $env:MOCK_GITHUB = "true"
    Set-Location "$root\modules\pipeline-core"
    python -m uvicorn api.server:app --host 0.0.0.0 --port $port
} -ArgumentList $RepoRoot, $BackendPort

Start-Sleep -Seconds 2

# Verify backend health
try {
    $resp = Invoke-RestMethod -Uri "http://localhost:$BackendPort/" -Method Get -TimeoutSec 5 -ErrorAction SilentlyContinue
    if ($resp.status -eq "OPERATIONAL") {
        Write-Host "  [OK] FastAPI Control Plane running in MOCK_MODE." -ForegroundColor Green
    }
} catch {
    Write-Host "  [i] Backend initialized in background." -ForegroundColor Gray
}

# ── 3. UI MODULE: Launch Vite React Cockpit ──────────────────────────────────
Write-Host "`n[3/3] Launching UI Module (React Cockpit on http://localhost:$UiPort)..." -ForegroundColor Yellow
$uiDir = Join-Path $RepoRoot "apps\wizard-ui"
if (-not (Test-Path (Join-Path $uiDir "node_modules"))) {
    Write-Host "       Installing UI dependencies (npm install)..." -ForegroundColor DarkYellow
    Push-Location $uiDir
    npm install
    Pop-Location
}

Write-Host ""
Write-Host "=====================================================================" -ForegroundColor Green
Write-Host " Modernization Factory is LIVE in MOCK MODE!" -ForegroundColor Green
Write-Host " • Cockpit UI:              http://localhost:$UiPort" -ForegroundColor Cyan
Write-Host " • API Control Plane:       http://localhost:$BackendPort" -ForegroundColor Cyan
Write-Host " • API Interactive Docs:    http://localhost:$BackendPort/docs" -ForegroundColor Cyan
Write-Host " • Java LST Metadata:       artifacts\raw_lst\metadata_extracted.json" -ForegroundColor Gray
Write-Host "=====================================================================" -ForegroundColor Green
Write-Host " Press [Ctrl+C] to stop the UI and terminate the background server." -ForegroundColor Gray
Write-Host ""

try {
    Set-Location $uiDir
    npm run dev -- --host 0.0.0.0 --port $UiPort
} finally {
    Write-Host "`nShutting down Python background server..." -ForegroundColor Yellow
    Stop-Job -Job $backendJob -ErrorAction SilentlyContinue
    Remove-Job -Job $backendJob -ErrorAction SilentlyContinue
    Write-Host "All mock mode services stopped." -ForegroundColor Green
}
