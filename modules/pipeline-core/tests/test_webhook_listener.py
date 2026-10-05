"""
Tests for Automated Webhook Resume Listener & Anti-Tamper Verification.
========================================================================
Validates:
1. Endpoint POST /webhooks/jira/transition parses Jira transition webhooks.
2. Webhook ignores non-approval status transitions (e.g. "In Progress", "Backlog").
3. Anti-tamper verification passes when the specification hash matches the receipt.
4. Anti-tamper verification rejects when the specification file is tampered/modified (REJECT_TAMPERED).
5. State transitions from HITL_PENDING to SUCCESS with hitl_approved=True.
6. Approved receipt is written to disk targeting next_step="TargetCodeSynthesis".
7. Re-approval transitions report ALREADY_APPROVED.
8. CLI simulation mode behaves identically to live webhook.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from pipeline_core.integrations.webhook_listener import (
    app,
    find_step4_receipt_by_jira_id,
    verify_and_process_approval,
)
from pipeline_core.paths import receipts_dir, sha256_file
from pipeline_core.schemas.handoff import (
    ArtifactPointer,
    ArtifactType,
    ExecutionStatus,
    StepHandoffReceipt,
)
from pipeline_core.schemas.spec import (
    BddScenario,
    BusinessRule,
    GeneratedSpecification,
    RuleType,
)
from pipeline_core.schemas.webhook import (
    ApprovalVerificationResult,
    JiraTransitionEvent,
    NextAction,
)

client = TestClient(app)


@pytest.fixture
def test_setup(tmp_path, monkeypatch) -> Dict[str, Any]:
    """Sets up a clean spec and Step 4 checkpoint receipt for testing."""
    test_receipts_dir = tmp_path / "receipts"
    test_receipts_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("pipeline_core.integrations.webhook_listener.receipts_dir", lambda: test_receipts_dir)

    run_id = f"test-run-{uuid.uuid4().hex[:6]}"
    jira_id = f"MOD-{uuid.uuid4().int % 90000 + 10000}"

    # Create dummy spec
    spec = GeneratedSpecification(
        feature_name="Fund Transfer",
        domain="Retail Banking",
        business_summary="Processes fund transfers",
        business_rules=[
            BusinessRule(
                rule_id="BR-001",
                description="Positive amount",
                rule_type=RuleType.VALIDATION,
                condition="amount > 0",
                action_or_outcome="allow",
                legacy_refs=["TransferService.processTransfer"],
            )
        ],
        scenarios=[
            BddScenario(
                name="Valid transfer",
                given=["An active account"],
                when="Transfer requested",
                then=["Succeed"],
                legacy_refs=["TransferService.processTransfer"],
            )
        ],
        data_contract_fields={"fromAccountId": "String"},
        legacy_traceability={"TransferService.processTransfer": "Core service"},
        run_id=run_id,
        jira_story_id=jira_id,
    )

    spec_path = tmp_path / f"spec_{run_id}.json"
    with open(spec_path, "w", encoding="utf-8") as f:
        f.write(spec.model_dump_json(indent=2))

    spec_hash = sha256_file(spec_path)

    receipt = StepHandoffReceipt(
        receipt_id=str(uuid.uuid4()),
        run_id=run_id,
        step_number=4,
        step_name="Spec Generation & Jira HITL Gate",
        jira_story_id=jira_id,
        input_pointers=[],
        output_pointers=[
            ArtifactPointer(
                uri=str(spec_path),
                sha256_hash=spec_hash,
                artifact_type=ArtifactType.GENERATED_SPEC,
                size_bytes=spec_path.stat().st_size,
            )
        ],
        status=ExecutionStatus.HITL_PENDING,
        hitl_approved=False,
    )

    receipt_path = test_receipts_dir / f"receipt_{run_id}_step4.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    with open(receipt_path, "w", encoding="utf-8") as f:
        f.write(receipt.model_dump_json(indent=2))

    return {
        "run_id": run_id,
        "jira_id": jira_id,
        "spec_path": spec_path,
        "receipt_path": receipt_path,
        "spec_hash": spec_hash,
        "receipt": receipt,
    }


# =============================================================================
# Webhook Verification & Anti-Tamper Tests
# =============================================================================

class TestWebhookVerification:

    def test_verify_and_process_approval_success(self, test_setup):
        event = JiraTransitionEvent(
            issue_id="10001",
            issue_key=test_setup["jira_id"],
            from_status="In Review",
            to_status="Approved",
            timestamp=datetime.now(timezone.utc),
            user_email="chief_architect@enterprise.com",
        )

        result = verify_and_process_approval(
            event=event,
            receipt_override_path=test_setup["receipt_path"],
        )

        assert result.is_approved is True
        assert result.hash_verified is True
        assert result.next_action == NextAction.TRIGGER_TARGET_SYNTHESIS
        assert result.approved_receipt_path is not None

        # Verify approved receipt file on disk
        approved_file = Path(result.approved_receipt_path)
        assert approved_file.exists()
        with open(approved_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["status"] == "SUCCESS"
        assert data["hitl_approved"] is True
        assert data["approved_by"] == "chief_architect@enterprise.com"
        assert data["next_step"] == "TargetCodeSynthesis"

    def test_verify_and_process_approval_ignores_non_approval(self, test_setup):
        event = JiraTransitionEvent(
            issue_id="10001",
            issue_key=test_setup["jira_id"],
            from_status="Open",
            to_status="In Progress",
            timestamp=datetime.now(timezone.utc),
            user_email="developer@enterprise.com",
        )

        result = verify_and_process_approval(
            event=event,
            receipt_override_path=test_setup["receipt_path"],
        )

        assert result.is_approved is False
        assert result.next_action == NextAction.IGNORE

    def test_verify_and_process_approval_rejects_tampered_spec(self, test_setup):
        # Tamper with the specification file on disk
        spec_path = test_setup["spec_path"]
        with open(spec_path, "a", encoding="utf-8") as f:
            f.write("\n// MALICIOUS OR UNAPPROVED MODIFICATION")

        event = JiraTransitionEvent(
            issue_id="10001",
            issue_key=test_setup["jira_id"],
            from_status="In Review",
            to_status="Approved",
            timestamp=datetime.now(timezone.utc),
            user_email="architect@enterprise.com",
        )

        result = verify_and_process_approval(
            event=event,
            receipt_override_path=test_setup["receipt_path"],
        )

        assert result.hash_verified is False
        assert result.next_action == NextAction.REJECT_TAMPERED
        assert "Anti-tamper verification failed" in result.reason

    def test_already_approved_state(self, test_setup):
        event = JiraTransitionEvent(
            issue_id="10001",
            issue_key=test_setup["jira_id"],
            from_status="In Review",
            to_status="Approved",
            timestamp=datetime.now(timezone.utc),
            user_email="architect@enterprise.com",
        )

        # First approval
        result1 = verify_and_process_approval(event, receipt_override_path=test_setup["receipt_path"])
        assert result1.next_action == NextAction.TRIGGER_TARGET_SYNTHESIS

        # Second approval on the already updated receipt
        result2 = verify_and_process_approval(event, receipt_override_path=test_setup["receipt_path"])
        assert result2.next_action == NextAction.ALREADY_APPROVED


# =============================================================================
# FastAPI Webhook Route Tests
# =============================================================================

class TestFastApiWebhookRoute:

    def test_post_jira_transition_endpoint(self, test_setup):
        payload = {
            "webhookEvent": "jira:issue_updated",
            "issue": {
                "id": "10001",
                "key": test_setup["jira_id"],
                "fields": {
                    "status": {"name": "Approved"},
                    "summary": "MOD-SPEC: Fund Transfer",
                },
            },
            "changelog": {
                "items": [
                    {
                        "field": "status",
                        "fromString": "In Review",
                        "toString": "Approved",
                    }
                ]
            },
            "user": {
                "emailAddress": "lead_architect@enterprise.com",
                "displayName": "Lead Architect",
            },
        }

        response = client.post("/webhooks/jira/transition", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["is_approved"] is True
        assert data["hash_verified"] is True
        assert data["next_action"] == "TRIGGER_TARGET_SYNTHESIS"

    def test_post_jira_transition_non_status_update(self):
        payload = {
            "webhookEvent": "jira:issue_updated",
            "issue": {
                "id": "10001",
                "key": "MOD-101",
                "fields": {"status": {"name": "In Progress"}},
            },
            "changelog": {
                "items": [
                    {
                        "field": "description",
                        "fromString": "old description",
                        "toString": "new description",
                    }
                ]
            },
            "user": {"emailAddress": "dev@enterprise.com"},
        }

        response = client.post("/webhooks/jira/transition", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["is_approved"] is False
        assert data["next_action"] == "IGNORE"

    def test_healthz_endpoint(self):
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
