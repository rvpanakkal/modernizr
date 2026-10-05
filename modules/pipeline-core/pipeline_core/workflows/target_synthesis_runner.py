"""
Step 5 Orchestrator: Target Code Synthesis Runner
==================================================
Orchestrates the synthesis of target enterprise assets from an approved
modernization specification (Step 4 HITL Gate approved).

Workflow:
1. Ingests the approved receipt (receipt_{run_id}_approved.json).
2. Verifies HITL Approval Guardrail:
   - Explicitly checks that receipt.hitl_approved == True and status == SUCCESS.
   - Fails with PermissionError if approval is missing or unverified.
3. Cryptographically re-verifies the specification artifact SHA-256 checksum.
4. Executes TargetSynthesizerAgent:
   - Queries Enterprise Catalog for reuse.
   - Generates Java 21 / Spring Boot 3.5.x REST backend.
   - Generates Angular 18+ Microfrontend with reactive Signals.
   - Generates OpenAPI 3.0.3 YAML contract.
   - Generates JUnit 5 BDD Acceptance test suite.
5. Emits Step 5 StepHandoffReceipt (receipt_{run_id}_step5.json) with status=COMPLETED.

Architectural Invariants Enforced:
- "Code-to-Spec-to-Code": Synthesizes exclusively from GeneratedSpecification.
- HITL Guardrail: Step 5 is strictly blocked until human approval metadata exists.
- Pointer & Receipt Pattern: Persists all generated code to disk and records SHA-256 hashes.
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

from pipeline_core.agents.target_synthesizer import TargetSynthesizerAgent
from pipeline_core.paths import (
    receipts_dir,
    resolve_artifact_uri,
    sha256_file,
    target_code_dir,
)
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
log = logging.getLogger("TargetSynthesisRunner")


class TargetSynthesisRunner:
    """
    Executes Step 5 Target Code Synthesis following verified HITL approval.
    """

    def __init__(
        self,
        synthesizer: Optional[TargetSynthesizerAgent] = None,
    ) -> None:
        self.synthesizer = synthesizer or TargetSynthesizerAgent()

    def run(
        self,
        approved_receipt_input: Union[StepHandoffReceipt, Path, str],
        output_dir: Optional[Path] = None,
    ) -> StepHandoffReceipt:
        """
        Executes Step 5 Target Synthesis.

        Args:
            approved_receipt_input: Approved StepHandoffReceipt object or path to JSON.
            output_dir: Optional output directory for target code.

        Returns:
            StepHandoffReceipt in status ExecutionStatus.COMPLETED.

        Raises:
            PermissionError: If human approval metadata is missing or receipt is unapproved.
            FileNotFoundError: If referenced specification file cannot be found.
            ValueError: If specification SHA-256 hash does not match receipt.
        """
        # ── 1. Load and Validate Approved Receipt ───────────────────────────
        if isinstance(approved_receipt_input, (str, Path)):
            receipt_file = Path(approved_receipt_input)
            if not receipt_file.exists():
                raise FileNotFoundError(f"Receipt file does not exist: {receipt_file}")
            with open(receipt_file, "r", encoding="utf-8") as f:
                receipt_data = json.load(f)
            receipt = StepHandoffReceipt.model_validate(receipt_data)
        elif isinstance(approved_receipt_input, StepHandoffReceipt):
            receipt = approved_receipt_input
        else:
            raise TypeError(f"Invalid receipt input type: {type(approved_receipt_input)}")

        log.info("[TargetSynthesisRunner] Ingested receipt: %s (Run ID: %s)", receipt.receipt_id, receipt.run_id)

        # ── 2. Enforce HITL Approval Invariant ──────────────────────────────
        if not receipt.hitl_approved or receipt.status not in (ExecutionStatus.SUCCESS, ExecutionStatus.COMPLETED):
            log.error(
                "[TargetSynthesisRunner] SECURITY GUARDRAIL VIOLATION: "
                "Attempted to execute Step 5 without verified HITL approval! "
                "Receipt status: %s, hitl_approved: %s",
                receipt.status, receipt.hitl_approved,
            )
            raise PermissionError(
                f"Cannot execute Step 5: Human-in-the-Loop (HITL) approval missing or receipt in unapproved state "
                f"(status={receipt.status}, hitl_approved={receipt.hitl_approved})."
            )

        log.info(
            "[TargetSynthesisRunner] [OK] HITL Approval Verified: Approved by '%s' at %s",
            receipt.approved_by, receipt.approval_timestamp,
        )

        # ── 3. Resolve & Verify Specification Checksum ──────────────────────
        spec_pointer = None
        for ptr in receipt.output_pointers:
            if ptr.artifact_type in (ArtifactType.GENERATED_SPEC, ArtifactType.BDD_GHERKIN):
                spec_pointer = ptr
                break

        if not spec_pointer:
            raise ValueError(f"No GENERATED_SPEC artifact pointer found in receipt {receipt.receipt_id}")

        spec_path = resolve_artifact_uri(spec_pointer.uri)
        if not spec_path.exists():
            raise FileNotFoundError(f"Referenced specification file not found: {spec_path}")

        current_hash = sha256_file(spec_path)
        if current_hash != spec_pointer.sha256_hash:
            raise ValueError(
                f"Anti-tamper verification failed! Spec file hash mismatch: "
                f"expected {spec_pointer.sha256_hash}, calculated {current_hash}."
            )
        log.info("[TargetSynthesisRunner] [OK] Specification integrity verified (SHA-256: %s...)", current_hash[:12])

        # ── 4. Load Specification & Synthesize Target Code ───────────────────
        with open(spec_path, "r", encoding="utf-8") as f:
            spec_data = json.load(f)
        spec = GeneratedSpecification.model_validate(spec_data)

        target_dir = output_dir or target_code_dir()
        synthesis_result = self.synthesizer.synthesize(spec, output_root=target_dir)

        output_pointers = synthesis_result["artifact_pointers"]
        catalog_reuse = synthesis_result["catalog_reuse"]

        # ── 5. Emit Step 5 Completion Receipt ────────────────────────────────
        run_id = receipt.run_id or "run-001"
        jira_id = receipt.jira_story_id or "MOD-101"
        receipt_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        step_5_receipt = StepHandoffReceipt(
            receipt_id=receipt_id,
            run_id=run_id,
            step_number=5,
            step_name="Target Code Synthesis (Spring Boot 3.5.x, Angular Signals & OpenAPI)",
            jira_story_id=jira_id,
            input_pointers=[spec_pointer],
            output_pointers=output_pointers,
            status=ExecutionStatus.COMPLETED,
            hitl_approved=True,
            approved_by=receipt.approved_by,
            approval_timestamp=receipt.approval_timestamp,
            objective=f"Modernized target code synthesized for {jira_id} following architect sign-off",
            locked_decisions={
                "target_java_version": "21",
                "target_spring_boot_version": "3.5.0",
                "target_angular_version": "18.0 (Signals & Standalone)",
                "contract_format": "OpenAPI 3.0.3",
                "catalog_reuse_candidates": ", ".join(str(s.get("service_id", "")) for s in catalog_reuse if s.get("service_id")) or "none",
                "source_spec_sha256": current_hash,
            },
            non_goals=[
                "Modifying legacy mainframe databases directly",
                "Altering approved daily ceiling limit of $50,000.00",
                "Mixing Angular presentation state with Spring Boot domain service transactions",
            ],
            next_step="DeploymentVerification",
            started_at=now,
            completed_at=now,
            metrics={
                "generated_files_count": len(output_pointers),
                "catalog_candidates_found": len(catalog_reuse),
                "total_bytes_synthesized": sum(p.size_bytes for p in output_pointers),
            },
        )

        receipt_file = receipts_dir() / f"receipt_{run_id}_step5.json"
        receipt_file.parent.mkdir(parents=True, exist_ok=True)
        with open(receipt_file, "w", encoding="utf-8") as f:
            f.write(step_5_receipt.model_dump_json(indent=2))

        log.info(
            "[TargetSynthesisRunner] [OK] Step 5 COMPLETED. Checkpoint receipt written to: %s",
            receipt_file,
        )
        return step_5_receipt


def run_target_synthesis(
    receipt_path: str,
    output_dir: Optional[str] = None,
) -> StepHandoffReceipt:
    """Functional convenience entry point."""
    runner = TargetSynthesisRunner()
    target_out = Path(output_dir) if output_dir else target_code_dir()
    return runner.run(approved_receipt_input=receipt_path, output_dir=target_out)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Step 5: Target Code Synthesis (Requires approved Step 4 receipt)"
    )
    parser.add_argument(
        "--receipt",
        required=True,
        help="Path to approved Step 4 receipt JSON (receipt_*_approved.json)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory to save generated target code",
    )

    args = parser.parse_args()

    try:
        receipt = run_target_synthesis(
            receipt_path=args.receipt,
            output_dir=args.output_dir,
        )
    except PermissionError as e:
        print(f"\n[ERROR] SECURITY GUARDRAIL ENFORCED: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"\n[ERROR] Target synthesis failed: {e}", file=sys.stderr)
        sys.exit(1)

    print("\n" + "=" * 70)
    print("STEP 5: TARGET CODE SYNTHESIS COMPLETED")
    print(f"Status:         {receipt.status.value}")
    print(f"Run ID:         {receipt.run_id}")
    print(f"Jira Story ID:  {receipt.jira_story_id}")
    print(f"Receipt ID:     {receipt.receipt_id}")
    print(f"Approved By:    {receipt.approved_by}")
    print(f"Next Step:      {receipt.next_step}")
    print(f"Generated Files: {len(receipt.output_pointers)}")
    print("-" * 70)
    for p in receipt.output_pointers:
        print(f"  - [{p.artifact_type.value}] {p.uri} ({p.size_bytes} bytes)")
    print("=" * 70)


if __name__ == "__main__":
    main()
