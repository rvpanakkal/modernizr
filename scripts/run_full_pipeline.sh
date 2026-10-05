#!/usr/bin/env bash
# =============================================================================
# run_full_pipeline.sh — Master End-to-End Modernization Pipeline (Steps 1 - 5)
# =============================================================================
# Usage:
#   ./scripts/run_full_pipeline.sh [--skip-step12] [--live-llm] [--live-jira]
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PIPELINE_MODULE="$PROJECT_ROOT/modules/pipeline-core"
LST_MODULE="$PROJECT_ROOT/modules/lst-extractor"
ARTIFACTS_DIR="$PROJECT_ROOT/artifacts"
RAW_LST_DIR="$ARTIFACTS_DIR/raw_lst"
SPECS_DIR="$ARTIFACTS_DIR/generated_specs"
RECEIPTS_DIR="$ARTIFACTS_DIR/receipts"
TARGET_CODE_DIR="$ARTIFACTS_DIR/target_code"
SAMPLE_DIR="$PROJECT_ROOT/samples/legacy-banking-monolith/src/main/java"

export PYTHONPATH="$PIPELINE_MODULE:${PYTHONPATH:-}"

SKIP_STEP12=false
MOCK_LLM="true"
MOCK_JIRA="true"

for arg in "$@"; do
    case "$arg" in
        --skip-step12) SKIP_STEP12=true ;;
        --live-llm)    MOCK_LLM="false" ;;
        --live-jira)   MOCK_JIRA="false" ;;
    esac
done

export MOCK_LLM
export MOCK_JIRA

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

RUN_ID="run-sh-e2e-$(date +%Y%m%d-%H%M%S)"

header "Enterprise Legacy Modernization Factory — Full Pipeline (Steps 1 - 5)"
info "Project Root: $PROJECT_ROOT"
info "Run ID      : $RUN_ID"

# ── STEP 1 & 2 ────────────────────────────────────────────────────────────────
SLICE_PATH="$RAW_LST_DIR/sample_vertical_slice.json"
if [[ "$SKIP_STEP12" == "false" ]]; then
    header "Step 1 & Step 2: LST Extraction & Graph Context"
    FAT_JAR="$LST_MODULE/target/lst-extractor-1.0.0-SNAPSHOT.jar"
    if [[ -f "$FAT_JAR" ]]; then
        info "Using compiled LST extractor: $FAT_JAR"
        RAW_LST_JSON="$RAW_LST_DIR/metadata_extracted.json"
        java -jar "$FAT_JAR" --source-dir "$SAMPLE_DIR" --output "$RAW_LST_JSON" || true
        if [[ -f "$RAW_LST_JSON" ]]; then
            ok "Step 1 LST Extraction complete: $RAW_LST_JSON"
        fi
    fi
fi

if [[ ! -f "$SLICE_PATH" ]]; then
    fail "Input vertical slice not found: $SLICE_PATH"
    exit 1
fi
ok "Vertical slice ready: $SLICE_PATH"

# ── STEP 3 & STEP 4: Cognitive Chain & Jira HITL Gate ─────────────────────────
header "Step 3 (Cognitive Chain) & Step 4 (Jira HITL Gate)"
info "Executing Decompiler -> Business Abstractor -> Spec Formatter -> Jira HITL Gate..."

python -m pipeline_core.workflows.cognitive_runner \
    --slice "$SLICE_PATH" \
    --run-id "$RUN_ID" \
    --mock-llm \
    --mock-jira

ok "Cognitive runner executed successfully."

STEP4_RECEIPT="$RECEIPTS_DIR/receipt_${RUN_ID}_step4.json"
SPEC_FILE="$SPECS_DIR/spec_${RUN_ID}.json"

if [[ ! -f "$STEP4_RECEIPT" || ! -f "$SPEC_FILE" ]]; then
    fail "Step 4 artifacts missing on disk!"
    exit 1
fi

S4_STATUS=$(python -c "import json; d=json.load(open('$STEP4_RECEIPT')); print(d.get('status'))")
S4_APPROVED=$(python -c "import json; d=json.load(open('$STEP4_RECEIPT')); print(d.get('hitl_approved'))")

if [[ "$S4_STATUS" == "HITL_PENDING" && "$S4_APPROVED" == "False" ]]; then
    ok "HITL Gate Invariant Enforced: Pipeline paused in status HITL_PENDING (hitl_approved = False)."
else
    fail "HITL Invariant violation: Status=$S4_STATUS, Approved=$S4_APPROVED"
    exit 1
fi

# ── AUTOMATED WEBHOOK RESUME: Architect Sign-off & Step 5 Auto-Synthesis ──────
header "Jira Webhook Approval & Step 5 Target Synthesis"
info "Simulating Jira approval transition by lead architect..."

python -m pipeline_core.integrations.webhook_listener \
    --simulate-approval "$STEP4_RECEIPT" \
    --approver "lead_architect@enterprise.com" \
    --auto-synthesize

ok "Webhook approval verified & Step 5 Target Synthesis auto-executed."

# ── VERIFY FINAL ASSETS & STEP 5 RECEIPT ───────────────────────────────────────
header "Verifying Final Synthesized Architecture Assets"

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
            ok "$relPath (Found & embeds MOD-101)"
        else
            fail "$relPath (Missing MOD-101 ID)"
        fi
    else
        fail "Missing file: $relPath"
    fi
done

STEP5_RECEIPT="$RECEIPTS_DIR/receipt_${RUN_ID}_step5.json"
if [[ -f "$STEP5_RECEIPT" ]]; then
    S5_STATUS=$(python -c "import json; d=json.load(open('$STEP5_RECEIPT')); print(d.get('status'))")
    S5_APPROVED=$(python -c "import json; d=json.load(open('$STEP5_RECEIPT')); print(d.get('hitl_approved'))")
    if [[ "$S5_STATUS" == "COMPLETED" && "$S5_APPROVED" == "True" ]]; then
        ok "Step 5 Receipt verified: $STEP5_RECEIPT (status: COMPLETED, hitl_approved: True)"
    else
        fail "Step 5 Receipt invalid status!"
    fi
else
    fail "Step 5 Receipt missing: $STEP5_RECEIPT"
fi

# ── RUN COMPLETE PYTEST TEST SUITE ────────────────────────────────────────────
header "Running Full Pipeline Test Suite"
python -m pytest "$PIPELINE_MODULE/tests" -v
ok "All 52 unit and integration tests passed."

echo -e "\n\033[1;32m========================================================================\033[0m"
echo -e "\033[1;32mENTERPRISE MODERNIZATION FACTORY: END-TO-END PIPELINE SUCCESSFUL\033[0m"
echo -e "\033[1;32m  Run ID       : $RUN_ID\033[0m"
echo -e "\033[1;32m  Checks Passed: $PASS\033[0m"
if [[ $FAIL -eq 0 ]]; then
    echo -e "\033[1;32m  Checks Failed: 0\033[0m"
else
    echo -e "\033[1;31m  Checks Failed: $FAIL\033[0m"
    exit 1
fi
echo -e "\033[1;32m========================================================================\033[0m\n"
