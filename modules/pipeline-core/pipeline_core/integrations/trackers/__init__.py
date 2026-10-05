"""
Pluggable Issue Trackers Package
"""

from pipeline_core.integrations.trackers.base import BaseIssueTracker, IssueCreationResult
from pipeline_core.integrations.trackers.factory import IssueTrackerFactory
from pipeline_core.integrations.trackers.github import GitHubIssueTracker, format_github_markdown
from pipeline_core.integrations.trackers.jira import JiraIssueTracker, format_jira_wiki_markup
from pipeline_core.integrations.trackers.local import LocalFileIssueTracker

__all__ = [
    "BaseIssueTracker",
    "IssueCreationResult",
    "IssueTrackerFactory",
    "JiraIssueTracker",
    "GitHubIssueTracker",
    "LocalFileIssueTracker",
    "format_jira_wiki_markup",
    "format_github_markdown",
]
