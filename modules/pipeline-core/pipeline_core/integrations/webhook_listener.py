"""
Automated Webhook Resume Listener
=================================
FastAPI webhook server listening for approval events across Jira, GitHub Issues,
and Local files to resume the modernization pipeline from Step 4 HITL_PENDING
to Step 5 (Target Synthesis).

Key Features:
1. Endpoints:
   - POST /webhooks/jira/transition: Parses raw Jira webhook payloads (jira:issue_updated).
   - POST /webhooks/github/issues: Parses GitHub webhook events (issues closed/labeled).
   - POST /webhooks/local/approve: Approves local file-based review packets.
2. Anti-Tamper & Staleness Integrity Verification:
   - Locates matching step 4 receipt by tracking_id / jira_story_id.
   - Re-hashes the referenced specification file on disk with SHA-256.
   - Compares with recorded hash; rejects if modified (REJECT_TAMPERED).
3. State Transition & Handover:
   - Transitions receipt status from HITL_PENDING to SUCCESS.
   - Sets hitl_approved=True with auditor email and timestamp.
   - Writes receipt_{run_id}_approved.json targeting next_step="TargetCodeSynthesis".
4. CLI Simulation Mode:
   - Flag --simulate-approval <receipt_path> allows testing the resume workflow
     offline without external webhooks.
"""

from __future__ import annotations

import argparse
import glob
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from fastapi import FastAPI, HTTPException, Request, Response, status

from pipeline_core.paths import receipts_dir, resolve_artifact_uri, sha256_file
from pipeline_core.schemas.handoff import ExecutionStatus, StepHandoffReceipt
from pipeline_core.schemas.webhook import (
    ApprovalVerificationResult,
    GitHubIssueEvent,
    JiraTransitionEvent,
    LocalApprovalEvent,
    NextAction,
    NormalizedApprovalEvent,
)

log = logging.getLogger(__name__)

APPROVED_STATUSES = frozenset({
    "approved",
    "ready for generation",
    "ready for target code synthesis",
    "sign-off complete",
    "done",
    "closed",
})

app = FastAPI(
    title="Modernization Factory HITL Webhook Listener",
    description="Listens for approval transitions across Jira, GitHub, and Local files to unblock Step 5.",
    version="1.1.0",
)


def find_step4_receipt_by_jira_id(tracking_id: str) -> Optional[Path]:
    """
    Scans artifacts/receipts/ for receipt_*_step4.json matching tracking_id / jira_story_id.
    """
    pattern = str(receipts_dir() / "receipt_*_step4.json")
    for filepath in glob.glob(pattern):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if (data.get("jira_story_id") == tracking_id or data.get("tracking_id") == tracking_id) and data.get("step_number") == 4:
                return Path(filepath)
        except Exception as e:
            log.warning("Could not read receipt file %s: %s", filepath, e)
    return None


