#!/usr/bin/env bash
# =============================================================================
# run_step5_target_synthesis.sh — Bash Step 5 Target Synthesis Verification
# =============================================================================
# Usage:
#   ./scripts/run_step5_target_synthesis.sh [RECEIPT_PATH]
#
# Prerequisites:
#   - Python 3.11+ on PATH with pipeline-core requirements installed
#   - A verified Step 4 approved receipt (receipt_*_approved.json)
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PIPELINE_MODULE="$PROJECT_ROOT/modules/pipeline-core"
ARTIFACTS_DIR="$PROJECT_ROOT/artifacts"
RECEIPTS_DIR="$ARTIFACTS_DIR/receipts"
TARGET_CODE_DIR="$ARTIFACTS_DIR/target_code"

export PYTHONPATH="$PIPELINE_MODULE:${PYTHONPATH:-}"

PASS=0
FAIL=0

header() {
    echo -e "\n\033[1;36m==== $1 ========================================================\033[0m"
}
ok() {
    echo -e "  \033[1;32m[OK]\033[0m $1"
    PASS=$((PASS + 1))
}
fail() {
    echo -e "  \033[1;31m[FAIL]\033[0m $1"
    FAIL=$((FAIL + 1))
}
info() {
    echo -e "  \033[1;33m-->\033[0m $1"
}

header "Step 5: Target Enterprise Code Synthesis"

RECEIPT_PATH="${1:-}"
if [[ -z "$RECEIPT_PATH" ]]; then
    # Find most recent approved receipt
    RECEIPT_PATH=$(ls -t "$RECEIPTS_DIR"/receipt_*_approved.json 2>/dev/null | head -n 1 || true)
    if [[ -z "$RECEIPT_PATH" || ! -f "$RECEIPT_PATH" ]]; then
        fail "No approved receipt found in $RECEIPTS_DIR. Run Step 4 and approve first!"
        exit 1
    fi
fi

info "Using approved receipt: $RECEIPT_PATH"

# Enforce HITL metadata presence before execution
HITL_APPROVED=$(python -c "import json; d=json.load(open('$RECEIPT_PATH')); print(d.get('hitl_approved'))")
STATUS=$(python -c "import json; d=json.load(open('$RECEIPT_PATH')); print(d.get('status'))")
APPROVED_BY=$(python -c "import json; d=json.load(open('$RECEIPT_PATH')); print(d.get('approved_by'))")
RUN_ID=$(python -c "import json; d=json.load(open('$RECEIPT_PATH')); print(d.get('run_id'))")

if [[ "$HITL_APPROVED" != "True" || "$STATUS" != "SUCCESS" ]]; then
    fail "Security violation: Receipt is not approved! status=$STATUS, hitl_approved=$HITL_APPROVED"
    exit 2
fi
ok "Verified Human-in-the-Loop approval metadata (Approved by: $APPROVED_BY)"

# Execute Step 5 Target Synthesis
python -m pipeline_core.workflows.target_synthesis_runner --receipt "$RECEIPT_PATH"
ok "Target synthesis completed successfully."

# Verify generated assets
header "Verifying Generated Target Enterprise Assets"

EXPECTED_ASSETS=(
    "contracts/openapi_mod-101.yaml"
    "spring_boot/src/main/java/com/enterprise/modernization/dto/TransferRequest.java"
    "spring_boot/src/main/java/com/enterprise/modernization/dto/TransferResponse.java"
    "spring_boot/src/main/java/com/enterprise/modernization/service/TransferService.java"
    "spring_boot/src/main/java/com/enterprise/modernization/web/TransferController.java"
    "angular/src/app/transfer/transfer.component.ts"
    "angular/src/app/transfer/transfer.component.html"
    "spring_boot/src/test/java/com/enterprise/modernization/service/TransferServiceTest.java"
)

for relPath in "${EXPECTED_ASSETS[@]}"; do
    fullPath="$TARGET_CODE_DIR/$relPath"
    if [[ -f "$fullPath" ]]; then
        if grep -q "MOD-101" "$fullPath"; then
            ok "$relPath (Found & embeds MOD-101 traceability ID)"
        else
            fail "$relPath (Found, but MISSING MOD-101 traceability ID)"
        fi
    else
        fail "Missing generated asset: $relPath"
    fi
done

# Verify Step 5 receipt
STEP5_RECEIPT="$RECEIPTS_DIR/receipt_${RUN_ID}_step5.json"
if [[ -f "$STEP5_RECEIPT" ]]; then
    S5_STATUS=$(python -c "import json; d=json.load(open('$STEP5_RECEIPT')); print(d.get('status'))")
    S5_APPROVED=$(python -c "import json; d=json.load(open('$STEP5_RECEIPT')); print(d.get('hitl_approved'))")
    if [[ "$S5_STATUS" == "COMPLETED" && "$S5_APPROVED" == "True" ]]; then
        ok "Step 5 Receipt verified: $STEP5_RECEIPT (status: COMPLETED, hitl_approved: True)"
    else
        fail "Step 5 Receipt invalid: status=$S5_STATUS, hitl_approved=$S5_APPROVED"
    fi
else
    fail "Step 5 Receipt not found: $STEP5_RECEIPT"
fi

echo -e "\n\033[1;32m========================================================================\033[0m"
echo -e "\033[1;32mSTEP 5 TARGET SYNTHESIS VERIFICATION COMPLETE\033[0m"
echo -e "\033[1;32m  Checks Passed: $PASS\033[0m"
if [[ $FAIL -eq 0 ]]; then
    echo -e "\033[1;32m  Checks Failed: 0\033[0m"
else
    echo -e "\033[1;31m  Checks Failed: $FAIL\033[0m"
    exit 1
fi
echo -e "\033[1;32m========================================================================\033[0m\n"
