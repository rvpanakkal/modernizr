"""
Router for Pipeline Step 3: Multi-Pass Cognitive Extraction & Live Telemetry Streaming.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, Dict, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from api.dependencies import get_event_bus, get_runner_bridge
from api.services.event_bus import EventBus
from api.services.runner_bridge import RunnerBridge

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pipeline", tags=["Pipeline Execution"])


class RunInitiateRequest(BaseModel):
    entry_fqn: str = Field(default="com.legacy.banking.web.TransferManagedBean")
    slice_data: Optional[Dict[str, Any]] = None
    tracker_type: str = Field(default="jira")


class RunInitiateResponse(BaseModel):
    run_id: str
    status: str
    entry_fqn: str
    stream_url: str
    message: str


@router.post("/runs", response_model=RunInitiateResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_pipeline_run(
    request: RunInitiateRequest,
    background_tasks: BackgroundTasks,
    runner: RunnerBridge = Depends(get_runner_bridge),
) -> RunInitiateResponse:
    """
    Initiates the 3-pass cognitive extraction chain for a vertical slice.
    Spawns background extraction and returns the run_id for real-time SSE telemetry tracking.
    """
    run_id = f"run-{uuid.uuid4().hex[:8]}"
    log.info("[Pipeline Router] Initiating cognitive run %s for %s", run_id, request.entry_fqn)

    # Launch background extraction task
    background_tasks.add_task(
        runner.execute_cognitive_chain,
        run_id=run_id,
        entry_fqn=request.entry_fqn,
        slice_data=request.slice_data,
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
    Streams pass transitions, token burn rate, generated operations, and logs in real-time.
    """
    log.info("[Pipeline Router] SSE telemetry client connected to run_id: %s", run_id)

    async def event_generator():
        try:
            async for event in bus.subscribe(run_id):
                yield {
                    "event": event.get("type", "message"),
                    "data": json.dumps(event),
                }
        except asyncio.CancelledError:
            log.info("[Pipeline Router] SSE connection closed for run_id: %s", run_id)
            raise

    return EventSourceResponse(
        event_generator(),
        media_type="text/event-stream",
        ping=15,  # Heartbeat ping every 15s to keep connection alive
    )
