"""
Step 3 & Step 4 Orchestrator: Multi-Pass Cognitive Extraction Chain & Jira HITL Gate
=====================================================================================
Orchestrates the deterministic transformation of legacy vertical execution slices
into technology-agnostic specifications and registers human-in-the-loop checkpoints:

  [Step 2 Vertical Slice]
           │
           ▼
  [Pass 1: DecompilerAgent]  ──> DecompiledSlice (Java EE plumbing stripped)
           │
           ▼
  [Pass 2: BusinessAbstractorAgent] ──> List[BusinessRule] (Domain logic & thresholds)
           │
           ▼
  [Pass 3: SpecFormatterAgent] ──> GeneratedSpecification (Gherkin BDD & Traceability)
           │
           ▼
  [Step 4: JiraHitlGate] ──> Posts Story to Jira REST API & records SHA-256
           │
           ▼
  [StepHandoffReceipt (HITL_PENDING)] ──> Pauses for Human Approval

Architectural Invariants Enforced:
- "Code-to-Spec-to-Code" only (direct Code-to-Code translation strictly forbidden).
- Pointer & Receipt Pattern: Persists spec and receipt to disk, emitting SHA-256 hashes.
- HITL Guardrail: Emits receipt with status=HITL_PENDING, preventing progression to Step 5.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Union

from pipeline_core.agents.business_abstractor import BusinessAbstractorAgent
from pipeline_core.agents.decompiler import DecompilerAgent
from pipeline_core.agents.spec_formatter import SpecFormatterAgent
from pipeline_core.integrations.jira_gate import HitlGate, JiraHitlGate
from pipeline_core.paths import receipts_dir, sha256_file, specs_dir
from pipeline_core.schemas.handoff import (
    ArtifactPointer,
    ArtifactType,
    ExecutionStatus,
    StepHandoffReceipt,
)
from pipeline_core.schemas.spec import GeneratedSpecification

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("CognitiveRunner")


DEFAULT_CANONICAL_SLICE: Dict[str, Any] = {
    "sliceId": "com.legacy.banking.web.TransferManagedBean",
    "entryPoint": {
        "fqn": "com.legacy.banking.web.TransferManagedBean",
        "simpleName": "TransferManagedBean",
        "kind": "CLASS",
        "annotations": ["ManagedBean", "SessionScoped"],
        "methods": [
            {"name": "execute", "returnType": "java.lang.String", "signature": "execute()"},
            {"name": "reset", "returnType": "void", "signature": "reset()"},
        ],
    },
    "executionPaths": [
        {"path": "TransferManagedBean → TransferProcessingService → CicsMainframeGateway", "depth": 2},
        {"path": "TransferManagedBean → TransferProcessingService → AccountRepository", "depth": 2},
    ],
    "componentSummary": [
        {"fqn": "com.legacy.banking.web.TransferManagedBean", "simpleName": "TransferManagedBean", "role": "ENTRY_POINT"},
        {"fqn": "com.legacy.banking.service.TransferProcessingService", "simpleName": "TransferProcessingService", "role": "DOMAIN_SERVICE"},
        {"fqn": "com.legacy.banking.gateway.CicsMainframeGateway", "simpleName": "CicsMainframeGateway", "role": "INTEGRATION_BOUNDARY"},
        {"fqn": "com.legacy.banking.repository.AccountRepository", "simpleName": "AccountRepository", "role": "DATA_ACCESS"},
    ],
    "callFlows": [
        {
            "callerClass": "TransferManagedBean",
            "callerMethod": "execute",
            "calleeClass": "TransferProcessingService",
            "calleeMethod": "processTransfer",
            "returnType": "java.lang.String",
        },
        {
            "callerClass": "TransferProcessingService",
            "callerMethod": "processTransfer",
            "calleeClass": "CicsMainframeGateway",
            "calleeMethod": "executeTransfer",
            "returnType": "java.lang.String",
        },
        {
            "callerClass": "TransferProcessingService",
            "callerMethod": "processTransfer",
            "calleeClass": "AccountRepository",
            "calleeMethod": "findById",
            "returnType": "com.legacy.banking.domain.Account",
        },
        {
            "callerClass": "TransferProcessingService",
            "callerMethod": "processTransfer",
            "calleeClass": "AccountRepository",
            "calleeMethod": "updateBalance",
            "returnType": "void",
        },
    ],
    "integrationBoundaries": [
        {
            "fqn": "com.legacy.banking.gateway.CicsMainframeGateway",
            "simpleName": "CicsMainframeGateway",
            "role": "INTEGRATION_BOUNDARY",
        },
        {
            "fqn": "com.legacy.banking.repository.AccountRepository",
            "simpleName": "AccountRepository",
            "role": "DATA_ACCESS",
        },
    ],
    "methodImplementations": [
        {
            "className": "com.legacy.banking.service.TransferProcessingService",
            "name": "processTransfer",
            "signature": "processTransfer(java.lang.String, java.lang.String, java.math.BigDecimal)",
            "paramTypes": ["String", "String", "BigDecimal"],
            "returnType": "String",
            "body": (
                "if (amount == null || amount.compareTo(BigDecimal.ZERO) <= 0) {\n"
                "    throw new IllegalArgumentException(\"Transfer amount must be greater than zero. Received: \" + amount);\n"
                "}\n"
                "Account fromAccount = accountRepository.findById(fromAccountId);\n"
                "Account toAccount   = accountRepository.findById(toAccountId);\n"
                "if (fromAccount == null) {\n"
                "    throw new IllegalArgumentException(\"Source account not found: \" + fromAccountId);\n"
                "}\n"
                "if (toAccount == null) {\n"
                "    throw new IllegalArgumentException(\"Destination account not found: \" + toAccountId);\n"
                "}\n"
                "if (fromAccount.getBalance().compareTo(amount) < 0) {\n"
                "    throw new IllegalStateException(\"Insufficient funds in account\");\n"
                "}\n"
                "if (!\"ACTIVE\".equals(fromAccount.getStatus())) {\n"
                "    throw new IllegalStateException(\"Source account is not active\");\n"
                "}\n"
                "String correlationId = cicsGateway.executeTransfer(fromAccountId, toAccountId, amount);\n"
                "accountRepository.updateBalance(fromAccountId, fromAccount.getBalance().subtract(amount));\n"
                "accountRepository.updateBalance(toAccountId, toAccount.getBalance().add(amount));\n"
                "return correlationId;"
            ),
        }
    ],
    "estimatedTokens": 1450,
    "withinBudget": True,
}


class CognitiveExtractionRunner:
    """
    Executes the 3-pass cognitive extraction chain and triggers the Jira HITL Gate.
    """

    def __init__(
        self,
        decompiler: Optional[DecompilerAgent] = None,
        business_abstractor: Optional[BusinessAbstractorAgent] = None,
        spec_formatter: Optional[SpecFormatterAgent] = None,
        hitl_gate: Optional[HitlGate] = None,
        tracker_type: Optional[str] = None,
        jira_gate: Optional[JiraHitlGate] = None,
    ) -> None:
        self.decompiler = decompiler or DecompilerAgent()
        self.business_abstractor = business_abstractor or BusinessAbstractorAgent()
        self.spec_formatter = spec_formatter or SpecFormatterAgent()
        if hitl_gate:
            self.hitl_gate = hitl_gate
        elif jira_gate:
            self.hitl_gate = jira_gate
        else:
            self.hitl_gate = HitlGate(tracker_type=tracker_type)
        self.jira_gate = self.hitl_gate  # Backward compatibility alias

    def run(
        self,
        slice_input: Union[Dict[str, Any], Path, str],
        run_id: Optional[str] = None,
        output_dir: Optional[Path] = None,
    ) -> StepHandoffReceipt:
        """
        Runs Step 3 and Step 4 end-to-end.

        Args:
            slice_input: In-memory dictionary or file path to vertical slice JSON.
            run_id: Unique execution identifier (auto-generated if omitted).
            output_dir: Target directory for generated specifications.

        Returns:
            StepHandoffReceipt in status ExecutionStatus.HITL_PENDING.
        """
        run_id = run_id or f"run-{uuid.uuid4().hex[:8]}"
        spec_dir = output_dir or specs_dir()
        spec_dir.mkdir(parents=True, exist_ok=True)

        # ── 1. Resolve and validate input slice ──────────────────────────────
        raw_slice_path: Optional[Path] = None
        if isinstance(slice_input, (str, Path)):
            p = Path(slice_input)
            if p.exists() and p.is_file():
                raw_slice_path = p
                with open(p, "r", encoding="utf-8") as f:
                    slice_data = json.load(f)
                log.info("[CognitiveRunner] Loaded vertical slice from file: %s", p)
            else:
                log.warning("[CognitiveRunner] Specified slice path '%s' not found. Using canonical sample slice.", slice_input)
                slice_data = DEFAULT_CANONICAL_SLICE
        elif isinstance(slice_input, dict):
            slice_data = slice_input
            log.info("[CognitiveRunner] Using provided in-memory vertical slice: %s", slice_data.get("sliceId", "unknown"))
        else:
            log.warning("[CognitiveRunner] Invalid slice_input type. Using canonical sample slice.")
            slice_data = DEFAULT_CANONICAL_SLICE

        # Create input ArtifactPointer
        if raw_slice_path and raw_slice_path.exists():
            input_hash = sha256_file(raw_slice_path)
            input_size = raw_slice_path.stat().st_size
            input_pointer = ArtifactPointer(
                uri=str(raw_slice_path),
                sha256_hash=input_hash,
                artifact_type=ArtifactType.GRAPH_SLICE,
                size_bytes=input_size,
                media_type="application/json",
            )
        else:
            slice_bytes = json.dumps(slice_data, indent=2).encode("utf-8")
            input_pointer = ArtifactPointer.create_from_content(
                content=slice_bytes,
                uri=f"artifacts/raw_lst/{slice_data.get('sliceId', 'slice')}.json",
                artifact_type=ArtifactType.GRAPH_SLICE,
                media_type="application/json",
            )

        log.info("[CognitiveRunner] Starting Step 3 Cognitive Extraction Chain (Run ID: %s)", run_id)

        # ── 2. Pass 1: Technical Decompiler ─────────────────────────────────
        log.info("[CognitiveRunner] Pass 1/3: Decompiling vertical slice (stripping Java EE plumbing)...")
        decompiled_slice = self.decompiler.decompile(slice_data)
        log.info(
            "[CognitiveRunner] [OK] Pass 1 Complete: %d operations extracted for %s",
            len(decompiled_slice.operations),
            decompiled_slice.entry_point,
        )

        # ── 2. Pass 2: Business Rule Extractor ──────────────────────────────
        log.info("[CognitiveRunner] Pass 2/3: Extracting technology-agnostic business rules...")
        business_rules = self.business_abstractor.extract_rules(decompiled_slice)
        log.info(
            "[CognitiveRunner] [OK] Pass 2 Complete: %d business rules extracted across categories %s",
            len(business_rules),
            list({r.rule_type.value for r in business_rules}),
        )

        # ── 3. Pass 3: Gherkin BDD & Contract Synthesizer ────────────────────
        log.info("[CognitiveRunner] Pass 3/3: Synthesizing Gherkin BDD scenarios and traceability matrix...")
        spec = self.spec_formatter.format_specification(
            business_rules=business_rules,
            entry_context=slice_data,
        )
        spec.run_id = run_id
        log.info(
            "[CognitiveRunner] [OK] Pass 3 Complete: Specification synthesized '%s' with %d scenarios and %d traceability links",
            spec.feature_name,
            len(spec.scenarios),
            len(spec.legacy_traceability),
        )

        # ── 4. Persist Specification to Disk (Pointer & Receipt Pattern) ────
        spec_path = spec_dir / f"spec_{run_id}.json"
        with open(spec_path, "w", encoding="utf-8") as f:
            f.write(spec.model_dump_json(indent=2))
        log.info("[CognitiveRunner] Persisted specification JSON to disk: %s", spec_path)

        # ── 5. Step 4: Traceability & Jira HITL Gate ────────────────────────
        log.info("[CognitiveRunner] Entering Step 4: Jira HITL Gate publishing...")
        receipt = self.jira_gate.publish_and_checkpoint(
            spec=spec,
            spec_path=spec_path,
            run_id=run_id,
            input_pointers=[input_pointer],
        )

        log.info(
            "[CognitiveRunner] [OK] Pipeline PAUSED at Step 4 HITL Gate. Jira ID: %s | Receipt: %s (Status: %s)",
            receipt.jira_story_id,
            receipt.receipt_id,
            receipt.status.value,
        )
        return receipt


def run_cognitive_chain(
    slice_path: Optional[str] = None,
    run_id: Optional[str] = None,
    output_dir: Optional[str] = None,
    tracker_type: Optional[str] = None,
) -> StepHandoffReceipt:
    """Functional convenience entry point."""
    runner = CognitiveExtractionRunner(tracker_type=tracker_type)
    target_out = Path(output_dir) if output_dir else specs_dir()
    return runner.run(
        slice_input=slice_path or DEFAULT_CANONICAL_SLICE,
        run_id=run_id,
        output_dir=target_out,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Step 3 (Cognitive Extraction Chain) and Step 4 (HITL Gate)"
    )
    parser.add_argument(
        "--slice",
        type=str,
        default=None,
        help="Path to the vertical slice JSON file (defaults to canonical banking slice)",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Custom run ID (defaults to auto-generated UUID)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory to save generated specifications",
    )
    parser.add_argument(
        "--tracker",
        type=str,
        default=None,
        choices=["jira", "github", "local"],
        help="Target issue tracker for Step 4 HITL Gate (default: env ISSUE_TRACKER or 'jira')",
    )
    parser.add_argument(
        "--mock-llm",
        action="store_true",
        help="Force deterministic offline LLM mock mode",
    )
    parser.add_argument(
        "--mock-jira",
        action="store_true",
        help="Force mock Jira REST API mode",
    )
    parser.add_argument(
        "--mock-github",
        action="store_true",
        help="Force mock GitHub REST API mode",
    )

    args = parser.parse_args()

    if args.mock_llm:
        os.environ["MOCK_LLM"] = "true"
    if args.mock_jira:
        os.environ["MOCK_JIRA"] = "true"
    if args.mock_github:
        os.environ["MOCK_GITHUB"] = "true"

    receipt = run_cognitive_chain(
        slice_path=args.slice,
        run_id=args.run_id,
        output_dir=args.output_dir,
        tracker_type=args.tracker,
    )

    print("\n" + "=" * 70)
    print("STEP 3 & STEP 4 EXECUTION COMPLETED")
    print(f"Status:         {receipt.status.value}")
    print(f"Run ID:         {receipt.run_id}")
    print(f"Jira Story ID:  {receipt.jira_story_id}")
    print(f"Receipt ID:     {receipt.receipt_id}")
    print(f"HITL Approved:  {receipt.hitl_approved}")
    print(f"Next Step:      {receipt.next_step}")
    if receipt.output_pointers:
        print(f"Spec Artifact:  {receipt.output_pointers[0].uri}")
        print(f"Spec SHA-256:   {receipt.output_pointers[0].sha256_hash}")
    print("=" * 70)


if __name__ == "__main__":
    main()
