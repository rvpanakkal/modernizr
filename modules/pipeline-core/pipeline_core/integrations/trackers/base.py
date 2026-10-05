"""
Base Issue Tracker Abstraction
==============================
Defines the abstract interface and data models for all HITL issue creation
and tracking backends (Jira, GitHub Issues, Local Files, etc.).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from pipeline_core.schemas.spec import GeneratedSpecification


class IssueCreationResult(BaseModel):
    """Result emitted after successfully publishing a specification to an issue tracker."""
    model_config = ConfigDict(extra="ignore")

    tracking_id: str = Field(..., description="Unique issue/tracking identifier, e.g. MOD-101, GH-42, LOCAL-101")
    issue_url: Optional[str] = Field(default=None, description="Web URL or file URI to the created issue")
    tracker_type: str = Field(..., description="Tracker provider name (e.g. jira, github, local)")
    raw_payload: Dict[str, Any] = Field(default_factory=dict, description="Raw metadata or payload from the tracker")


class BaseIssueTracker(ABC):
    """
    Abstract strategy for human-in-the-loop issue creation and tracking.
    Enforces the Open-Closed Principle for enterprise tracking systems.
    """

    @property
    @abstractmethod
    def tracker_type(self) -> str:
        """Returns the canonical provider name (e.g. 'jira', 'github', 'local')."""
        pass

    @abstractmethod
    def format_description(self, spec: GeneratedSpecification) -> str:
        """Renders the GeneratedSpecification into the tracker's native markup/markdown."""
        pass

    @abstractmethod
    def create_issue(
        self,
        spec: GeneratedSpecification,
        spec_path: Path,
        run_id: str,
    ) -> IssueCreationResult:
        """
        Publishes the specification and creates a review issue/item.
        Returns an IssueCreationResult containing the generated tracking ID.
        """
        pass

    @abstractmethod
    def check_approval_status(self, tracking_id: str) -> Dict[str, Any]:
        """
        Inspects the issue status to check whether human sign-off has occurred.
        Returns a dictionary with at least {"tracking_id": str, "approved": bool, "status": str}.
        """
        pass
