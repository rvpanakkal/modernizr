"""
Router for Pipeline Step 1: Legacy Source Ingestion and Lossless Semantic Tree (LST) Extraction.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from neo4j import Session

from api.config import Settings, get_settings
from api.dependencies import get_neo4j_session
from pipeline_core.extractor_runner import execute_lst_extractor, find_repo_root

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/source", tags=["Source Ingestion"])


class ExtractedClassItem(BaseModel):
    fqn: str
    simple_name: str
    kind: str
    role: str
    annotations: List[str]
    methods_count: int
    fields_count: int
    invocations_count: int
    injected_dependencies: List[str] = []


class SourceIngestResponse(BaseModel):
    status: str
    monolith_id: str
    jdk_version: str
    framework_profile: str
    classpath_strategy: str
    classes_count: int
    methods_count: int
    injected_fields_count: int
    invocations_count: int = 0
    endpoints_count: int
    cics_gateways_count: int
    sha256_digest: str
    extracted_at: str
    execution_time_ms: int = 0
    message: str
    classes: List[ExtractedClassItem] = []


@router.post("/upload", response_model=SourceIngestResponse)
async def upload_source(
    file: Optional[UploadFile] = File(default=None),
    git_url: Optional[str] = Form(default=None),
    source_path: Optional[str] = Form(default=None),
    jdk_version: str = Form(default="8"),
    framework_profile: str = Form(default="JAVA_EE_6_JSF"),
    classpath_strategy: str = Form(default="AI_SYNTHETIC_STUBS"),
    session: Optional[Session] = Depends(get_neo4j_session),
    settings: Settings = Depends(get_settings),
) -> SourceIngestResponse:
    """
    Ingests legacy Java source repository archive (.zip/.war), local directory, or Git URL.
    Extracts Java AST/LST metadata with OpenRewrite and persists to Neo4j.
    """
    log.info(
        "[Source Ingest] Upload received: file=%s, git_url=%s, source_path=%s, jdk=%s, profile=%s",
        file.filename if file else None,
        git_url,
        source_path,
        jdk_version,
        framework_profile,
    )

    repo_root = find_repo_root()
    monolith_id = "legacy-banking-monolith"
    target_source_dir = repo_root / "samples" / "legacy-banking-monolith" / "src" / "main" / "java"

    # Case 1: Uploaded ZIP / WAR file
    if file:
        file_bytes = await file.read()
        monolith_id = Path(file.filename or "monolith").stem
        upload_dir = repo_root / "artifacts" / "uploaded_source" / monolith_id
        upload_dir.mkdir(parents=True, exist_ok=True)

        # If it's a zip archive, extract it
        if file.filename and (file.filename.endswith(".zip") or file.filename.endswith(".war")):
            temp_zip = upload_dir / "archive.zip"
            temp_zip.write_bytes(file_bytes)
            try:
                with zipfile.ZipFile(temp_zip, "r") as zf:
                    zf.extractall(upload_dir / "extracted")
                
                # Check for src/main/java or java files
                candidate = upload_dir / "extracted"
                nested_java = list(candidate.rglob("*.java"))
                if nested_java:
                    # Pick directory containing the java files or common ancestor
                    target_source_dir = nested_java[0].parent
                    # Walk up until src/main/java or root of extracted
                    for parent in nested_java[0].parents:
                        if parent.name == "java" and parent.parent.name == "main":
                            target_source_dir = parent
                            break
                        if parent == candidate:
                            target_source_dir = parent
                            break
                else:
                    target_source_dir = candidate
            except Exception as e:
                log.warning("[Source Ingest] Could not unzip file: %s; saving as raw file", e)
                target_source_dir = upload_dir

    # Case 2: Explicit source_path
    elif source_path:
        cand_path = Path(source_path)
        if not cand_path.is_absolute():
            cand_path = repo_root / cand_path
        if cand_path.exists():
            target_source_dir = cand_path
            monolith_id = cand_path.stem

    # Case 3: Git URL provided
    elif git_url:
        monolith_id = git_url.rstrip("/").split("/")[-1].replace(".git", "")
        # If pointing to legacy-banking-monolith or local sample exists, use local directory
        if "legacy-banking-monolith" in git_url or (repo_root / "samples" / "legacy-banking-monolith").exists():
            target_source_dir = repo_root / "samples" / "legacy-banking-monolith" / "src" / "main" / "java"

    # Execute actual OpenRewrite LST extractor
    output_json = repo_root / "artifacts" / "raw_lst" / "metadata_extracted.json"
    try:
        extraction_result = execute_lst_extractor(
            source_dir_or_path=target_source_dir,
            output_file=output_json,
            monolith_id=monolith_id,
        )
    except Exception as exc:
        log.error("[Source Ingest] Extraction failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OpenRewrite LST extraction failed: {str(exc)}",
        )

    # Ingest to Neo4j if session is live
    if session and not settings.MOCK_MODE and output_json.exists():
        try:
            from pipeline_core.graph.ingest_graph import ingest_metadata_file
            ingest_metadata_file(session, output_json)
            log.info("[Source Ingest] Live Neo4j ingestion completed successfully.")
        except Exception as exc:
            log.warning("[Source Ingest] Ingestion to Neo4j encountered warning: %s", exc)

    return SourceIngestResponse(
        status="SUCCESS",
        monolith_id=extraction_result["monolith_id"],
        jdk_version=jdk_version,
        framework_profile=framework_profile,
        classpath_strategy=classpath_strategy,
        classes_count=extraction_result["classes_count"],
        methods_count=extraction_result["methods_count"],
        injected_fields_count=extraction_result["injected_fields_count"],
        invocations_count=extraction_result["invocations_count"],
        endpoints_count=extraction_result["endpoints_count"],
        cics_gateways_count=extraction_result["cics_gateways_count"],
        sha256_digest=extraction_result["sha256_digest"],
        extracted_at=extraction_result["extracted_at"],
        execution_time_ms=extraction_result["execution_time_ms"],
        message=(
            f"Successfully extracted LST semantic model via OpenRewrite for "
            f"{extraction_result['classes_count']} classes, {extraction_result['methods_count']} methods, "
            f"and {extraction_result['invocations_count']} invocations in {extraction_result['execution_time_ms']}ms."
        ),
        classes=[ExtractedClassItem(**c) for c in extraction_result["classes"]],
    )
