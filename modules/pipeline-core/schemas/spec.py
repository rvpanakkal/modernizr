"""
Pydantic v2 schemas for Step 3: Cognitive Extraction & Generated Specifications.
Defines data contracts for Business Rules, BDD Scenarios, Traceability, and Cryptographic Receipts.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class TraceabilityAnchor(BaseModel):
    legacy_file: str
    start_line: int
    end_line: int


class BusinessRule(BaseModel):
    rule_id: str               # e.g., "BR-TRANSFER-001"
    name: str = ""             # e.g., "Daily Ceiling Clearance"
    description: str
    severity: str = "HIGH"     # "CRITICAL" | "HIGH" | "STANDARD"
    traceability: TraceabilityAnchor

    # Optional fields for backward compatibility
    rule_type: Optional[str] = "VALIDATION"
    condition: Optional[str] = None
    action_or_outcome: Optional[str] = None
    legacy_refs: List[str] = Field(default_factory=list)


class BddScenario(BaseModel):
    scenario_id: str
    title: str
    gherkin_text: str          # "Scenario: ... Given ... When ... Then ..."
    linked_rule_ids: List[str] = Field(default_factory=list)
    traceability: TraceabilityAnchor

    # Optional fields for backward compatibility
    name: Optional[str] = None
    given: List[str] = Field(default_factory=list)
    when: str = ""
    then: List[str] = Field(default_factory=list)
    legacy_refs: List[str] = Field(default_factory=list)


class GeneratedSpecification(BaseModel):
    run_id: str
    feature_name: str
    domain: str
    entry_fqn: str
    bdd_scenarios: List[BddScenario]
    business_rules: List[BusinessRule]
    openapi_spec_yaml: str
    legacy_source_snapshot: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sha256_hash: str

    # Optional metadata fields for downstream Step 4 / Jira gate compatibility
    business_summary: Optional[str] = None
    scenarios: List[BddScenario] = Field(default_factory=list)
    data_contract_fields: Dict[str, str] = Field(default_factory=dict)
    legacy_traceability: Dict[str, str] = Field(default_factory=dict)
    jira_story_id: Optional[str] = None
    tracker_type: Optional[str] = "jira"

    def model_post_init(self, __context) -> None:
        if not self.scenarios and self.bdd_scenarios:
            self.scenarios = self.bdd_scenarios
        if not self.business_summary:
            self.business_summary = f"Modernized service specification for {self.feature_name}"
        if not self.legacy_traceability:
            # Populate mapping from bdd_scenarios
            for scenario in self.bdd_scenarios:
                self.legacy_traceability[f"{scenario.traceability.legacy_file}#L{scenario.traceability.start_line}"] = scenario.title


class StepHandoffReceipt(BaseModel):
    receipt_id: str
    run_id: str
    stage: str = "COGNITIVE_EXTRACTION"
    status: str = "HITL_PENDING"  # "HITL_PENDING" | "APPROVED" | "FAILED"
    spec_sha256: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
