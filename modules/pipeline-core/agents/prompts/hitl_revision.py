"""
Revision prompts for Step 4 Human-in-the-Loop (HITL) review.
Instructs Claude 3.7 Sonnet to surgically revise business invariants,
Gherkin BDD scenarios, OpenAPI 3.0 contracts, and legacy line traceability.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

HITL_REVISION_SYSTEM_PROMPT = """You are an Enterprise Principal Systems Architect and Polyglot Modernization Specialist.
Your task is to revise a modernized service specification based on an enterprise architect's review feedback and corrections.

CRITICAL INVARIANTS:
1. Token & Logic Optimization: Do not touch container plumbing. Work strictly on business invariants, validation thresholds, acceptance scenarios, and API schema boundaries.
2. Business Invariants (business_rules):
   - Surgically incorporate reviewer corrections (e.g. dormant account checks, risk ceilings, custom exception types).
   - Each rule must include:
     - rule_id (e.g. 'BR-001')
     - name (concise summary)
     - description (detailed rule specification)
     - severity ('CRITICAL' | 'HIGH' | 'STANDARD')
     - traceability: { 'legacy_file': string, 'start_line': integer, 'end_line': integer }
     - rule_type ('VALIDATION' | 'THRESHOLD' | 'COMPLIANCE' | 'SECURITY')
     - condition (plain boolean expression)
     - action_or_outcome (system reaction when condition met)
     - legacy_refs (list of file:line citations)
3. Acceptance Scenarios (bdd_scenarios):
   - Generate executable Gherkin BDD scenarios with Scenario / Given / When / Then blocks covering all revised rules and edge cases.
   - Each scenario must include:
     - scenario_id (e.g. 'SCN-001')
     - title (descriptive scenario title)
     - gherkin_text (complete Gherkin text)
     - linked_rule_ids (list of rule_ids verified by this scenario)
     - traceability: { 'legacy_file': string, 'start_line': integer, 'end_line': integer }
     - given, when, then step arrays
4. API Contract (openapi_spec_yaml):
   - Valid OpenAPI 3.0 YAML string reflecting all new schema attributes, request models, validation constraints, and HTTP error codes.
5. Bidirectional Line Traceability (legacy_traceability):
   - Map each rule or scenario citation back to legacy Java source lines.

OUTPUT FORMAT:
Return ONLY a valid, parseable JSON object matching this schema. Do NOT include markdown commentary or code block markers outside the JSON.
{
  "feature_name": string,
  "domain": string,
  "business_summary": string,
  "business_rules": [...],
  "bdd_scenarios": [...],
  "data_contract_fields": { "field_name": "type and description" },
  "openapi_spec_yaml": string,
  "legacy_traceability": { "line_citation": "rule_or_scenario_id" },
  "jira_story_id": string
}
"""


def build_hitl_revision_user_prompt(
    current_spec: Dict[str, Any],
    reviewer_feedback: str,
    decompiled_code: str,
    manual_edits: Optional[str] = None,
) -> str:
    """Builds the user prompt guiding Claude 3.7 to incorporate architect feedback."""
    spec_summary = {
        "feature_name": current_spec.get("feature_name", ""),
        "domain": current_spec.get("domain", ""),
        "business_summary": current_spec.get("business_summary", ""),
        "business_rules": current_spec.get("business_rules", []),
        "bdd_scenarios": current_spec.get("bdd_scenarios", []) or current_spec.get("scenarios", []),
        "data_contract_fields": current_spec.get("data_contract_fields", {}),
        "jira_story_id": current_spec.get("jira_story_id", "MOD-101"),
    }

    edits_clause = ""
    if manual_edits and manual_edits.strip():
        edits_clause = f"\n\n## ARCHITECT MANUAL EDITS / PROPOSED TEXT:\n{manual_edits.strip()}"

    return f"""Please surgically revise the modernized specification according to the architect's review feedback.

## REVIEWER FEEDBACK & REFINE INSTRUCTIONS:
{reviewer_feedback.strip()}
{edits_clause}

## ORIGINAL LEGACY SOURCE / DECOMPILED DOMAIN LOGIC:
```java
{decompiled_code.strip() if decompiled_code else "// Source not provided; preserve existing traceability"}
```

## CURRENT SPECIFICATION STATE:
```json
{json.dumps(spec_summary, indent=2)}
```

Generate the revised, complete specification JSON incorporating all reviewer adjustments, updated BDD scenarios, refreshed OpenAPI 3.0 YAML, and line-level traceability. Output valid JSON only.
"""
