"""
Pydantic v2 schemas for File-based JSON / NetworkX Graph Subsystem.
Models for GraphNode, GraphEdge, IngestionStats, SliceResponse, and Diagnostics.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    id: str = Field(description="Unique identifier / fully qualified class name (FQN)")
    label: str = Field(description="Simple class name or display label")
    name: Optional[str] = Field(default=None, description="Display name fallback")
    layer: str = Field(default="SERVICE", description="Architectural layer: PRESENTATION, API, SERVICE, INTEGRATION, DATA, UTIL")
    role: Optional[str] = Field(default=None, description="Semantic role: JSF_MANAGED_BEAN, REST_ENDPOINT, DOMAIN_SERVICE, etc.")
    color: Optional[str] = Field(default=None, description="HEX color code for UI graph rendering")
    file_path: Optional[str] = Field(default=None, description="Relative file path in repository")
    start_line: Optional[int] = Field(default=None, description="Starting line in source file")
    end_line: Optional[int] = Field(default=None, description="Ending line in source file")
    annotations: List[str] = Field(default_factory=list, description="Class-level annotations")
    methods: List[str] = Field(default_factory=list, description="Declared method names")
    source_code: Optional[str] = Field(default=None, description="Extracted source code snippet")

    def model_post_init(self, __context: Any) -> None:
        if not self.name:
            self.name = self.label
        if not self.color:
            layer_upper = self.layer.upper()
            colors = {
                "PRESENTATION": "#3b82f6",
                "API": "#06b6d4",
                "SERVICE": "#10b981",
                "INTEGRATION": "#8b5cf6",
                "DATA": "#f59e0b",
                "DOMAIN": "#f59e0b",
                "SECURITY": "#ec4899",
                "UTIL": "#6b7280",
            }
            self.color = colors.get(layer_upper, "#3b82f6")


class GraphEdge(BaseModel):
    id: str = Field(description="Unique edge identifier")
    source: str = Field(description="Source node FQN")
    target: str = Field(description="Target node FQN")
    relationship: str = Field(default="INJECTS", description="Relationship type: INJECTS, CALLS, CONNECTS_TO")
    type: Optional[str] = Field(default=None, description="Edge type (synonym for relationship)")
    label: Optional[str] = Field(default=None, description="Edge label")

    def model_post_init(self, __context: Any) -> None:
        if not self.type:
            self.type = self.relationship
        if not self.label:
            self.label = self.relationship


class GraphMetadata(BaseModel):
    extracted_at: str
    total_classes: int
    total_methods: int = 0
    total_edges: int = 0
    resolved_type_percentage: float = 100.0
    source_hash: Optional[str] = None


class LSTGraphData(BaseModel):
    metadata: GraphMetadata
    nodes: List[GraphNode]
    edges: List[GraphEdge]


class EntryPoint(BaseModel):
    fqn: str
    simple_name: str
    layer: str = Field(description="Presentation, API, Integration, etc.")
    role: str
    kind: str = "CLASS"
    annotations: List[str] = Field(default_factory=list)
    injected_dependencies: List[str] = Field(default_factory=list)
    description: str = ""


# Alias for backward-compatibility with existing router
EntrypointItem = EntryPoint


class SliceRequest(BaseModel):
    entry_fqn: str = Field(default="com.enterprise.banking.TransferManagedBean")
    max_depth: int = Field(default=5, ge=1, le=8)


class SliceResponse(BaseModel):
    slice_id: str
    entry_fqn: str
    max_depth: int
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    total_nodes: int = 0
    total_edges: int = 0
    execution_paths: List[str] = Field(default_factory=list)
    component_summary: List[Dict[str, Any]] = Field(default_factory=list)
    estimated_tokens: int = 0
    max_tokens: int = 6000
    within_budget: bool = True
    legacy_source: str = ""
    raw_slice: Dict[str, Any] = Field(default_factory=dict)


class IngestionStats(BaseModel):
    status: str = "SUCCESS"
    classes_parsed: int
    resolved_type_percentage: float
    entry_points_detected: int
    total_edges: int = 0
    graph_file_path: str
    extracted_at: str = ""
    sha256_digest: str = ""


# Extended Ingestion Result with backwards compatibility
class SourceIngestionResult(IngestionStats):
    monolith_id: str = "legacy-banking-monolith"
    jdk_version: str = "8"
    framework_profile: str = "JAVA_EE_6_JSF"
    classpath_strategy: str = "AI_SYNTHETIC_STUBS"
    classes_count: int = 0
    methods_count: int = 0
    injected_fields_count: int = 0
    invocations_count: int = 0
    endpoints_count: int = 0
    cics_gateways_count: int = 0
    execution_time_ms: int = 0
    message: str = ""


class DiagnosticsResponse(BaseModel):
    status: str = "HEALTHY"
    graph_loaded: bool = True
    total_nodes: int = 0
    total_edges: int = 0
    total_entrypoints: int = 0
    resolved_type_percentage: float = 100.0
    graph_file_path: str = "artifacts/metadata/lst_graph.json"
    extracted_at: Optional[str] = None
    sha256_digest: Optional[str] = None
    entry_point_names: List[str] = Field(default_factory=list)
