#!/usr/bin/env bash
# =============================================================================
# run_step1_and_step2.sh — End-to-end Pipeline Step 1 + Step 2 Verification
# =============================================================================
# Usage:
#   bash scripts/run_step1_and_step2.sh
#
# Prerequisites:
#   - Java 17+ on PATH (mvn)
#   - Python 3.11+ with pydantic and neo4j packages (or: cd modules/pipeline-core && poetry install)
#   - Neo4j running (docker compose up -d)
#
# Environment overrides (optional):
#   NEO4J_URI      — default: bolt://localhost:7687
#   NEO4J_USER     — default: neo4j
#   NEO4J_PASSWORD — default: modernization_secret
#   JIRA_STORY_ID  — default: MOD-001
# =============================================================================

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

LST_MODULE="${PROJECT_ROOT}/modules/lst-extractor"
PIPELINE_MODULE="${PROJECT_ROOT}/modules/pipeline-core"
SAMPLE_DIR="${PROJECT_ROOT}/samples/legacy-banking-monolith/src/main/java"
ARTIFACT_OUT="${PROJECT_ROOT}/artifacts/raw_lst/metadata_extracted.json"
RECEIPT_OUT="${PROJECT_ROOT}/artifacts/receipts/step2_receipt.json"
FAT_JAR="${LST_MODULE}/target/lst-extractor-1.0.0-SNAPSHOT.jar"

NEO4J_URI="${NEO4J_URI:-bolt://localhost:7687}"
NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:-modernization_secret}"
JIRA_STORY_ID="${JIRA_STORY_ID:-MOD-001}"

ENTRY_CLASS="com.legacy.banking.web.TransferManagedBean"

PASS=0
FAIL=0

export PYTHONPATH="${PIPELINE_MODULE}:${PYTHONPATH:-}"

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

step_header() { echo -e "\n${CYAN}${BOLD}━━━━ $1 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"; }
ok()          { echo -e "  ${GREEN}✓${NC} $1"; PASS=$((PASS+1)); }
fail()        { echo -e "  ${RED}✗${NC} $1"; FAIL=$((FAIL+1)); }
info()        { echo -e "  ${YELLOW}→${NC} $1"; }

# ── Guard: check prerequisites ────────────────────────────────────────────────
step_header "Prerequisite Checks"

if ! command -v mvn &>/dev/null; then
    fail "Maven (mvn) not found on PATH. Install Java 17+ and Maven 3.9+."
    exit 1
fi
ok "Maven found: $(mvn --version | head -1)"

if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
    fail "Python 3.11+ not found on PATH."
    exit 1
fi
PYTHON="${PYTHON:-python3}"
command -v "$PYTHON" &>/dev/null || PYTHON="python"
ok "Python found: $($PYTHON --version)"

# ── Step 1A: Maven Build ──────────────────────────────────────────────────────
step_header "Step 1A — Build LST Extractor (Maven)"

info "Building fat JAR: ${FAT_JAR}"
if mvn clean package -f "${LST_MODULE}/pom.xml" -q; then
    ok "Maven build succeeded."
else
    fail "Maven build FAILED. Check compilation errors above."
    exit 1
fi

if [[ ! -f "${FAT_JAR}" ]]; then
    fail "Fat JAR not found at expected path: ${FAT_JAR}"
    exit 1
fi
ok "Fat JAR exists: $(du -sh "${FAT_JAR}" | cut -f1)"

# ── Step 1B: Run LST Extraction against sample legacy codebase ───────────────
step_header "Step 1B — Run LST Extraction (Java EE Sample: legacy-banking-monolith)"

mkdir -p "$(dirname "${ARTIFACT_OUT}")"
info "Source directory : ${SAMPLE_DIR}"
info "Output artifact  : ${ARTIFACT_OUT}"

if java -jar "${FAT_JAR}" \
        --source-dir "${SAMPLE_DIR}" \
        --output "${ARTIFACT_OUT}"; then
    ok "LST extraction completed."
else
    fail "LST extraction FAILED."
    exit 1
fi

if [[ ! -f "${ARTIFACT_OUT}" ]]; then
    fail "Output artifact not generated: ${ARTIFACT_OUT}"
    exit 1