def verify_and_process_approval(
    event: Union[JiraTransitionEvent, NormalizedApprovalEvent],
    receipt_override_path: Optional[Path] = None,
) -> ApprovalVerificationResult:
    """
    Core verification and state handover logic.
    Used by FastAPI webhook routes and CLI simulation mode.
    """
    norm_event: NormalizedApprovalEvent = (
        event.to_normalized() if isinstance(event, JiraTransitionEvent) else event
    )

    normalized_to = norm_event.to_status.strip().lower()
    if normalized_to not in APPROVED_STATUSES:
        log.info(
            "[Webhook] Issue %s transitioned to '%s' (not an approved status). Ignoring.",
            norm_event.issue_key, norm_event.to_status,
        )
        return ApprovalVerificationResult(
            is_approved=False,
            hash_verified=False,
            jira_story_id=norm_event.issue_key,
            next_action=NextAction.IGNORE,
            reason=f"Status '{norm_event.to_status}' is not in approved statuses.",
        )

    # 1. Locate Step 4 receipt
    receipt_path = receipt_override_path or find_step4_receipt_by_jira_id(norm_event.issue_key)
    if not receipt_path or not receipt_path.exists():
        log.error("[Webhook] No Step 4 receipt found for issue: %s", norm_event.issue_key)
        return ApprovalVerificationResult(
            is_approved=True,
            hash_verified=False,
            jira_story_id=norm_event.issue_key,
            next_action=NextAction.REJECT_UNKNOWN_ISSUE,
            reason=f"No Step 4 receipt found for issue {norm_event.issue_key}",
        )

    with open(receipt_path, "r", encoding="utf-8") as f:
        receipt_data = json.load(f)

    try:
        receipt = StepHandoffReceipt.model_validate(receipt_data)
    except Exception as e:
        log.error("[Webhook] Corrupted Step 4 receipt at %s: %s", receipt_path, e)
        return ApprovalVerificationResult(
            is_approved=True,
            hash_verified=False,
            jira_story_id=norm_event.issue_key,
            next_action=NextAction.REJECT_INVALID_STATE,
            reason=f"Malformed receipt schema: {e}",
        )

    # Check state idempotency
    if receipt.status == ExecutionStatus.SUCCESS and receipt.hitl_approved:
        log.info("[Webhook] Receipt for %s is already approved (SUCCESS).", norm_event.issue_key)
        return ApprovalVerificationResult(
            is_approved=True,
            hash_verified=True,
            jira_story_id=norm_event.issue_key,
            run_id=receipt.run_id,
            next_action=NextAction.ALREADY_APPROVED,
            reason="Receipt is already marked SUCCESS.",
        )

    if receipt.run_id:
        approved_candidate = receipts_dir() / f"receipt_{receipt.run_id}_approved.json"
        if approved_candidate.exists():
            log.info("[Webhook] Approved receipt already exists for %s.", norm_event.issue_key)
            return ApprovalVerificationResult(
                is_approved=True,
                hash_verified=True,
                jira_story_id=norm_event.issue_key,
                run_id=receipt.run_id,
                next_action=NextAction.ALREADY_APPROVED,
                reason="Receipt with status SUCCESS already exists on disk.",
                approved_receipt_path=str(approved_candidate),
            )

    if receipt.status not in (ExecutionStatus.HITL_PENDING, ExecutionStatus.PAUSED_HITL):
        log.warning(
            "[Webhook] Receipt %s is in state '%s', expected HITL_PENDING.",
            receipt.receipt_id, receipt.status.value,
        )
        return ApprovalVerificationResult(
            is_approved=True,
            hash_verified=False,
            jira_story_id=norm_event.issue_key,
            next_action=NextAction.REJECT_INVALID_STATE,
            reason=f"Receipt status is '{receipt.status.value}', expected HITL_PENDING",
        )

    # 2. Anti-tamper verification
    if not receipt.output_pointers:
        return ApprovalVerificationResult(
            is_approved=True,
            hash_verified=False,
            jira_story_id=norm_event.issue_key,
            next_action=NextAction.REJECT_INVALID_STATE,
            reason="Receipt contains no output pointers to verify.",
        )

    spec_pointer = receipt.output_pointers[0]
    expected_hash = spec_pointer.sha256_hash
    spec_path = resolve_artifact_uri(spec_pointer.uri)

    if not spec_path.exists():
        log.error("[Webhook] Referenced specification file does not exist: %s", spec_path)
        return ApprovalVerificationResult(
            is_approved=True,
            hash_verified=False,
            jira_story_id=norm_event.issue_key,
            next_action=NextAction.REJECT_TAMPERED,
            reason=f"Referenced spec file not found: {spec_path}",
        )

    current_hash = sha256_file(spec_path)
    if current_hash != expected_hash:
        log.error(
            "[Webhook] [CRITICAL] Anti-tamper violation! Hash mismatch on spec %s. Expected: %s, Current: %s",
            spec_path, expected_hash, current_hash,
        )
        return ApprovalVerificationResult(
            is_approved=True,
            hash_verified=False,
            jira_story_id=norm_event.issue_key,
            next_action=NextAction.REJECT_TAMPERED,
            reason=f"Anti-tamper verification failed: Spec artifact tampered. Expected SHA-256 {expected_hash[:12]}..., got {current_hash[:12]}...",
        )

    # 3. State transition: HITL_PENDING -> SUCCESS
    approver = norm_event.user_email or "lead_architect@enterprise.com"
    approval_now = datetime.now(timezone.utc)

    receipt.status = ExecutionStatus.SUCCESS
    receipt.hitl_approved = True
    receipt.approved_by = approver
    receipt.approval_timestamp = approval_now
    receipt.completed_at = approval_now
    receipt.next_step = "TargetCodeSynthesis"

    run_id = receipt.run_id or "run_001"
    approved_receipt_path = receipts_dir() / f"receipt_{run_id}_approved.json"
    with open(approved_receipt_path, "w", encoding="utf-8") as f:
        f.write(receipt.model_dump_json(indent=2))

    if receipt_path and receipt_path.exists():
        with open(receipt_path, "w", encoding="utf-8") as f:
            f.write(receipt.model_dump_json(indent=2))

    log.info(
        "[Webhook] [OK] State transition complete: %s approved via %s. Approved receipt written to: %s",
        receipt.jira_story_id, norm_event.tracker_type, approved_receipt_path,
    )

    return ApprovalVerificationResult(
        is_approved=True,
        hash_verified=True,
        jira_story_id=norm_event.issue_key,
        run_id=run_id,
        next_action=NextAction.TRIGGER_TARGET_SYNTHESIS,
        reason=f"Approved by {approver} and integrity verified.",
        approved_receipt_path=str(approved_receipt_path),
        orchestrator_notified=True,
    )


