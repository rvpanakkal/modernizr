#!/usr/bin/env bash
# =============================================================================
# run_step3_and_step4.sh — Bash End-to-end Step 3 & Step 4 Pipeline Verification
# =============================================================================
# Usage:
#   ./scripts/run_step3_and_step4.sh [--live-llm] [--live-jira]
#
# Prerequisites:
#   - Python 3.11+ on PATH with pipeline-core requirements installed
#   - Optional: ANTHROPIC_API_KEY for live Claude 3.7 Sonnet cognitive passes
#   - Optional: JIRA_API_TOKEN, JIRA_BASE_URL for live Jira issue creation
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PIPELINE_MODULE="$PROJECT_ROOT/modules/pipeline-core"
ARTIFACTS_DIR="$PROJECT_ROOT/artifacts"
SPECS_DIR="$ARTIFACTS_DIR/generated_specs"
RECEIPTS_DIR="$ARTIFACTS_DIR/receipts"
SLICE_PATH="$ARTIFACTS_DIR/raw_lst/sample_vertical_slice.json"

export PYTHONPATH="$PIPELINE_MODULE:${PYTHONPATH:-}"

MOCK_LLM="true"
MOCK_JIRA="true"

for arg in "$@"; do
    case "$arg" in
        --live-llm)  MOCK_LLM="false" ;;
        --live-jira) MOCK_JIRA="false" ;;
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

RUN_ID="run-sh-$(date +%Y%m%d-%H%M%S)"

# ── Environment & Prerequisites ───────────────────────────────────────────────
header "Step 3/4 Prerequisites & Environment"
info "Project root : $PROJECT_ROOT"
info "Run ID       : $RUN_ID"
info "MOCK_LLM     : $MOCK_LLM"
info "MOCK_JIRA    : $MOCK_JIRA"

if [[ ! -f "$SLICE_PATH" ]]; then
    fail "Input vertical slice not found at: $SLICE_PATH"
    exit 1
fi
ok "Found input vertical slice: $SLICE_PATH"

# ── Step 3 & Step 4 Execution ─────────────────────────────────────────────────
header "Step 3: Multi-Pass Cognitive Chain & Step 4: Jira HITL Gate"
info "Executing Decompiler -> Business Abstractor -> Spec Formatter -> Jira HITL Gate..."

python -m pipeline_core.workflows.cognitive_runner \
    --slice "$SLICE_PATH" \
    --run-id "$RUN_ID" \
    --mock-llm \
    --mock-jira

ok "Cognitive runner finished successfully."

# ── Verify Step 4 Output Artifacts ────────────────────────────────────────────
header "Verifying Generated Specification & Step 4 Checkpoint Receipt"

EXPECTED_SPEC="$SPECS_DIR/spec_${RUN_ID}.json"
EXPECTED_RECEIPT="$RECEIPTS_DIR/receipt_${RUN_ID}_step4.json"

if [[ ! -f "$EXPECTED_SPEC" ]]; then
    fail "Generated specification JSON not found: $EXPECTED_SPEC"
    exit 1
fi
ok "Specification JSON generated on disk: $EXPECTED_SPEC"

if [[ ! -f "$EXPECTED_RECEIPT" ]]; then
    fail "Step 4 Checkpoint Receipt not found: $EXPECTED_RECEIPT"
    exit 1
fi
ok "Step 4 Checkpoint Receipt emitted: $EXPECTED_RECEIPT"

STATUS=$(python -c "import json; data=json.load(open('$EXPECTED_RECEIPT')); print(data.get('status'))")
JIRA_ID=$(python -c "import json; data=json.load(open('$EXPECTED_RECEIPT')); print(data.get('jira_story_id'))")
HITL_APPROVED=$(python -c "import json; data=json.load(open('$EXPECTED_RECEIPT')); print(data.get('hitl_approved'))")
NEXT_STEP=$(python -c "import json; data=json.load(open('$EXPECTED_RECEIPT')); print(data.get('next_step'))")

info "Receipt Status       : $STATUS"
info "Jira Story ID        : $JIRA_ID"
info "HITL Approved        : $HITL_APPROVED"
info "Next Step            : $NEXT_STEP"

if [[ "$STATUS" == "HITL_PENDING" ]]; then
    ok "Pipeline correctly PAUSED in status HITL_PENDING."
else
    fail "Expected status HITL_PENDING, found: $STATUS"
fi