fi
ok "Artifact file written: $(du -sh "${ARTIFACT_OUT}" | cut -f1)"

# Spot-check: verify artifact contains expected class
CLASS_COUNT=$(${PYTHON} -c "
import json, sys
with open('${ARTIFACT_OUT}') as f:
    data = json.load(f)
print(len(data.get('classes', [])))
")
info "Extracted class count: ${CLASS_COUNT}"
if [[ "${CLASS_COUNT}" -ge 1 ]]; then
    ok "Artifact contains ${CLASS_COUNT} class record(s)."
else
    fail "Artifact contains 0 class records. Extraction may have failed silently."
fi

# Check TransferManagedBean is present
FOUND=$(${PYTHON} -c "
import json
with open('${ARTIFACT_OUT}') as f:
    data = json.load(f)
names = [c.get('simpleName','') for c in data.get('classes', [])]
print('YES' if 'TransferManagedBean' in names else 'NO')
")
if [[ "${FOUND}" == "YES" ]]; then
    ok "TransferManagedBean found in extracted metadata."
else
    fail "TransferManagedBean NOT found in extracted metadata."
fi

# ── Step 2A: Neo4j Ingestion ──────────────────────────────────────────────────
step_header "Step 2A — Neo4j Graph Ingestion (Pipeline Core)"

# Check Neo4j connectivity
info "Testing Neo4j connectivity at: ${NEO4J_URI}"
if ! ${PYTHON} -c "
import sys
try:
    from neo4j import GraphDatabase
    d = GraphDatabase.driver('${NEO4J_URI}', auth=('${NEO4J_USER}','${NEO4J_PASSWORD}'))
    d.verify_connectivity()
    d.close()
    print('OK')
except Exception as e:
    print(f'FAIL: {e}', file=sys.stderr)
    sys.exit(1)
" 2>&1; then
    fail "Cannot connect to Neo4j at ${NEO4J_URI}. Ensure 'docker compose up -d' is running."
    exit 1
fi
ok "Neo4j connection verified."

mkdir -p "$(dirname "${RECEIPT_OUT}")"
info "Ingesting: ${ARTIFACT_OUT}"

if ${PYTHON} -m pipeline_core.graph.ingest_graph \
        --input     "${ARTIFACT_OUT}" \
        --uri       "${NEO4J_URI}" \
        --user      "${NEO4J_USER}" \
        --password  "${NEO4J_PASSWORD}" \
        --receipt-out "${RECEIPT_OUT}" \
        --jira-id   "${JIRA_STORY_ID}"; then
    ok "Neo4j ingestion completed."
else
    fail "Neo4j ingestion FAILED."
    exit 1
fi

if [[ -f "${RECEIPT_OUT}" ]]; then
    ok "StepHandoffReceipt written: ${RECEIPT_OUT}"
    STEP2_STATUS=$(${PYTHON} -c "
import json
with open('${RECEIPT_OUT}') as f:
    r = json.load(f)
print(r.get('status','UNKNOWN'))
")
    ok "Receipt status: ${STEP2_STATUS}"
else
    fail "Receipt file not generated."
fi

# ── Step 2B: GraphRAG Vertical Slice Extraction ───────────────────────────────
step_header "Step 2B — GraphRAG Vertical Slice Verification"

info "Discovering entry points …"
info "Extracting vertical slice for: ${ENTRY_CLASS}"

SLICE_OUTPUT=$(${PYTHON} -c "
import json, sys, logging
logging.disable(logging.CRITICAL)
try:
    from neo4j import GraphDatabase
    from pipeline_core.graph.queries import find_entry_points, extract_vertical_slice

    driver = GraphDatabase.driver('${NEO4J_URI}', auth=('${NEO4J_USER}','${NEO4J_PASSWORD}'))
    with driver.session() as session:
        entry_points = find_entry_points(session)
        print(f'ENTRY_COUNT:{len(entry_points)}', file=sys.stderr)

        slice_ctx = extract_vertical_slice(session, '${ENTRY_CLASS}', max_depth=5)
        print(json.dumps(slice_ctx, indent=2, default=str))
    driver.close()
except Exception as e:
    print(json.dumps({'error': str(e)}), file=sys.stdout)
    sys.exit(1)
" 2>&1)

# Parse stderr for entry count
ENTRY_COUNT=$(echo "${SLICE_OUTPUT}" | grep "ENTRY_COUNT:" | sed 's/ENTRY_COUNT://')
SLICE_JSON=$(echo "${SLICE_OUTPUT}" | grep -v "ENTRY_COUNT:")

if [[ -n "${ENTRY_COUNT}" && "${ENTRY_COUNT}" -ge 1 ]]; then
    ok "${ENTRY_COUNT} entry point(s) discovered in Neo4j."
else
    info "Entry count: ${ENTRY_COUNT:-unknown}"
fi

# Check slice contains expected execution path
if echo "${SLICE_JSON}" | ${PYTHON} -c "
import json, sys
data = json.load(sys.stdin)
if 'error' in data:
    print(f'ERROR: {data[\"error\"]}')
    sys.exit(1)
paths = [p['path'] for p in data.get('executionPaths', [])]
boundaries = [b['simpleName'] for b in data.get('integrationBoundaries', [])]
components = [c['simpleName'] for c in data.get('componentSummary', [])]
print(f'Execution paths: {paths}')
print(f'Boundaries:      {boundaries}')
print(f'Components:      {components}')
print(f'Token estimate:  {data.get(\"estimatedTokens\", \"?\")}')
within = data.get('withinBudget', False)
print(f'Within budget:   {within}')
# Verify chain
found_svc = any('TransferProcessingService' in c for c in components)
found_gw  = any('CicsMainframeGateway' in c for c in components)
if found_svc: print('CHAIN_SVC:YES')
if found_gw:  print('CHAIN_GW:YES')
"; then
    ok "Vertical slice extracted successfully."
else
    fail "Slice extraction returned an error."
fi

CHAIN_SVC=$(echo "${SLICE_JSON}" | ${PYTHON} -c "
import json, sys
data = json.load(sys.stdin)
comps = [c.get('simpleName','') for c in data.get('componentSummary',[])]
print('YES' if 'TransferProcessingService' in comps else 'NO')
" 2>/dev/null || echo "NO")

CHAIN_GW=$(echo "${SLICE_JSON}" | ${PYTHON} -c "
import json, sys
data = json.load(sys.stdin)
comps = [c.get('simpleName','') for c in data.get('componentSummary',[])]
print('YES' if 'CicsMainframeGateway' in comps else 'NO')
" 2>/dev/null || echo "NO")

if [[ "${CHAIN_SVC}" == "YES" ]]; then
    ok "TransferManagedBean → TransferProcessingService chain verified in slice."
else
    fail "TransferProcessingService NOT found in vertical slice."
fi

if [[ "${CHAIN_GW}" == "YES" ]]; then
    ok "TransferProcessingService → CicsMainframeGateway boundary verified in slice."
else
    fail "CicsMainframeGateway NOT found in vertical slice. (May be expected if call graph resolution failed.)"
fi

# Print extracted slice JSON
echo -e "\n${BOLD}━━━━ Extracted Vertical Slice JSON ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo "${SLICE_JSON}" | ${PYTHON} -m json.tool 2>/dev/null || echo "${SLICE_JSON}"

# ── Final Summary ─────────────────────────────────────────────────────────────
step_header "Summary"
echo -e "  Passed: ${GREEN}${BOLD}${PASS}${NC}   Failed: ${RED}${BOLD}${FAIL}${NC}"

if [[ "${FAIL}" -eq 0 ]]; then
    echo -e "\n${GREEN}${BOLD}  ✓ All pipeline stages completed successfully.${NC}"
    echo -e "  TransferManagedBean → TransferProcessingService → CicsMainframeGateway"
    echo -e "  vertical slice is ready for Step 3 (Decompiler) cognitive processing.\n"
    exit 0
else
    echo -e "\n${RED}${BOLD}  ✗ ${FAIL} stage(s) failed. Review errors above.${NC}\n"
    exit 1
fi
