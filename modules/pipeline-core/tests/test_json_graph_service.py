"""
Tests for JsonGraphService and file-based NetworkX graph engine.
Verifies zero-database graph loading, BFS slicing, token budgeting, and diagnostics.
"""

import json
from pathlib import Path
import pytest
from api.services.json_graph_service import JsonGraphService
from pipeline_core.schemas.graph import EntryPoint, SliceResponse, DiagnosticsResponse


@pytest.fixture
def graph_service():
    service = JsonGraphService()
    service.load_graph()
    return service


def test_json_graph_service_loads_nodes_and_edges(graph_service):
    assert graph_service.graph.number_of_nodes() >= 5
    assert graph_service.graph.number_of_edges() >= 4
    diag = graph_service.get_diagnostics()
    assert diag.status == "HEALTHY"
    assert diag.graph_loaded is True
    assert diag.total_nodes >= 5


def test_entrypoint_discovery(graph_service):
    entrypoints = graph_service.get_entrypoints()
    assert len(entrypoints) >= 1
    fqns = [ep.fqn for ep in entrypoints]
    # Check for transfer bean
    assert any("TransferManagedBean" in f for f in fqns)
    # Check layers
    layers = [ep.layer for ep in entrypoints]
    assert "Presentation" in layers


def test_vertical_slice_bfs_traversal(graph_service):
    # Slice for TransferManagedBean
    entry_fqn = "com.enterprise.banking.TransferManagedBean"
    if entry_fqn not in graph_service.graph:
        entry_fqn = "com.legacy.banking.web.TransferManagedBean"

    slice_resp = graph_service.extract_vertical_slice(entry_fqn=entry_fqn, max_depth=5)
    assert isinstance(slice_resp, SliceResponse)
    assert slice_resp.entry_fqn == entry_fqn
    assert slice_resp.total_nodes >= 3
    assert slice_resp.total_edges >= 2
    assert slice_resp.within_budget is True
    assert slice_resp.estimated_tokens > 0
    assert len(slice_resp.execution_paths) >= 1


def test_slice_token_budget_calculation(graph_service):
    entry_fqn = "com.legacy.banking.web.TransferManagedBean"
    if entry_fqn not in graph_service.graph:
        entry_fqn = "com.enterprise.banking.TransferManagedBean"

    slice_resp = graph_service.extract_vertical_slice(entry_fqn=entry_fqn, max_depth=3)
    assert slice_resp.max_tokens == 6000
    assert slice_resp.estimated_tokens <= 6000
    assert slice_resp.within_budget is True


def test_nonexistent_node_slice_returns_empty(graph_service):
    slice_resp = graph_service.extract_vertical_slice("com.nonexistent.Class", max_depth=5)
    assert slice_resp.total_nodes == 0
    assert slice_resp.within_budget is True


def test_diagnostics_endpoint(graph_service):
    diag = graph_service.get_diagnostics()
    assert isinstance(diag, DiagnosticsResponse)
    assert diag.total_nodes == graph_service.graph.number_of_nodes()
    assert diag.total_edges == graph_service.graph.number_of_edges()
    assert diag.resolved_type_percentage >= 90.0