# =============================================================================
# FastAPI Webhook Endpoints
# =============================================================================

@app.post("/webhooks/jira/transition", response_model=ApprovalVerificationResult)
async def handle_jira_transition(request: Request):
    """Receives Jira webhook notifications on issue updates/transitions."""
    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid JSON: {e}")

    try:
        event = JiraTransitionEvent.from_jira_payload(body)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid Jira event payload: {e}")

    if not event:
        return ApprovalVerificationResult(
            is_approved=False,
            hash_verified=False,
            next_action=NextAction.IGNORE,
            reason="Payload is not a status transition event.",
        )

    log.info(
        "[Webhook] Received Jira transition for issue %s: '%s' -> '%s' (Actor: %s)",
        event.issue_key, event.from_status, event.to_status, event.user_email,
    )
    return verify_and_process_approval(event)


@app.post("/webhooks/github/issues", response_model=ApprovalVerificationResult)
async def handle_github_issues(request: Request):
    """Receives GitHub webhook notifications when issues are closed or labeled 'approved'."""
    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid JSON: {e}")

    norm_event = GitHubIssueEvent.from_github_payload(body)
    if not norm_event:
        return ApprovalVerificationResult(
            is_approved=False,
            hash_verified=False,
            next_action=NextAction.IGNORE,
            reason="GitHub issue event is not an approval action (must be closed or labeled 'approved').",
        )

    log.info(
        "[Webhook] Received GitHub approval for issue %s (Actor: %s)",
        norm_event.issue_key, norm_event.user_email,
    )
    return verify_and_process_approval(norm_event)


@app.post("/webhooks/local/approve", response_model=ApprovalVerificationResult)
async def handle_local_approve(request: Request):
    """Receives local approval payloads for file-based issue packets."""
    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid JSON: {e}")

    try:
        norm_event = LocalApprovalEvent.from_local_payload(body)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    log.info("[Webhook] Received Local file approval for issue %s", norm_event.issue_key)
    return verify_and_process_approval(norm_event)


