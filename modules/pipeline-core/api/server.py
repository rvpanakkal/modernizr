"""
FastAPI Server Root for the Enterprise Legacy Modernization Factory.
Wires CORS middleware, lifecycle hooks, exception handlers, and API routers.
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict

# Ensure repository and modules/pipeline-core are on sys.path
api_dir = Path(__file__).resolve().parent
pipeline_core_dir = api_dir.parent
repo_root = pipeline_core_dir.parent.parent

for p in (str(pipeline_core_dir), str(repo_root)):
    if p not in sys.path:
        sys.path.insert(0, p)

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from api.config import Settings, get_settings
from api.dependencies import close_neo4j_driver, init_neo4j_driver
from api.routers import graph, hitl, pipeline, source, synthesis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("ModernizationApi")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management: connects to Neo4j on startup and releases connections on shutdown."""
    settings = get_settings()
    log.info("[Server] Initializing Modernization Factory API (Mock Mode: %s)...", settings.MOCK_MODE)
    init_neo4j_driver(settings)
    yield
    log.info("[Server] Shutting down Modernization Factory API...")
    close_neo4j_driver()


app = FastAPI(
    title="Enterprise Legacy Modernization Factory API",
    description=(
        "Production-grade control plane orchestrating deterministic Code-to-Spec-to-Code "
        "transformation from Java EE / JSF monoliths to Java 21 / Spring Boot 3.5.x and Angular Microfrontends."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS for frontend access
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Exception Handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.exception("[Server] Unhandled exception processing %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "message": str(exc),
            "path": request.url.path,
        },
    )


# Router Aggregation
app.include_router(source.router)
app.include_router(graph.router)
app.include_router(pipeline.router)
app.include_router(hitl.router)
app.include_router(synthesis.router)


@app.get("/", tags=["System"])
def root_info() -> Dict[str, Any]:
    return {
        "service": "Enterprise Legacy Modernization Factory Control Plane",
        "version": "1.0.0",
        "status": "OPERATIONAL",
        "pipeline_stages": [
            "Step 1: Ingestion & LST Parsing",
            "Step 2: Neo4j Graph Storage & GraphRAG Slicing",
            "Step 3: Multi-Pass Cognitive Extraction Chain",
            "Step 4: HITL Review & Jira Gate Checkpoint",
            "Step 5: Catalog Reuse & Target Enterprise Synthesis",
        ],
        "docs_url": "/docs",
    }


@app.get("/api/health", tags=["System"])
def health_check() -> Dict[str, Any]:
    return {
        "status": "HEALTHY",
        "mock_mode": settings.MOCK_MODE,
        "mock_jira": settings.MOCK_JIRA,
    }


if __name__ == "__main__":
    uvicorn.run(
        "api.server:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
    )
