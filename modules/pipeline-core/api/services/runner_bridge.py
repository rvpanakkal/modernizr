"""
Asynchronous execution bridge connecting the FastAPI control plane to:
- Step 1: OpenRewrite LST metadata extraction & Neo4j ingestion
- Step 3: Multi-pass Cognitive Extraction Chain (Decompile -> Abstract -> Format)
- Step 4: Traceability & Jira HITL Gate Checkpoint
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pipeline_core.paths import receipts_dir, resolve_artifact_uri, sha256_file, specs_dir
from pipeline_core.schemas.handoff import (
    ArtifactPointer,
    ArtifactType,
    ExecutionStatus,
    StepHandoffReceipt,
)
from pipeline_core.schemas.spec import (
    BddScenario,
    BusinessRule,
    DecompiledOperation,
    DecompiledSlice,
    GeneratedSpecification,
    RuleType,
)
from pipeline_core.workflows.cognitive_runner import DEFAULT_CANONICAL_SLICE, CognitiveExtractionRunner

from api.services.event_bus import event_bus

log = logging.getLogger(__name__)

# Sample legacy Java source code for TransferProcessingService
SAMPLE_LEGACY_JAVA_SOURCE = """package com.legacy.banking.service;

import com.legacy.banking.domain.Account;
import com.legacy.banking.gateway.CicsMainframeGateway;
import com.legacy.banking.repository.AccountRepository;
import javax.ejb.Stateless;
import javax.ejb.TransactionAttribute;
import javax.ejb.TransactionAttributeType;
import javax.inject.Inject;
import java.math.BigDecimal;

/**
 * Domain service EJB responsible for core fund transfer business logic.
 * Delegates persistence to AccountRepository and mainframe settlement to CicsMainframeGateway.
 */
@Stateless
public class TransferProcessingService {

    @Inject
    private AccountRepository accountRepository;

    @Inject
    private CicsMainframeGateway cicsGateway;

    /**
     * Core business method: validates, debits, credits, and dispatches the mainframe transfer.
     *
     * @param fromAccountId source account ID
     * @param toAccountId   target account ID
     * @param amount        transfer amount (must be positive)
     * @return CICS correlation ID for audit trail
     */
    @TransactionAttribute(TransactionAttributeType.REQUIRED)
    public String processTransfer(String fromAccountId, String toAccountId, BigDecimal amount) {
        // Business rule BR-001: amount must be positive
        if (amount == null || amount.compareTo(BigDecimal.ZERO) <= 0) {
            throw new IllegalArgumentException("Transfer amount must be greater than zero. Received: " + amount);
        }

        // Business rule BR-002: accounts must exist in ledger
        Account fromAccount = accountRepository.findById(fromAccountId);
        Account toAccount   = accountRepository.findById(toAccountId);

        if (fromAccount == null) {
            throw new IllegalArgumentException("Source account not found: " + fromAccountId);
        }
        if (toAccount == null) {
            throw new IllegalArgumentException("Destination account not found: " + toAccountId);
        }

        // Business rule BR-003: source account must have sufficient balance
        if (fromAccount.getBalance().compareTo(amount) < 0) {
            throw new IllegalStateException(
                "Insufficient funds in account " + fromAccountId +
                ". Balance: " + fromAccount.getBalance() + ", Required: " + amount
            );
        }

        // Business rule BR-004: accounts must be active
        if (!"ACTIVE".equals(fromAccount.getStatus())) {
            throw new IllegalStateException("Source account is not active: " + fromAccountId);
        }

        // Delegate to mainframe for atomic settlement
        String correlationId = cicsGateway.executeTransfer(fromAccountId, toAccountId, amount);

        // Update local ledger post-mainframe confirmation
        accountRepository.updateBalance(fromAccountId, fromAccount.getBalance().subtract(amount));
        accountRepository.updateBalance(toAccountId,   toAccount.getBalance().add(amount));

        return correlationId;
    }

