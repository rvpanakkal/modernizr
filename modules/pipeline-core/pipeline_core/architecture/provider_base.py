"""
Abstract Base Class for Target Architecture Providers.
======================================================
Defines the contract for ingesting an enterprise reference microservice
(or future ADR / archetype) and harvesting a canonical ArchitectureProfile.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from pipeline_core.schemas.architecture import ArchitectureProfile


class TargetArchitectureProvider(ABC):
    """
    Abstract base provider for harvesting and constructing Architecture Profiles.
    """

    @abstractmethod
    def build_profile(
        self,
        source_path_or_uri: str,
        profile_name: str,
        profile_id: Optional[str] = None,
    ) -> ArchitectureProfile:
        """
        Inspects the reference target microservice across four structural layers:
        1. Build & BOM (dependencies, starters, plugins)
        2. Package & Layering Topology (layering pattern, base package)
        3. Code Pattern Exemplars (exception handling, REST controllers, services, security)
        4. Executable Invariant Rules (ArchUnit assertions)

        Returns an immutable ArchitectureProfile with computed SHA-256 hash.
        """
        raise NotImplementedError
