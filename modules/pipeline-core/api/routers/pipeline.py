"""
Router for Pipeline Step 3: Multi-Pass Cognitive Extraction & Live Telemetry Streaming.
Implements run initiation, SSE event streaming, and run status queries.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from api.dependencies import get_event_bus
from api.services.event_bus import EventBus, event_bus
from agents.cognitive_chain import cognitive_chain
from schemas.spec import GeneratedSpecification

log = logging.getLogger("PipelineRouter")

router = APIRouter(prefix="/api/pipeline", tags=["Pipeline Execution"])

# In-memory registry of recent runs
RUNS_REGISTRY: Dict[str, Dict[str, Any]] = {}


class RunInitiateRequest(BaseModel):
    entry_fqn: str = Field(default="com.legacy.banking.web.TransferManagedBean")
    max_depth: int = Field(default=5)
    slice_payload: Optional[Dict[str, Any]] = None
    slice_data: Optional[Dict[str, Any]] = None
    tracker_type: str = Field(default="jira")


class RunInitiateResponse(BaseModel):
    run_id: str
    status: str
    entry_fqn: str
    stream_url: str
    message: str


class RunSummary(BaseModel):
    run_id: str
    entry_fqn: str
    status: str  # "RUNNING" | "HITL_PENDING" | "COMPLETED" | "FAILED"
    created_at: str
    spec_available: bool = False
    sha256_hash: Optional[str] = None


async def _run_cognitive_extraction(
    run_id: str,
    entry_fqn: str,
    max_depth: int,
    slice_data: Optional[Dict[str, Any]],
    tracker_type: str,
) -> None:
    """Background task executing the 3-pass Cognitive Chain."""
    try:
        RUNS_REGISTRY[run_id]["status"] = "RUNNING"
        spec = await cognitive_chain.execute(
            run_id=run_id,
            entry_fqn=entry_fqn,
            max_depth=max_depth,
            slice_data=slice_data,
            tracker_type=tracker_type,
        )
        RUNS_REGISTRY[run_id]["status"] = "HITL_PENDING"
        RUNS_REGISTRY[run_id]["sha256_hash"] = spec.sha256_hash
        RUNS_REGISTRY[run_id]["spec_available"] = True
    except Exception as exc:
        log.exception("[PipelineRouter] Extraction run %s failed: %s", run_id, exc)
        RUNS_REGISTRY[run_id]["status"] = "FAILED"
        RUNS_REGISTRY[run_id]["error"] = str(exc)
        await event_bus.publish(run_id, "ERROR", {"error": str(exc), "run_id": run_id})


@router.post("/runs", response_model=RunInitiateResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_pipeline_run(
    request: RunInitiateRequest,
    background_tasks: BackgroundTasks,
) -> RunInitiateResponse:
    """
    Initiates the 3-pass cognitive extraction chain for a vertical slice.
    Spawns background extraction and returns the run_id for real-time SSE telemetry tracking.
    """
    run_id = f"run-{uuid.uuid4().hex[:8]}"
    log.info("[PipelineRouter] Initiating cognitive run %s for %s", run_id, request.entry_fqn)

    slice_data = request.slice_payload or request.slice_data

    # Record in registry
    now_iso = datetime.now(timezone.utc).isoformat()
    RUNS_REGISTRY[run_id] = {
        "run_id": run_id,
        "entry_fqn": request.entry_fqn,
        "status": "RUNNING",
        "created_at": now_iso,
        "spec_available": False,
        "sha256_hash": None,
    }

    # Launch background extraction task
    background_tasks.add_task(
        _run_cognitive_extraction,
        run_id=run_id,
        entry_fqn=request.entry_fqn,
        max_depth=request.max_depth,
        slice_data=slice_data,
        tracker_type=request.tracker_type,
    )

    return RunInitiateResponse(
        run_id=run_id,
        status="STARTED",
        entry_fqn=request.entry_fqn,
        stream_url=f"/api/pipeline/runs/{run_id}/stream",
        message="Cognitive extraction chain launched. Connect to stream_url for live telemetry.",
    )


@router.get("/runs/{run_id}/stream")
async def stream_pipeline_telemetry(
    run_id: str,
    bus: EventBus = Depends(get_event_bus),
) -> EventSourceResponse:
    """
    Server-Sent Events (SSE) telemetry endpoint.
    Streams PASS_STARTED, TOKEN_CHUNK, PASS_COMPLETED, SPEC_GENERATED, EXTRACTION_COMPLETE in real-time.
    """
    log.info("[PipelineRouter] SSE telemetry client connected to run_id: %s", run_id)

    async def event_generator():
        try:
            async for event in bus.subscribe(run_id):
                event_type = event.get("type", "message")
                yield {
                    "event": event_type,
                    "data": json.dumps(event),
                }
        except asyncio.CancelledError:
            log.info("[PipelineRouter] SSE connection closed for run_id: %s", run_id)
            raise

    return EventSourceResponse(
        event_generator(),
        media_type="text/event-stream",
        ping=15,  # Heartbeat ping every 15s to keep connection alive
    )


@router.get("/runs", response_model=List[RunSummary])
def list_pipeline_runs() -> List[RunSummary]:
    """
    Lists recent pipeline runs and their current statuses (RUNNING, HITL_PENDING, COMPLETED, FAILED).
    """
    summaries: List[RunSummary] = []

    # Include in-memory runs
    for run_id, data in RUNS_REGISTRY.items():
        summaries.append(
            RunSummary(
                run_id=run_id,
                entry_fqn=data.get("entry_fqn", ""),
                status=data.get("status", "RUNNING"),
                created_at=data.get("created_at", ""),
                spec_available=data.get("spec_available", False),
                sha256_hash=data.get("sha256_hash"),
            )
        )

    # Check specs directory for any disk runs not in registry
    specs_dir = Path(__file__).resolve().parent.parent.parent / "artifacts" / "specs"
    if specs_dir.exists():
        for file in specs_dir.glob("*.json"):
            run_id = file.stem
            if run_id not in RUNS_REGISTRY:
                try:
                    spec_data = json.loads(file.read_text(encoding="utf-8"))
                    summaries.append(
                        RunSummary(
                            run_id=run_id,
                            entry_fqn=spec_data.get("entry_fqn", ""),
                            status="HITL_PENDING",
                            created_at=spec_data.get("created_at", datetime.now(timezone.utc).isoformat()),
                            spec_available=True,
                            sha256_hash=spec_data.get("sha256_hash"),
                        )
                    )
                except Exception:
                    pass

    # Sort newest first
    summaries.sort(key=lambda s: s.created_at, reverse=True)
    return summaries


@router.get("/runs/{run_id}")
def get_pipeline_run(run_id: str) -> Dict[str, Any]:
    """
    Returns metadata and specification for a specific run_id.
    """
    run_info = RUNS_REGISTRY.get(run_id)
    specs_dir = Path(__file__).resolve().parent.parent.parent / "artifacts" / "specs"
    spec_file = specs_dir / f"{run_id}.json"

    spec_data = None
    if spec_file.exists():
        try:
            spec_data = json.loads(spec_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    if not run_info and not spec_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline run '{run_id}' not found.",
        )

    return {
        "run_id": run_id,
        "status": run_info.get("status") if run_info else "HITL_PENDING",
        "entry_fqn": run_info.get("entry_fqn") if run_info else (spec_data.get("entry_fqn") if spec_data else ""),
        "spec": spec_data,
        "sha256_hash": spec_data.get("sha256_hash") if spec_data else run_info.get("sha256_hash") if run_info else None,
    }
