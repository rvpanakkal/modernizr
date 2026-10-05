# =============================================================================
# run_step3_and_step4.ps1 — Windows PowerShell End-to-end Step 3 & Step 4 Pipeline
# =============================================================================
# Usage:
#   .\scripts\run_step3_and_step4.ps1 [-MockLlm] [-MockJira]
#
# Prerequisites:
#   - Python 3.11+ on PATH with pipeline-core requirements installed
#   - Optional: ANTHROPIC_API_KEY for live Claude 3.7 Sonnet cognitive passes
#   - Optional: JIRA_API_TOKEN, JIRA_BASE_URL for live Jira issue creation
# =============================================================================

param (
    [switch]$MockLlm = $true,
    [switch]$MockJira = $true
)

$ErrorActionPreference = "Stop"

$ProjectRoot    = Split-Path -Parent $PSScriptRoot
$PipelineModule = Join-Path $ProjectRoot "modules\pipeline-core"
$ArtifactsDir   = Join-Path $ProjectRoot "artifacts"
$SpecsDir       = Join-Path $ArtifactsDir "generated_specs"
$ReceiptsDir    = Join-Path $ArtifactsDir "receipts"
$SlicePath      = Join-Path $ArtifactsDir "raw_lst\sample_vertical_slice.json"

$env:PYTHONPATH = "$PipelineModule;$env:PYTHONPATH"

if ($MockLlm)  { $env:MOCK_LLM = "true" }
if ($MockJira) { $env:MOCK_JIRA = "true" }

$Pass = 0; $Fail = 0

function Write-StepHeader($title) {
    Write-Host "`n==== $title ========================================================" -ForegroundColor Cyan
}
function Write-Ok($msg)   { Write-Host "  [OK] $msg" -ForegroundColor Green;  $script:Pass++ }
function Write-Fail($msg) { Write-Host "  [FAIL] $msg" -ForegroundColor Red;    $script:Fail++ }
function Write-Info($msg) { Write-Host "  --> $msg" -ForegroundColor Yellow }

$RunId = "run-ps-" + (Get-Date -Format "yyyyMMdd-HHmmss")

# ── Environment & Prerequisites ───────────────────────────────────────────────
Write-StepHeader "Step 3/4 Prerequisites & Environment"
Write-Info "Project root : $ProjectRoot"
Write-Info "Run ID       : $RunId"
Write-Info "MOCK_LLM     : $env:MOCK_LLM"
Write-Info "MOCK_JIRA    : $env:MOCK_JIRA"

if (-not (Test-Path $SlicePath)) {
    Write-Fail "Input vertical slice not found at: $SlicePath"
    exit 1
}
Write-Ok "Found input vertical slice: $SlicePath"

# ── Step 3 & Step 4 Execution ─────────────────────────────────────────────────
Write-StepHeader "Step 3: Multi-Pass Cognitive Chain & Step 4: Jira HITL Gate"
Write-Info "Executing Decompiler -> Business Abstractor -> Spec Formatter -> Jira HITL Gate..."

$runnerCmd = "python -m pipeline_core.workflows.cognitive_runner --slice `"$SlicePath`" --run-id `"$RunId`" --mock-llm --mock-jira"
Invoke-Expression $runnerCmd
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Cognitive runner execution failed!"
    exit 1
}
Write-Ok "Cognitive runner finished successfully."

# ── Verify Step 4 Output Artifacts ────────────────────────────────────────────
Write-StepHeader "Verifying Generated Specification & Step 4 Checkpoint Receipt"

$ExpectedSpecPath = Join-Path $SpecsDir "spec_$RunId.json"
$ExpectedReceiptPath = Join-Path $ReceiptsDir "receipt_${RunId}_step4.json"

if (-not (Test-Path $ExpectedSpecPath)) {
    Write-Fail "Generated specification JSON not found: $ExpectedSpecPath"
    exit 1
}
Write-Ok "Specification JSON generated on disk: $ExpectedSpecPath"

if (-not (Test-Path $ExpectedReceiptPath)) {
    Write-Fail "Step 4 Checkpoint Receipt not found: $ExpectedReceiptPath"
    exit 1
}
Write-Ok "Step 4 Checkpoint Receipt emitted: $ExpectedReceiptPath"

# Inspect Receipt Details
$receiptJson = Get-Content $ExpectedReceiptPath -Raw | ConvertFrom-Json
Write-Info "Receipt Status       : $($receiptJson.status)"
Write-Info "Jira Story ID        : $($receiptJson.jira_story_id)"
Write-Info "HITL Approved        : $($receiptJson.hitl_approved)"
Write-Info "Next Step            : $($receiptJson.next_step)"

if ($receiptJson.status -eq "HITL_PENDING") {
    Write-Ok "Pipeline correctly PAUSED in status HITL_PENDING."
} else {
    Write-Fail "Expected status HITL_PENDING, found: $($receiptJson.status)"
}

if ($receiptJson.hitl_approved -eq $false) {
    Write-Ok "Human-in-the-loop guardrail active (hitl_approved = False)."
} else {
    Write-Fail "Invariant violation: hitl_approved must be False prior to human review!"
}

