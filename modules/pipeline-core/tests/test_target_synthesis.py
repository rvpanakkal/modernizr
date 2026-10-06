"""
Tests for Step 5: Target Enterprise Code Synthesis.
====================================================
Validates:
1. HITL Guardrail: Step 5 strictly refuses to execute without verified human approval (PermissionError).
2. Anti-Tamper Security: Step 5 fails if specification hash does not match receipt.
3. Code Generation:
   - Java 21 / Spring Boot 3.5.x REST backend (Controller, Service, DTOs).
   - Angular 18+ Microfrontend with reactive Signals (transfer.component.ts, html).
   - OpenAPI 3.0.3 Contract YAML with schemas.
   - JUnit 5 BDD Acceptance Tests.
4. Traceability Invariant: Every generated artifact embeds the Jira Story ID (MOD-XXX).
5. Enterprise Catalog Interrogation: Interrogates catalog and records reuse decisions.
6. Receipt Emission: Emits Step 5 StepHandoffReceipt in status COMPLETED with SHA-256 hashes.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import pytest

from pipeline_core.agents.target_synthesizer import TargetSynthesizerAgent
from pipeline_core.integrations.catalog_client import EnterpriseCatalogClient
from pipeline_core.paths import sha256_file
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
from pipeline_core.workflows.target_synthesis_runner import TargetSynthesisRunner


@pytest.fixture
def sample_spec(tmp_path) -> Dict[str, Any]:
    run_id = f"test-synth-{uuid.uuid4().hex[:6]}"
    jira_id = "MOD-501"

    spec = GeneratedSpecification(
        feature_name="Fund Transfer & Settlement Management",
        domain="Retail Banking / Core Payments",
        business_summary="Processes retail fund transfers with CICS settlement",
        business_rules=[
            BusinessRule(
                rule_id="BR-001",
                description="Transfer amount must be strictly positive",
                rule_type=RuleType.VALIDATION,
                condition="amount > 0.00",
                action_or_outcome="allow transfer",
                legacy_refs=["TransferProcessingService.processTransfer"],
            ),
            BusinessRule(
                rule_id="BR-004",
                description="Daily cumulative transfer limit ceiling of $50,000.00",
                rule_type=RuleType.THRESHOLD,
                condition="amount <= $50,000.00",
                action_or_outcome="reject if ceiling exceeded",
                legacy_refs=["TransferProcessingService.processTransfer"],
            ),
        ],
        scenarios=[
            BddScenario(
                name="Successful fund transfer with CICS settlement",
                given=["An active source account with balance $5,000.00"],
                when="Transfer of $250.00 is submitted",
                then=["Dispatched to CICS gateway with transaction code TX9021"],
                legacy_refs=["TransferProcessingService.processTransfer"],
            )
        ],
        data_contract_fields={
            "sourceAccountId": "String",
            "destinationAccountId": "String",
            "amount": "BigDecimal",
        },
        legacy_traceability={
            "TransferProcessingService.processTransfer": "Core transaction processing",
        },
        run_id=run_id,
        jira_story_id=jira_id,
    )

    spec_file = tmp_path / f"spec_{run_id}.json"
    with open(spec_file, "w", encoding="utf-8") as f:
        f.write(spec.model_dump_json(indent=2))

    spec_hash = sha256_file(spec_file)

    approved_receipt = StepHandoffReceipt(
        receipt_id=str(uuid.uuid4()),
        run_id=run_id,
        step_number=4,
        step_name="Spec Generation & Jira HITL Gate",
        jira_story_id=jira_id,
        input_pointers=[],
        output_pointers=[
            ArtifactPointer(
                uri=str(spec_file),
                sha256_hash=spec_hash,
                artifact_type=ArtifactType.GENERATED_SPEC,
                size_bytes=spec_file.stat().st_size,
            )
        ],
        status=ExecutionStatus.SUCCESS,
        hitl_approved=True,
        approved_by="lead_architect@enterprise.com",
        approval_timestamp=datetime.now(timezone.utc),
    )

    unapproved_receipt = StepHandoffReceipt(
        receipt_id=str(uuid.uuid4()),
        run_id=run_id,
        step_number=4,
        step_name="Spec Generation & Jira HITL Gate",
        jira_story_id=jira_id,
        input_pointers=[],
        output_pointers=[
            ArtifactPointer(
                uri=str(spec_file),
                sha256_hash=spec_hash,
                artifact_type=ArtifactType.GENERATED_SPEC,
                size_bytes=spec_file.stat().st_size,
            )
        ],
        status=ExecutionStatus.HITL_PENDING,
        hitl_approved=False,
    )

    return {
        "spec": spec,
        "spec_file": spec_file,
        "spec_hash": spec_hash,
        "approved_receipt": approved_receipt,
        "unapproved_receipt": unapproved_receipt,
        "run_id": run_id,
        "jira_id": jira_id,
    }


# =============================================================================
# Security & HITL Guardrail Tests
# =============================================================================

class TestStep5SecurityGuardrails:

    def test_refuses_execution_when_hitl_not_approved(self, sample_spec, tmp_path):
        runner = TargetSynthesisRunner()
        with pytest.raises(PermissionError) as exc_info:
            runner.run(
                approved_receipt_input=sample_spec["unapproved_receipt"],
                output_dir=tmp_path / "out",
            )
        assert "Human-in-the-Loop (HITL) approval missing" in str(exc_info.value)

    def test_refuses_execution_when_spec_tampered(self, sample_spec, tmp_path):
        # Maliciously modify the specification file on disk
        with open(sample_spec["spec_file"], "a", encoding="utf-8") as f:
            f.write("\n// UNAUTHORIZED TAMPERING")

        runner = TargetSynthesisRunner()
        with pytest.raises(ValueError) as exc_info:
            runner.run(
                approved_receipt_input=sample_spec["approved_receipt"],
                output_dir=tmp_path / "out",
            )
        assert "Anti-tamper verification failed" in str(exc_info.value)


# =============================================================================
# Target Code Synthesis & Traceability Tests
# =============================================================================

class TestTargetCodeSynthesis:

    def test_synthesizes_all_target_assets(self, sample_spec, tmp_path):
        target_dir = tmp_path / "target_out"
        runner = TargetSynthesisRunner()
        receipt = runner.run(
            approved_receipt_input=sample_spec["approved_receipt"],
            output_dir=target_dir,
        )

        assert receipt.status == ExecutionStatus.COMPLETED
        assert receipt.hitl_approved is True
        assert receipt.step_number == 5
        assert len(receipt.output_pointers) >= 8

        # 1. OpenAPI Specification Verification
        openapi_file = target_dir / "contracts" / f"openapi_{sample_spec['jira_id'].lower()}.yaml"
        assert openapi_file.exists()
        openapi_text = openapi_file.read_text(encoding="utf-8")
        assert "openapi: 3.0.3" in openapi_text
        assert "/transfers:" in openapi_text
        assert "TransferRequest:" in openapi_text
        assert "TransferResponse:" in openapi_text
        assert sample_spec["jira_id"] in openapi_text

        # 2. Spring Boot 3.5.x Backend Verification
        spring_base = target_dir / "spring_boot" / "src" / "main" / "java" / "com" / "enterprise" / "modernization"
        ctrl_file = spring_base / "web" / "TransferController.java"
        svc_file = spring_base / "service" / "TransferService.java"
        req_file = spring_base / "dto" / "TransferRequest.java"
        resp_file = spring_base / "dto" / "TransferResponse.java"

        assert ctrl_file.exists()
        assert svc_file.exists()
        assert req_file.exists()
        assert resp_file.exists()

        ctrl_text = ctrl_file.read_text(encoding="utf-8")
        assert "@RestController" in ctrl_text
        assert "@RequestMapping(\"/api/v1/transfers\")" in ctrl_text
        assert "@PostMapping" in ctrl_text
        assert sample_spec["jira_id"] in ctrl_text

        svc_text = svc_file.read_text(encoding="utf-8")
        assert "@Service" in svc_text
        assert "50000.00" in svc_text
        assert "TX9021" in svc_text
        assert sample_spec["jira_id"] in svc_text

        req_text = req_file.read_text(encoding="utf-8")
        assert "public record TransferRequest" in req_text
        assert "@NotBlank" in req_text
        assert "@DecimalMin" in req_text
        assert sample_spec["jira_id"] in req_text

        # 3. Angular 18+ Standalone with Signals Verification
        ng_dir = target_dir / "angular" / "src" / "app" / "transfer"
        ng_ts = ng_dir / "transfer.component.ts"
        ng_html = ng_dir / "transfer.component.html"

        assert ng_ts.exists()
        assert ng_html.exists()

        ng_ts_text = ng_ts.read_text(encoding="utf-8")
        assert "standalone: true" in ng_ts_text
        assert "signal<string>('')" in ng_ts_text
        assert "computed(() =>" in ng_ts_text
        assert sample_spec["jira_id"] in ng_ts_text

        ng_html_text = ng_html.read_text(encoding="utf-8")
        assert "@if (successResponse()" in ng_html_text
        assert "@if (errorMessage()" in ng_html_text
        assert "{{ resp.message }}" in ng_html_text
        assert sample_spec["jira_id"] in ng_html_text

        # 4. JUnit 5 BDD Acceptance Tests Verification
        test_file = target_dir / "spring_boot" / "src" / "test" / "java" / "com" / "enterprise" / "modernization" / "service" / "TransferServiceTest.java"
        assert test_file.exists()
        test_text = test_file.read_text(encoding="utf-8")
        assert "@Test" in test_text
        assert "shouldExecuteSuccessfulTransferWithSettlement" in test_text
        assert "shouldRejectTransferExceedingDailyCeilingLimitOf50000" in test_text
        assert sample_spec["jira_id"] in test_text

    def test_every_generated_artifact_has_valid_sha256(self, sample_spec, tmp_path):
        target_dir = tmp_path / "target_out"
        runner = TargetSynthesisRunner()
        receipt = runner.run(
            approved_receipt_input=sample_spec["approved_receipt"],
            output_dir=target_dir,
        )

        for ptr in receipt.output_pointers:
            file_on_disk = Path(ptr.uri)
            assert file_on_disk.exists()
            assert ptr.sha256_hash == sha256_file(file_on_disk)
            assert ptr.size_bytes == file_on_disk.stat().st_size
            assert ptr.artifact_type in (
                ArtifactType.OPENAPI_SPEC,
                ArtifactType.SPRING_BOOT_CODE,
                ArtifactType.ANGULAR_CODE,
            )

    def test_catalog_reuse_interrogation(self, sample_spec, tmp_path):
        catalog_client = EnterpriseCatalogClient()
        synthesizer = TargetSynthesizerAgent(catalog_client=catalog_client)
        result = synthesizer.synthesize(sample_spec["spec"], output_root=tmp_path / "out")

        catalog_reuse = result["catalog_reuse"]
        assert len(catalog_reuse) >= 1
        service_ids = [s["service_id"] for s in catalog_reuse]
        assert "SVC-PAYMENT-V2" in service_ids
