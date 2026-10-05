from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import hashlib
from pydantic import BaseModel, Field, field_validator, ConfigDict


# =============================================================================
# Pipeline Infrastructure Schemas
# =============================================================================

class ExecutionStatus(str, Enum):
    PENDING      = "PENDING"
    IN_PROGRESS  = "IN_PROGRESS"
    PAUSED_HITL  = "PAUSED_HITL"   # legacy alias retained for the Step 1-2 era workflow engine
    HITL_PENDING = "HITL_PENDING"  # Step 4 gate: spec published to Jira, awaiting human sign-off
    COMPLETED    = "COMPLETED"
    SUCCESS      = "SUCCESS"       # Step 4 gate: human approval verified, pipeline unblocked
    FAILED       = "FAILED"


class ArtifactType(str, Enum):
    RAW_LST_JSON     = "RAW_LST_JSON"
    GRAPH_NODE_EXPORT = "GRAPH_NODE_EXPORT"
    GRAPH_SLICE      = "GRAPH_SLICE"
    DECOMPILED_SPEC  = "DECOMPILED_SPEC"
    BUSINESS_RULES   = "BUSINESS_RULES"
    GENERATED_SPEC   = "GENERATED_SPEC"
    BDD_GHERKIN      = "BDD_GHERKIN"
    OPENAPI_SPEC     = "OPENAPI_SPEC"
    RAML_SPEC        = "RAML_SPEC"
    SPRING_BOOT_CODE = "SPRING_BOOT_CODE"
    ANGULAR_CODE     = "ANGULAR_CODE"


class ArtifactPointer(BaseModel):
    """
    Pointer & Receipt Pattern: Encapsulates artifact storage pointers without
    passing raw content in agent memory. Carries SHA-256 hash for integrity verification.
    """
    uri:           str            = Field(..., description="File path URI or S3 link to the artifact")
    sha256_hash:   str            = Field(..., description="SHA-256 digest verifying artifact integrity")
    artifact_type: ArtifactType   = Field(..., description="Category of artifact stored")
    media_type:    str            = Field(default="application/json", description="MIME type of stored content")
    size_bytes:    int            = Field(default=0, ge=0,  description="Artifact size in bytes")
    metadata:      Dict[str, Any] = Field(default_factory=dict, description="Arbitrary key-value metadata tags")

    @classmethod
    def create_from_content(
        cls,
        content:       str | bytes,
        uri:           str,
        artifact_type: ArtifactType,
        media_type:    str = "application/json",
    ) -> "ArtifactPointer":
        content_bytes = content.encode("utf-8") if isinstance(content, str) else content
        digest = hashlib.sha256(content_bytes).hexdigest()
        return cls(
            uri=uri,
            sha256_hash=digest,
            artifact_type=artifact_type,
            media_type=media_type,
            size_bytes=len(content_bytes),
        )

    @classmethod
    def create_from_file(cls, file_path: str, artifact_type: ArtifactType) -> "ArtifactPointer":
        """Create an ArtifactPointer by hashing an actual file on disk."""
        import os
        sha256 = hashlib.sha256()
        size   = 0
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
                size += len(chunk)
        return cls(
            uri=file_path,
            sha256_hash=sha256.hexdigest(),
            artifact_type=artifact_type,
            media_type="application/json",
            size_bytes=size,
        )


class StepHandoffReceipt(BaseModel):
    """
    Deterministic pipeline handoff receipt enforcing Code-to-Spec-to-Code traceability.
    Carries all metadata needed for audit and HITL gate enforcement.
    """
    receipt_id:       str                   = Field(..., description="Unique UUID receipt identifier")
    step_number:      int                   = Field(..., ge=1, le=5, description="Pipeline step number (1-5)")
    step_name:        str                   = Field(..., description="Human-readable step name")
    jira_story_id:    str                   = Field(..., pattern=r"^(MOD-\d+|GH-\d+|#\d+|LOCAL-[A-Za-z0-9_-]+)$", description="Tracking ID e.g. MOD-101, GH-42, LOCAL-101")
    tracker_type:     str                   = Field(default="jira", description="Issue tracker type: jira, github, local, etc.")
    input_pointers:   List[ArtifactPointer] = Field(default_factory=list)
    output_pointers:  List[ArtifactPointer] = Field(default_factory=list)
    status:           ExecutionStatus       = Field(default=ExecutionStatus.PENDING)
    hitl_approved:    bool                  = Field(default=False)
    approved_by:      Optional[str]         = Field(default=None)
    approval_timestamp: Optional[datetime]  = Field(default=None)
    started_at:       datetime              = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at:     Optional[datetime]    = Field(default=None)
    duration_ms:      Optional[int]         = Field(default=None, ge=0)
    error_message:    Optional[str]         = Field(default=None)
    metrics:          Dict[str, Any]        = Field(default_factory=dict, description="Step-specific metrics (node/edge counts etc.)")
    run_id:           Optional[str]         = Field(default=None, description="Pipeline run identifier shared by all receipts of one run")
    objective:        Optional[str]         = Field(default=None, description="What this checkpoint asks of the next actor")
    locked_decisions: Dict[str, str]        = Field(default_factory=dict, description="Decisions frozen at this checkpoint (e.g. jira_story_id, feature_name)")
    non_goals:        List[str]             = Field(default_factory=list, description="Explicitly out-of-scope items for this checkpoint")
    next_step:        Optional[str]         = Field(default=None, description="Entry point to trigger once this receipt is SUCCESS")

    @field_validator("hitl_approved")
    @classmethod
    def check_hitl_approval_integrity(cls, v: bool, info) -> bool:
        if info.data.get("step_number") == 5 and not v:
            raise ValueError(
                "Execution of Step 5 (Target Synthesis) requires hitl_approved=True. "
                "Obtain human approval via the Jira HITL gate before proceeding."
            )
        return v


