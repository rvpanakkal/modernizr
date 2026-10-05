# =============================================================================
# run_step1_and_step2.ps1 — Windows PowerShell End-to-end Pipeline Verification
# =============================================================================
# Usage:
#   .\scripts\run_step1_and_step2.ps1
#
# Prerequisites:
#   - Java 17+ on PATH (mvn)
#   - Python 3.11+ with pydantic and neo4j packages
#   - Neo4j running (docker compose up -d)
# =============================================================================

$ErrorActionPreference = "Stop"

$ProjectRoot   = Split-Path -Parent $PSScriptRoot
$LstModule     = Join-Path $ProjectRoot "modules\lst-extractor"
$PipelineModule = Join-Path $ProjectRoot "modules\pipeline-core"
$SampleDir     = Join-Path $ProjectRoot "samples\legacy-banking-monolith\src\main\java"
$ArtifactOut   = Join-Path $ProjectRoot "artifacts\raw_lst\metadata_extracted.json"
$ReceiptOut    = Join-Path $ProjectRoot "artifacts\receipts\step2_receipt.json"
$FatJar        = Join-Path $LstModule "target\lst-extractor-1.0.0-SNAPSHOT.jar"

$Neo4jUri      = $env:NEO4J_URI      ?? "bolt://localhost:7687"
$Neo4jUser     = $env:NEO4J_USER     ?? "neo4j"
$Neo4jPassword = $env:NEO4J_PASSWORD ?? "modernization_secret"
$JiraStoryId   = $env:JIRA_STORY_ID  ?? "MOD-001"
$EntryClass    = "com.legacy.banking.web.TransferManagedBean"

$Pass = 0; $Fail = 0
$env:PYTHONPATH = "$PipelineModule;$env:PYTHONPATH"

function Write-StepHeader($title) {
    Write-Host "`n━━━━ $title ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
}
function Write-Ok($msg)   { Write-Host "  ✓ $msg" -ForegroundColor Green;  $script:Pass++ }
function Write-Fail($msg) { Write-Host "  ✗ $msg" -ForegroundColor Red;    $script:Fail++ }
function Write-Info($msg) { Write-Host "  → $msg" -ForegroundColor Yellow }

# ── Step 1A: Maven Build ──────────────────────────────────────────────────────
Write-StepHeader "Step 1A — Build LST Extractor (Maven)"

Write-Info "Building fat JAR …"
& mvn clean package -f "$LstModule\pom.xml" -q
if ($LASTEXITCODE -ne 0) { Write-Fail "Maven build FAILED."; exit 1 }
Write-Ok "Maven build succeeded."

if (-not (Test-Path $FatJar)) { Write-Fail "Fat JAR not found: $FatJar"; exit 1 }
Write-Ok "Fat JAR: $FatJar"

# ── Step 1B: LST Extraction ───────────────────────────────────────────────────
Write-StepHeader "Step 1B — LST Extraction (legacy-banking-monolith)"

New-Item -ItemType Directory -Force -Path (Split-Path $ArtifactOut) | Out-Null
Write-Info "Source: $SampleDir"
Write-Info "Output: $ArtifactOut"

& java -jar "$FatJar" --source-dir "$SampleDir" --output "$ArtifactOut"
if ($LASTEXITCODE -ne 0) { Write-Fail "LST extraction FAILED."; exit 1 }
Write-Ok "LST extraction completed."

$payload = Get-Content $ArtifactOut -Raw | ConvertFrom-Json
$classCount = $payload.classes.Count
Write-Info "Extracted class count: $classCount"

if ($classCount -ge 1) { Write-Ok "$classCount class record(s) extracted." }
else                   { Write-Fail "0 class records — extraction may have failed silently." }

$found = $payload.classes | Where-Object { $_.simpleName -eq "TransferManagedBean" }
if ($found)  { Write-Ok "TransferManagedBean found in metadata." }
else         { Write-Fail "TransferManagedBean NOT found in metadata." }

# ── Step 2A: Neo4j Ingestion ──────────────────────────────────────────────────
Write-StepHeader "Step 2A — Neo4j Graph Ingestion"