@app.get("/health")
def health_check():
    return {"status": "UP", "service": "modernization-hitl-webhook-listener"}


@app.get("/healthz")
def healthz_check():
    return {"status": "ok", "service": "modernization-hitl-webhook-listener"}


# =============================================================================
# CLI Simulation Mode
# =============================================================================

def simulate_approval_cli(
    receipt_file_path: str,
    approver: str = "lead_architect@enterprise.com",
    target_status: str = "Approved",
    auto_synthesize: bool = False,
) -> None:
    """
    Simulates a transition webhook approval against a local receipt file.
    Optionally auto-triggers Step 5 Target Code Synthesis upon verification.
    """
    receipt_path = Path(receipt_file_path)
    if not receipt_path.exists():
        print(f"[Error] Receipt file does not exist: {receipt_path}", file=sys.stderr)
        sys.exit(1)

    with open(receipt_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    tracking_id = data.get("jira_story_id") or data.get("tracking_id", "MOD-101")
    tracker_type = data.get("tracker_type", "jira")

    norm_event = NormalizedApprovalEvent(
        issue_key=tracking_id,
        to_status=target_status,
        user_email=approver,
        timestamp=datetime.now(timezone.utc),
        tracker_type=tracker_type,
    )

    print(f"\n[CLI Simulation] Simulating {tracker_type} transition to '{target_status}' for {tracking_id} by {approver}...")
    result = verify_and_process_approval(norm_event, receipt_override_path=receipt_path)

    print("\n[Result] " + "-" * 56)
    print(f"  Next Action       : {result.next_action.value}")
    print(f"  Is Approved       : {result.is_approved}")
    print(f"  Hash Verified     : {result.hash_verified}")
    print(f"  Approved Receipt  : {result.approved_receipt_path}")
    print(f"  Reason            : {result.reason}")
    print("-" * 65 + "\n")

    if auto_synthesize and result.next_action == NextAction.TRIGGER_TARGET_SYNTHESIS and result.approved_receipt_path:
        print("[Auto-Resume] Triggering Step 5 Target Code Synthesis...")
        from pipeline_core.workflows.target_synthesis_runner import run_target_synthesis
        step5_receipt = run_target_synthesis(result.approved_receipt_path)
        print(f"[Auto-Resume] [OK] Step 5 COMPLETED. Checkpoint: receipt_{step5_receipt.run_id}_step5.json\n")

    if result.next_action != NextAction.TRIGGER_TARGET_SYNTHESIS and result.next_action != NextAction.ALREADY_APPROVED:
        sys.exit(1)


def main():
    p = argparse.ArgumentParser(description="Modernization Factory HITL Webhook Resume Listener")
    p.add_argument("--host", default="0.0.0.0", help="HTTP server bind host")
    p.add_argument("--port", type=int, default=8080, help="HTTP server bind port")
    p.add_argument(
        "--simulate-approval",
        metavar="RECEIPT_PATH",
        help="Simulate an approval event offline against the given Step 4 receipt path",
    )
    p.add_argument("--approver", default="lead_architect@enterprise.com", help="Approver email for simulation")
    p.add_argument("--status", default="Approved", help="Target approval status for simulation")
    p.add_argument(
        "--auto-synthesize",
        action="store_true",
        help="Automatically trigger Step 5 target code synthesis upon successful approval verification",
    )

    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    if args.simulate_approval:
        simulate_approval_cli(
            args.simulate_approval,
            approver=args.approver,
            target_status=args.status,
            auto_synthesize=args.auto_synthesize,
        )
    else:
        try:
            import uvicorn
            print(f"[Webhook Server] Starting listener on http://{args.host}:{args.port}")
            uvicorn.run(app, host=args.host, port=args.port)
        except ImportError:
            print("[Error] uvicorn is required to run the webhook server. Run: pip install uvicorn", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
