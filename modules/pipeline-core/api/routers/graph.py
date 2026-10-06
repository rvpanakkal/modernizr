"""
Router for Graph Discovery and NetworkX Vertical Slice Extraction.
Executes in-memory topological BFS queries and token budgeting without external database dependencies.
"""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import get_json_graph_service
from api.services.json_graph_service import JsonGraphService
from pipeline_core.schemas.graph import (
    EntryPoint,
    EntrypointItem,
    GraphEdge,
    GraphNode,
    SliceRequest,
    SliceResponse,
)

log = logging.getLogger("GraphRouter")

router = APIRouter(prefix="/api/graph", tags=["Graph & Topology"])


@router.get("/entrypoints", response_model=List[EntryPoint])
def get_entrypoints(
    graph_service: JsonGraphService = Depends(get_json_graph_service),
) -> List[EntryPoint]:
    """
    Returns detected entry points (@ManagedBean, @Path, @RestController, etc.)
    discovered by the in-memory NetworkX DiGraph.
    """
    entrypoints = graph_service.get_entrypoints()
    if not entrypoints:
        # If graph is empty, attempt reload
        graph_service.load_graph()
        entrypoints = graph_service.get_entrypoints()

    log.info("[GraphRouter] Discovered %d entry points in NetworkX graph.", len(entrypoints))
    return entrypoints


@router.post("/slice", response_model=SliceResponse)
def extract_vertical_slice(
    request: SliceRequest,
    graph_service: JsonGraphService = Depends(get_json_graph_service),
) -> SliceResponse:
    """
    Executes directed BFS traversal starting at entry_fqn up to max_depth.
    Extracts the induced subgraph, computes execution paths, aggregates source code,
    and checks compliance against the 6,000 token budget.
    """
    log.info(
        "[GraphRouter] Extracting vertical slice for entry_fqn=%s, max_depth=%d",
        request.entry_fqn,
        request.max_depth,
    )
    slice_resp = graph_service.extract_vertical_slice(
        entry_fqn=request.entry_fqn,
        max_depth=request.max_depth,
    )
    return slice_resp
