"""
Dependency injection providers for FastAPI routers.
Zero Database Infrastructure: provides in-memory NetworkX JsonGraphService singleton.
Retains backward-compatible stubs for configuration and service singletons.
"""

from __future__ import annotations

import logging
from typing import Generator, Optional

from api.config import Settings, get_settings
from api.services.event_bus import EventBus, event_bus
from api.services.catalog_matcher import CatalogMatcher, catalog_matcher
from api.services.runner_bridge import RunnerBridge, runner_bridge
from api.services.json_graph_service import JsonGraphService, json_graph_service

log = logging.getLogger(__name__)


def get_json_graph_service() -> JsonGraphService:
    """Dependency provider for the singleton JsonGraphService."""
    return json_graph_service


def get_neo4j_driver() -> Optional[Any]:
    """Deprecated: Zero-database mode replaces Neo4j with NetworkX JsonGraphService."""
    return None


def get_neo4j_session() -> Generator[Optional[Any], None, None]:
    """Deprecated: Yields None as Neo4j is replaced with file-based NetworkX engine."""
    yield None


def init_neo4j_driver(settings: Settings) -> None:
    """Deprecated stub: Initializes file-based NetworkX JsonGraphService on boot."""
    log.info("[JsonGraph] File-based NetworkX graph engine active (Zero Database Infrastructure).")
    json_graph_service.load_graph()


def close_neo4j_driver() -> None:
    """Deprecated stub: No external database connections to close."""
    pass


def get_event_bus() -> EventBus:
    return event_bus


def get_runner_bridge() -> RunnerBridge:
    return runner_bridge


def get_catalog_matcher() -> CatalogMatcher:
    return catalog_matcher
