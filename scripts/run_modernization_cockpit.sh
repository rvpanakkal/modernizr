#!/usr/bin/env bash
# =============================================================================
# Modernization Cockpit Orchestration Launcher
# =============================================================================
# Starts the Neo4j graph container (if Docker is present), bootstraps the
# FastAPI control plane on port 8000, and launches the Vite React Cockpit UI on port 5173.
# =============================================================================

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "====================================================================="
echo "   ENTERPRISE LEGACY MODERNIZATION FACTORY — COCKPIT LAUNCHER        "
echo "====================================================================="

# 1. Start Neo4j Container via Docker Compose (Graceful fallback to mock mode)
echo "[1/3] Checking Neo4j Graph Database status..."
if command -v docker &> /dev/null && docker info &> /dev/null; then
    echo "       Docker daemon detected. Ensuring Neo4j container is running..."
    docker-compose up -d neo4j
    echo "       Waiting for Neo4j Bolt port 7687..."
    for i in {1..15}; do
        if nc -z localhost 7687 2>/dev/null || (exec 3<>/dev/tcp/localhost/7687) 2>/dev/null; then
            echo "       Neo4j is healthy and responding on bolt://localhost:7687"
            break
        fi
        sleep 1
    done
else
    echo "       Docker daemon not running or not found."
    echo "       Operating FastAPI Control Plane in Resilient MOCK_MODE."
fi

# 2. Start FastAPI Control Plane Server
echo "[2/3] Starting FastAPI Control Plane on http://localhost:8000..."
export PYTHONPATH="$REPO_ROOT/modules/pipeline-core:$PYTHONPATH"
export MOCK_MODE="${MOCK_MODE:-true}"
export MOCK_JIRA="${MOCK_JIRA:-true}"

python -m uvicorn api.server:app --app-dir "$REPO_ROOT/modules/pipeline-core" --host 0.0.0.0 --port 8000 &
API_PID=$!

# 3. Start Vite React UI Server
echo "[3/3] Starting Modernization Wizard UI on http://localhost:5173..."
cd "$REPO_ROOT/apps/wizard-ui"
npm run dev -- --host 0.0.0.0 --port 5173 &
UI_PID=$!

cleanup() {
    echo ""
    echo "Shutting down Modernization Cockpit processes..."
    kill $API_PID 2>/dev/null || true
    kill $UI_PID 2>/dev/null || true
    echo "Services stopped cleanly."
}
trap cleanup SIGINT SIGTERM EXIT

echo ""
echo "====================================================================="
echo " Modernization Cockpit is LIVE!"
echo " • Cockpit UI:              http://localhost:5173"
echo " • API Control Plane:       http://localhost:8000"
echo " • API Interactive Docs:    http://localhost:8000/docs"
echo "====================================================================="
echo " Press [Ctrl+C] to stop all services."

wait