# =============================================================================
# LST Export Payload Schemas — mirrors Java LSTExportPayload POJO
#
# All Pydantic models use camelCase aliases matching the Jackson-serialized JSON
# emitted by ExtractorCli. populate_by_name=True allows both snake_case and
# camelCase to be used in Python code.
# =============================================================================

class InvocationRecord(BaseModel):
    """Method-level call graph edge: caller class/method → target class/method."""
    model_config = ConfigDict(populate_by_name=True)

    caller_class_fqn:  str       = Field(..., alias="callerClassFqn")
    caller_method_name: str      = Field(..., alias="callerMethodName")
    target_class_fqn:  str       = Field(..., alias="targetClassFqn")
    target_method_name: str      = Field(..., alias="targetMethodName")
    return_type:       str       = Field(default="void", alias="returnType")
    argument_types:    List[str] = Field(default_factory=list, alias="argumentTypes")


class FieldRecord(BaseModel):
    """Dependency-injected field on a class (via @EJB, @Inject, @Autowired, @PersistenceContext)."""
    model_config = ConfigDict(populate_by_name=True)

    name:       str            = Field(...)
    type:       str            = Field(...)
    type_fqn:   Optional[str] = Field(default=None, alias="typeFqn")
    annotation: str            = Field(...)


class MethodRecord(BaseModel):
    """Method declaration extracted from a class."""
    model_config = ConfigDict(populate_by_name=True)

    name:              str            = Field(...)
    return_type:       str            = Field(default="void",   alias="returnType")
    parameter_types:   List[str]      = Field(default_factory=list, alias="parameterTypes")
    annotations:       List[str]      = Field(default_factory=list)
    signature:         Optional[str]  = Field(default=None)
    thrown_exceptions: List[str]      = Field(default_factory=list, alias="thrownExceptions")
    branch_count:      int            = Field(default=0, alias="branchCount")
    body_source:       Optional[str]  = Field(default=None, alias="bodySource")


class ClassRecord(BaseModel):
    """
    Full metadata record for a single Java class or interface extracted from the LST.
    Includes annotations, injected fields, declared methods, and outbound call invocations.
    """
    model_config = ConfigDict(populate_by_name=True)

    fqn:         str                   = Field(...)
    simple_name: str                   = Field(..., alias="simpleName")
    kind:        str                   = Field(default="CLASS")
    annotations: List[str]             = Field(default_factory=list)
    fields:      List[FieldRecord]     = Field(default_factory=list)
    methods:     List[MethodRecord]    = Field(default_factory=list)
    invocations: List[InvocationRecord] = Field(default_factory=list)


class LSTExportPayload(BaseModel):
    """
    Top-level schema for the JSON artifact produced by ExtractorCli (Pipeline Step 1).
    Validated by ingest_graph.py (Pipeline Step 2) before Neo4j ingestion.
    """
    model_config = ConfigDict(populate_by_name=True)

    schema_version:   str              = Field(default="1.0.0", alias="schemaVersion")
    extracted_at:     str              = Field(..., alias="extractedAt")
    source_directory: str              = Field(..., alias="sourceDirectory")
    classes:          List[ClassRecord] = Field(default_factory=list)


# Backward compatibility aliases
LSTExportSchema = LSTExportPayload
ClassMetadataSchema = ClassRecord
MethodMetadataSchema = MethodRecord
FieldMetadataSchema = FieldRecord

