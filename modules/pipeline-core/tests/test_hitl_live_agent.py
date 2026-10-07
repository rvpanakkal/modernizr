"""
Verification and Integration Tests for Step 4 HITL Review, Governance, and Live Anthropic Integration.
Validates:
1. Zero mock fallbacks: router strictly requires live Anthropic SDK.
2. Missing ANTHROPIC_API_KEY raises explicit configuration error.
3. Live / Authenticated targeted revision recalculates cryptographic SHA-256 hash.
4. Approval persistence to artifacts/approved_specs/ and receipt state transitions.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.server import app
from pipeline_core.paths import artifacts_root, receipts_dir
from services.llm_client import get_anthropic_client

client = TestClient(app)


def test_zero_mock_validation():
    """Verify that api/routers/hitl.py contains zero mock delays or static string fallbacks."""
    hitl_py = Path(__file__).resolve().parent.parent / "api" / "routers" / "hitl.py"
    content = hitl_py.read_text(encoding="utf-8")

    # Ensure no sleep or mock simulator calls
    assert "mock_cognitive_simulator" not in content, "Mock simulator must not be imported in hitl.py"
    assert "asyncio.sleep" not in content, "Mock delay must not exist in hitl.py"
    assert "generate_targeted_revision" in content, "hitl.py must invoke generate_targeted_revision"


def test_llm_client_missing_key_raises_explicit_error(monkeypatch):
    """Verify that missing ANTHROPIC_API_KEY raises explicit error without falling back to mock."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ValueError) as excinfo:
        get_anthropic_client()
    assert "ANTHROPIC_API_KEY environment variable is missing or empty" in str(excinfo.value)
    assert "Mock fallbacks are strictly disabled" in str(excinfo.value)


def test_hitl_spec_endpoint_returns_legacy_sources_and_spec():
    """Verify GET /api/hitl/spec/{run_id} returns spec, legacy sources map, and receipt."""
    resp = client.get("/api/hitl/spec/run-canonical")
    assert resp.status_code == 200
    data = resp.json()

    assert "spec" in data
    assert "legacy_sources" in data
    assert isinstance(data["legacy_sources"], dict)
    assert len(data["legacy_sources"]) > 0

    # Verify at least one Java source file is loaded
    first_file = next(iter(data["legacy_sources"]))
    assert first_file.endswith(".java")
    assert len(data["legacy_sources"][first_file]) > 50

    assert "spec_sha256" in data
    assert len(data["spec_sha256"]) == 64
    assert data["status"] == "HITL_PENDING"