if [[ "$HITL_APPROVED" == "False" ]]; then
    ok "Human-in-the-loop guardrail active (hitl_approved = False)."
else
    fail "Invariant violation: hitl_approved must be False prior to human review!"
fi

# ── Automated Webhook Resume: Simulate Architect Approval ─────────────────────
header "Automated Webhook Resume & Cryptographic Integrity Verification"
info "Simulating Lead Architect Jira transition to 'Approved'..."

python -m pipeline_core.integrations.webhook_listener \
    --simulate-approval "$EXPECTED_RECEIPT" \
    --approver "lead_architect@enterprise.com" \
    --status "Approved"

ok "Webhook approval simulation succeeded."

APPROVED_RECEIPT="$RECEIPTS_DIR/receipt_${RUN_ID}_approved.json"
if [[ ! -f "$APPROVED_RECEIPT" ]]; then
    fail "Approved receipt file not found: $APPROVED_RECEIPT"
    exit 1
fi
ok "Approved receipt generated: $APPROVED_RECEIPT"

APP_STATUS=$(python -c "import json; data=json.load(open('$APPROVED_RECEIPT')); print(data.get('status'))")
APP_APPROVED=$(python -c "import json; data=json.load(open('$APPROVED_RECEIPT')); print(data.get('hitl_approved'))")

if [[ "$APP_STATUS" == "SUCCESS" && "$APP_APPROVED" == "True" ]]; then
    ok "State transition confirmed: status=SUCCESS, hitl_approved=True."
    ok "Target synthesis unblocked (next_step: $NEXT_STEP)."
else
    fail "State transition failed: Status=$APP_STATUS, Approved=$APP_APPROVED"
fi

# ── Anti-Tamper Security Verification ─────────────────────────────────────────
header "Anti-Tamper Security & Guardrail Verification"
info "Testing cryptographic rejection when specification is modified without approval..."

TAMPER_RUN_ID="tamper-sh-$(date +%Y%m%d-%H%M%S)"
TAMPER_SPEC="$SPECS_DIR/spec_${TAMPER_RUN_ID}.json"
TAMPER_RECEIPT="$RECEIPTS_DIR/receipt_${TAMPER_RUN_ID}_step4.json"

cp "$EXPECTED_SPEC" "$TAMPER_SPEC"
python -c "
import json
d = json.load(open('$EXPECTED_RECEIPT'))
d['run_id'] = '$TAMPER_RUN_ID'
d['jira_story_id'] = 'MOD-999'
d['status'] = 'HITL_PENDING'
d['hitl_approved'] = False
d['output_pointers'][0]['uri'] = '$TAMPER_SPEC'
with open('$TAMPER_RECEIPT', 'w') as f:
    json.dump(d, f, indent=2)
"

# Maliciously tamper with the spec file
echo "// MALICIOUS TAMPERING" >> "$TAMPER_SPEC"

TAMPER_OUTPUT=$(python -c "
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
res = verify_and_process_approval(event, receipt_override_path=Path('$TAMPER_RECEIPT'))
if res.next_action == NextAction.REJECT_TAMPERED:
    print('SECURITY_TAMPER_DETECTED')
else:
    print('SECURITY_BYPASS_FAILURE: ' + str(res.next_action))
")

if [[ "$TAMPER_OUTPUT" =~ "SECURITY_TAMPER_DETECTED" ]]; then
    ok "Anti-tamper guardrail passed: unauthorized modification rejected with REJECT_TAMPERED."
else
    fail "Anti-tamper guardrail failed! Output: $TAMPER_OUTPUT"
fi

rm -f "$TAMPER_SPEC" "$TAMPER_RECEIPT"

# ── Run Pytest Suite ──────────────────────────────────────────────────────────
header "Running Pytest Suite"
python -m pytest "$PIPELINE_MODULE/tests" -v
ok "All unit & integration tests passed."

# ── Summary ───────────────────────────────────────────────────────────────────
echo -e "\n\033[1;32m========================================================================\033[0m"
echo -e "\033[1;32mSTEP 3 & STEP 4 PIPELINE VERIFICATION COMPLETE\033[0m"
echo -e "\033[1;32m  Checks Passed: $PASS\033[0m"
if [[ $FAIL -eq 0 ]]; then
    echo -e "\033[1;32m  Checks Failed: 0\033[0m"
else
    echo -e "\033[1;31m  Checks Failed: $FAIL\033[0m"
    exit 1
fi
echo -e "\033[1;32m========================================================================\033[0m\n"