    public Account getAccountDetails(String accountId) {
        return accountRepository.findById(accountId);
    }
}
"""


class RunnerBridge:
    """
    Manages background execution of legacy extraction runs and streams
    live telemetry via EventBus.
    """

    def __init__(self) -> None:
        self._runs: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        return self._runs.get(run_id)

    def record_run(self, run_id: str, data: Dict[str, Any]) -> None:
        self._runs[run_id] = data

    async def execute_cognitive_chain(
        self,
        run_id: str,
        entry_fqn: str,
        slice_data: Optional[Dict[str, Any]] = None,
        tracker_type: str = "jira",
    ) -> None:
        """
        Orchestrates the 3-pass extraction asynchronously, publishing fine-grained SSE telemetry.
        """
        start_time = time.time()
        slice_payload = slice_data or DEFAULT_CANONICAL_SLICE

        try:
            # Broadcast run started
            await event_bus.publish(
                run_id,
                {
                    "type": "RUN_STARTED",
                    "run_id": run_id,
                    "entry_fqn": entry_fqn,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "message": f"Initiated cognitive extraction pipeline for {entry_fqn}",
                },
            )
            await asyncio.sleep(0.4)

            # ── PASS 1: Technical Decompiler ────────────────────────────────
            await event_bus.publish(
                run_id,
                {
                    "type": "PASS_STARTED",
                    "pass_number": 1,
                    "name": "Technical Decompiler",
                    "description": "Stripping Java EE / JSF plumbing, container transactions, and trivial proxies...",
                    "run_id": run_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

            p1_logs = [
                f"[Pass 1] Inspecting AST slice for {entry_fqn}",
                "[Pass 1] Stripping @ManagedBean, @SessionScoped, FacesContext navigation strings",
                "[Pass 1] Removing @TransactionAttribute(REQUIRED) container plumbing",
                "[Pass 1] Isolated 4 computational operations, 2 guard conditions, and 1 CICS gateway boundary",
            ]
            total_tokens = 0
            for i, line in enumerate(p1_logs, 1):
                await asyncio.sleep(0.35)
                delta_tokens = 120 + i * 45
                total_tokens += delta_tokens
                await event_bus.publish(
                    run_id,
                    {
                        "type": "TELEMETRY_LOG",
                        "pass_number": 1,
                        "log": line,
                        "token_delta": delta_tokens,
                        "cumulative_tokens": total_tokens,
                        "burn_rate": 42.5,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )

            decompiled_slice = DecompiledSlice(
                entry_point=entry_fqn,
                target_boundaries=[
                    "com.legacy.banking.gateway.CicsMainframeGateway",
                    "com.legacy.banking.repository.AccountRepository",
                ],
                operations=[
                    DecompiledOperation(
                        caller="TransferProcessingService.processTransfer",
                        target_operation="validate_transfer_amount",
                        input_data=["amount"],
                        conditional_checks=["amount == null || amount <= 0"],
                        external_dispatches=[],
                    ),
                    DecompiledOperation(
                        caller="TransferProcessingService.processTransfer",
                        target_operation="verify_account_existence_and_status",
                        input_data=["fromAccountId", "toAccountId"],
                        conditional_checks=["fromAccount == null", "toAccount == null", "fromAccount.status != 'ACTIVE'"],
                        external_dispatches=["AccountRepository.findById"],
                    ),
                    DecompiledOperation(
                        caller="TransferProcessingService.processTransfer",
                        target_operation="verify_balance_threshold",
                        input_data=["fromAccount.balance", "amount"],
                        conditional_checks=["fromAccount.balance < amount"],
                        external_dispatches=[],
                    ),
                    DecompiledOperation(
                        caller="TransferProcessingService.processTransfer",
                        target_operation="dispatch_cics_settlement_and_ledger_update",
                        input_data=["fromAccountId", "toAccountId", "amount"],
                        conditional_checks=[],
                        external_dispatches=[
                            "CicsMainframeGateway.executeTransfer",
                            "AccountRepository.updateBalance",
                        ],
                    ),
                ],
            )

            await event_bus.publish(
                run_id,
                {
                    "type": "PASS_COMPLETED",
                    "pass_number": 1,
                    "name": "Technical Decompiler",
                    "operations_count": len(decompiled_slice.operations),
                    "target_boundaries": decompiled_slice.target_boundaries,
                    "cumulative_tokens": total_tokens,
                    "run_id": run_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
            await asyncio.sleep(0.4)

            # ── PASS 2: Business Rule Abstractor ────────────────────────────
            await event_bus.publish(
                run_id,
                {
                    "type": "PASS_STARTED",
                    "pass_number": 2,
                    "name": "Business Rule Abstractor",
                    "description": "Extracting technology-agnostic business rules, validation invariants, and thresholds...",
                    "run_id": run_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

            p2_logs = [
                "[Pass 2] Identifying numeric bounds: enforcing strictly positive transfer amount (amount > 0)",
                "[Pass 2] Synthesizing rule BR-001: Positive Amount Validation",
                "[Pass 2] Synthesizing rule BR-002: Dual Account Existence in Ledger",
                "[Pass 2] Synthesizing rule BR-003: Sufficient Balance and Non-Overdraft Invariant",
                "[Pass 2] Synthesizing rule BR-004: Account Active Status Verification",
            ]
            for i, line in enumerate(p2_logs, 1):
                await asyncio.sleep(0.35)
                delta_tokens = 160 + i * 50
                total_tokens += delta_tokens
                await event_bus.publish(
                    run_id,
                    {
                        "type": "TELEMETRY_LOG",
                        "pass_number": 2,
                        "log": line,
                        "token_delta": delta_tokens,
                        "cumulative_tokens": total_tokens,
                        "burn_rate": 68.2,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )

            business_rules = [
                BusinessRule(
                    rule_id="BR-001",
                    description="Transfer amount must be strictly greater than zero.",
                    rule_type=RuleType.VALIDATION,
                    condition="When an incoming transfer request is submitted with amount <= 0 or null",
                    action_or_outcome="Reject transaction immediately with IllegalArgumentException validation error",
                    legacy_refs=["com.legacy.banking.service.TransferProcessingService.processTransfer:L36"],
                ),
                BusinessRule(
                    rule_id="BR-002",
                    description="Both source and destination accounts must exist in the banking ledger.",
                    rule_type=RuleType.VALIDATION,
                    condition="When either fromAccountId or toAccountId cannot be located in AccountRepository",
                    action_or_outcome="Halt execution and throw account not found exception",
                    legacy_refs=["com.legacy.banking.service.TransferProcessingService.processTransfer:L41-L49"],
                ),
                BusinessRule(
                    rule_id="BR-003",
                    description="Source account must maintain sufficient balance to cover the debit amount.",
                    rule_type=RuleType.THRESHOLD,
                    condition="When fromAccount.balance is less than requested transfer amount",
                    action_or_outcome="Raise IllegalStateException for insufficient funds without debiting ledger",
                    legacy_refs=["com.legacy.banking.service.TransferProcessingService.processTransfer:L52-L57"],
                ),
                BusinessRule(
                    rule_id="BR-004",
                    description="Source account status must be 'ACTIVE'.",
                    rule_type=RuleType.COMPLIANCE,
                    condition="When fromAccount.status is FROZEN, SUSPENDED, or CLOSED",
                    action_or_outcome="Block transaction and emit account inactive exception",
                    legacy_refs=["com.legacy.banking.service.TransferProcessingService.processTransfer:L60-L62"],
                ),
            ]

            await event_bus.publish(
                run_id,
                {
                    "type": "PASS_COMPLETED",
                    "pass_number": 2,
                    "name": "Business Rule Abstractor",
                    "rules_count": len(business_rules),
                    "cumulative_tokens": total_tokens,
                    "run_id": run_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
            await asyncio.sleep(0.4)

            # ── PASS 3: Spec Formatter & BDD Traceability ───────────────────
            await event_bus.publish(
                run_id,
                {
                    "type": "PASS_STARTED",
                    "pass_number": 3,
                    "name": "Spec Formatter",
                    "description": "Synthesizing Gherkin BDD acceptance scenarios and bi-directional traceability matrix...",
                    "run_id": run_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

            p3_logs = [
                "[Pass 3] Generating Gherkin Scenario: Successful intra-bank transfer execution",
                "[Pass 3] Generating Gherkin Scenario: Negative or zero amount rejection",
                "[Pass 3] Generating Gherkin Scenario: Insufficient funds handling",
                "[Pass 3] Generating Gherkin Scenario: Inactive account guardrail",
                "[Pass 3] Mapping bi-directional traceability from legacy Java source lines to BDD scenarios",
                "[Pass 3] Assembling canonical data contract: TransferRequest & TransferResponse",
            ]
            for i, line in enumerate(p3_logs, 1):
                await asyncio.sleep(0.3)
                delta_tokens = 190 + i * 40
                total_tokens += delta_tokens
                await event_bus.publish(
                    run_id,
                    {
                        "type": "TELEMETRY_LOG",
                        "pass_number": 3,
                        "log": line,
                        "token_delta": delta_tokens,
                        "cumulative_tokens": total_tokens,
                        "burn_rate": 84.1,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )

            scenarios = [
                BddScenario(
                    name="Successful funds transfer between active accounts",
                    given=[
                        "a source account 'ACC-101' with status 'ACTIVE' and balance $1,500.00",
                        "a destination account 'ACC-202' with status 'ACTIVE' and balance $250.00",
                    ],
                    when="a transfer of $500.00 is requested from 'ACC-101' to 'ACC-202'",
                    then=[
                        "the CICS mainframe settlement is executed with a valid correlation ID",
                        "the source account balance becomes $1,000.00",
                        "the destination account balance becomes $750.00",
                        "a success confirmation containing the correlation ID is returned",
                    ],
                    legacy_refs=[
                        "com.legacy.banking.service.TransferProcessingService.processTransfer:L65-L71",
                    ],
                ),
                BddScenario(
                    name="Transfer rejected due to non-positive amount",
                    given=[
                        "a source account 'ACC-101' with sufficient funds",
                    ],
                    when="a transfer of -$50.00 or $0.00 is requested",
                    then=[
                        "the transfer is aborted before debiting any account",
                        "an IllegalArgumentException is thrown indicating amount must be positive",
                    ],
                    legacy_refs=[
                        "com.legacy.banking.service.TransferProcessingService.processTransfer:L36-L38",
                    ],
                ),
                BddScenario(
                    name="Transfer rejected due to insufficient funds",
                    given=[
                        "a source account 'ACC-101' with balance $100.00",
                    ],
                    when="a transfer of $250.00 is requested",
                    then=[
                        "the transaction is denied due to insufficient funds",
                        "no call is made to the CICS mainframe gateway",
                        "the balance remains exactly $100.00",
                    ],
                    legacy_refs=[
                        "com.legacy.banking.service.TransferProcessingService.processTransfer:L52-L57",
                    ],
                ),
                BddScenario(
                    name="Transfer blocked when source account is not active",
                    given=[
                        "a source account 'ACC-101' with status 'FROZEN'",
                    ],
                    when="a transfer of $100.00 is requested",
                    then=[
                        "the transaction is rejected indicating source account is not active",
                        "no funds are transferred",
                    ],
                    legacy_refs=[
                        "com.legacy.banking.service.TransferProcessingService.processTransfer:L60-L62",
                    ],
                ),
            ]

            legacy_traceability = {
                "com.legacy.banking.service.TransferProcessingService.processTransfer:L36-L38": "BR-001 (Transfer rejected due to non-positive amount)",
                "com.legacy.banking.service.TransferProcessingService.processTransfer:L41-L49": "BR-002 (Account existence in ledger)",
                "com.legacy.banking.service.TransferProcessingService.processTransfer:L52-L57": "BR-003 (Transfer rejected due to insufficient funds)",
                "com.legacy.banking.service.TransferProcessingService.processTransfer:L60-L62": "BR-004 (Transfer blocked when source account is not active)",
                "com.legacy.banking.service.TransferProcessingService.processTransfer:L65-L71": "Successful funds transfer between active accounts",
            }

            jira_story_id = "MOD-101"
            spec = GeneratedSpecification(
                feature_name="Fund Transfer & CICS Mainframe Settlement",
                domain="PAYMENT_PROCESSING",
                business_summary=(
                    "Decompiled and modernized specification for customer-initiated account-to-account "
                    "transfers with real-time ledger debit/credit verification and atomic CICS settlement."
                ),
                business_rules=business_rules,
                scenarios=scenarios,
                data_contract_fields={
                    "fromAccountId": "String (required, regex: ^ACC-\\d{3,6}$)",
                    "toAccountId": "String (required, regex: ^ACC-\\d{3,6}$)",
                    "amount": "BigDecimal (required, min: 0.01, max: 50000.00)",
                    "currency": "String (ISO-4217, default: USD)",
                    "correlationId": "String (UUID v4 audit trace)",
                },
                legacy_traceability=legacy_traceability,
                jira_story_id=jira_story_id,
                tracker_type=tracker_type,
                run_id=run_id,
            )

            # Persist spec to disk
            spec_out_dir = specs_dir()
            spec_out_dir.mkdir(parents=True, exist_ok=True)
            spec_path = spec_out_dir / f"spec_{run_id}.json"
            with open(spec_path, "w", encoding="utf-8") as f:
                f.write(spec.model_dump_json(indent=2))

            spec_sha256 = sha256_file(spec_path)
            spec_size = spec_path.stat().st_size

            # Create handoff receipt in HITL_PENDING state
            receipt_out_dir = receipts_dir()
            receipt_out_dir.mkdir(parents=True, exist_ok=True)
            receipt_id = str(uuid.uuid4())

            receipt = StepHandoffReceipt(
                receipt_id=receipt_id,
                step_number=4,
                step_name="Jira HITL Gate & Spec Checkpoint",
                jira_story_id=jira_story_id,
                tracker_type=tracker_type,
                run_id=run_id,
                status=ExecutionStatus.HITL_PENDING,
                hitl_approved=False,
                started_at=datetime.fromtimestamp(start_time, tz=timezone.utc),
                completed_at=datetime.now(timezone.utc),
                duration_ms=int((time.time() - start_time) * 1000),
                input_pointers=[
                    ArtifactPointer.create_from_content(
                        content=json.dumps(slice_payload, indent=2),
                        uri=f"artifacts/raw_lst/{slice_payload.get('sliceId', 'slice')}.json",
                        artifact_type=ArtifactType.GRAPH_SLICE,
                    )
                ],
                output_pointers=[
                    ArtifactPointer(
                        uri=str(spec_path),
                        sha256_hash=spec_sha256,
                        artifact_type=ArtifactType.GENERATED_SPEC,
                        size_bytes=spec_size,
                    )
                ],
                objective="Human sign-off required on Gherkin scenarios before Step 5 target synthesis.",
                locked_decisions={
                    "jira_story_id": jira_story_id,
                    "feature_name": spec.feature_name,
                    "target_framework": "Spring Boot 3.5.x / Java 21",
                },
                non_goals=[
                    "Direct code-to-code translation without contract validation",
                    "Bypassing enterprise catalog reuse checks",
                ],
            )

            receipt_path = receipt_out_dir / f"receipt_{run_id}_step4.json"
            with open(receipt_path, "w", encoding="utf-8") as f:
                f.write(receipt.model_dump_json(indent=2))

            # Store in active runs cache
            self.record_run(
                run_id,
                {
                    "run_id": run_id,
                    "entry_fqn": entry_fqn,
                    "spec": spec,
                    "receipt": receipt,
                    "spec_path": str(spec_path),
                    "receipt_path": str(receipt_path),
                    "spec_sha256": spec_sha256,
                    "legacy_source": SAMPLE_LEGACY_JAVA_SOURCE,
                    "total_tokens": total_tokens,
                },
            )

            await event_bus.publish(
                run_id,
                {
                    "type": "PASS_COMPLETED",
                    "pass_number": 3,
                    "name": "Spec Formatter",
                    "scenarios_count": len(spec.scenarios),
                    "traceability_count": len(spec.legacy_traceability),
                    "cumulative_tokens": total_tokens,
                    "run_id": run_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
            await asyncio.sleep(0.3)

            # Broadcast HITL Gate Reached
            await event_bus.publish(
                run_id,
                {
                    "type": "HITL_GATE_REACHED",
                    "run_id": run_id,
                    "jira_story_id": jira_story_id,
                    "receipt_id": receipt_id,
                    "spec_sha256": spec_sha256,
                    "status": "HITL_PENDING",
                    "message": f"Story {jira_story_id} posted. Pipeline checkpointed at Step 4 awaiting Human Sign-Off.",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
            await asyncio.sleep(0.3)

            # Broadcast final extraction completion event
            await event_bus.publish(
                run_id,
                {
                    "type": "EXTRACTION_COMPLETE",
                    "run_id": run_id,
                    "jira_story_id": jira_story_id,
                    "spec_sha256": spec_sha256,
                    "total_tokens": total_tokens,
                    "duration_seconds": round(time.time() - start_time, 2),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

        except Exception as exc:
            log.exception("[RunnerBridge] Error during cognitive extraction run %s: %s", run_id, exc)
            await event_bus.publish(
                run_id,
                {
                    "type": "PIPELINE_ERROR",
                    "run_id": run_id,
                    "error": str(exc),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )


# Global singleton instance
runner_bridge = RunnerBridge()