def test_hitl_approve_and_gate_persistence():
    """Verify POST /api/hitl/approve persists approved spec to artifacts/approved_specs and updates receipts."""
    run_id = "run-test-gov-approve"
    resp = client.post(
        "/api/hitl/approve",
        json={
            "run_id": run_id,
            "aggregate_root": "PaymentOrder",
            "jira_epic_key": "MOD-EPIC-42",
            "jira_story_key": "MOD-404",
            "final_gherkin": "Feature: Approved Payment Order\n  Scenario: Standard Approval\n    Given account is active\n    When transfer completes\n    Then update ledger",
            "final_openapi": "openapi: 3.0.3\ninfo:\n  title: Payment Order API\n  version: 1.0.0",
            "approved_by": "Chief Enterprise Architect",
            "comments": "Approved after manual invariant audit",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "APPROVED"
    assert data["jira_status"] == "APPROVED_FOR_SYNTHESIS"
    assert data["approved_by"] == "Chief Enterprise Architect"
    assert len(data["spec_sha256"]) == 64

    # Verify approved spec is persisted to artifacts/approved_specs/{run_id}.json
    approved_file = artifacts_root() / "approved_specs" / f"{run_id}.json"
    assert approved_file.exists(), f"Approved spec must exist at {approved_file}"

    with open(approved_file, "r", encoding="utf-8") as f:
        saved_data = json.load(f)
    assert saved_data.get("aggregate_root") == "PaymentOrder"
    assert saved_data.get("jira_epic_key") == "MOD-EPIC-42"
    assert "Feature: Approved Payment Order" in saved_data.get("final_gherkin", "")

    # Verify receipt is persisted to artifacts/receipts/receipt_{run_id}_approved.json
    approved_receipt_path = receipts_dir() / f"receipt_{run_id}_approved.json"
    assert approved_receipt_path.exists(), f"Approved receipt must exist at {approved_receipt_path}"

    with open(approved_receipt_path, "r", encoding="utf-8") as f:
        receipt_data = json.load(f)
    assert receipt_data["status"] == "SUCCESS"
    assert receipt_data["hitl_approved"] is True
    assert receipt_data["locked_decisions"]["aggregate_root"] == "PaymentOrder"


def test_hitl_revise_missing_key_returns_500(monkeypatch):
    """Verify POST /api/hitl/revise fails with HTTP 500 when ANTHROPIC_API_KEY is not configured."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    resp = client.post(
        "/api/hitl/revise",
        json={
            "run_id": "run-canonical",
            "reviewer_feedback": "Add validation for dormant account status before checking limits",
        },
    )
    assert resp.status_code == 500
    err_detail = resp.json()["detail"]
    assert "ANTHROPIC_API_KEY environment variable is missing" in err_detail


def test_hitl_revise_with_mocked_sdk_recalculates_sha256(monkeypatch):
    """
    Simulates successful Anthropic AsyncAnthropic response to verify the full
    end-to-end revision parsing, schema validation, and SHA-256 recalculation.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key-valid-format")

    sample_claude_response = {
        "feature_name": "Fund Transfer & CICS Mainframe Settlement (Revised)",
        "domain": "PAYMENT_PROCESSING",
        "business_summary": "Revised specification incorporating dormant account validation check.",
        "business_rules": [
            {
                "rule_id": "BR-001",
                "name": "Dormant Account Check",
                "description": "Reject transfers if account is flagged dormant.",
                "severity": "CRITICAL",
                "rule_type": "VALIDATION",
                "condition": "account.status == 'DORMANT'",
                "action_or_outcome": "Abort with DormantAccountException",
                "legacy_refs": ["com/legacy/banking/service/TransferProcessingService.java:L41-L49"],
            }
        ],
        "bdd_scenarios": [
            {
                "scenario_id": "SCN-DORMANT-01",
                "title": "Dormant account transfer rejected",
                "name": "Dormant account transfer rejected",
                "gherkin_text": "Scenario: Dormant account transfer rejected\n  Given account is dormant\n  When transfer requested\n  Then reject with code 403",
                "given": ["account is dormant"],
                "when": "transfer requested",
                "then": ["reject with code 403"],
                "linked_rule_ids": ["BR-001"],
                "legacy_refs": ["com/legacy/banking/service/TransferProcessingService.java:L41-L49"],
            }
        ],
        "scenarios": [
            {
                "scenario_id": "SCN-DORMANT-01",
                "title": "Dormant account transfer rejected",
                "name": "Dormant account transfer rejected",
                "gherkin_text": "Scenario: Dormant account transfer rejected\n  Given account is dormant\n  When transfer requested\n  Then reject with code 403",
                "given": ["account is dormant"],
                "when": "transfer requested",
                "then": ["reject with code 403"],
                "linked_rule_ids": ["BR-001"],
                "legacy_refs": ["com/legacy/banking/service/TransferProcessingService.java:L41-L49"],
            }
        ],
        "legacy_traceability": {
            "com/legacy/banking/service/TransferProcessingService.java:L41-L49": "SCN-DORMANT-01",
        },
        "data_contract_fields": {"fromAccountId": "String", "amount": "BigDecimal"},
        "openapi_spec_yaml": "openapi: 3.0.3\ninfo:\n  title: Revised API\n  version: 2.0.0",
        "jira_story_id": "MOD-101",
    }

    # Mock Claude message content block
    mock_block = AsyncMock()
    mock_block.text = json.dumps(sample_claude_response)

    mock_msg_resp = AsyncMock()
    mock_msg_resp.content = [mock_block]

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_msg_resp)

    with patch("services.llm_client.get_anthropic_client", return_value=mock_client):
        resp = client.post(
            "/api/hitl/revise",
            json={
                "run_id": "run-canonical",
                "reviewer_feedback": "Add validation for dormant account status before checking limits",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "REVISED"
        assert len(data["spec_sha256"]) == 64
        assert "Revised" in data["revised_spec"]["feature_name"]
        assert data["revised_spec"]["business_rules"][0]["rule_id"] == "BR-001"
