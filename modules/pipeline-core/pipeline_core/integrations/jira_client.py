import os
import requests
from typing import Dict, Any, Optional


class JiraClient:
    """
    Jira REST API Client stub for publishing specs and managing Human-in-the-Loop (HITL) gate approvals.
    """

    def __init__(self, base_url: Optional[str] = None, user_email: Optional[str] = None, api_token: Optional[str] = None):
        self.base_url = base_url or os.getenv("JIRA_BASE_URL", "https://enterprise.atlassian.net")
        self.user_email = user_email or os.getenv("JIRA_USER_EMAIL", "devops@enterprise.com")
        self.api_token = api_token or os.getenv("JIRA_API_TOKEN", "mock_token")
        self.project_key = os.getenv("JIRA_PROJECT_KEY", "MOD")

    def create_story(self, summary: str, description: str, spec_body: str) -> str:
        """
        Creates Jira Story and returns tracking ID (e.g., MOD-101).
        """
        print(f"[Jira Client] Creating story in project {self.project_key}: '{summary}'")
        # Mocking Jira API response for local development / testing
        mock_id_number = 101
        jira_story_id = f"{self.project_key}-{mock_id_number}"
        print(f"[Jira Client] Story created successfully: {jira_story_id}")
        return jira_story_id

    def check_hitl_approval_status(self, jira_story_id: str) -> Dict[str, Any]:
        """
        Queries Jira transition status and custom field approval metadata.
        """
        print(f"[Jira Client] Checking HITL approval metadata for story {jira_story_id}...")
        return {
            "jira_story_id": jira_story_id,
            "status": "APPROVED",
            "approved_by": "architect@enterprise.com",
            "approved": True
        }
