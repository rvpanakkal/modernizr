"""
Architecture Profile Registry.
==============================
Manages persistence, listing, retrieval, and active selection of
Architecture Profiles in artifacts/architecture_profiles/.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pipeline_core.architecture.archunit_templates import get_standard_archunit_rules
from pipeline_core.paths import architecture_profiles_dir, atomic_write_text
from pipeline_core.schemas.architecture import (
    ArchUnitRule,
    ArchitectureProfile,
    CodePatternExemplar,
    LayeringPattern,
)

log = logging.getLogger("ArchitectureRegistry")


class ArchitectureProfileRegistry:
    """
    Registry for managing persisted ArchitectureProfiles and the active profile pointer.
    """

    def __init__(self, storage_dir: Optional[Path] = None) -> None:
        self.storage_dir = storage_dir or architecture_profiles_dir()
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.active_pointer_file = self.storage_dir / "active_profile.json"

    def save_profile(self, profile: ArchitectureProfile) -> Path:
        """
        Persists an ArchitectureProfile to disk with integrity checksum.
        File path: artifacts/architecture_profiles/{profile_id}.json
        """
        # Ensure hash is up-to-date
        if not profile.sha256_hash:
            profile = profile.with_computed_hash()

        profile_path = self.storage_dir / f"{profile.profile_id}.json"
        content = profile.model_dump_json(indent=2)
        atomic_write_text(profile_path, content)
        log.info("[ArchitectureRegistry] Saved profile '%s' to %s", profile.profile_id, profile_path)
        return profile_path

    def get_profile(self, profile_id: str) -> Optional[ArchitectureProfile]:
        """Loads a profile by its unique ID."""
        profile_path = self.storage_dir / f"{profile_id}.json"
        if not profile_path.exists():
            return None
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return ArchitectureProfile.model_validate(data)
        except Exception as e:
            log.error("[ArchitectureRegistry] Failed to load profile %s: %s", profile_path, e)
            return None

    def list_profiles(self) -> List[ArchitectureProfile]:
        """Lists all stored profiles ordered by creation time descending."""
        profiles: List[ArchitectureProfile] = []
        for file in self.storage_dir.glob("*.json"):
            if file.name == "active_profile.json":
                continue
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                profiles.append(ArchitectureProfile.model_validate(data))
            except Exception as e:
                log.warning("[ArchitectureRegistry] Skipping unreadable profile %s: %s", file, e)

        # If empty, ensure default baseline is available
        if not profiles:
            default_profile = self._build_default_baseline_profile()
            self.save_profile(default_profile)
            profiles.append(default_profile)

        profiles.sort(key=lambda p: p.created_at, reverse=True)
        return profiles

    def set_active_profile(self, profile_id: str) -> ArchitectureProfile:
        """
        Designates a profile as the active profile for pipeline execution.
        """
        profile = self.get_profile(profile_id)
        if not profile:
            raise KeyError(f"Architecture profile '{profile_id}' not found in registry.")

        pointer_data = {
            "active_profile_id": profile.profile_id,
            "profile_name": profile.name,
            "sha256_hash": profile.sha256_hash,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        atomic_write_text(self.active_pointer_file, json.dumps(pointer_data, indent=2))
        log.info("[ArchitectureRegistry] Active profile set to: %s (%s)", profile.profile_id, profile.name)
        return profile

    def get_active_profile(self) -> ArchitectureProfile:
        """
        Retrieves the currently active ArchitectureProfile.
        Falls back to the most recently created profile, or generates a baseline profile.
        """
        if self.active_pointer_file.exists():
            try:
                with open(self.active_pointer_file, "r", encoding="utf-8") as f:
                    ptr = json.load(f)
                active_id = ptr.get("active_profile_id")
                if active_id:
                    profile = self.get_profile(active_id)
                    if profile:
                        return profile
            except Exception as e:
                log.warning("[ArchitectureRegistry] Error reading active_profile pointer: %s", e)

        # Fallback to first available profile or create default
        all_profiles = self.list_profiles()
        if all_profiles:
            active = all_profiles[0]
            self.set_active_profile(active.profile_id)
            return active

        default_profile = self._build_default_baseline_profile()
        self.save_profile(default_profile)
        self.set_active_profile(default_profile.profile_id)
        return default_profile

    def _build_default_baseline_profile(self) -> ArchitectureProfile:
        """Constructs an enterprise default Java 21 / Spring Boot 3.5.0 baseline profile."""
        now = datetime.now(timezone.utc)
        pom_template = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.5.0</version>
        <relativePath/>
    </parent>
    <groupId>{{GROUP_ID}}</groupId>
    <artifactId>{{ARTIFACT_ID}}</artifactId>
    <version>1.0.0-SNAPSHOT</version>
    <name>{{PROJECT_NAME}}</name>
    <description>Modernized Target Enterprise Microservice</description>

    <properties>
        <java.version>21</java.version>
        <archunit.version>1.3.0</archunit.version>
    </properties>

    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-actuator</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>com.tngtech.archunit</groupId>
            <artifactId>archunit-junit5</artifactId>
            <version>${archunit.version}</version>
            <scope>test</scope>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
            </plugin>
        </plugins>
    </build>
</project>"""

        exemplar = CodePatternExemplar(
            pattern_name="GlobalExceptionHandler",
            target_layer="controller",
            annotations_matched=["@RestControllerAdvice"],
            code_snippet="""package com.enterprise.modernization.web;

import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.net.URI;
import java.time.Instant;

@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(IllegalArgumentException.class)
    public ProblemDetail handleIllegalArgument(IllegalArgumentException ex) {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST, ex.getMessage());
        problem.setTitle("Validation Invariant Failure");
        problem.setType(URI.create("urn:problem:validation-error"));
        problem.setProperty("timestamp", Instant.now());
        return problem;
    }
}""",
            origin_file="src/main/java/com/enterprise/modernization/web/GlobalExceptionHandler.java",
        )

        profile = ArchitectureProfile(
            profile_id="arch-spring-boot-3.5-default",
            name="Spring Boot 3.5 Enterprise Microservice Baseline",
            target_runtime="Java 21 / Spring Boot 3.5.0",
            created_at=now,
            base_package_pattern="com.enterprise.{domain}.v2",
            layering_pattern=LayeringPattern.CONTROLLER_SERVICE_REPOSITORY,
            build_file_template=pom_template,
            required_dependencies=[
                "org.springframework.boot:spring-boot-starter-web",
                "org.springframework.boot:spring-boot-starter-validation",
                "org.springframework.boot:spring-boot-starter-actuator",
                "com.tngtech.archunit:archunit-junit5",
            ],
            exemplars=[exemplar],
            conformance_rules=get_standard_archunit_rules(),
            sha256_hash="",
        )
        return profile.with_computed_hash()


# Module-level singleton
_registry_instance: Optional[ArchitectureProfileRegistry] = None


def get_architecture_registry() -> ArchitectureProfileRegistry:
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = ArchitectureProfileRegistry()
    return _registry_instance
