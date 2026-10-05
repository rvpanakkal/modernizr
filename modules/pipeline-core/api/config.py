"""
Configuration settings for the Modernization Factory API.
"""

from functools import lru_cache
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables or defaults."""

    # Server settings
    HOST: str = Field(default="0.0.0.0", description="API bind host")
    PORT: int = Field(default=8000, description="API bind port")
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
        description="Allowed CORS origin URLs",
    )

    # Neo4j Graph Database
    NEO4J_URI: str = Field(default="bolt://localhost:7687", description="Neo4j Bolt connection URI")
    NEO4J_USER: str = Field(default="neo4j", description="Neo4j username")
    NEO4J_PASSWORD: str = Field(default="modernization_secret", description="Neo4j password")

    # Issue Tracker / Jira Integration
    JIRA_URL: str = Field(default="https://jira.enterprise.internal", description="Jira Base URL")
    JIRA_USER: str = Field(default="modernization-bot", description="Jira bot username")
    JIRA_API_TOKEN: str = Field(default="mock-jira-token", description="Jira API / Bearer token")
    JIRA_PROJECT_KEY: str = Field(default="MOD", description="Jira project key")

    # Simulation / Mock Flags
    MOCK_MODE: bool = Field(default=True, description="Enable mock fallback responses when external systems are unavailable")
    MOCK_JIRA: bool = Field(default=True, description="Simulate Jira REST transitions without live Jira instance")
    MOCK_LLM: bool = Field(default=True, description="Simulate LLM cognitive agent inference")

    # Cognitive LLM Credentials
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None, description="Anthropic API Key for live Claude 3.7 models")

    # Storage Paths
    ARTIFACTS_DIR: str = Field(default="artifacts", description="Root directory for pipeline artifacts")
    CATALOG_API_URL: str = Field(default="https://catalog.internal.enterprise.com/api/v1", description="Enterprise Catalog URL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
