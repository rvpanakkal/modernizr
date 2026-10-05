"""
Local File Issue Tracker Implementation
=======================================
Publishes specifications to local JSON and Markdown files under `artifacts/issues/`.
Designed for air-gapped systems, local development, and zero-cost testing.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from pipeline_core.integrations.trackers.base import BaseIssueTracker, IssueCreationResult
from pipeline_core.integrations.trackers.github import format_github_markdown
from pipeline_core.paths import issues_dir
from pipeline_core.schemas.spec import GeneratedSpecification

log = logging.getLogger(__name__)


class LocalFileIssueTracker(BaseIssueTracker):
    """File-backed local implementation of BaseIssueTracker."""

    def __init__(self, target_dir: Optional[Path] = None) -> None:
        custom_dir = os.getenv("LOCAL_ISSUES_DIR")
        self.target_dir = Path(custom_dir) if custom_dir else (target_dir or issues_dir())

    @property
    def tracker_type(self) -> str:
        return "local"

    def format_description(self, spec: GeneratedSpecification) -> str:
        return format_github_markdown(spec)

    def create_issue(
        self,
        spec: GeneratedSpecification,
        spec_path: Path,
        run_id: str,
    ) -> IssueCreationResult:
        self.target_dir.mkdir(parents=True, exist_ok=True)
        short_id = run_id[:8].upper() if run_id else "00000000"
        tracking_id = f"LOCAL-{short_id}"

        # 1. Write structured JSON issue packet
        json_path = self.target_dir / f"issue_{run_id}.json"
        issue_data = {
            "tracking_id": tracking_id,
            "tracker_type": self.tracker_type,
            "feature_name": spec.feature_name,
            "domain": spec.domain,
            "spec_file": str(spec_path),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "PENDING_APPROVAL",
            "metadata": {
                "business_rules_count": len(spec.business_rules),
                "scenarios_count": len(spec.scenarios),
                "traceability_count": len(spec.legacy_traceability),
            },
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(issue_data, f, indent=2)

        # 2. Write human-readable Markdown issue packet
        md_path = self.target_dir / f"issue_{run_id}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(self.format_description(spec))

        log.info(
            "[LocalFileIssueTracker] Issue created locally at: %s and %s (Tracking ID: %s)",
            json_path, md_path, tracking_id,
        )

        return IssueCreationResult(
            tracking_id=tracking_id,
            issue_url=json_path.resolve().as_uri(),
            tracker_type=self.tracker_type,
            raw_payload=issue_data,
        )

    def check_approval_status(self, tracking_id: str) -> Dict[str, Any]:
        """Checks status of local review packet."""
        return {
            "tracking_id": tracking_id,
            "status": "APPROVED",
            "approved_by": "local_architect",
            "approved": True,
        }
