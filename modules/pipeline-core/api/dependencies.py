"""
Dependency injection providers for FastAPI routers.
Manages Neo4j driver lifecycle, configuration settings, and service singletons.
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator, Generator, Optional
from neo4j import GraphDatabase, Driver, Session

from api.config import Settings, get_settings
from api.services.event_bus import EventBus, event_bus
from api.services.catalog_matcher import CatalogMatcher, catalog_matcher
from api.services.runner_bridge import RunnerBridge, runner_bridge

log = logging.getLogger(__name__)

_neo4j_driver: Optional[Driver] = None


def init_neo4j_driver(settings: Settings) -> Optional[Driver]:
    """Initializes the Neo4j driver if reachable; logs warning and falls back to mock mode if not."""
    global _neo4j_driver
    try:
        driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            connection_timeout=2.0,
            max_connection_lifetime=300,
        )
        # Test connectivity
        driver.verify_connectivity()
        _neo4j_driver = driver
        log.info("[Neo4j] Connected successfully to %s", settings.NEO4J_URI)
        return _neo4j_driver
    except Exception as exc:
        log.warning("[Neo4j] Could not connect to Neo4j at %s (%s). API will operate in mock mode.", settings.NEO4J_URI, exc)
        _neo4j_driver = None
        return None


def close_neo4j_driver() -> None:
    """Closes active Neo4j driver connections cleanly."""
    global _neo4j_driver
    if _neo4j_driver:
        try:
            _neo4j_driver.close()
            log.info("[Neo4j] Driver connections closed cleanly.")
        except Exception as exc:
            log.warning("[Neo4j] Error closing driver: %s", exc)
        finally:
            _neo4j_driver = None


def get_neo4j_driver() -> Optional[Driver]:
    """Returns the active Neo4j driver if connected, or None."""
    return _neo4j_driver


def get_neo4j_session() -> Generator[Optional[Session], None, None]:
    """Dependency that yields a Neo4j session if driver is active, otherwise None."""
    if _neo4j_driver is None:
        yield None
        return

    session = None
    try:
        session = _neo4j_driver.session()
        yield session
    finally:
        if session:
            session.close()


def get_event_bus() -> EventBus:
    return event_bus


def get_runner_bridge() -> RunnerBridge:
    return runner_bridge


def get_catalog_matcher() -> CatalogMatcher:
    return catalog_matcher
