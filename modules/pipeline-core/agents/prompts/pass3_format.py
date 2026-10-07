"""
Pass 3 Prompt: Spec Formatter.
Synthesizes executable Gherkin BDD scenarios, OpenAPI 3.0 YAML contracts,
and bidirectional legacy traceability maps, governed by the active ArchitectureProfile.
"""

from typing import Optional

PASS3_SYSTEM_PROMPT = """You are the Spec Formatter & Target Contract Synthesizer Agent in an automated legacy modernization pipeline.
Your job is to synthesize formal, technology-agnostic BDD acceptance specifications (Gherkin syntax) and an OpenAPI 3.0 YAML service contract.

INVARIANTS:
1. Every BDD scenario must have scenario_id, title, gherkin_text (with Given, When, Then), linked_rule_ids, and a traceability anchor.
2. Formulate an OpenAPI 3.0 YAML definition describing the target REST endpoint, request body schema, and 200/400/422 response schemas.
3. Adhere strictly to the active ArchitectureProfile's package naming patterns and REST conventions (e.g. RFC 7807 problem details).
4. Map every scenario back to legacy source line ranges (legacy_file, start_line, end_line).
"""

def build_pass3_user_prompt(
    entry_fqn: str,
    feature_name: str,
    domain: str,
    business_rules_json: str,
    architecture_profile_name: str,
    base_package_pattern: str,
) -> str:
    return f"""Synthesize the target specification for `{feature_name}` (Domain: `{domain}`, Entrypoint: `{entry_fqn}`).

ACTIVE ARCHITECTURE PROFILE:
- Name: {architecture_profile_name}
- Base Package: {base_package_pattern}

=== EXTRACTED BUSINESS RULES ===
{business_rules_json}
================================

Generate a complete JSON object adhering to this structure:
{{
  "feature_name": "{feature_name}",
  "domain": "{domain}",
  "entry_fqn": "{entry_fqn}",
  "bdd_scenarios": [
    {{
      "scenario_id": "SCN-001",
      "title": "Successful Funds Transfer",
      "gherkin_text": "Scenario: Successful Funds Transfer\\n  Given source account \\"ACC-100\\" has a balance of $500.00\\n  And destination account \\"ACC-200\\" is active\\n  When a transfer of $100.00 is requested\\n  Then $100.00 is debited from \\"ACC-100\\"\\n  And $100.00 is credited to \\"ACC-200\\"\\n  And a mainframe correlation ID is returned",
      "linked_rule_ids": ["BR-TRANSFER-001", "BR-TRANSFER-002", "BR-TRANSFER-003"],
      "traceability": {{
        "legacy_file": "TransferProcessingService.java",
        "start_line": 76,
        "end_line": 120
      }}
    }}
  ],
  "openapi_spec_yaml": "openapi: 3.0.3\\ninfo:\\n  title: Transfer Service API\\n  version: 1.0.0\\npaths:\\n  /api/v1/transfers:\\n    post:\\n      summary: Execute transfer\\n      ...",
  "business_summary": "Modernized service specification for fund transfers."
}}
"""
