"""
Unit & Integration Tests for Pluggable Issue Trackers & HITL Gate
=================================================================
Tests:
1. JiraIssueTracker
2. GitHubIssueTracker
3. LocalFileIssueTracker
4. IssueTrackerFactory & Custom Registration (OCP)
5. Generic HitlGate with multiple backends
6. Webhook Listener endpoints for GitHub and Local approvals
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from pipeline_core.integrations.jira_gate import HitlGate, JiraHitlGate
from pipeline_core.integrations.trackers.base import BaseIssueTracker, IssueCreationResult
from pipeline_core.integrations.trackers.factory import IssueTrackerFactory
from pipeline_core.integrations.trackers.github import GitHubIssueTracker, format_github_markdown
from pipeline_core.integrations.trackers.jira import JiraIssueTracker, format_jira_wiki_markup
from pipeline_core.integrations.trackers.local import LocalFileIssueTracker
from pipeline_core.integrations.webhook_listener import app, verify_and_process_approval
from pipeline_core.schemas.handoff import ExecutionStatus, StepHandoffReceipt
from pipeline_core.schemas.spec import (
    BddScenario,
    BusinessRule,
    GeneratedSpecification,
    RuleType,
)
from pipeline_core.schemas.webhook import NextAction, NormalizedApprovalEvent


@pytest.fixture
def sample_spec():
    return GeneratedSpecification(
        feature_name="Fund Transfer Processing",
        domain="Core Banking",
        business_summary="Enforces balance validations and routes transfers to mainframe CICS.",
        business_rules=[
            BusinessRule(
                rule_id="BR-001",
                description="Amount must be positive",
                rule_type=RuleType.VALIDATION,
                condition="amount <= 0",
                action_or_outcome="Reject transfer with IllegalArgumentException",
                legacy_refs=["com.legacy.banking.service.TransferProcessingService.processTransfer"],
            ),
            BusinessRule(
                rule_id="BR-002",
                description="Transfers exceeding $50k require ceiling review",
                rule_type=RuleType.THRESHOLD,
                condition="amount > 50000.00",
                action_or_outcome="Route to compliance queue",
                legacy_refs=["com.legacy.banking.service.TransferProcessingService.processTransfer"],
            ),
        ],
        scenarios=[
            BddScenario(
                name="Successful Transfer Under Daily Limit",
                given=["source account has sufficient balance", "target account is active"],
                when="user submits transfer of $500",
                then=["funds debited from source", "CICS correlation ID generated"],
                legacy_refs=["com.legacy.banking.service.TransferProcessingService.processTransfer"],
            )
        ],
        data_contract_fields={
            "fromAccountId": "String (length 20, non-blank)",
            "amount": "BigDecimal (min 0.01)",
        },
        legacy_traceability={
            "com.legacy.banking.service.TransferProcessingService.processTransfer": "TransferService.processTransfer",
        },
    )


class TestJiraIssueTracker:
    def test_format_jira_wiki_markup(self, sample_spec):
        markup = format_jira_wiki_markup(sample_spec)
        assert "h1. Modernization Specification: Fund Transfer Processing" in markup
        assert "h2. Business Summary" in markup
        assert "h2. Acceptance Criteria (BDD)" in markup
        assert "{code:gherkin}" in markup
        assert "BR-001" in markup

    def test_mock_jira_creation(self, sample_spec, tmp_path, monkeypatch):
        monkeypatch.setenv("MOCK_JIRA", "true")
        tracker = JiraIssueTracker(project_key="MOD")
        spec_path = tmp_path / "spec.json"
        spec_path.write_text(sample_spec.model_dump_json())

        result = tracker.create_issue(sample_spec, spec_path, "run-101")
        assert result.tracking_id == "MOD-101"
        assert result.tracker_type == "jira"
        assert "MOD-101" in result.issue_url


class TestGitHubIssueTracker:
    def test_format_github_markdown(self, sample_spec):
        md = format_github_markdown(sample_spec)
        assert "# Modernization Specification: Fund Transfer Processing" in md
        assert "## Business Summary" in md
        assert "```gherkin" in md
        assert "| `BR-001` | **VALIDATION** |" in md
        assert "> [!IMPORTANT]" in md

    def test_mock_github_creation(self, sample_spec, tmp_path, monkeypatch):
        monkeypatch.setenv("MOCK_GITHUB", "true")
        tracker = GitHubIssueTracker(repository="enterprise/banking-mod")
        spec_path = tmp_path / "spec.json"
        spec_path.write_text(sample_spec.model_dump_json())

        result = tracker.create_issue(sample_spec, spec_path, "run-gh-01")
        assert result.tracking_id == "GH-101"
        assert result.tracker_type == "github"
        assert "enterprise/banking-mod/issues/101" in result.issue_url


class TestLocalFileIssueTracker:
    def test_local_file_creation(self, sample_spec, tmp_path):
        tracker = LocalFileIssueTracker(target_dir=tmp_path)
        spec_path = tmp_path / "spec.json"
        spec_path.write_text(sample_spec.model_dump_json())

        run_id = "testrun123"
        result = tracker.create_issue(sample_spec, spec_path, run_id)
        assert result.tracking_id == "LOCAL-TESTRUN1"
        assert result.tracker_type == "local"

        # Verify files created on disk
        json_file = tmp_path / f"issue_{run_id}.json"
        md_file = tmp_path / f"issue_{run_id}.md"
        assert json_file.exists()
        assert md_file.exists()

        data = json.loads(json_file.read_text(encoding="utf-8"))
        assert data["tracking_id"] == "LOCAL-TESTRUN1"
        assert data["feature_name"] == "Fund Transfer Processing"
        assert "Fund Transfer Processing" in md_file.read_text(encoding="utf-8")


class TestIssueTrackerFactory:
    def test_get_registered_trackers(self):
        supported = IssueTrackerFactory.list_supported_trackers()
        assert "jira" in supported
        assert "github" in supported
        assert "local" in supported

    def test_get_tracker_instances(self):
        jira = IssueTrackerFactory.get_tracker("jira")
        assert isinstance(jira, JiraIssueTracker)

        gh = IssueTrackerFactory.get_tracker("github")
        assert isinstance(gh, GitHubIssueTracker)

        local = IssueTrackerFactory.get_tracker("local")
        assert isinstance(local, LocalFileIssueTracker)

    def test_unsupported_tracker_raises(self):
        with pytest.raises(ValueError, match="Unsupported issue tracker provider 'unsupported'"):
            IssueTrackerFactory.get_tracker("unsupported")

    def test_custom_tracker_registration(self):
        class MockGitLabTracker(BaseIssueTracker):
            @property
            def tracker_type(self) -> str:
                return "gitlab"

            def format_description(self, spec: GeneratedSpecification) -> str:
                return "gitlab format"

            def create_issue(self, spec, spec_path, run_id) -> IssueCreationResult:
                return IssueCreationResult(
                    tracking_id="GL-42",
                    tracker_type="gitlab",
                    issue_url="https://gitlab.example.com/issues/42",
                )

            def check_approval_status(self, tracking_id: str):
                return {"tracking_id": tracking_id, "approved": True}

        IssueTrackerFactory.register_tracker("gitlab", MockGitLabTracker)
        tracker = IssueTrackerFactory.get_tracker("gitlab")
        assert isinstance(tracker, MockGitLabTracker)
        assert tracker.tracker_type == "gitlab"


class TestHitlGatePluggable:
    def test_hitl_gate_with_github(self, sample_spec, tmp_path, monkeypatch):
        monkeypatch.setenv("MOCK_GITHUB", "true")
        monkeypatch.setenv("MODERNIZATION_ARTIFACTS_DIR", str(tmp_path))

        gate = HitlGate(tracker_type="github")
        spec_path = tmp_path / "spec_gh.json"
        spec_path.write_text(sample_spec.model_dump_json())

        receipt = gate.publish_and_checkpoint(
            spec=sample_spec,
            spec_path=spec_path,
            run_id="run-gh-test",
        )
        assert receipt.jira_story_id == "GH-101"
        assert receipt.tracker_type == "github"
        assert receipt.status == ExecutionStatus.HITL_PENDING

    def test_hitl_gate_with_local(self, sample_spec, tmp_path, monkeypatch):
        monkeypatch.setenv("MODERNIZATION_ARTIFACTS_DIR", str(tmp_path))

        gate = HitlGate(tracker_type="local")
        spec_path = tmp_path / "spec_local.json"
        spec_path.write_text(sample_spec.model_dump_json())

        receipt = gate.publish_and_checkpoint(
            spec=sample_spec,
            spec_path=spec_path,
            run_id="run-loc-1",
        )
        assert receipt.jira_story_id.startswith("LOCAL-")
        assert receipt.tracker_type == "local"
        assert receipt.status == ExecutionStatus.HITL_PENDING


class TestWebhookListenerMultiTracker:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_github_webhook_closed_event(self, tmp_path, sample_spec, monkeypatch):
        monkeypatch.setenv("MODERNIZATION_ARTIFACTS_DIR", str(tmp_path))
        gate = HitlGate(tracker_type="github")
        spec_path = tmp_path / "spec_gh.json"
        spec_path.write_text(sample_spec.model_dump_json())

        receipt = gate.publish_and_checkpoint(
            spec=sample_spec,
            spec_path=spec_path,
            run_id="run-gh-wh",
        )
        assert receipt.jira_story_id == "GH-101"

        client = TestClient(app)
        github_payload = {
            "action": "closed",
            "issue": {"number": 101, "id": 999},
            "sender": {"login": "octocat", "email": "octocat@github.com"},
        }
        resp = client.post("/webhooks/github/issues", json=github_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_approved"] is True
        assert data["hash_verified"] is True
        assert data["next_action"] == "TRIGGER_TARGET_SYNTHESIS"

    def test_local_approve_endpoint(self, tmp_path, sample_spec, monkeypatch):
        monkeypatch.setenv("MODERNIZATION_ARTIFACTS_DIR", str(tmp_path))
        gate = HitlGate(tracker_type="local")
        spec_path = tmp_path / "spec_loc.json"
        spec_path.write_text(sample_spec.model_dump_json())

        run_id = "run-local-wh"
        receipt = gate.publish_and_checkpoint(
            spec=sample_spec,
            spec_path=spec_path,
            run_id=run_id,
        )
        tracking_id = receipt.jira_story_id

        client = TestClient(app)
        local_payload = {
            "tracking_id": tracking_id,
            "status": "Approved",
            "approver": "architect@enterprise.com",
        }
        resp = client.post("/webhooks/local/approve", json=local_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_approved"] is True
        assert data["hash_verified"] is True
        assert data["next_action"] == "TRIGGER_TARGET_SYNTHESIS"
