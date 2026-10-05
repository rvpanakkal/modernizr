"""
Issue Tracker Factory & Registry
================================
Provides a dynamic registry and factory for issue tracking backends.
Enforces the Open-Closed Principle (OCP) to allow custom integrations
(e.g., Azure DevOps, GitLab, Linear) to be registered at runtime.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional, Type

from pipeline_core.integrations.trackers.base import BaseIssueTracker
from pipeline_core.integrations.trackers.github import GitHubIssueTracker
from pipeline_core.integrations.trackers.jira import JiraIssueTracker
from pipeline_core.integrations.trackers.local import LocalFileIssueTracker

log = logging.getLogger(__name__)


class IssueTrackerFactory:
    """Factory and runtime registry for issue trackers."""

    _registry: Dict[str, Type[BaseIssueTracker]] = {
        "jira": JiraIssueTracker,
        "github": GitHubIssueTracker,
        "local": LocalFileIssueTracker,
    }

    @classmethod
    def register_tracker(cls, name: str, tracker_cls: Type[BaseIssueTracker]) -> None:
        """
        Registers an issue tracker implementation under a given name.
        Allows enterprise extensions to plug in custom tools without modifying core code.
        """
        key = name.strip().lower()
        if not issubclass(tracker_cls, BaseIssueTracker):
            raise TypeError(f"Class '{tracker_cls.__name__}' must inherit from BaseIssueTracker")
        cls._registry[key] = tracker_cls
        log.info("[IssueTrackerFactory] Registered issue tracker provider: '%s' -> %s", key, tracker_cls.__name__)

    @classmethod
    def list_supported_trackers(cls) -> List[str]:
        """Returns the list of currently registered tracker identifiers."""
        return sorted(list(cls._registry.keys()))

    @classmethod
    def get_tracker(
        cls,
        tracker_type: Optional[str] = None,
        **kwargs,
    ) -> BaseIssueTracker:
        """
        Resolves and instantiates the requested issue tracker.
        Falls back to the ISSUE_TRACKER environment variable, defaulting to 'jira'.
        """
        provider_name = (tracker_type or os.getenv("ISSUE_TRACKER", "jira")).strip().lower()
        tracker_cls = cls._registry.get(provider_name)
        if not tracker_cls:
            supported = ", ".join(f"'{k}'" for k in cls.list_supported_trackers())
            raise ValueError(
                f"Unsupported issue tracker provider '{provider_name}'. Supported providers: {supported}"
            )
        return tracker_cls(**kwargs)
