#!/usr/bin/env bash
# =============================================================================
# run_mock_mode.sh -- Modernization Factory Mock Mode Single-Click Launcher
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "====================================================================="
echo "   ENTERPRISE LEGACY MODERNIZATION FACTORY -- MOCK MODE LAUNCHER     "
echo "   (Running Java LST Extractor + Python FastAPI + React Cockpit UI)  "
echo "====================================================================="

# 1. Java Module: LST Extraction
FAT_JAR="$REPO_ROOT/modules/lst-extractor/target/lst-extractor-1.0.0-SNAPSHOT.jar"
RAW_OUT_DIR="$REPO_ROOT/artifacts/raw_lst"
RAW_OUT_JSON="$RAW_OUT_DIR/metadata_extracted.json"
mkdir -p "$RAW_OUT_DIR"

if [ -f "$FAT_JAR" ]; then
    echo "[1/3] Executing Java LST Extractor..."
    java -jar "$FAT_JAR" \
      --source-dir "$REPO_ROOT/samples/legacy-banking-monolith/src/main/java" \
      --output "$RAW_OUT_JSON" || true
else
    echo "[1/3] Fat JAR not found. Using pre-extracted metadata."
fi

# 2. Python Module: Launch FastAPI
echo "[2/3] Launching FastAPI Control Plane on http://localhost:8000..."
export PYTHONPATH="$REPO_ROOT/modules/pipeline-core:$PYTHONPATH"
export MOCK_MODE="true"
export MOCK_LLM="true"
export MOCK_JIRA="true"
export MOCK_GITHUB="true"

python3 -m uvicorn api.server:app --host 0.0.0.0 --port 8000 --app-dir "$REPO_ROOT/modules/pipeline-core" &
BACKEND_PID=$!

cleanup() {
    echo -e "\nShutting down Python background server (PID: $BACKEND_PID)..."
    kill "$BACKEND_PID" 2>/dev/null || true
    echo "Services stopped."
}
trap cleanup EXIT INT TERM

sleep 2

# 3. UI Module: Launch React Cockpit
echo "[3/3] Launching Vite React Cockpit on http://localhost:5173..."
cd "$REPO_ROOT/apps/wizard-ui"
if [ ! -d "node_modules" ]; then
    npm install
fi

echo ""
echo "====================================================================="
echo " Modernization Factory is LIVE in MOCK MODE!"
echo " • Cockpit UI:              http://localhost:5173"
echo " • API Control Plane:       http://localhost:8000"
echo " • API Interactive Docs:    http://localhost:8000/docs"
echo "====================================================================="
echo " Press [Ctrl+C] to stop."
echo ""

npm run dev -- --host 0.0.0.0 --port 5173
