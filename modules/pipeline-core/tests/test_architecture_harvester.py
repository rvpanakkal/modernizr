"""
Comprehensive Verification Suite for Target Architecture Provider Subsystem.
===========================================================================
Tests:
- 4-Layer Harvester Engine (Layer 1 BOM, Layer 2 Topology, Layer 3 Exemplars, Layer 4 ArchUnit)
- Dynamic ArchUnit test class generator
- Architecture Profile Registry (persistence, active selection, SHA-256 stability)
- FastAPI Architecture Router endpoints
- Step 3 & Step 5 pipeline integration hooks & Step 5.5 conformance gate
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient

from api.server import app
from pipeline_core.architecture.archunit_templates import (
    get_standard_archunit_rules,
    render_archunit_test_class,
)
from pipeline_core.architecture.reference_repo_provider import ReferenceMicroserviceProvider
from pipeline_core.architecture.registry import ArchitectureProfileRegistry, get_architecture_registry
from pipeline_core.paths import artifacts_root
from pipeline_core.schemas.architecture import (
    ArchitectureProfile,
    CodePatternExemplar,
    LayeringPattern,
)
from pipeline_core.schemas.handoff import ExecutionStatus, StepHandoffReceipt
from pipeline_core.schemas.spec import BusinessRule, RuleType
from pipeline_core.workflows.target_synthesis_runner import TargetSynthesisRunner, run_conformance_gate


@pytest.fixture
def reference_repo_path() -> Path:
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    sample_dir = repo_root / "samples" / "reference-spring-boot-service"
    assert sample_dir.exists(), f"Reference sample dir missing: {sample_dir}"
    return sample_dir


@pytest.fixture
def temp_registry_dir() -> Generator[Path, None, None]:
    with tempfile.TemporaryDirectory(prefix="test_arch_reg_") as td:
        yield Path(td)


@pytest.fixture
def test_client() -> TestClient:
    return TestClient(app)


# =============================================================================
# 1. Four-Layer Harvester Engine Tests
# =============================================================================

def test_layer1_build_and_bom_harvesting(reference_repo_path: Path):
    harvester = ReferenceMicroserviceProvider()
    profile = harvester.build_profile(
        source_path_or_uri=str(reference_repo_path),
        profile_name="Enterprise Reference Banking Service",
        profile_id="arch-ref-banking-test",
    )

    assert "Java 21" in profile.target_runtime
    assert "Spring Boot 3.5.0" in profile.target_runtime
    assert "org.springframework.boot:spring-boot-starter-web" in profile.required_dependencies
    assert "org.springframework.boot:spring-boot-starter-validation" in profile.required_dependencies
    assert "com.tngtech.archunit:archunit-junit5" in profile.required_dependencies

    # Build file template must parameterize project coordinates
    assert "{{GROUP_ID}}" in profile.build_file_template
    assert "{{ARTIFACT_ID}}" in profile.build_file_template
    assert "{{PROJECT_NAME}}" in profile.build_file_template
    assert "<artifactId>spring-boot-starter-parent</artifactId>" in profile.build_file_template


def test_layer2_topology_detection(reference_repo_path: Path):
    harvester = ReferenceMicroserviceProvider()
    profile = harvester.build_profile(
        source_path_or_uri=str(reference_repo_path),
        profile_name="Enterprise Reference Banking Service",
    )

    assert profile.layering_pattern == LayeringPattern.CONTROLLER_SERVICE_REPOSITORY
    assert "com.enterprise" in profile.base_package_pattern


def test_layer3_code_exemplar_extraction(reference_repo_path: Path):
    harvester = ReferenceMicroserviceProvider()
    profile = harvester.build_profile(
        source_path_or_uri=str(reference_repo_path),
        profile_name="Enterprise Reference Banking Service",
    )

    pattern_names = [e.pattern_name for e in profile.exemplars]
    assert "RestController" in pattern_names
    assert "GlobalExceptionHandler" in pattern_names
    assert "Service" in pattern_names

    # Check GlobalExceptionHandler exemplar
    handler_ex = next(e for e in profile.exemplars if e.pattern_name == "GlobalExceptionHandler")
    assert "@RestControllerAdvice" in handler_ex.annotations_matched
    assert "ProblemDetail" in handler_ex.code_snippet
    assert "handleIllegalArgument" in handler_ex.code_snippet

    # Check RestController exemplar
    controller_ex = next(e for e in profile.exemplars if e.pattern_name == "RestController")
    assert "@RestController" in controller_ex.annotations_matched
    assert "SampleAccountController" in controller_ex.code_snippet


def test_layer4_archunit_rule_harvesting(reference_repo_path: Path):
    harvester = ReferenceMicroserviceProvider()
    profile = harvester.build_profile(
        source_path_or_uri=str(reference_repo_path),
        profile_name="Enterprise Reference Banking Service",
    )

    rule_methods = [r.test_method_name for r in profile.conformance_rules]
    # Discovered from ArchitectureSampleArchTest.java
    assert "controllers_must_not_access_repositories_directly" in rule_methods
    assert "services_must_be_annotated_with_service" in rule_methods
    # Enterprise baseline merged
    assert any("entities" in r.lower() or "controller" in r.lower() for r in rule_methods)


def test_profile_sha256_integrity_digest(reference_repo_path: Path):
    harvester = ReferenceMicroserviceProvider()
    profile1 = harvester.build_profile(
        source_path_or_uri=str(reference_repo_path),
        profile_name="Enterprise Reference Service",
        profile_id="arch-ref-sha256-test",
    )

    assert profile1.sha256_hash
    assert len(profile1.sha256_hash) == 64  # Valid SHA-256 hex string

    # Re-computing on exact same profile content produces identical digest
    computed = profile1.compute_sha256()
    assert computed == profile1.sha256_hash


# =============================================================================
# 2. ArchUnit Template & Test Generation Tests
# =============================================================================

def test_render_archunit_test_class(reference_repo_path: Path):
    harvester = ReferenceMicroserviceProvider()
    profile = harvester.build_profile(
        source_path_or_uri=str(reference_repo_path),
        profile_name="Enterprise Reference Service",
    )

    rendered_java = render_archunit_test_class(
        profile=profile,
        package_name="com.enterprise.modernization",
        scan_package="com.enterprise.modernization",
    )

    assert "package com.enterprise.modernization;" in rendered_java
    assert '@AnalyzeClasses(packages = "com.enterprise.modernization"' in rendered_java
    assert "public class ArchitectureConformanceTest {" in rendered_java
    assert "@ArchTest" in rendered_java
    assert "public static final ArchRule" in rendered_java
    assert profile.sha256_hash in rendered_java


# =============================================================================
# 3. Architecture Profile Registry Tests
# =============================================================================

def test_registry_save_get_and_active_selection(temp_registry_dir: Path, reference_repo_path: Path):
    registry = ArchitectureProfileRegistry(storage_dir=temp_registry_dir)
    harvester = ReferenceMicroserviceProvider()
    profile = harvester.build_profile(
        source_path_or_uri=str(reference_repo_path),
        profile_name="Registry Test Service",
        profile_id="arch-registry-test",
    )

    saved_path = registry.save_profile(profile)
    assert saved_path.exists()

    loaded = registry.get_profile("arch-registry-test")
    assert loaded is not None
    assert loaded.profile_id == "arch-registry-test"
    assert loaded.sha256_hash == profile.sha256_hash

    # Set and get active profile
    active = registry.set_active_profile("arch-registry-test")
    assert active.profile_id == "arch-registry-test"

    retrieved_active = registry.get_active_profile()
    assert retrieved_active.profile_id == "arch-registry-test"

    # List profiles
    all_profiles = registry.list_profiles()
    assert any(p.profile_id == "arch-registry-test" for p in all_profiles)


# =============================================================================
# 4. FastAPI Router Endpoints Tests
# =============================================================================

def test_api_list_profiles(test_client: TestClient):
    response = test_client.get("/api/architecture/profiles")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    first = data[0]
    assert "profile_id" in first
    assert "name" in first
    assert "sha256_hash" in first
    assert "is_active" in first


def test_api_harvest_reference_and_select_active(test_client: TestClient, reference_repo_path: Path):
    # Harvest
    payload = {
        "repo_path": str(reference_repo_path),
        "profile_name": "API Harvested Profile",
        "profile_id": "arch-api-harvest-test",
    }
    harvest_resp = test_client.post("/api/architecture/harvest-reference", json=payload)
    assert harvest_resp.status_code == 200
    profile_data = harvest_resp.json()
    assert profile_data["profile_id"] == "arch-api-harvest-test"
    assert profile_data["name"] == "API Harvested Profile"
    assert len(profile_data["exemplars"]) >= 2

    # Get single profile
    get_resp = test_client.get("/api/architecture/profiles/arch-api-harvest-test")
    assert get_resp.status_code == 200
    assert get_resp.json()["profile_id"] == "arch-api-harvest-test"

    # Select active
    select_resp = test_client.post(
        "/api/architecture/select-active",
        json={"profile_id": "arch-api-harvest-test"},
    )
    assert select_resp.status_code == 200
    assert select_resp.json()["status"] == "SUCCESS"
    assert select_resp.json()["active_profile_id"] == "arch-api-harvest-test"


# =============================================================================
# 5. Pipeline Integration Hooks & Conformance Gate Tests
# =============================================================================

def test_step3_spec_formatter_profile_hook(reference_repo_path: Path):
    from pipeline_core.agents.spec_formatter import SpecFormatterAgent

    harvester = ReferenceMicroserviceProvider()
    profile = harvester.build_profile(
        source_path_or_uri=str(reference_repo_path),
        profile_name="Step 3 Hook Profile",
    )

    rules = [
        BusinessRule(
            rule_id="BR-001",
            description="Positive transfer amount requirement",
            rule_type=RuleType.VALIDATION,
            condition="amount <= 0",
            action_or_outcome="Reject transfer",
            legacy_refs=["com.legacy.banking.service.TransferProcessingService.processTransfer"],
        )
    ]

    formatter = SpecFormatterAgent(architecture_profile=profile)
    spec = formatter.format_specification(
        business_rules=rules,
        entry_context={"sliceId": "com.legacy.banking.web.TransferManagedBean"},
    )

    assert "packageConvention" in spec.data_contract_fields
    assert "com.enterprise" in spec.data_contract_fields["packageConvention"]
    assert "errorDetailStandard" in spec.data_contract_fields


def test_step5_deterministic_scaffolding_and_conformance_gate(reference_repo_path: Path):
    from pipeline_core.agents.target_synthesizer import TargetSynthesizerAgent
    from pipeline_core.schemas.spec import GeneratedSpecification, BddScenario

    harvester = ReferenceMicroserviceProvider()
    profile = harvester.build_profile(
        source_path_or_uri=str(reference_repo_path),
        profile_name="Step 5 Conformance Profile",
    )

    spec = GeneratedSpecification(
        feature_name="Fund Transfer Management",
        domain="Banking Transfers",
        business_summary="Target enterprise transfer service",
        business_rules=[
            BusinessRule(
                rule_id="BR-001",
                description="Valid positive amount",
                rule_type=RuleType.VALIDATION,
                condition="amount > 0",
                action_or_outcome="Proceed with transfer",
                legacy_refs=["com.legacy.banking.TransferProcessingService.processTransfer"],
            )
        ],
        scenarios=[
            BddScenario(
                name="Successful transfer",
                given=["Active account ACC-1001 with balance $5000"],
                when="Transfer $250 to ACC-2002",
                then=["Transfer succeeds"],
                legacy_refs=["com.legacy.banking.TransferProcessingService.processTransfer"],
            )
        ],
        data_contract_fields={"amount": "BigDecimal"},
        legacy_traceability={
            "com.legacy.banking.TransferProcessingService.processTransfer": "Core transaction processing"
        },
        jira_story_id="MOD-999",
    )

    with tempfile.TemporaryDirectory(prefix="test_synthesis_out_") as out_dir:
        out_path = Path(out_dir)
        synthesizer = TargetSynthesizerAgent()
        result = synthesizer.synthesize(spec, output_root=out_path, architecture_profile=profile)

        # 1. Deterministic pom.xml scaffolding
        spring_pom = out_path / "spring_boot" / "pom.xml"
        assert spring_pom.exists()
        pom_content = spring_pom.read_text(encoding="utf-8")
        assert "com.enterprise.modernization" in pom_content
        assert "modernized-banking-transfers" in pom_content
        assert "spring-boot-starter-web" in pom_content

        # 2. ArchUnit conformance test file generated
        arch_test_file = (
            out_path
            / "spring_boot"
            / "src"
            / "test"
            / "java"
            / "com"
            / "enterprise"
            / "modernization"
            / "ArchitectureConformanceTest.java"
        )
        assert arch_test_file.exists()
        test_content = arch_test_file.read_text(encoding="utf-8")
        assert "@AnalyzeClasses" in test_content
        assert "@ArchTest" in test_content

        # 3. Conformance Gate Runner execution
        conformance_passed = run_conformance_gate(str(out_path))
        assert conformance_passed is True
