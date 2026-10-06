"""
Data contracts for Target Architecture Profiles.
================================================
Governs:
- Layering topology patterns (Controller-Service-Repository, Hexagonal, Clean Architecture, Modular Monolith)
- Code pattern exemplars harvested from existing reference microservices
- ArchUnit executable invariant rules for Step 5.5 conformance gating
- Canonical, immutable ArchitectureProfile with SHA-256 integrity digest
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LayeringPattern(str, Enum):
    """Architectural layering patterns detected from repository topology."""
    CONTROLLER_SERVICE_REPOSITORY = "CONTROLLER_SERVICE_REPOSITORY"
    HEXAGONAL = "HEXAGONAL"
    CLEAN_ARCHITECTURE = "CLEAN_ARCHITECTURE"
    MODULAR_MONOLITH = "MODULAR_MONOLITH"


class CodePatternExemplar(BaseModel):
    """
    Harvested code pattern exemplar from an approved reference service.
    Serves as few-shot guidance during Step 5 LLM code synthesis.
    """
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    pattern_name: str = Field(..., min_length=1, description="E.g., GlobalExceptionHandler, RestController, SecurityConfig, AuditedEntity, Service")
    target_layer: str = Field(..., min_length=1, description="E.g., controller, service, repository, config, domain")
    annotations_matched: List[str] = Field(default_factory=list, description="Annotations detected, e.g. @RestControllerAdvice, @Service")
    code_snippet: str = Field(..., min_length=1, description="Sanitized source code stripped of file-specific licenses and boilerplate")
    origin_file: Optional[str] = Field(default=None, description="Relative path in reference repository where exemplar was harvested")


class ArchUnitRule(BaseModel):
    """
    Executable architectural invariant rule compiled into the target test suite.
    """
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    rule_id: str = Field(..., min_length=1, description="Unique identifier, e.g. ARCH-001")
    description: str = Field(..., min_length=1, description="Human-readable rationale for the invariant")
    test_method_name: str = Field(..., min_length=1, description="Java test method name in ArchUnit test class")
    rule_code: str = Field(..., min_length=1, description="Java ArchUnit assertion definition / method body")


class ArchitectureProfile(BaseModel):
    """
    Immutable canonical architecture profile harvested from reference microservices.
    Enforces build dependencies, package naming conventions, few-shot exemplars,
    and automated ArchUnit conformance gates.
    """
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    profile_id: str = Field(..., min_length=1, description="Unique slug, e.g. arch-payments-v2")
    name: str = Field(..., min_length=1, description="Descriptive profile name")
    target_runtime: str = Field(default="Java 21 / Spring Boot 3.5.x", description="Target platform runtime")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="UTC timestamp of profile harvesting")
    base_package_pattern: str = Field(..., min_length=1, description="Base package convention, e.g. com.enterprise.{domain}.v2")
    layering_pattern: LayeringPattern = Field(default=LayeringPattern.CONTROLLER_SERVICE_REPOSITORY, description="Detected architectural layering style")
    build_file_template: str = Field(..., min_length=1, description="Sanitized pom.xml template with dependency/plugin BOM")
    required_dependencies: List[str] = Field(default_factory=list, description="List of required Maven coordinates (groupId:artifactId)")
    exemplars: List[CodePatternExemplar] = Field(default_factory=list, description="Harvested few-shot exemplars")
    conformance_rules: List[ArchUnitRule] = Field(default_factory=list, description="ArchUnit invariant rules to enforce")
    sha256_hash: str = Field(default="", description="Cryptographic SHA-256 digest of canonical profile contents")

    def compute_sha256(self) -> str:
        """
        Computes SHA-256 digest across all canonical profile attributes (excluding sha256_hash).
        """
        payload = self.model_dump(mode="json", exclude={"sha256_hash"})
        canonical_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(canonical_bytes).hexdigest()

    def with_computed_hash(self) -> "ArchitectureProfile":
        """Returns a copy of the profile with sha256_hash computed and populated."""
        computed = self.compute_sha256()
        return self.model_copy(update={"sha256_hash": computed})
