"""
Tests for Batch Vertical Slice Extraction and Telemetry.
Verifies batch initiation, concurrent slice execution, status querying, and batch persistence.
"""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from api.server import app

client = TestClient(app)


def test_create_and_poll_batch():
    # 1. Post batch request with 3 entry FQNs
    entry_fqns = [
        "com.legacy.banking.web.TransferManagedBean",
        "com.legacy.banking.web.LoanApplicationManagedBean",
        "com.legacy.banking.web.AuthenticationManagedBean",
    ]
    resp = client.post(
        "/api/pipeline/batches",
        json={"entry_fqns": entry_fqns, "max_depth": 3, "tracker_type": "jira"},
    )
    assert resp.status_code == 202
    batch_data = resp.json()
    batch_id = batch_data["batch_id"]
    assert batch_id.startswith("batch-")
    assert batch_data["total_slices"] == 3
    assert len(batch_data["slices"]) == 3
    for s in batch_data["slices"]:
        assert s["status"] in ("QUEUED", "RUNNING", "COMPLETED")
        assert s["run_id"].startswith("run-")

    # 2. Query batch status
    status_resp = client.get(f"/api/pipeline/batches/{batch_id}")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["batch_id"] == batch_id
    assert status_data["total_slices"] == 3
    assert status_data["status"] in ("PROCESSING", "COMPLETED")

    # 3. Query list of batches
    list_resp = client.get("/api/pipeline/batches")
    assert list_resp.status_code == 200
    batches = list_resp.json()
    assert any(b["batch_id"] == batch_id for b in batches)


def test_batch_not_found():
    resp = client.get("/api/pipeline/batches/batch-non-existent")
    assert resp.status_code == 404