Write-Info "Testing Neo4j connectivity …"
$connTest = python -c "
from neo4j import GraphDatabase
d = GraphDatabase.driver('$Neo4jUri', auth=('$Neo4jUser','$Neo4jPassword'))
d.verify_connectivity()
d.close()
print('OK')
" 2>&1
if ($connTest -ne "OK") {
    Write-Fail "Cannot connect to Neo4j. Ensure docker compose up -d is running."
    exit 1
}
Write-Ok "Neo4j connection verified."

New-Item -ItemType Directory -Force -Path (Split-Path $ReceiptOut) | Out-Null

python -m pipeline_core.graph.ingest_graph `
    --input "$ArtifactOut" `
    --uri "$Neo4jUri" `
    --user "$Neo4jUser" `
    --password "$Neo4jPassword" `
    --receipt-out "$ReceiptOut" `
    --jira-id "$JiraStoryId"

if ($LASTEXITCODE -ne 0) { Write-Fail "Neo4j ingestion FAILED."; exit 1 }
Write-Ok "Neo4j ingestion completed."

if (Test-Path $ReceiptOut) {
    $receipt = Get-Content $ReceiptOut -Raw | ConvertFrom-Json
    Write-Ok "Receipt: status=$($receipt.status), classes=$($receipt.metrics.classes)"
}

# ── Step 2B: GraphRAG Slice Verification ──────────────────────────────────────
Write-StepHeader "Step 2B — GraphRAG Vertical Slice Verification"
Write-Info "Extracting slice for: $EntryClass"

$sliceJson = python -c "
import json, logging
logging.disable(logging.CRITICAL)
from neo4j import GraphDatabase
from pipeline_core.graph.queries import find_entry_points, extract_vertical_slice

driver = GraphDatabase.driver('$Neo4jUri', auth=('$Neo4jUser','$Neo4jPassword'))
with driver.session() as session:
    eps = find_entry_points(session)
    print(f'Found {len(eps)} entry points', flush=True)
    s = extract_vertical_slice(session, '$EntryClass', max_depth=5)
    print(json.dumps(s, indent=2, default=str))
driver.close()
" 2>&1

Write-Host $sliceJson

$sliceObj = $sliceJson | python -c "
import json, sys
lines = sys.stdin.read()
# Find the JSON object (skip info lines)
for i, line in enumerate(lines.split('\n')):
    if line.startswith('{'):
        print('\n'.join(lines.split('\n')[i:]))
        break
" | ConvertFrom-Json -ErrorAction SilentlyContinue

if ($sliceObj) {
    $components = $sliceObj.componentSummary | ForEach-Object { $_.simpleName }
    if ($components -contains "TransferProcessingService") {
        Write-Ok "TransferManagedBean → TransferProcessingService chain verified."
    } else {
        Write-Fail "TransferProcessingService NOT found in slice."
    }
    if ($components -contains "CicsMainframeGateway") {
        Write-Ok "TransferProcessingService → CicsMainframeGateway boundary verified."
    } else {
        Write-Fail "CicsMainframeGateway NOT found in slice. (May require call graph resolution.)"
    }
    Write-Info "Estimated tokens: $($sliceObj.estimatedTokens) | Within budget: $($sliceObj.withinBudget)"
} else {
    Write-Fail "Could not parse slice JSON output."
}

# ── Summary ───────────────────────────────────────────────────────────────────
Write-StepHeader "Summary"
Write-Host "  Passed: $Pass   Failed: $Fail"
if ($Fail -eq 0) {
    Write-Host "`n  ✓ All pipeline stages completed successfully." -ForegroundColor Green
    Write-Host "  TransferManagedBean → TransferProcessingService → CicsMainframeGateway" -ForegroundColor Green
    Write-Host "  vertical slice is ready for Step 3 cognitive processing.`n" -ForegroundColor Green
    exit 0
} else {
    Write-Host "`n  ✗ $Fail stage(s) failed. Review errors above.`n" -ForegroundColor Red
    exit 1
}
