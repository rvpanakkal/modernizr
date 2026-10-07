"""
Tests for Modernization Factory FastAPI endpoints.
"""

from fastapi.testclient import TestClient
from api.server import app

client = TestClient(app)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "HEALTHY"


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Enterprise Legacy Modernization Factory Control Plane"


def test_source_upload():
    response = client.post(
        "/api/source/upload",
        data={
            "git_url": "https://github.com/enterprise/legacy-banking-monolith.git",
            "jdk_version": "8",
            "framework_profile": "JAVA_EE_6_JSF",
            "classpath_strategy": "AI_SYNTHETIC_STUBS",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["monolith_id"] == "legacy-banking-monolith"
    assert data["classes_count"] > 0
    assert len(data["sha256_digest"]) == 64


def test_graph_entrypoints():
    response = client.get("/api/graph/entrypoints")
    assert response.status_code == 200
    items = response.json()
    assert len(items) >= 1
    assert any("TransferManagedBean" in item["simple_name"] for item in items)


def test_graph_slice():
    response = client.post(
        "/api/graph/slice",
        json={"entry_fqn": "com.legacy.banking.web.TransferManagedBean", "max_depth": 5},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["slice_id"] == "com.legacy.banking.web.TransferManagedBean"
    assert len(data["nodes"]) >= 3
    assert len(data["edges"]) >= 2
    assert "public class TransferProcessingService" in data["legacy_source"]
    assert data["within_budget"] is True


def test_graph_slice_loan_module():
    response = client.post(
        "/api/graph/slice",
        json={"entry_fqn": "com.legacy.banking.web.LoanApplicationManagedBean", "max_depth": 5},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["slice_id"] == "com.legacy.banking.web.LoanApplicationManagedBean"
    assert len(data["nodes"]) >= 5
    assert len(data["edges"]) >= 4
    assert "LoanProcessingService" in data["legacy_source"]
    assert data["within_budget"] is True


def test_graph_slice_auth_module():
    response = client.post(
        "/api/graph/slice",
        json={"entry_fqn": "com.legacy.banking.web.AuthenticationManagedBean", "max_depth": 5},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["slice_id"] == "com.legacy.banking.web.AuthenticationManagedBean"
    assert len(data["nodes"]) >= 3
    assert len(data["edges"]) >= 2
    assert "AzureAdAuthenticationService" in data["legacy_source"]
    assert data["within_budget"] is True


def test_pipeline_runs_and_spec_lifecycle():
    # 1. Start Run
    run_resp = client.post(
        "/api/pipeline/runs",
        json={"entry_fqn": "com.legacy.banking.web.TransferManagedBean", "tracker_type": "jira"},
    )
    assert run_resp.status_code == 202
    run_data = run_resp.json()
    run_id = run_data["run_id"]
    assert run_id.startswith("run-")

    # 2. Get Spec for Review
    spec_resp = client.get(f"/api/spec/{run_id}")
    assert spec_resp.status_code == 200
    spec_data = spec_resp.json()
    assert spec_data["jira_story_id"] == "MOD-101"
    assert len(spec_data["spec"]["business_rules"]) >= 4
    assert len(spec_data["spec_sha256"]) == 64

    # 3. Hitl Revise
    import os
    if not os.getenv("ANTHROPIC_API_KEY"):
        from unittest.mock import AsyncMock, patch
        from pipeline_core.schemas.spec import GeneratedSpecification
        mock_spec = GeneratedSpecification.model_validate(spec_data["spec"])
        with patch("api.routers.hitl.generate_targeted_revision", new=AsyncMock(return_value=mock_spec)):
            revise_resp = client.post(
                "/api/hitl/revise",
                json={"run_id": run_id, "feedback": "Enforce high-risk transaction flag for transfers > $10,000", "target_pass": 2},
            )
    else:
        revise_resp = client.post(
            "/api/hitl/revise",
            json={"run_id": run_id, "feedback": "Enforce high-risk transaction flag for transfers > $10,000", "target_pass": 2},
        )
    assert revise_resp.status_code == 200
    revised_data = revise_resp.json()
    assert revised_data["status"] == "REVISED"

    # 4. Hitl Approve
    approve_resp = client.post(
        "/api/hitl/approve",
        json={"run_id": run_id, "approved_by": "Senior Architect", "comments": "Approved for synthesis"},
    )
    assert approve_resp.status_code == 200
    approve_data = approve_resp.json()
    assert approve_data["status"] == "APPROVED"
    assert approve_data["jira_status"] == "APPROVED_FOR_SYNTHESIS"

    # 5. Catalog Match
    catalog_resp = client.get("/api/catalog/match?domain=PAYMENT_PROCESSING")
    assert catalog_resp.status_code == 200
    cat_data = catalog_resp.json()
    assert cat_data["best_match"]["service_id"] == "ms-payment-clearing"
    assert cat_data["best_match"]["similarity_score"] >= 0.90

    # 6. Target Synthesis Generate
    synth_resp = client.post(
        "/api/synthesis/generate",
        json={"run_id": run_id, "target_stack": "spring_boot_3_5"},
    )
    assert synth_resp.status_code == 200
    synth_data = synth_resp.json()
    assert synth_data["status"] == "COMPLETED"
    assert len(synth_data["files"]) >= 6
    file_names = [f["filename"] for f in synth_data["files"]]
    assert "TransferRequest.java" in file_names
    assert "TransferProcessingService.java" in file_names
    assert "transfer.component.ts" in file_names
    assert "openapi_mod101.yaml" in file_names