# ── Automated Webhook Resume: Simulate Architect Approval ─────────────────────
Write-StepHeader "Automated Webhook Resume & Cryptographic Integrity Verification"
Write-Info "Simulating Lead Architect Jira transition to 'Approved'..."

$webhookCmd = "python -m pipeline_core.integrations.webhook_listener --simulate-approval `"$ExpectedReceiptPath`" --approver `"lead_architect@enterprise.com`" --status `"Approved`""
Invoke-Expression $webhookCmd
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Webhook simulation failed!"
    exit 1
}
Write-Ok "Webhook approval simulation succeeded."

$ApprovedReceiptPath = Join-Path $ReceiptsDir "receipt_${RunId}_approved.json"
if (-not (Test-Path $ApprovedReceiptPath)) {
    Write-Fail "Approved receipt file not found: $ApprovedReceiptPath"
    exit 1
}
Write-Ok "Approved receipt generated: $ApprovedReceiptPath"

$approvedJson = Get-Content $ApprovedReceiptPath -Raw | ConvertFrom-Json
if ($approvedJson.status -eq "SUCCESS" -and $approvedJson.hitl_approved -eq $true) {
    Write-Ok "State transition confirmed: status=SUCCESS, hitl_approved=True."
    Write-Ok "Target synthesis unblocked (next_step: $($approvedJson.next_step))."
} else {
    Write-Fail "State transition failed: Status=$($approvedJson.status), Approved=$($approvedJson.hitl_approved)"
}

# ── Anti-Tamper Security Verification ─────────────────────────────────────────
Write-StepHeader "Anti-Tamper Security & Guardrail Verification"
Write-Info "Testing cryptographic rejection when specification is modified without approval..."

$TamperedRunId = "tamper-test-" + (Get-Date -Format "yyyyMMdd-HHmmss")
$TamperedSpecPath = Join-Path $SpecsDir "spec_${TamperedRunId}.json"
$TamperedReceiptPath = Join-Path $ReceiptsDir "receipt_${TamperedRunId}_step4.json"

Copy-Item $ExpectedSpecPath $TamperedSpecPath
$tamperedReceiptObj = Get-Content $ExpectedReceiptPath -Raw | ConvertFrom-Json
$tamperedReceiptObj.run_id = $TamperedRunId
$tamperedReceiptObj.jira_story_id = "MOD-999"
$tamperedReceiptObj.status = "HITL_PENDING"
$tamperedReceiptObj.hitl_approved = $false
$tamperedReceiptObj.output_pointers[0].uri = $TamperedSpecPath
$tamperedReceiptObj | ConvertTo-Json -Depth 10 | Set-Content $TamperedReceiptPath

# Maliciously tamper with the spec file
Add-Content $TamperedSpecPath "`n// TAMPERED CONTENT INSERTION"

$tamperCheck = python -c "
import json
from pipeline_core.integrations.webhook_listener import verify_and_process_approval
from pipeline_core.schemas.webhook import JiraTransitionEvent, NextAction
from datetime import datetime, timezone
from pathlib import Path

event = JiraTransitionEvent(
    issue_id='9999',
    issue_key='MOD-999',
    from_status='In Review',
    to_status='Approved',
    timestamp=datetime.now(timezone.utc),
    user_email='attacker@enterprise.com'
)
res = verify_and_process_approval(event, receipt_override_path=Path(r'$TamperedReceiptPath'))
if res.next_action == NextAction.REJECT_TAMPERED:
    print('SECURITY_TAMPER_DETECTED')
else:
    print('SECURITY_BYPASS_FAILURE: ' + str(res.next_action))
"

if ($tamperCheck -match "SECURITY_TAMPER_DETECTED") {
    Write-Ok "Anti-tamper guardrail passed: unauthorized modification rejected with REJECT_TAMPERED."
} else {
    Write-Fail "Anti-tamper guardrail failed: Tampered spec was not properly rejected! Output: $tamperCheck"
}

# Clean up tamper test files
Remove-Item $TamperedSpecPath -ErrorAction SilentlyContinue
Remove-Item $TamperedReceiptPath -ErrorAction SilentlyContinue

# ── Run Pytest Suite ──────────────────────────────────────────────────────────
Write-StepHeader "Running Pytest Suite"
python -m pytest "$PipelineModule\tests" -v
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Pytest suite failed!"
    exit 1
}
Write-Ok "All unit & integration tests passed."

# ── Summary ───────────────────────────────────────────────────────────────────
Write-Host "`n========================================================================" -ForegroundColor Green
Write-Host "STEP 3 & STEP 4 PIPELINE VERIFICATION COMPLETE" -ForegroundColor Green
Write-Host "  Checks Passed: $Pass" -ForegroundColor Green
Write-Host "  Checks Failed: $Fail" -ForegroundColor $(if ($Fail -eq 0) { "Green" } else { "Red" })
Write-Host "========================================================================`n" -ForegroundColor Green
