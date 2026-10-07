"""
Pydantic v2 schemas for Batch Vertical Slice Extraction and Telemetry.
Models for BatchRunRequest, SliceRunSummary, and BatchRunStatus.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field


class BatchRunRequest(BaseModel):
    entry_fqns: List[str] = Field(..., min_length=1, description="List of entry-point class FQNs to extract")
    max_depth: int = Field(default=5, ge=1, le=8, description="Maximum graph BFS traversal depth")
    tracker_type: str = Field(default="jira", description="Issue tracker type for specifications")


class SliceRunSummary(BaseModel):
    run_id: str
    entry_fqn: str
    class_name: str
    status: str = Field(default="QUEUED", description="QUEUED | RUNNING | COMPLETED | FAILED")
    current_pass: Optional[int] = Field(default=None, description="Active pass number (1, 2, or 3)")
    tokens_consumed: int = 0
    duration_ms: int = 0
    spec_path: Optional[str] = None
    error_message: Optional[str] = None


class BatchRunStatus(BaseModel):
    batch_id: str
    total_slices: int
    completed_slices: int = 0
    failed_slices: int = 0
    status: str = Field(default="PROCESSING", description="PROCESSING | COMPLETED | PARTIAL_FAILURE | FAILED")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    slices: List[SliceRunSummary] = Field(default_factory=list)
