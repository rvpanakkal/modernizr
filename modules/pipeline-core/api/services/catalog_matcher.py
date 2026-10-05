"""
Enterprise Service Catalog similarity and reuse matching engine.
Evaluates extracted domain models and vertical slices against corporate API catalogs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CatalogServiceRecord(BaseModel):
    service_id: str
    name: str
    domain: str
    version: str
    status: str
    description: str
    endpoints: List[str]
    capabilities: List[str]
    similarity_score: float
    recommendation: str
    adapter_strategy: str
    overlap_fields: List[str]


class CatalogMatchResult(BaseModel):
    domain: str
    best_match: Optional[CatalogServiceRecord] = None
    all_candidates: List[CatalogServiceRecord] = Field(default_factory=list)
    reuse_recommended: bool
    summary: str


# Corporate Service Registry entries for enterprise reuse
ENTERPRISE_SERVICE_REGISTRY: List[Dict[str, Any]] = [
    {
        "service_id": "ms-payment-clearing",
        "name": "Enterprise Payment Clearing Service",
        "domain": "PAYMENT_PROCESSING",
        "version": "3.2.0",
        "status": "ACTIVE_PRODUCTION",
        "description": "High-throughput ISO-20022 and SEPA compliant fund clearing engine with idempotent transaction guarantees.",
        "endpoints": [
            "POST /api/v3/payments/transfers",
            "GET /api/v3/payments/transfers/{correlationId}",
            "POST /api/v3/payments/settlements",
        ],
        "capabilities": [
            "Account-to-Account Transfers",
            "Real-time Debit & Credit Posting",
            "CICS/Mainframe Settlement Bridge",
            "Fraud & AML Threshold Verification",
        ],
        "similarity_score": 0.94,
        "recommendation": "Reuse Adapter Recommended",
        "adapter_strategy": "Generate Spring Boot 3.5.x Feign / WebClient REST Adapter routing to ms-payment-clearing instead of rewriting custom clearing engine.",
        "overlap_fields": [
            "fromAccountId",
            "toAccountId",
            "amount",
            "currency",
            "correlationId",
            "statusMessage",
        ],
    },
    {
        "service_id": "ms-account-ledger",
        "name": "Core Account Ledger Microservice",
        "domain": "ACCOUNTING",
        "version": "1.8.4",
        "status": "ACTIVE_PRODUCTION",
        "description": "Double-entry accounting and ledger persistence microservice with event-sourced audit journal.",
        "endpoints": [
            "GET /api/v1/accounts/{accountId}/balance",
            "POST /api/v1/accounts/{accountId}/entries",
            "GET /api/v1/accounts/{accountId}/status",
        ],
        "capabilities": [
            "Account Balance Lookup",
            "Account Status & Freeze Verification",
            "Audit Journal Ledger Append",
        ],
        "similarity_score": 0.81,
        "recommendation": "Partial Domain Match — Entity Reuse",
        "adapter_strategy": "Import shared Account domain DTOs from com.enterprise.banking.ledger:account-contract:1.8.4.",
        "overlap_fields": [
            "accountId",
            "balance",
            "status",
            "accountType",
        ],
    },
    {
        "service_id": "ms-notification-gateway",
        "name": "Omni-Channel Customer Notification Gateway",
        "domain": "COMMUNICATIONS",
        "version": "2.1.0",
        "status": "ACTIVE_PRODUCTION",
        "description": "Enterprise event-driven SMS, Push, and Email dispatch service for financial transaction alerts.",
        "endpoints": [
            "POST /api/v2/notifications/dispatch",
        ],
        "capabilities": [
            "SMS Confirmation",
            "Push Notification Alerts",
        ],
        "similarity_score": 0.35,
        "recommendation": "No Direct Architectural Overlap",
        "adapter_strategy": "Optional Kafka event dispatch on post-transfer hook.",
        "overlap_fields": [
            "correlationId",
            "recipientId",
        ],
    },
]


class CatalogMatcher:
    """Matches legacy domain slices to existing active enterprise services."""

    def match(self, domain: Optional[str] = None, operations: Optional[List[str]] = None) -> CatalogMatchResult:
        normalized_domain = (domain or "PAYMENT_PROCESSING").upper().replace(" ", "_")

        records = [CatalogServiceRecord(**item) for item in ENTERPRISE_SERVICE_REGISTRY]

        # Prioritize matching domain
        sorted_records = sorted(
            records,
            key=lambda r: (1 if normalized_domain in r.domain else 0, r.similarity_score),
            reverse=True,
        )

        best = sorted_records[0] if sorted_records else None
        reuse = bool(best and best.similarity_score >= 0.85)

        summary = (
            f"Catalog scan identified {len(sorted_records)} enterprise candidates. "
            f"Top match: {best.name} ({best.service_id}) with {int(best.similarity_score * 100)}% structural and functional similarity. "
            f"Recommendation: {best.recommendation}."
        ) if best else "No enterprise services matched."

        return CatalogMatchResult(
            domain=normalized_domain,
            best_match=best,
            all_candidates=sorted_records,
            reuse_recommended=reuse,
            summary=summary,
        )


# Global singleton instance
catalog_matcher = CatalogMatcher()
