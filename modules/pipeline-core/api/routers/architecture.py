"""
FastAPI Router for Target Architecture Profiles and Harvester.
==============================================================
Provides endpoints for:
- Ingesting and harvesting enterprise reference microservices across 4 structural layers
- Listing and inspecting canonical ArchitectureProfiles
- Selecting active ArchitectureProfile for pipeline runs
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field

from pipeline_core.architecture import (
    ReferenceMicroserviceProvider,
    get_architecture_registry,
)
from pipeline_core.schemas.architecture import ArchitectureProfile

log = logging.getLogger("ArchitectureRouter")

router = APIRouter(prefix="/api/architecture", tags=["Target Architecture"])


class HarvestReferenceRequest(BaseModel):
    repo_path: str = Field(..., description="Path to reference repository on filesystem")
    profile_name: str = Field(..., description="Display name for the harvested profile")
    profile_id: Optional[str] = Field(default=None, description="Optional custom profile slug")


class SelectActiveProfileRequest(BaseModel):
    profile_id: str = Field(..., description="Profile slug to activate")


class ProfileSummary(BaseModel):
    profile_id: str
    name: str
    target_runtime: str
    layering_pattern: str
    base_package_pattern: str
    created_at: str
    sha256_hash: str
    exemplars_count: int
    conformance_rules_count: int
    is_active: bool


@router.post("/harvest-reference", response_model=ArchitectureProfile)
async def harvest_reference(
    request: Request,
    file: Optional[UploadFile] = File(None),
    profile_name: Optional[str] = Form(None),
    repo_path: Optional[str] = Form(None),
    profile_id: Optional[str] = Form(None),
) -> ArchitectureProfile:
    """
    Ingests a reference enterprise microservice (via filesystem path or zip archive)
    and harvests an immutable canonical ArchitectureProfile across 4 structural layers.
    """
    content_type = request.headers.get("content-type", "").lower()
    harvester = ReferenceMicroserviceProvider()
    registry = get_architecture_registry()

    target_path_str: str = ""
    target_name: str = ""
    target_id: Optional[str] = None
    cleanup_temp_dir: Optional[str] = None

    try:
        if "application/json" in content_type:
            body = await request.json()
            target_path_str = body.get("repo_path", "")
            target_name = body.get("profile_name", "")
            target_id = body.get("profile_id")
            if not target_path_str or not target_name:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Both 'repo_path' and 'profile_name' are required in JSON body.",
                )
        elif file is not None and file.filename:
            # Multipart upload
            target_name = profile_name or Path(file.filename).stem
            target_id = profile_id
            temp_dir = tempfile.mkdtemp(prefix="upload_ref_")
            cleanup_temp_dir = temp_dir
            zip_dest = Path(temp_dir) / file.filename
            with open(zip_dest, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            target_path_str = str(zip_dest)
        elif repo_path:
            target_path_str = repo_path
            target_name = profile_name or Path(repo_path).name
            target_id = profile_id
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Must provide either JSON payload with 'repo_path' or multipart zip 'file'.",
            )

        log.info("[ArchitectureRouter] Harvesting reference from: %s (Name: %s)", target_path_str, target_name)
        profile = harvester.build_profile(
            source_path_or_uri=target_path_str,
            profile_name=target_name,
            profile_id=target_id,
        )

        registry.save_profile(profile)
        # Automatically make freshly harvested profile active
        registry.set_active_profile(profile.profile_id)
        return profile

    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        log.exception("[ArchitectureRouter] Harvesting failed: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Harvesting failed: {e}")
    finally:
        if cleanup_temp_dir and os.path.exists(cleanup_temp_dir):
            try:
                shutil.rmtree(cleanup_temp_dir, ignore_errors=True)
            except Exception:
                pass


@router.get("/profiles", response_model=List[ProfileSummary])
def list_profiles() -> List[ProfileSummary]:
    """
    Lists all available ArchitectureProfiles with summary metadata and active status.
    """
    registry = get_architecture_registry()
    profiles = registry.list_profiles()
    active_profile = registry.get_active_profile()
    active_id = active_profile.profile_id if active_profile else ""

    summaries = []
    for p in profiles:
        summaries.append(
            ProfileSummary(
                profile_id=p.profile_id,
                name=p.name,
                target_runtime=p.target_runtime,
                layering_pattern=p.layering_pattern.value,
                base_package_pattern=p.base_package_pattern,
                created_at=p.created_at.isoformat(),
                sha256_hash=p.sha256_hash,
                exemplars_count=len(p.exemplars),
                conformance_rules_count=len(p.conformance_rules),
                is_active=(p.profile_id == active_id),
            )
        )
    return summaries


@router.get("/profiles/{profile_id}", response_model=ArchitectureProfile)
def get_profile(profile_id: str) -> ArchitectureProfile:
    """
    Returns the complete ArchitectureProfile including BOM, exemplars, and ArchUnit rules.
    """
    registry = get_architecture_registry()
    profile = registry.get_profile(profile_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Architecture profile '{profile_id}' not found.",
        )
    return profile


@router.post("/select-active")
def select_active_profile(request: SelectActiveProfileRequest) -> Dict[str, Any]:
    """
    Designates the active ArchitectureProfile for pipeline runs.
    """
    registry = get_architecture_registry()
    try:
        active = registry.set_active_profile(request.profile_id)
        return {
            "status": "SUCCESS",
            "active_profile_id": active.profile_id,
            "profile_name": active.name,
            "sha256_hash": active.sha256_hash,
        }
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
