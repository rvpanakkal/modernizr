"""
Mock Cognitive Extraction Simulator.
Streams realistic multi-pass LLM reasoning logs, token deltas, and synthesizes
a cryptographically signed GeneratedSpecification when external LLM credentials are absent.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from api.services.event_bus import event_bus
from schemas.spec import (
    BddScenario,
    BusinessRule,
    GeneratedSpecification,
    StepHandoffReceipt,
    TraceabilityAnchor,
)

log = logging.getLogger("MockSimulator")

OPENAPI_YAML_SAMPLE = """openapi: 3.0.3
info:
  title: Enterprise Modernized Transfer Service API
  version: 1.0.0
  description: High-throughput fund transfer microservice conforming to target enterprise architecture.
paths:
  /api/v1/transfers:
    post:
      summary: Execute Account Fund Transfer
      operationId: executeTransfer
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/TransferRequest'
      responses:
        '200':
          description: Transfer executed and settled successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/TransferResponse'
        '400':
          description: Validation error or negative transfer amount
          content:
            application/problem+json:
              schema:
                $ref: '#/components/schemas/ProblemDetail'
        '422':
          description: Insufficient funds or inactive account
          content:
            application/problem+json:
              schema:
                $ref: '#/components/schemas/ProblemDetail'
components:
  schemas:
    TransferRequest:
      type: object
      required:
        - fromAccountId
        - toAccountId
        - amount
      properties:
        fromAccountId:
          type: string
          example: ACC-001082
        toAccountId:
          type: string
          example: ACC-009941
        amount:
          type: number
          format: double
          minimum: 0.01
          example: 1500.00
    TransferResponse:
      type: object
      properties:
        transferId:
          type: string
          example: XFER-908124
        correlationId:
          type: string
          format: uuid
        status:
          type: string
          example: COMPLETED
        settledAmount:
          type: number
        timestamp:
          type: string
          format: date-time
    ProblemDetail:
      type: object
      properties:
        type:
          type: string
        title:
          type: string
        status:
          type: integer
        detail:
          type: string
