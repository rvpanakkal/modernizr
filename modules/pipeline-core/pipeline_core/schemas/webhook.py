"""
Webhook data contracts for the Step 4 HITL resume listener.
Supports normalized events across Jira, GitHub Issues, and Local Files.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class NormalizedApprovalEvent(BaseModel):
    """Normalized view of an approval event across any issue tracking backend."""
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    issue_key: str = Field(..., description="Unique issue key, e.g. MOD-101, GH-101, LOCAL-101")
    to_status: str = Field(..., min_length=1, description="Status transitioned to, e.g. Approved, Closed")
    user_email: Optional[str] = Field(default=None, description="Approver/actor email or username")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tracker_type: str = Field(default="jira", description="Tracker provider: jira, github, local")
    from_status: Optional[str] = None
    issue_id: Optional[str] = None


class JiraTransitionEvent(BaseModel):
    """Normalised view of a Jira ``jira:issue_updated`` webhook that changed the issue status."""
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    issue_id: str = Field(..., min_length=1)
    issue_key: str = Field(..., pattern=r"^[A-Z][A-Z0-9]+-\d+$", description="e.g. MOD-101")
    from_status: Optional[str] = None
    to_status: str = Field(..., min_length=1)
    timestamp: datetime
    user_email: Optional[str] = Field(
        default=None,
        description="Actor email; falls back to display name / account id when Jira hides the email",
    )

    def to_normalized(self) -> NormalizedApprovalEvent:
        return NormalizedApprovalEvent(
            issue_key=self.issue_key,
            to_status=self.to_status,
            user_email=self.user_email,
            timestamp=self.timestamp,
            tracker_type="jira",
            from_status=self.from_status,
            issue_id=self.issue_id,
        )

    @classmethod
    def from_jira_payload(cls, payload: Dict[str, Any]) -> Optional["JiraTransitionEvent"]:
        """
        Parse a raw Jira webhook body.
        Returns ``None`` when the payload is a valid Jira event that is *not* a status transition.
        """
        if payload.get("webhookEvent") != "jira:issue_updated":
            return None

        issue = payload.get("issue")
        if not isinstance(issue, dict) or not issue.get("key") or not issue.get("id"):
            raise ValueError("Webhook payload is missing issue.id / issue.key")

        status_item = None
        for item in (payload.get("changelog") or {}).get("items", []) or []:
            if str(item.get("field", "")).lower() == "status":
                status_item = item
                break
        if status_item is None:
            return None  # an update, but not a transition

        to_status = status_item.get("toString")
        if not to_status:
            raise ValueError("Status changelog item has no 'toString'")

        raw_ts = payload.get("timestamp")
        if isinstance(raw_ts, (int, float)):
            ts = datetime.fromtimestamp(raw_ts / 1000.0, tz=timezone.utc)  # Jira sends epoch millis
        else:
            ts = datetime.now(timezone.utc)

        user = payload.get("user") or {}
        actor = user.get("emailAddress") or user.get("displayName") or user.get("accountId")

        return cls(
            issue_id=str(issue["id"]),
            issue_key=str(issue["key"]),
            from_status=status_item.get("fromString"),
            to_status=to_status,
            timestamp=ts,
            user_email=actor,
        )


class GitHubIssueEvent(BaseModel):
    """Parser for GitHub ``issues`` webhook events (e.g. labeled 'approved' or closed)."""

    @classmethod
    def from_github_payload(cls, payload: Dict[str, Any]) -> Optional[NormalizedApprovalEvent]:
        action = payload.get("action")
        issue = payload.get("issue")
        if not isinstance(issue, dict) or not issue.get("number"):
            return None

        issue_num = issue["number"]
        issue_key = f"GH-{issue_num}"
        sender = payload.get("sender") or {}
        actor = sender.get("login") or sender.get("email")

        # Determine transition status
        to_status: Optional[str] = None
        if action == "closed":
            to_status = "Approved"
        elif action == "labeled":
            label_name = (payload.get("label") or {}).get("name", "").lower()
            if label_name in ("approved", "sign-off complete", "ready for generation"):
                to_status = "Approved"

        if not to_status:
            return None

        return NormalizedApprovalEvent(
            issue_key=issue_key,
            to_status=to_status,
            user_email=actor,
            tracker_type="github",
            issue_id=str(issue.get("id", issue_num)),
        )


class LocalApprovalEvent(BaseModel):
    """Parser for Local file approval requests."""

    @classmethod
    def from_local_payload(cls, payload: Dict[str, Any]) -> NormalizedApprovalEvent:
        tracking_id = payload.get("tracking_id") or payload.get("issue_key")
        if not tracking_id:
            raise ValueError("Local approval payload must contain 'tracking_id' or 'issue_key'")

        status = payload.get("status", "Approved")
        approver = payload.get("approver") or payload.get("user_email", "local_architect@enterprise.com")

        return NormalizedApprovalEvent(
            issue_key=tracking_id,
            to_status=status,
            user_email=approver,
            tracker_type="local",
        )


class NextAction(str, Enum):
    TRIGGER_TARGET_SYNTHESIS = "TRIGGER_TARGET_SYNTHESIS"  # approved + verified -> start Step 5
    IGNORE = "IGNORE"                                      # not an approval transition
    REJECT_TAMPERED = "REJECT_TAMPERED"                    # SHA-256 mismatch: spec changed since publication
    REJECT_UNKNOWN_ISSUE = "REJECT_UNKNOWN_ISSUE"          # no step-4 receipt for this key
    REJECT_INVALID_STATE = "REJECT_INVALID_STATE"          # receipt not in HITL_PENDING
    ALREADY_APPROVED = "ALREADY_APPROVED"                  # idempotent replay of a processed approval


class ApprovalVerificationResult(BaseModel):
    """Outcome of verifying an approval event against the persisted step-4 receipt."""
    model_config = ConfigDict(extra="ignore")

    is_approved: bool
    hash_verified: bool
    jira_story_id: Optional[str] = None
    next_action: NextAction
    run_id: Optional[str] = None
    reason: Optional[str] = None
    approved_receipt_path: Optional[str] = None
    orchestrator_notified: bool = False
