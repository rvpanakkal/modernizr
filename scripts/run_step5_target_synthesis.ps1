# =============================================================================
# run_step5_target_synthesis.ps1 — Windows PowerShell Step 5 Target Synthesis
# =============================================================================
# Usage:
#   .\scripts\run_step5_target_synthesis.ps1 [-ReceiptPath <path>]
#
# Prerequisites:
#   - Python 3.11+ on PATH with pipeline-core requirements installed
#   - A verified Step 4 approved receipt (receipt_*_approved.json)
# =============================================================================

param (
    [string]$ReceiptPath = ""
)

$ErrorActionPreference = "Stop"

$ProjectRoot    = Split-Path -Parent $PSScriptRoot
$PipelineModule = Join-Path $ProjectRoot "modules\pipeline-core"
$ArtifactsDir   = Join-Path $ProjectRoot "artifacts"
$ReceiptsDir    = Join-Path $ArtifactsDir "receipts"
$TargetCodeDir  = Join-Path $ArtifactsDir "target_code"

$env:PYTHONPATH = "$PipelineModule;$env:PYTHONPATH"

$Pass = 0; $Fail = 0

function Write-StepHeader($title) {
    Write-Host "`n==== $title ========================================================" -ForegroundColor Cyan
}
function Write-Ok($msg)   { Write-Host "  [OK] $msg" -ForegroundColor Green;  $script:Pass++ }
function Write-Fail($msg) { Write-Host "  [FAIL] $msg" -ForegroundColor Red;    $script:Fail++ }
function Write-Info($msg) { Write-Host "  --> $msg" -ForegroundColor Yellow }

Write-StepHeader "Step 5: Target Enterprise Code Synthesis"

# Locate approved receipt if not passed
if (-not $ReceiptPath) {
    $approvedCandidates = Get-ChildItem -Path $ReceiptsDir -Filter "receipt_*_approved.json" | Sort-Object LastWriteTime -Descending
    if ($approvedCandidates.Count -eq 0) {
        Write-Fail "No approved receipt found in $ReceiptsDir. Run Step 4 and approve first!"
        exit 1
    }
    $ReceiptPath = $approvedCandidates[0].FullName
}

Write-Info "Using approved receipt: $ReceiptPath"

# Enforce HITL metadata presence before execution
$receiptJson = Get-Content $ReceiptPath -Raw | ConvertFrom-Json
if ($receiptJson.hitl_approved -ne $true -or $receiptJson.status -ne "SUCCESS") {
    Write-Fail "Security violation: Receipt is not approved! status=$($receiptJson.status), hitl_approved=$($receiptJson.hitl_approved)"
    exit 2
}
Write-Ok "Verified Human-in-the-Loop approval metadata (Approved by: $($receiptJson.approved_by))"

# Execute Step 5 Target Synthesis
$synthCmd = "python -m pipeline_core.workflows.target_synthesis_runner --receipt `"$ReceiptPath`""
Invoke-Expression $synthCmd
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Target synthesis execution failed!"
    exit 1
}
Write-Ok "Target synthesis completed successfully."

# Verify generated assets
Write-StepHeader "Verifying Generated Target Enterprise Assets"

$ExpectedAssets = @(
    "contracts\openapi_mod-101.yaml",
    "spring_boot\src\main\java\com\enterprise\modernization\dto\TransferRequest.java",
    "spring_boot\src\main\java\com\enterprise\modernization\dto\TransferResponse.java",
    "spring_boot\src\main\java\com\enterprise\modernization\service\TransferService.java",
    "spring_boot\src\main\java\com\enterprise\modernization\web\TransferController.java",
    "angular\src\app\transfer\transfer.component.ts",
    "angular\src\app\transfer\transfer.component.html",
    "spring_boot\src\test\java\com\enterprise\modernization\service\TransferServiceTest.java"
)

foreach ($relPath in $ExpectedAssets) {
    $fullPath = Join-Path $TargetCodeDir $relPath
    if (Test-Path $fullPath) {
        $content = Get-Content $fullPath -Raw
        if ($content -match "MOD-101") {
            Write-Ok "$relPath (Found & embeds MOD-101 traceability ID)"
        } else {
            Write-Fail "$relPath (Found, but MISSING MOD-101 traceability ID)"
        }
    } else {
        Write-Fail "Missing generated asset: $relPath"
    }
}

# Verify Step 5 receipt
$RunId = $receiptJson.run_id
$Step5ReceiptPath = Join-Path $ReceiptsDir "receipt_${RunId}_step5.json"
if (Test-Path $Step5ReceiptPath) {
    $s5 = Get-Content $Step5ReceiptPath -Raw | ConvertFrom-Json
    if ($s5.status -eq "COMPLETED" -and $s5.hitl_approved -eq $true -and $s5.step_number -eq 5) {
        Write-Ok "Step 5 Receipt verified: $Step5ReceiptPath (status: COMPLETED, hitl_approved: True)"
    } else {
        Write-Fail "Step 5 Receipt invalid: status=$($s5.status), hitl_approved=$($s5.hitl_approved)"
    }
} else {
    Write-Fail "Step 5 Receipt not found: $Step5ReceiptPath"
}

Write-Host "`n========================================================================" -ForegroundColor Green
Write-Host "STEP 5 TARGET SYNTHESIS VERIFICATION COMPLETE" -ForegroundColor Green
Write-Host "  Checks Passed: $Pass" -ForegroundColor Green
Write-Host "  Checks Failed: $Fail" -ForegroundColor $(if ($Fail -eq 0) { "Green" } else { "Red" })
Write-Host "========================================================================`n" -ForegroundColor Green
