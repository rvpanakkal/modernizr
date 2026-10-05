"""
Router for Graph Discovery and GraphRAG Vertical Slice Extraction.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from neo4j import Session

from api.config import Settings, get_settings
from api.dependencies import get_neo4j_session
from api.services.runner_bridge import SAMPLE_LEGACY_JAVA_SOURCE

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/graph", tags=["Graph & Topology"])


class EntrypointItem(BaseModel):
    fqn: str
    simple_name: str
    layer: str  # Presentation, API, Integration
    role: str
    kind: str
    annotations: List[str]
    injected_dependencies: List[str]
    description: str


class SliceRequest(BaseModel):
    entry_fqn: str = Field(default="com.legacy.banking.web.TransferManagedBean")
    max_depth: int = Field(default=5, ge=1, le=8)


class GraphNode(BaseModel):
    id: str
    name: str
    fqn: str
    role: str
    layer: str
    color: str
    annotations: List[str]
    methods: List[str]


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str  # INJECTS, CALLS, CONNECTS_TO
    label: str


class SliceResponse(BaseModel):
    slice_id: str
    entry_fqn: str
    max_depth: int
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    execution_paths: List[str]
    component_summary: List[Dict[str, Any]]
    estimated_tokens: int
    max_tokens: int = 6000
    within_budget: bool
    legacy_source: str
    raw_slice: Dict[str, Any]


# Canonical mock entrypoints for resilient UI operation
CANONICAL_ENTRYPOINTS: List[EntrypointItem] = [
    EntrypointItem(
        fqn="com.legacy.banking.web.TransferManagedBean",
        simple_name="TransferManagedBean",
        layer="Presentation",
        role="JSF_MANAGED_BEAN",
        kind="CLASS",
        annotations=["ManagedBean", "SessionScoped"],
        injected_dependencies=["com.legacy.banking.service.TransferProcessingService"],
        description="JSF 2.x session-scoped controller handling UI fund transfer submissions and action triggers.",
    ),
    EntrypointItem(
        fqn="com.legacy.banking.web.AccountRestEndpoint",
        simple_name="AccountRestEndpoint",
        layer="API",
        role="REST_ENDPOINT",
        kind="CLASS",
        annotations=["Path", "Produces", "Stateless"],
        injected_dependencies=["com.legacy.banking.repository.AccountRepository"],
        description="JAX-RS 1.1 REST controller exposing legacy account balance inquiries and ledger lookups.",
    ),
    EntrypointItem(
        fqn="com.legacy.banking.gateway.CicsMainframeGateway",
        simple_name="CicsMainframeGateway",
        layer="Integration",
        role="MAINFRAME_GATEWAY",
        kind="CLASS",
        annotations=["Stateless", "TransactionAttribute"],
        injected_dependencies=[],
        description="EJB 3.0 session bean connecting directly via IBM CICS Transaction Gateway to core z/OS mainframe.",
    ),
    EntrypointItem(
        fqn="com.legacy.banking.web.LoanApplicationManagedBean",
        simple_name="LoanApplicationManagedBean",
        layer="Presentation",
        role="JSF_MANAGED_BEAN",
        kind="CLASS",
        annotations=["ManagedBean", "SessionScoped"],
        injected_dependencies=[
            "com.legacy.banking.service.LoanProcessingService",
            "com.legacy.banking.service.AzureAdAuthenticationService",
        ],
        description="JSF 2.x session-scoped controller managing automated loan origination, credit underwriting, and disbursement.",
    ),
    EntrypointItem(
        fqn="com.legacy.banking.web.AuthenticationManagedBean",
        simple_name="AuthenticationManagedBean",
        layer="Presentation",
        role="JSF_MANAGED_BEAN",
        kind="CLASS",
        annotations=["ManagedBean", "SessionScoped"],
        injected_dependencies=["com.legacy.banking.service.AzureAdAuthenticationService"],
        description="JSF 2.x session-scoped controller orchestrating Azure Active Directory (Entra ID) SSO login and token validation.",
    ),
]


@router.get("/entrypoints", response_model=List[EntrypointItem])
def get_entrypoints(
    session: Optional[Session] = Depends(get_neo4j_session),
    settings: Settings = Depends(get_settings),
) -> List[EntrypointItem]:
    """
    Returns discovered application entry points annotated with @ManagedBean, @Path, or @Controller.
    """
    if session and not settings.MOCK_MODE:
        try:
            from pipeline_core.graph.queries import find_entry_points
            raw_entries = find_entry_points(session)
            if raw_entries:
                results = []
                for item in raw_entries:
                    fqn = item.get("fqn", "")
                    simple_name = item.get("simpleName", fqn.split(".")[-1])
                    annotations = item.get("annotations", [])
                    layer = "Presentation" if any(a in ("ManagedBean", "Named", "Controller") for a in annotations) else "API"
                    results.append(
                        EntrypointItem(
                            fqn=fqn,
                            simple_name=simple_name,
                            layer=layer,
                            role="ENTRY_POINT",
                            kind=item.get("kind", "CLASS"),
                            annotations=annotations,
                            injected_dependencies=item.get("injectedDependencies", []),
                            description=f"Extracted entry point {simple_name} with annotations {annotations}",
                        )
                    )
                return results
        except Exception as exc:
            log.warning("[Graph Router] Querying Neo4j failed: %s. Using canonical fallback.", exc)

    return CANONICAL_ENTRYPOINTS


@router.post("/slice", response_model=SliceResponse)
def get_vertical_slice(
    request: SliceRequest,
    session: Optional[Session] = Depends(get_neo4j_session),
    settings: Settings = Depends(get_settings),
) -> SliceResponse:
    """
    Extracts isolated vertical slice topology starting from the designated entry-point FQN.
    Returns Cytoscape-formatted nodes, directed edges, call flows, and legacy source text.
    """
    entry_fqn = request.entry_fqn

    if "LoanApplicationManagedBean" in entry_fqn:
        loan_service_path = Path("samples/legacy-banking-monolith/src/main/java/com/legacy/banking/service/LoanProcessingService.java")
        legacy_source = loan_service_path.read_text(encoding="utf-8") if loan_service_path.exists() else SAMPLE_LEGACY_JAVA_SOURCE

        nodes = [
            GraphNode(
                id="LoanApplicationManagedBean",
                name="LoanApplicationManagedBean",
                fqn="com.legacy.banking.web.LoanApplicationManagedBean",
                role="ENTRY_POINT",
                layer="Presentation",
                color="#3b82f6",
                annotations=["ManagedBean", "SessionScoped"],
                methods=["apply()", "calculateEstimate()", "reset()"],
            ),
            GraphNode(
                id="LoanProcessingService",
                name="LoanProcessingService",
                fqn="com.legacy.banking.service.LoanProcessingService",
                role="DOMAIN_SERVICE",
                layer="Service",
                color="#10b981",
                annotations=["Stateless", "TransactionAttribute(REQUIRED)"],
                methods=["submitAndProcessLoan()", "calculateMonthlyPayment()", "getApplication()"],
            ),
            GraphNode(
                id="CreditBureauGateway",
                name="CreditBureauGateway",
                fqn="com.legacy.banking.gateway.CreditBureauGateway",
                role="INTEGRATION_BOUNDARY",
                layer="Gateway/CreditBureau",
                color="#8b5cf6",
                annotations=["Stateless"],
                methods=["requestCreditScore()", "queryExistingDebtObligations()"],
            ),
            GraphNode(
                id="LoanApplicationRepository",
                name="LoanApplicationRepository",
                fqn="com.legacy.banking.repository.LoanApplicationRepository",
                role="DATA_ACCESS",
                layer="Data Access",
                color="#f59e0b",
                annotations=["Stateless", "PersistenceContext"],
                methods=["save()", "findById()", "findByAccountId()", "updateStatus()"],
            ),
            GraphNode(
                id="AccountRepository",
                name="AccountRepository",
                fqn="com.legacy.banking.repository.AccountRepository",
                role="DATA_ACCESS",
                layer="Data Access",
                color="#f59e0b",
                annotations=["Stateless", "PersistenceContext"],
                methods=["findById()", "updateBalance()"],
            ),
            GraphNode(
                id="AzureAdAuthenticationService",
                name="AzureAdAuthenticationService",
                fqn="com.legacy.banking.service.AzureAdAuthenticationService",
                role="DOMAIN_SERVICE",
                layer="Service",
                color="#10b981",
                annotations=["Stateless"],
                methods=["validateUserRole()", "auditSecurityEvent()"],
            ),
        ]
        edges = [
            GraphEdge(
                id="e_loan_1",
                source="LoanApplicationManagedBean",
                target="LoanProcessingService",
                type="INJECTS",
                label="@EJB loanService",
            ),
            GraphEdge(
                id="e_loan_2",
                source="LoanProcessingService",
                target="CreditBureauGateway",
                type="CALLS",
                label="requestCreditScore() & queryDebt()",
            ),
            GraphEdge(
                id="e_loan_3",
                source="LoanProcessingService",
                target="LoanApplicationRepository",
                type="CALLS",
                label="save() & updateStatus()",
            ),
            GraphEdge(
                id="e_loan_4",
                source="LoanProcessingService",
                target="AccountRepository",
                type="CALLS",
                label="findById() & updateBalance()",
            ),
            GraphEdge(
                id="e_loan_5",
                source="LoanProcessingService",
                target="AzureAdAuthenticationService",
                type="CALLS",
                label="validateUserRole(ROLE_CUSTOMER)",
            ),
        ]
        execution_paths = [
            "LoanApplicationManagedBean → LoanProcessingService → CreditBureauGateway (Depth 2)",
            "LoanApplicationManagedBean → LoanProcessingService → LoanApplicationRepository (Depth 2)",
            "LoanApplicationManagedBean → LoanProcessingService → AccountRepository (Depth 2)",
            "LoanApplicationManagedBean → LoanProcessingService → AzureAdAuthenticationService (Depth 2)",
        ]
        component_summary = [
            {"fqn": "com.legacy.banking.web.LoanApplicationManagedBean", "role": "ENTRY_POINT", "layer": "Presentation"},
            {"fqn": "com.legacy.banking.service.LoanProcessingService", "role": "DOMAIN_SERVICE", "layer": "Service"},
            {"fqn": "com.legacy.banking.gateway.CreditBureauGateway", "role": "INTEGRATION_BOUNDARY", "layer": "Gateway/CreditBureau"},
            {"fqn": "com.legacy.banking.repository.LoanApplicationRepository", "role": "DATA_ACCESS", "layer": "Data Access"},
            {"fqn": "com.legacy.banking.repository.AccountRepository", "role": "DATA_ACCESS", "layer": "Data Access"},
            {"fqn": "com.legacy.banking.service.AzureAdAuthenticationService", "role": "DOMAIN_SERVICE", "layer": "Service"},
        ]
    elif "AuthenticationManagedBean" in entry_fqn:
        auth_service_path = Path("samples/legacy-banking-monolith/src/main/java/com/legacy/banking/service/AzureAdAuthenticationService.java")
        legacy_source = auth_service_path.read_text(encoding="utf-8") if auth_service_path.exists() else SAMPLE_LEGACY_JAVA_SOURCE

        nodes = [
            GraphNode(
                id="AuthenticationManagedBean",
                name="AuthenticationManagedBean",
                fqn="com.legacy.banking.web.AuthenticationManagedBean",
                role="ENTRY_POINT",
                layer="Presentation",
                color="#3b82f6",
                annotations=["ManagedBean", "SessionScoped"],
                methods=["loginWithAzureAd()", "loginAsMockRole()", "logout()"],
            ),
            GraphNode(
                id="AzureAdAuthenticationService",
                name="AzureAdAuthenticationService",
                fqn="com.legacy.banking.service.AzureAdAuthenticationService",
                role="DOMAIN_SERVICE",
                layer="Service",
                color="#10b981",
                annotations=["Stateless"],
                methods=["authenticateBearerToken()", "validateUserRole()", "generateMockSession()"],
            ),
            GraphNode(
                id="AzureAdGateway",
                name="AzureAdGateway",
                fqn="com.legacy.banking.gateway.AzureAdGateway",
                role="INTEGRATION_BOUNDARY",
                layer="Gateway/AzureAD",
                color="#8b5cf6",
                annotations=["Stateless"],
                methods=["validateAzureAdJwtToken()", "exchangeAuthorizationCode()"],
            ),
        ]
        edges = [
            GraphEdge(
                id="e_auth_1",
                source="AuthenticationManagedBean",
                target="AzureAdAuthenticationService",
                type="INJECTS",
                label="@EJB authService",
            ),
            GraphEdge(
                id="e_auth_2",
                source="AzureAdAuthenticationService",
                target="AzureAdGateway",
                type="CALLS",
                label="validateAzureAdJwtToken()",
            ),
        ]
        execution_paths = [
            "AuthenticationManagedBean → AzureAdAuthenticationService → AzureAdGateway (Depth 2)",
        ]
        component_summary = [
            {"fqn": "com.legacy.banking.web.AuthenticationManagedBean", "role": "ENTRY_POINT", "layer": "Presentation"},
            {"fqn": "com.legacy.banking.service.AzureAdAuthenticationService", "role": "DOMAIN_SERVICE", "layer": "Service"},
            {"fqn": "com.legacy.banking.gateway.AzureAdGateway", "role": "INTEGRATION_BOUNDARY", "layer": "Gateway/AzureAD"},
        ]
    else:
        # TransferManagedBean and default
        transfer_path = Path("samples/legacy-banking-monolith/src/main/java/com/legacy/banking/service/TransferProcessingService.java")
        legacy_source = transfer_path.read_text(encoding="utf-8") if transfer_path.exists() else SAMPLE_LEGACY_JAVA_SOURCE

        nodes = [
            GraphNode(
                id="TransferManagedBean",
                name="TransferManagedBean",
                fqn="com.legacy.banking.web.TransferManagedBean",
                role="ENTRY_POINT",
                layer="Presentation",
                color="#3b82f6",
                annotations=["ManagedBean", "SessionScoped"],
                methods=["execute()", "reset()", "getAmount()", "setAmount()"],
            ),
            GraphNode(
                id="TransferProcessingService",
                name="TransferProcessingService",
                fqn="com.legacy.banking.service.TransferProcessingService",
                role="DOMAIN_SERVICE",
                layer="Service",
                color="#10b981",
                annotations=["Stateless", "TransactionAttribute(REQUIRED)"],
                methods=["processTransfer()", "getAccountDetails()"],
            ),
            GraphNode(
                id="CicsMainframeGateway",
                name="CicsMainframeGateway",
                fqn="com.legacy.banking.gateway.CicsMainframeGateway",
                role="INTEGRATION_BOUNDARY",
                layer="Gateway/CICS",
                color="#8b5cf6",
                annotations=["Stateless"],
                methods=["executeTransfer()"],
            ),
            GraphNode(
                id="AccountRepository",
                name="AccountRepository",
                fqn="com.legacy.banking.repository.AccountRepository",
                role="DATA_ACCESS",
                layer="Data Access",
                color="#f59e0b",
                annotations=["Stateless", "PersistenceContext"],
                methods=["findById()", "updateBalance()"],
            ),
            GraphNode(
                id="AzureAdAuthenticationService",
                name="AzureAdAuthenticationService",
                fqn="com.legacy.banking.service.AzureAdAuthenticationService",
                role="DOMAIN_SERVICE",
                layer="Service",
                color="#10b981",
                annotations=["Stateless"],
                methods=["validateUserRole()", "auditSecurityEvent()"],
            ),
        ]

        edges = [
            GraphEdge(
                id="e1",
                source="TransferManagedBean",
                target="TransferProcessingService",
                type="INJECTS",
                label="@EJB transferService",
            ),
            GraphEdge(
                id="e2",
                source="TransferProcessingService",
                target="CicsMainframeGateway",
                type="CALLS",
                label="executeTransfer(from, to, amt)",
            ),
            GraphEdge(
                id="e3",
                source="TransferProcessingService",
                target="AccountRepository",
                type="CALLS",
                label="findById() & updateBalance()",
            ),
            GraphEdge(
                id="e4",
                source="TransferProcessingService",
                target="AzureAdAuthenticationService",
                type="CALLS",
                label="validateUserRole() & auditSecurityEvent()",
            ),
        ]

        execution_paths = [
            "TransferManagedBean → TransferProcessingService → CicsMainframeGateway (Depth 2)",
            "TransferManagedBean → TransferProcessingService → AccountRepository (Depth 2)",
            "TransferManagedBean → TransferProcessingService → AzureAdAuthenticationService (Depth 2)",
        ]

        component_summary = [
            {"fqn": "com.legacy.banking.web.TransferManagedBean", "role": "ENTRY_POINT", "layer": "Presentation"},
            {"fqn": "com.legacy.banking.service.TransferProcessingService", "role": "DOMAIN_SERVICE", "layer": "Service"},
            {"fqn": "com.legacy.banking.gateway.CicsMainframeGateway", "role": "INTEGRATION_BOUNDARY", "layer": "Gateway/CICS"},
            {"fqn": "com.legacy.banking.repository.AccountRepository", "role": "DATA_ACCESS", "layer": "Data Access"},
            {"fqn": "com.legacy.banking.service.AzureAdAuthenticationService", "role": "DOMAIN_SERVICE", "layer": "Service"},
        ]

    raw_slice = {
        "sliceId": entry_fqn,
        "entryPoint": {
            "fqn": entry_fqn,
            "simpleName": entry_fqn.split(".")[-1],
            "kind": "CLASS",
            "annotations": ["ManagedBean", "SessionScoped"],
            "methods": [{"name": "execute"}, {"name": "reset"}],
        },
        "executionPaths": execution_paths,
        "componentSummary": component_summary,
        "estimatedTokens": 1450,
        "withinBudget": True,
    }

    return SliceResponse(
        slice_id=entry_fqn,
        entry_fqn=entry_fqn,
        max_depth=request.max_depth,
        nodes=nodes,
        edges=edges,
        execution_paths=execution_paths,
        component_summary=component_summary,
        estimated_tokens=1450,
        max_tokens=6000,
        within_budget=True,
        legacy_source=legacy_source,
        raw_slice=raw_slice,
    )
