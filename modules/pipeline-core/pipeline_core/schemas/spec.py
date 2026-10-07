"""
Step 3 data contracts — strict Pydantic v2 schemas for the multi-pass cognitive chain.

Each pass has its own bounded output contract:

    Pass 1 (Technical Decompiler)  -> DecompiledSlice
    Pass 2 (Business Abstractor)   -> BusinessRuleSet   (-> List[BusinessRule])
    Pass 3 (Spec Formatter)        -> GeneratedSpecification

All models use ``extra="forbid"`` so that a hallucinated/unknown field produced by the LLM is rejected
(and fed back into the agent's repair loop) instead of being silently dropped.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_STRICT = ConfigDict(extra="forbid", str_strip_whitespace=True)

_GHERKIN_KEYWORD = re.compile(r"^(given|when|then|and|but)\s+", re.IGNORECASE)


def _strip_gherkin_keyword(step: str) -> str:
    """Steps are stored keyword-less; renderers add Given/When/Then/And."""
    return _GHERKIN_KEYWORD.sub("", step.strip())


class TraceabilityAnchor(BaseModel):
    legacy_file: str = ""
    start_line: int = 1
    end_line: int = 1


# =============================================================================
# Pass 1 — Technical Decompiler output
# =============================================================================

class DecompiledOperation(BaseModel):
    """One discrete computational step with all Java EE / JSF plumbing stripped away."""
    model_config = _STRICT

    caller: str = Field(..., min_length=1, description="Component/method that performs the operation")
    target_operation: str = Field(..., min_length=1, description="Operation being performed or invoked")
    input_data: List[str] = Field(default_factory=list, description="Data elements consumed by the operation")
    conditional_checks: List[str] = Field(
        default_factory=list,
        description="Branch/guard conditions, verbatim in plain logic (e.g. 'amount <= 0')",
    )
    external_dispatches: List[str] = Field(
        default_factory=list,
        description="Calls leaving the slice: mainframe/CICS transactions, repositories, other services",
    )


class DecompiledSlice(BaseModel):
    """Container for the Pass 1 output."""
    model_config = _STRICT

    entry_point: str = Field(..., min_length=1, description="Entry component of the vertical slice (FQN)")
    target_boundaries: List[str] = Field(
        default_factory=list,
        description="Integration boundaries reached by the slice (e.g. CICS gateway, repository FQNs)",
    )
    operations: List[DecompiledOperation] = Field(..., min_length=1)


# =============================================================================
# Pass 2 — Business Rule Extraction output
# =============================================================================

class RuleType(str, Enum):
    VALIDATION = "VALIDATION"
    THRESHOLD = "THRESHOLD"
    ROUTING = "ROUTING"
    COMPLIANCE = "COMPLIANCE"


class BusinessRule(BaseModel):
    """A technology-agnostic business rule."""
    model_config = _STRICT

    rule_id: str = Field(..., pattern=r"^BR-\d{3}$", description="Stable identifier, e.g. BR-001")
    description: str = Field(..., min_length=1)
    rule_type: RuleType
    condition: str = Field(..., min_length=1, description="When the rule applies, in business terms")
    action_or_outcome: str = Field(..., min_length=1, description="What must happen when the condition holds")
    legacy_refs: List[str] = Field(
        default_factory=list,
        description="Legacy class FQNs / method signatures this rule was derived from",
    )


class BusinessRuleSet(BaseModel):
    """Object wrapper so Pass 2 can be forced through a single tool-call schema (top level must be an object)."""
    model_config = _STRICT

    rules: List[BusinessRule] = Field(..., min_length=1)

    @model_validator(mode="after")
    def _unique_rule_ids(self) -> "BusinessRuleSet":
        _assert_unique_rule_ids(self.rules)
        return self


def _assert_unique_rule_ids(rules: List[BusinessRule]) -> None:
    seen: set[str] = set()
    for r in rules:
        if r.rule_id in seen:
            raise ValueError(f"Duplicate rule_id '{r.rule_id}'")
        seen.add(r.rule_id)


# =============================================================================
# Pass 3 — Gherkin BDD & contract synthesis output
# =============================================================================

class BddScenario(BaseModel):
    """A Gherkin-compliant acceptance scenario, linked to the legacy source it was derived from."""
    model_config = _STRICT

    name: str = Field(..., min_length=1)
    given: List[str] = Field(..., min_length=1)
    when: str = Field(..., min_length=1)
    then: List[str] = Field(..., min_length=1)
    legacy_refs: List[str] = Field(
        ..., min_length=1,
        description="Legacy FQN/method keys; each must also be a key of GeneratedSpecification.legacy_traceability",
    )

    @field_validator("given", "then", mode="after")
    @classmethod
    def _strip_keywords_list(cls, steps: List[str]) -> List[str]:
        cleaned = [_strip_gherkin_keyword(s) for s in steps]
        if any(not s for s in cleaned):
            raise ValueError("Gherkin steps must not be empty")
        return cleaned

    @field_validator("when", mode="after")
    @classmethod
    def _strip_keyword_when(cls, step: str) -> str:
        cleaned = _strip_gherkin_keyword(step)
        if not cleaned:
            raise ValueError("Gherkin 'when' step must not be empty")
        return cleaned


class GeneratedSpecification(BaseModel):
    """The technology-agnostic specification that is published to Jira and gated by a human."""
    model_config = _STRICT

    feature_name: str = Field(..., min_length=1)
    domain: str = Field(..., min_length=1)
    business_summary: str = Field(..., min_length=1)
    business_rules: List[BusinessRule] = Field(..., min_length=1)
    scenarios: List[BddScenario] = Field(..., min_length=1)
    data_contract_fields: Dict[str, str] = Field(
        default_factory=dict, description="Modern contract field name -> type/description",
    )
    legacy_traceability: Dict[str, str] = Field(
        ..., min_length=1, description="Legacy FQN/method -> spec component (rule id / scenario name / contract field)",
    )

    # Populated by the orchestrator after the issue exists (Pass 3 cannot know them).
    jira_story_id: Optional[str] = Field(
        default=None,
        pattern=r"^(MOD-\d+|GH-\d+|#\d+|LOCAL-[A-Za-z0-9_-]+)$",
        description="Tracking ID e.g. MOD-101, GH-42, LOCAL-101",
    )
    tracker_type: Optional[str] = Field(default="jira", description="Issue tracker type: jira, github, local, etc.")
    run_id: Optional[str] = Field(default=None)

    @model_validator(mode="after")
    def _cross_reference_integrity(self) -> "GeneratedSpecification":
        _assert_unique_rule_ids(self.business_rules)
        trace_keys = set(self.legacy_traceability)
        for scenario in self.scenarios:
            missing = [ref for ref in scenario.legacy_refs if ref not in trace_keys]
            if missing:
                raise ValueError(
                    f"Scenario '{scenario.name}' references {missing} which are not keys of legacy_traceability"
                )
        return self
