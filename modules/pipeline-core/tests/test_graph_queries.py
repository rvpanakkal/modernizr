"""
Tests for GraphRAG query formatting and slice structure validation.
These tests validate the *output format* of queries.py without requiring a live Neo4j connection.
"""
import pytest
from pipeline_core.graph.queries import (
    ENTRY_POINT_ANNOTATIONS,
    BOUNDARY_NAME_FRAGMENTS,
    MAX_SLICE_TOKENS,
    _infer_role,
    _estimate_tokens,
    _truncate_to_budget,
    _extract_boundaries,
    _build_component_summary,
)


class TestEntryPointAnnotations:
    def test_managed_bean_is_entry_point(self):
        assert "ManagedBean" in ENTRY_POINT_ANNOTATIONS

    def test_path_is_entry_point(self):
        assert "Path" in ENTRY_POINT_ANNOTATIONS

    def test_rest_controller_is_entry_point(self):
        assert "RestController" in ENTRY_POINT_ANNOTATIONS


class TestBoundaryFragments:
    def test_gateway_is_boundary(self):
        assert "Gateway" in BOUNDARY_NAME_FRAGMENTS

    def test_repository_is_boundary(self):
        assert "Repository" in BOUNDARY_NAME_FRAGMENTS

    def test_dao_is_boundary(self):
        assert "DAO" in BOUNDARY_NAME_FRAGMENTS


class TestRoleInference:
    def test_gateway_role(self):
        assert _infer_role("CicsMainframeGateway", []) == "INTEGRATION_BOUNDARY"

    def test_repository_role(self):
        assert _infer_role("AccountRepository", []) == "DATA_ACCESS"

    def test_service_role_by_name(self):
        assert _infer_role("TransferProcessingService", []) == "DOMAIN_SERVICE"

    def test_service_role_by_annotation(self):
        assert _infer_role("BusinessLogicBean", ["Stateless"]) == "DOMAIN_SERVICE"

    def test_unknown_component(self):
        assert _infer_role("SomeUnknownBean", []) == "COMPONENT"


class TestTokenEstimation:
    def test_empty_context_returns_nonzero(self):
        tokens = _estimate_tokens({"sliceId": "com.example.Foo"})
        assert tokens > 0

    def test_larger_context_returns_more_tokens(self):
        small = _estimate_tokens({"data": "x"})
        large = _estimate_tokens({"data": "x" * 10000})
        assert large > small

    def test_max_token_constant(self):
        assert MAX_SLICE_TOKENS == 6_000


class TestBudgetTruncation:
    def test_truncation_cuts_call_flows(self):
        ctx = {
            "callFlows":             list(range(50)),   # 50 items
            "executionPaths":        list(range(20)),   # 20 items
            "methodImplementations": list(range(20)),   # 20 items
            "estimatedTokens":       9999,
            "withinBudget":          False,
        }
        truncated = _truncate_to_budget(ctx)
        assert len(truncated["callFlows"])             <= 10
        assert len(truncated["executionPaths"])        <= 5
        assert len(truncated["methodImplementations"]) <= 5
        assert truncated.get("truncated") is True


class TestBoundaryExtraction:
    def test_gateway_detected_as_boundary(self):
        paths = [
            {
                "componentFqn":         "com.legacy.banking.gateway.CicsMainframeGateway",
                "componentSimpleName":  "CicsMainframeGateway",
                "componentAnnotations": ["Stateless"],
                "componentMethods":     [{"name": "executeTransfer", "returnType": "java.lang.String"}],
                "depth":                2,
            }
        ]
        boundaries = _extract_boundaries(paths)
        assert len(boundaries) == 1
        assert boundaries[0]["simpleName"]  == "CicsMainframeGateway"
        assert boundaries[0]["role"]        == "INTEGRATION_BOUNDARY"

    def test_service_not_detected_as_boundary(self):
        paths = [
            {
                "componentFqn":         "com.legacy.banking.service.TransferProcessingService",
                "componentSimpleName":  "TransferProcessingService",
                "componentAnnotations": ["Stateless"],
                "componentMethods":     [],
                "depth":                1,
            }
        ]
        boundaries = _extract_boundaries(paths)
        assert len(boundaries) == 0

    def test_repository_detected_as_boundary(self):
        paths = [
            {
                "componentFqn":         "com.legacy.banking.repository.AccountRepository",
                "componentSimpleName":  "AccountRepository",
                "componentAnnotations": ["Stateless"],
                "componentMethods":     [],
                "depth":                2,
            }
        ]
        boundaries = _extract_boundaries(paths)
        assert len(boundaries) == 1
        assert boundaries[0]["role"] == "DATA_ACCESS"


class TestComponentSummary:
    def test_entry_point_is_first(self):
        entry = {
            "fqn": "com.legacy.banking.web.TransferManagedBean",
            "simpleName": "TransferManagedBean",
            "kind": "CLASS",
            "annotations": ["ManagedBean"],
            "methods": [],
        }
        paths = [
            {
                "componentFqn": "com.legacy.banking.service.TransferProcessingService",
                "componentSimpleName": "TransferProcessingService",
                "componentAnnotations": ["Stateless"],
                "depth": 1,
            }
        ]
        summary = _build_component_summary(entry, paths)
        assert summary[0]["role"] == "ENTRY_POINT"
        assert summary[0]["simpleName"] == "TransferManagedBean"
        assert len(summary) == 2

    def test_no_duplicates_in_summary(self):
        entry = {
            "fqn": "com.example.EntryClass",
            "simpleName": "EntryClass",
            "kind": "CLASS",
            "annotations": [],
            "methods": [],
        }
        # Same component appears in two paths at different depths
        paths = [
            {"componentFqn": "com.example.ServiceA", "componentSimpleName": "ServiceA",
             "componentAnnotations": [], "depth": 1},
            {"componentFqn": "com.example.ServiceA", "componentSimpleName": "ServiceA",
             "componentAnnotations": [], "depth": 2},
        ]
        summary = _build_component_summary(entry, paths)
        fqns = [c["fqn"] for c in summary]
        assert len(fqns) == len(set(fqns)), "No duplicates expected in component summary"
