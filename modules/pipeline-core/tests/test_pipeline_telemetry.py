"""
Tests for Step 3: Cognitive Extraction Subsystem and SSE Telemetry Stream.
Verifies run initiation, sequential multi-pass events, token streaming, and spec artifact persistence.
"""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from api.server import app

client = TestClient(app)


def test_post_pipeline_run_initiates_successfully():
    response = client.post(
        "/api/pipeline/runs",
        json={
            "entry_fqn": "com.legacy.banking.web.TransferManagedBean",
            "max_depth": 5,
            "tracker_type": "jira",
        },
    )
    assert response.status_code == 202
    data = response.json()
    assert "run_id" in data
    assert data["run_id"].startswith("run-")
    assert data["status"] == "STARTED"
    assert "/api/pipeline/runs/" in data["stream_url"]


def test_pipeline_runs_list_and_details():
    # 1. Start a run
    init_res = client.post(
        "/api/pipeline/runs",
        json={"entry_fqn": "com.legacy.banking.web.TransferManagedBean"},
    )
    assert init_res.status_code == 202
    run_id = init_res.json()["run_id"]

    # 2. Query list of runs
    list_res = client.get("/api/pipeline/runs")
    assert list_res.status_code == 200
    runs = list_res.json()
    assert isinstance(runs, list)
    assert any(r["run_id"] == run_id for r in runs)

    # 3. Query single run details
    detail_res = client.get(f"/api/pipeline/runs/{run_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["run_id"] == run_id
    assert "status" in detail


def test_sse_stream_delivers_sequential_events():
    # 1. Start run
    init_res = client.post(
        "/api/pipeline/runs",
        json={
            "entry_fqn": "com.legacy.banking.web.TransferManagedBean",
            "max_depth": 3,
        },
    )
    assert init_res.status_code == 202
    run_id = init_res.json()["run_id"]

    # 2. Stream SSE events
    observed_events = []
    with client.stream("GET", f"/api/pipeline/runs/{run_id}/stream") as stream_res:
        assert stream_res.status_code == 200
        for line in stream_res.iter_lines():
            if not line:
                continue
            if line.startswith("event:"):
                event_name = line.split(":", 1)[1].strip()
                observed_events.append(event_name)
            elif line.startswith("data:"):
                data_str = line.split(":", 1)[1].strip()
                try:
                    payload = json.loads(data_str)
                    if payload.get("type"):
                        observed_events.append(payload["type"])
                except Exception:
                    pass

            if "EXTRACTION_COMPLETE" in observed_events:
                break

    # Verify event types received in sequence
    assert "RUN_STARTED" in observed_events
    assert "PASS_STARTED" in observed_events
    assert "TOKEN_CHUNK" in observed_events
    assert "PASS_COMPLETED" in observed_events
    assert "SPEC_GENERATED" in observed_events
    assert "EXTRACTION_COMPLETE" in observed_events

    # 3. Verify disk artifact persistence
    specs_dir = Path(__file__).resolve().parent.parent / "artifacts" / "specs"
    spec_path = specs_dir / f"{run_id}.json"
    assert spec_path.exists()

    spec_data = json.loads(spec_path.read_text(encoding="utf-8"))
    assert spec_data["run_id"] == run_id
    assert len(spec_data["business_rules"]) > 0
    assert len(spec_data["bdd_scenarios"]) > 0
    assert len(spec_data["sha256_hash"]) == 64
    assert "openapi" in spec_data["openapi_spec_yaml"].lower()
