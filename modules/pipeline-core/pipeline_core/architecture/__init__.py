"""
Target Architecture Provider Subsystem.
=======================================
Provides:
- Architecture Profile schema and lifecycle management
- 4-layer inspection harvester for enterprise reference microservices
- Dynamic ArchUnit executable conformance test generation
- Profile persistence registry and active profile gating
"""

from pipeline_core.architecture.archunit_templates import (
    STANDARD_RULES,
    get_standard_archunit_rules,
    render_archunit_test_class,
)
from pipeline_core.architecture.provider_base import TargetArchitectureProvider
from pipeline_core.architecture.reference_repo_provider import ReferenceMicroserviceProvider
from pipeline_core.architecture.registry import (
    ArchitectureProfileRegistry,
    get_architecture_registry,
)

__all__ = [
    "TargetArchitectureProvider",
    "ReferenceMicroserviceProvider",
    "ArchitectureProfileRegistry",
    "get_architecture_registry",
    "STANDARD_RULES",
    "get_standard_archunit_rules",
    "render_archunit_test_class",
]
