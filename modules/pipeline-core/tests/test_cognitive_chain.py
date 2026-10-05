"""
Tests for Step 3 (Multi-Pass Cognitive Extraction Chain) and Step 4 (Jira HITL Gate).
======================================================================================
Validates:
1. Pass 1: Technical Decompiler strips Java EE plumbing into clean DecompiledSlice.
2. Pass 2: Business Rule Extractor maps operations to typed BusinessRules ($50k ceiling, TX9021, ACTIVE).
3. Pass 3: Spec Formatter synthesizes valid Gherkin BDD scenarios with legacy traceability.
4. Step 4 Gate: JiraHitlGate posts story, calculates SHA-256, and pauses in HITL_PENDING.
5. End-to-End: CognitiveExtractionRunner executes deterministically and produces valid receipts.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

import pytest

from pipeline_core.agents.business_abstractor import BusinessAbstractorAgent
from pipeline_core.agents.decompiler import DecompilerAgent
from pipeline_core.agents.spec_formatter import SpecFormatterAgent
from pipeline_core.integrations.jira_gate import JiraHitlGate, format_jira_wiki_markup
from pipeline_core.paths import sha256_file
from pipeline_core.schemas.handoff import ExecutionStatus, StepHandoffReceipt
from pipeline_core.schemas.spec import (
    BusinessRule,
    DecompiledOperation,
    DecompiledSlice,
    GeneratedSpecification,
    RuleType,
)
from pipeline_core.workflows.cognitive_runner import (
    DEFAULT_CANONICAL_SLICE,
    CognitiveExtractionRunner,
)


@pytest.fixture(autouse=True)
def set_mock_env(monkeypatch):
    """Ensure all agents and integrations run in deterministic offline mode during tests."""
    monkeypatch.setenv("MOCK_LLM", "true")
    monkeypatch.setenv("MOCK_JIRA", "true")


@pytest.fixture
def sample_slice() -> Dict[str, Any]:
    return DEFAULT_CANONICAL_SLICE


# =============================================================================
# Pass 1: Technical Decompiler Tests
# =============================================================================

class TestDecompilerAgent:

    def test_decompile_strips_plumbing_and_extracts_operations(self, sample_slice):
        agent = DecompilerAgent()
        result = agent.decompile(sample_slice)

        assert isinstance(result, DecompiledSlice)
        assert result.entry_point == "com.legacy.banking.web.TransferManagedBean"
        assert len(result.operations) >= 1

        op = result.operations[0]
        assert isinstance(op, DecompiledOperation)
        assert "TransferProcessingService.processTransfer" in op.caller

        # Verify plumbing was stripped and computational checks preserved
        checks_text = " ".join(op.conditional_checks).lower()
        assert "greater than zero" in checks_text or "positive" in checks_text
        assert "active" in checks_text
        assert "balance" in checks_text

        # Verify integration dispatches are identified
        dispatches_text = " ".join(op.external_dispatches)
        assert "CicsMainframeGateway" in dispatches_text
        assert "AccountRepository" in dispatches_text

    def test_decompile_handles_empty_slice_gracefully(self):
        agent = DecompilerAgent()
        result = agent.decompile({"sliceId": "com.legacy.UnknownBean"})
        assert isinstance(result, DecompiledSlice)
        assert result.entry_point == "com.legacy.UnknownBean"
        assert len(result.operations) >= 1


# =============================================================================
# Pass 2: Business Rule Extractor Tests
# =============================================================================

class TestBusinessAbstractorAgent:

    def test_extract_rules_contains_required_domain_invariants(self, sample_slice):
        decompiler = DecompilerAgent()
        decompiled = decompiler.decompile(sample_slice)

        abstractor = BusinessAbstractorAgent()
        rules = abstractor.extract_rules(decompiled)

        assert len(rules) >= 5
        rule_ids = [r.rule_id for r in rules]
        assert "BR-001" in rule_ids
        assert "BR-002" in rule_ids
        assert "BR-003" in rule_ids
        assert "BR-004" in rule_ids
        assert "BR-005" in rule_ids

        # Verify $50,000.00 ceiling limit rule is present
        ceiling_rule = next((r for r in rules if r.rule_id == "BR-004"), None)
        assert ceiling_rule is not None
        assert ceiling_rule.rule_type == RuleType.THRESHOLD
        assert "$50,000.00" in ceiling_rule.condition or "$50,000.00" in ceiling_rule.description

        # Verify CICS TX9021 routing rule is present
        routing_rule = next((r for r in rules if r.rule_id == "BR-005"), None)
        assert routing_rule is not None
        assert routing_rule.rule_type == RuleType.ROUTING
        assert "TX9021" in routing_rule.action_or_outcome

        # Verify ACTIVE status rule is present
        active_rule = next((r for r in rules if r.rule_id == "BR-002"), None)
        assert active_rule is not None
        assert active_rule.rule_type == RuleType.COMPLIANCE
        assert "ACTIVE" in active_rule.condition or "ACTIVE" in active_rule.action_or_outcome


# =============================================================================
# Pass 3: Spec Formatter Tests
# =============================================================================

class TestSpecFormatterAgent:

    def test_format_specification_synthesizes_bdd_and_traceability(self, sample_slice):
        decompiler = DecompilerAgent()
        decompiled = decompiler.decompile(sample_slice)
        abstractor = BusinessAbstractorAgent()
        rules = abstractor.extract_rules(decompiled)

        formatter = SpecFormatterAgent()
        spec = formatter.format_specification(rules, entry_context=sample_slice)

        assert isinstance(spec, GeneratedSpecification)
        assert spec.feature_name == "Fund Transfer & Settlement Management"
        assert len(spec.scenarios) >= 5
        assert len(spec.data_contract_fields) >= 4
        assert len(spec.legacy_traceability) >= 4

        # Validate Gherkin scenario structure
        for scenario in spec.scenarios:
            assert len(scenario.given) >= 1
            assert len(scenario.when) >= 1
            assert len(scenario.then) >= 1
            assert len(scenario.legacy_refs) >= 1
            # Check that every legacy_ref exists in the traceability matrix
            for ref in scenario.legacy_refs:
                assert ref in spec.legacy_traceability, f"Phantom legacy ref {ref} not in traceability matrix"


# =============================================================================
# Step 4: Traceability & Jira HITL Gate Tests
# =============================================================================

class TestJiraHitlGate:

    def test_format_jira_wiki_markup(self, sample_slice):
        decompiler = DecompilerAgent()
        decompiled = decompiler.decompile(sample_slice)
        abstractor = BusinessAbstractorAgent()
        rules = abstractor.extract_rules(decompiled)
        formatter = SpecFormatterAgent()
        spec = formatter.format_specification(rules, entry_context=sample_slice)

        markup = format_jira_wiki_markup(spec)
        assert "h1. Modernization Specification:" in markup
        assert "h2. Business Summary" in markup
        assert "h2. Business Invariants & Domain Rules" in markup
        assert "h2. Acceptance Criteria (BDD)" in markup
        assert "h2. Modern Data Contract" in markup
        assert "h2. Legacy Traceability Matrix" in markup
        assert "{code:gherkin}" in markup

    def test_publish_and_checkpoint_pauses_in_hitl_pending(self, tmp_path, sample_slice):
        decompiler = DecompilerAgent()
        decompiled = decompiler.decompile(sample_slice)
        abstractor = BusinessAbstractorAgent()
        rules = abstractor.extract_rules(decompiled)
        formatter = SpecFormatterAgent()
        spec = formatter.format_specification(rules, entry_context=sample_slice)

        spec_file = tmp_path / "spec_test_001.json"
        with open(spec_file, "w", encoding="utf-8") as f:
            f.write(spec.model_dump_json(indent=2))

        gate = JiraHitlGate()
        receipt = gate.publish_and_checkpoint(
            spec=spec,
            spec_path=spec_file,
            run_id="test-run-unit",
        )

        assert isinstance(receipt, StepHandoffReceipt)
        assert receipt.status == ExecutionStatus.HITL_PENDING
        assert receipt.hitl_approved is False
        assert receipt.jira_story_id == "MOD-101"
        assert receipt.next_step == "TargetCodeSynthesis"
        assert len(receipt.output_pointers) == 1

        output_ptr = receipt.output_pointers[0]
        assert output_ptr.sha256_hash == sha256_file(spec_file)


# =============================================================================
# End-to-End Orchestrator Runner Tests
# =============================================================================

class TestCognitiveExtractionRunner:

    def test_e2e_runner_execution(self, tmp_path, sample_slice):
        runner = CognitiveExtractionRunner()
        run_id = "test-e2e-run"
        receipt = runner.run(
            slice_input=sample_slice,
            run_id=run_id,
            output_dir=tmp_path,
        )

        assert receipt.run_id == run_id
        assert receipt.status == ExecutionStatus.HITL_PENDING
        assert receipt.hitl_approved is False
        assert receipt.jira_story_id == "MOD-101"

        # Verify spec on disk
        spec_path = tmp_path / f"spec_{run_id}.json"
        assert spec_path.exists()

        with open(spec_path, "r", encoding="utf-8") as f:
            spec_data = json.load(f)

        assert spec_data["feature_name"] == "Fund Transfer & Settlement Management"
        assert len(spec_data["business_rules"]) >= 4
        assert len(spec_data["scenarios"]) >= 5
