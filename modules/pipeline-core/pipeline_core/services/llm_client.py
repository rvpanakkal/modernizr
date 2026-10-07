"""
Re-export from services.llm_client for package imports.
"""

from services.llm_client import generate_targeted_revision, get_anthropic_client

__all__ = ["generate_targeted_revision", "get_anthropic_client"]
