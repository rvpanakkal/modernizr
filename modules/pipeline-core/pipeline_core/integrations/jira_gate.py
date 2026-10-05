"""
Traceability & Pluggable HITL Gate Integration
==============================================
Implements the Human-in-the-Loop (HITL) gate for Step 4.
Supports Jira, GitHub Issues, and Local Files via IssueTrackerFactory.

Key Responsibilities:
1. Formats GeneratedSpecification into provider-specific markup (Wiki Markup / GFM / JSON).
2. Publishes the story/issue to the configured issue tracker (Jira, GitHub, or Local Files).
3. Computes the SHA-256 checksum of the persisted specification JSON.
4. Generates and persists a StepHandoffReceipt at artifacts/receipts/receipt_{run_id}_step4.json
   with status=HITL_PENDING, locking decisions and setting explicit non-goals.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pipeline_core.integrations.trackers.base import BaseIssueTracker, IssueCreationResult
from pipeline_core.integrations.trackers.factory import IssueTrackerFactory
from pipeline_core.integrations.trackers.jira import JiraIssueTracker, format_jira_wiki_markup
from pipeline_core.paths import receipts_dir, sha256_file
from pipeline_core.schemas.handoff import (
    ArtifactPointer,
    ArtifactType,
    ExecutionStatus,
    StepHandoffReceipt,
)
from pipeline_core.schemas.spec import GeneratedSpecification

log = logging.getLogger(__name__)

# Re-export for backward compatibility
__all__ = ["HitlGate", "JiraHitlGate", "format_jira_wiki_markup"]


class HitlGate:
    """
    Generic Human-in-the-Loop (HITL) Gate orchestrator.
    Publishes specifications to any registered IssueTracker and checkpoints the pipeline.
    """

    def __init__(
        self,
        tracker: Optional[BaseIssueTracker] = None,
        tracker_type: Optional[str] = None,
        **tracker_kwargs: Any,
    ) -> None:
        if tracker:
            self.tracker = tracker
        else:
            self.tracker = IssueTrackerFactory.get_tracker(tracker_type=tracker_type, **tracker_kwargs)

    def publish_and_checkpoint(
        self,
        spec: GeneratedSpecification,
        spec_path: Path,
        run_id: str,
        input_pointers: Optional[List[ArtifactPointer]] = None,
    ) -> StepHandoffReceipt:
        """
        1. Posts spec to the configured Issue Tracker (Jira, GitHub, Local).
        2. Computes SHA-256 hash of spec_path.
        3. Emits receipt_{run_id}_step4.json in HITL_PENDING state.
        """
        creation_result: IssueCreationResult = self.tracker.create_issue(
            spec=spec,
            spec_path=spec_path,
            run_id=run_id,
        )

        tracking_id = creation_result.tracking_id
        spec.jira_story_id = tracking_id
        spec.tracker_type = self.tracker.tracker_type
        spec.run_id = run_id

        # Update spec file with tracking ID
        with open(spec_path, "w", encoding="utf-8") as f:
            f.write(spec.model_dump_json(indent=2))

        # Checksum of the specification file
        spec_sha256 = sha256_file(spec_path)
        spec_size = spec_path.stat().st_size

        output_pointer = ArtifactPointer(
            uri=str(spec_path),
            sha256_hash=spec_sha256,
            artifact_type=ArtifactType.GENERATED_SPEC,
            size_bytes=spec_size,
            media_type="application/json",
        )

        # Build Step 4 checkpoint receipt
        receipt_id = str(uuid.uuid4())
        step_name = f"Spec Generation & {self.tracker.tracker_type.capitalize()} HITL Gate"
        receipt = StepHandoffReceipt(
            receipt_id=receipt_id,
            run_id=run_id,
            step_number=4,
            step_name=step_name,
            jira_story_id=tracking_id,
            tracker_type=self.tracker.tracker_type,
            input_pointers=input_pointers or [],
            output_pointers=[output_pointer],
            status=ExecutionStatus.HITL_PENDING,
            hitl_approved=False,
            objective=f"Human-in-the-Loop review and sign-off required for issue {tracking_id} ({self.tracker.tracker_type})",
            locked_decisions={
                "jira_story_id": tracking_id,
                "tracking_id": tracking_id,
                "tracker_type": self.tracker.tracker_type,
                "feature_name": spec.feature_name,
                "domain": spec.domain,
                "spec_sha256": spec_sha256,
            },
            non_goals=[
                "Direct code generation without human sign-off",
                "Modification of legacy mainframe schemas",
                "Bypassing architectural review of daily ceiling limits ($50,000.00)",
            ],
            next_step="TargetCodeSynthesis",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            metrics={
                "business_rules_count": len(spec.business_rules),
                "scenarios_count": len(spec.scenarios),
                "data_contract_fields_count": len(spec.data_contract_fields),
                "traceability_links_count": len(spec.legacy_traceability),
            },
        )

        receipt_file = receipts_dir() / f"receipt_{run_id}_step4.json"
        receipt_file.parent.mkdir(parents=True, exist_ok=True)
        with open(receipt_file, "w", encoding="utf-8") as f:
            f.write(receipt.model_dump_json(indent=2))

        log.info(
            "[HitlGate] [OK] Issue created via %s: %s. Checkpoint written to: %s (Status: HITL_PENDING)",
            self.tracker.tracker_type, tracking_id, receipt_file,
        )
        return receipt


class JiraHitlGate(HitlGate):
    """
    Backward-compatible subclass for Jira HITL Gate.
    Maintains identical constructor signature and behavior as legacy implementation.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        user_email: Optional[str] = None,
        api_token: Optional[str] = None,
        project_key: Optional[str] = None,
    ) -> None:
        jira_tracker = JiraIssueTracker(
            base_url=base_url,
            user_email=user_email,
            api_token=api_token,
            project_key=project_key,
        )
        super().__init__(tracker=jira_tracker)
        self.base_url = jira_tracker.base_url
        self.user_email = jira_tracker.user_email
        self.api_token = jira_tracker.api_token
        self.project_key = jira_tracker.project_key

    def _create_jira_story(self, summary: str, description: str, domain: str) -> str:
        """Maintained for backward-compatibility with existing tests/callers."""
        dummy_spec = GeneratedSpecification(
            feature_name=summary.replace("MOD-SPEC: ", "").split(" [")[0],
            domain=domain,
            business_summary=description,
            business_rules=[],
            scenarios=[],
            legacy_traceability={"com.legacy.dummy": "dummy"},
        )
        result = self.tracker.create_issue(dummy_spec, Path("dummy"), "legacy")
        return result.tracking_id
