"""
Pass 2 Prompt: Business Abstractor.
Extracts pure business rules, validation thresholds, calculations, and invariants from decompiled operations.
"""

PASS2_SYSTEM_PROMPT = """You are the Business Rule Abstractor Agent in an automated legacy modernization factory.
Your mission is to take decompiled operations and extract unambiguous, technology-agnostic business invariants, validation thresholds, and domain constraints.

INVARIANTS:
1. Every business rule must be assigned a unique ID in format `BR-XXX` or `BR-TRANSFER-XXX`.
2. Categorize severity as "CRITICAL", "HIGH", or "STANDARD".
3. Formulate the condition and outcome strictly in business terms, omitting implementation specifics.
4. Provide a line-level traceability anchor pointing to the source file and line boundaries.
"""

def build_pass2_user_prompt(entry_fqn: str, decompiled_operations_json: str, legacy_source: str) -> str:
    return f"""Analyze the decompiled vertical slice operations for `{entry_fqn}` and extract all core business rules and invariants.

=== DECOMPILED OPERATIONS ===
{decompiled_operations_json}
==============================

=== REFERENCE LEGACY CODE ===
{legacy_source}
=============================

Extract all business rules in JSON format:
{{
  "rules": [
    {{
      "rule_id": "BR-TRANSFER-001",
      "name": "Positive Amount Validation",
      "description": "Transfer amount must be strictly positive and greater than zero.",
      "severity": "CRITICAL",
      "condition": "amount <= 0 or amount is null",
      "action_or_outcome": "Reject transfer with IllegalArgumentException validation error",
      "traceability": {{
        "legacy_file": "TransferProcessingService.java",
        "start_line": 77,
        "end_line": 80
      }}
    }}
  ]
}}
"""