"""

SAMPLE_PASS1_CHUNKS = [
    "[Pass 1] Inspecting Java EE source for TransferManagedBean...\n",
    "[Pass 1] Found presentation controller: javax.faces.bean.ManagedBean session-scoped.\n",
    "[Pass 1] Stripping @ManagedBean, @SessionScoped, FacesContext navigation outcomes.\n",
    "[Pass 1] Stripping @EJB injection of TransferProcessingService.\n",
    "[Pass 1] Decompiling execute() -> transferService.processTransfer(fromAccountId, toAccountId, amount).\n",
    "[Pass 1] Inspecting TransferProcessingService EJB transaction boundaries (@TransactionAttribute REQUIRED).\n",
    "[Pass 1] Extracted Operation 1: validateTransferAmount(amount > 0).\n",
    "[Pass 1] Extracted Operation 2: lookupAccounts(fromAccountId, toAccountId).\n",
    "[Pass 1] Extracted Operation 3: checkBalance(fromAccount.balance >= amount).\n",
    "[Pass 1] Extracted Operation 4: dispatchCicsMainframe(fromAccountId, toAccountId, amount) -> correlationId.\n",
    "[Pass 1] Extracted Operation 5: updateLedgerBalance(debit source, credit destination).\n",
    "[Pass 1] Technical decompiler pass completed successfully. 5 operations isolated.\n",
]

SAMPLE_PASS2_CHUNKS = [
    "[Pass 2] Initializing Business Abstractor agent...\n",
    "[Pass 2] Isolating domain invariants from container runtime...\n",
    "[Pass 2] Discovered Invariant BR-TRANSFER-001: Transfer amount must be positive (amount > 0.00).\n",
    "[Pass 2] Discovered Invariant BR-TRANSFER-002: Dual Account Existence Validation.\n",
    "[Pass 2] Discovered Invariant BR-TRANSFER-003: Sufficient Source Account Balance Check.\n",
    "[Pass 2] Discovered Invariant BR-TRANSFER-004: Account Active Status Policy.\n",
    "[Pass 2] Discovered Invariant BR-TRANSFER-005: Atomic External Settlement Settlement via Mainframe Gateway.\n",
    "[Pass 2] Traceability mapped across TransferProcessingService.java (lines 75-125).\n",
    "[Pass 2] Business rules structured and cataloged.\n",
]

SAMPLE_PASS3_CHUNKS = [
    "[Pass 3] Launching Spec Formatter agent with active profile: Enterprise-Spring-Boot-3.5-Standard...\n",
    "[Pass 3] Synthesizing Gherkin BDD Feature: Funds Transfer Operations.\n",
    "[Pass 3] Generating Scenario 1: Successful Fund Transfer with Positive Balance.\n",
    "[Pass 3] Generating Scenario 2: Transfer Rejection Due to Negative or Zero Amount.\n",
    "[Pass 3] Generating Scenario 3: Transfer Rejection Due to Insufficient Funds.\n",
    "[Pass 3] Generating Scenario 4: Inactive Account Transfer Block.\n",
    "[Pass 3] Generating OpenAPI 3.0 YAML specification conforming to RFC 7807 problem details...\n",
    "[Pass 3] Establishing line-level bidirectional traceability matrix...\n",
    "[Pass 3] Computing cryptographic SHA-256 integrity hash...\n",
    "[Pass 3] Specification sealed and ready for Human-In-The-Loop review.\n",
]


class MockCognitiveSimulator:
    """Simulates real-time 3-pass LLM execution with realistic chunk pacing."""

    def __init__(self, artifacts_dir: Optional[Path] = None):
        if artifacts_dir:
            self.artifacts_dir = artifacts_dir
        else:
            self.artifacts_dir = Path(__file__).resolve().parent.parent / "artifacts" / "specs"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    async def run(
        self,
        run_id: str,
        entry_fqn: str = "com.legacy.banking.web.TransferManagedBean",
        delay_ms: int = 40,
        legacy_source: str = "",
    ) -> GeneratedSpecification:
        """Executes simulated 3-pass streaming pipeline."""
        if "PYTEST_CURRENT_TEST" in os.environ:
            delay_ms = 0

        # 1. RUN_STARTED
        await event_bus.publish(run_id, "RUN_STARTED", {
            "run_id": run_id,
            "entry_fqn": entry_fqn,
            "message": f"Cognitive Extraction Chain initialized for {entry_fqn}",
        })

        # --- PASS 1: Technical Decompiler ---
        p1_start = datetime.now(timezone.utc)
        await event_bus.publish(run_id, "PASS_STARTED", {
            "pass_number": 1,
            "name": "Technical Decompiler",
            "description": "Strip container plumbing, JSF context, and transaction boilerplates.",
        })

        p1_tokens = 0
        for chunk in SAMPLE_PASS1_CHUNKS:
            chunk_tokens = max(1, len(chunk) // 4)
            p1_tokens += chunk_tokens
            await event_bus.publish(run_id, "TOKEN_CHUNK", {
                "pass": 1,
                "token": chunk,
                "token_delta": chunk_tokens,
                "cumulative_tokens": p1_tokens,
            })
            await asyncio.sleep(delay_ms / 1000.0)

        p1_latency = int((datetime.now(timezone.utc) - p1_start).total_seconds() * 1000)
        await event_bus.publish(run_id, "PASS_COMPLETED", {
            "pass_number": 1,
            "name": "Technical Decompiler",
            "latency_ms": p1_latency,
            "tokens": p1_tokens,
            "summary": "5 operations decompiled; container plumbing stripped.",
        })

        # --- PASS 2: Business Abstractor ---
        p2_start = datetime.now(timezone.utc)
        await event_bus.publish(run_id, "PASS_STARTED", {
            "pass_number": 2,
            "name": "Business Abstractor",
            "description": "Extract pure business invariants, validation rules, and thresholds.",
        })

        p2_tokens = 0
        for chunk in SAMPLE_PASS2_CHUNKS:
            chunk_tokens = max(1, len(chunk) // 4)
            p2_tokens += chunk_tokens
            await event_bus.publish(run_id, "TOKEN_CHUNK", {
                "pass": 2,
                "token": chunk,
                "token_delta": chunk_tokens,
                "cumulative_tokens": p1_tokens + p2_tokens,
            })
            await asyncio.sleep(delay_ms / 1000.0)

        p2_latency = int((datetime.now(timezone.utc) - p2_start).total_seconds() * 1000)
        await event_bus.publish(run_id, "PASS_COMPLETED", {
            "pass_number": 2,
            "name": "Business Abstractor",
            "latency_ms": p2_latency,
            "tokens": p2_tokens,
            "summary": "5 business rules extracted with line-level traceability.",
        })

        # --- PASS 3: Spec Formatter ---
        p3_start = datetime.now(timezone.utc)
        await event_bus.publish(run_id, "PASS_STARTED", {
            "pass_number": 3,
            "name": "Spec Formatter & Target Synthesis",
            "description": "Generate Gherkin BDD scenarios, OpenAPI 3.0 YAML, and bidirectional line mappings.",
        })

        p3_tokens = 0
        for chunk in SAMPLE_PASS3_CHUNKS:
            chunk_tokens = max(1, len(chunk) // 4)
            p3_tokens += chunk_tokens
            await event_bus.publish(run_id, "TOKEN_CHUNK", {
                "pass": 3,
                "token": chunk,
                "token_delta": chunk_tokens,
                "cumulative_tokens": p1_tokens + p2_tokens + p3_tokens,
            })
            await asyncio.sleep(delay_ms / 1000.0)

        p3_latency = int((datetime.now(timezone.utc) - p3_start).total_seconds() * 1000)
        await event_bus.publish(run_id, "PASS_COMPLETED", {
            "pass_number": 3,
            "name": "Spec Formatter & Target Synthesis",
            "latency_ms": p3_latency,
            "tokens": p3_tokens,
            "summary": "Synthesized 4 Gherkin BDD scenarios and OpenAPI 3.0 specification.",
        })

        # Build Domain Entities
        legacy_file = "TransferProcessingService.java"
        business_rules = [
            BusinessRule(
                rule_id="BR-TRANSFER-001",
                name="Positive Transfer Amount",
                description="Transfer amount must be strictly greater than zero.",
                severity="CRITICAL",
                traceability=TraceabilityAnchor(legacy_file=legacy_file, start_line=77, end_line=80),
            ),
            BusinessRule(
                rule_id="BR-TRANSFER-002",
                name="Account Ledger Verification",
                description="Both source and destination accounts must exist in the persistent ledger.",
                severity="CRITICAL",
                traceability=TraceabilityAnchor(legacy_file=legacy_file, start_line=83, end_line=91),
            ),
            BusinessRule(
                rule_id="BR-TRANSFER-003",
                name="Sufficient Balance Check",
                description="Source account balance must be greater than or equal to transfer amount.",
                severity="HIGH",
                traceability=TraceabilityAnchor(legacy_file=legacy_file, start_line=94, end_line=99),
            ),
            BusinessRule(
                rule_id="BR-TRANSFER-004",
                name="Active Account State",
                description="Source account status must be 'ACTIVE' for fund transfers.",
                severity="HIGH",
                traceability=TraceabilityAnchor(legacy_file=legacy_file, start_line=102, end_line=104),
            ),
        ]

        bdd_scenarios = [
            BddScenario(
                scenario_id="SCN-001",
                title="Successful Account-to-Account Fund Transfer",
                gherkin_text=(
                    "Scenario: Successful Account-to-Account Fund Transfer\n"
                    "  Given source account \"ACC-100\" has balance $500.00 and status \"ACTIVE\"\n"
                    "  And destination account \"ACC-200\" exists and status is \"ACTIVE\"\n"
                    "  When a transfer of $100.00 is requested\n"
                    "  Then account \"ACC-100\" balance is updated to $400.00\n"
                    "  And account \"ACC-200\" balance is updated to $100.00\n"
                    "  And a CICS correlation ID is issued"
                ),
                linked_rule_ids=["BR-TRANSFER-001", "BR-TRANSFER-002", "BR-TRANSFER-003", "BR-TRANSFER-004"],
                traceability=TraceabilityAnchor(legacy_file=legacy_file, start_line=75, end_line=120),
            ),
            BddScenario(
                scenario_id="SCN-002",
                title="Reject Transfer with Zero or Negative Amount",
                gherkin_text=(
                    "Scenario: Reject Transfer with Zero or Negative Amount\n"
                    "  Given a fund transfer request with amount 0.00 or -50.00\n"
                    "  When the transfer validation is triggered\n"
                    "  Then the system rejects the transaction with a 400 Bad Request error"
                ),
                linked_rule_ids=["BR-TRANSFER-001"],
                traceability=TraceabilityAnchor(legacy_file=legacy_file, start_line=77, end_line=80),
            ),
            BddScenario(
                scenario_id="SCN-003",
                title="Reject Transfer with Insufficient Balance",
                gherkin_text=(
                    "Scenario: Reject Transfer with Insufficient Balance\n"
                    "  Given source account \"ACC-100\" has balance $50.00\n"
                    "  When a transfer of $200.00 is requested\n"
                    "  Then the system halts execution and raises an Insufficient Funds fault"
                ),
                linked_rule_ids=["BR-TRANSFER-003"],
                traceability=TraceabilityAnchor(legacy_file=legacy_file, start_line=94, end_line=99),
            ),
        ]

        # Calculate deterministic SHA-256
        spec_content = json.dumps({
            "run_id": run_id,
            "entry_fqn": entry_fqn,
            "rules": [r.model_dump() for r in business_rules],
            "scenarios": [s.model_dump() for s in bdd_scenarios],
            "openapi": OPENAPI_YAML_SAMPLE,
        }, sort_keys=True)
        sha256_hash = hashlib.sha256(spec_content.encode("utf-8")).hexdigest()

        spec = GeneratedSpecification(
            run_id=run_id,
            feature_name="Account Fund Transfer Service",
            domain="banking.transfers",
            entry_fqn=entry_fqn,
            bdd_scenarios=bdd_scenarios,
            business_rules=business_rules,
            openapi_spec_yaml=OPENAPI_YAML_SAMPLE,
            legacy_source_snapshot=legacy_source or f"// Legacy source for {entry_fqn}",
            sha256_hash=sha256_hash,
            business_summary="Fully modernized, reactive Spring Boot 3.5.x fund transfer microservice.",
            data_contract_fields={
                "fromAccountId": "string",
                "toAccountId": "string",
                "amount": "BigDecimal",
                "correlationId": "UUID",
            },
            legacy_traceability={
                f"{legacy_file}#L77-L80": "BR-TRANSFER-001",
                f"{legacy_file}#L83-L91": "BR-TRANSFER-002",
                f"{legacy_file}#L94-L99": "BR-TRANSFER-003",
                f"{legacy_file}#L102-L104": "BR-TRANSFER-004",
            },
        )

        # Persist spec to artifacts/specs/{run_id}.json
        spec_file = self.artifacts_dir / f"{run_id}.json"
        spec_file.write_text(spec.model_dump_json(indent=2), encoding="utf-8")
        log.info("[MockSimulator] Saved specification to %s", spec_file)

        # Emit SPEC_GENERATED & EXTRACTION_COMPLETE events
        await event_bus.publish(run_id, "SPEC_GENERATED", {
            "run_id": run_id,
            "sha256_hash": sha256_hash,
            "total_rules": len(business_rules),
            "total_scenarios": len(bdd_scenarios),
            "spec": spec.model_dump(mode="json"),
        })

        await event_bus.publish(run_id, "EXTRACTION_COMPLETE", {
            "run_id": run_id,
            "status": "HITL_PENDING",
            "spec_sha256": sha256_hash,
            "total_tokens": p1_tokens + p2_tokens + p3_tokens,
            "spec": spec.model_dump(mode="json"),
        })

        return spec


# Singleton instance
mock_cognitive_simulator = MockCognitiveSimulator()
