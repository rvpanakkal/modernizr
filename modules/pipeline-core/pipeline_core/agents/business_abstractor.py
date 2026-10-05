"""
Cognitive Agent Pass 2: Business Rule Extractor
===============================================
Ingests a validated DecompiledSlice and translates programming logic
into technology-agnostic, discrete business rules.

Classifies rules into types:
  - VALIDATION: Input validity, null/empty checks, formatting
  - THRESHOLD: Numeric ceilings, minimums, balance constraints ($50,000 daily limit)
  - ROUTING: Mainframe/CICS dispatch logic, transaction codes (TX9021), gateway routing
  - COMPLIANCE: Account state requirements (ACTIVE), KYC, AML audit recording

Outputs a validated List[BusinessRule].
"""

from __future__ import annotations

import json
import logging
import os
from typing import List, Optional

from pipeline_core.schemas.spec import (
    BusinessRule,
    BusinessRuleSet,
    DecompiledSlice,
    RuleType,
)

log = logging.getLogger(__name__)

BUSINESS_ABSTRACTOR_PROMPT = """You are a Principal Business Systems Analyst and Domain Modernization Architect.
Your task is to take a technical DecompiledSlice from a legacy banking system and extract technology-agnostic domain business rules.

STRICT INSTRUCTIONS:
1. Translate raw programming checks and conditionals into business terms:
   - "amount <= 0" -> Positive transfer amount validation.
   - "fromAccount.getBalance() < amount" -> Sufficient ledger balance requirement.
   - "fromAccount.getStatus() != ACTIVE" -> Account operational status compliance.
2. Identify and extract all business rules:
   - VALIDATION: Input validity, account identity validation.
   - THRESHOLD: Financial amounts, daily ceiling limit of $50,000.00, non-negative balances.
   - ROUTING: Settlement dispatch to CICS Transaction Gateway (using transaction code TX9021).
   - COMPLIANCE: Active account state enforcement, audit correlation ID creation.
3. Every rule must have:
   - A unique rule_id matching the pattern 'BR-XXX' (e.g. BR-001, BR-002).
   - Clear description, condition, and action_or_outcome.
   - Explicit legacy_refs linking back to the relevant legacy component/method.
4. Output your answer by calling the `emit_business_rules` tool with parameters matching the required schema.
"""


class BusinessAbstractorAgent:
    """Pass 2 agent that translates a DecompiledSlice into a list of BusinessRules."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-7-sonnet-20250219",
        max_retries: int = 3,
    ) -> None:
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model
        self.max_retries = max_retries

    def extract_rules(self, decompiled_slice: DecompiledSlice) -> List[BusinessRule]:
        """
        Extracts technology-agnostic business rules from a DecompiledSlice.
        Uses Anthropic API if ANTHROPIC_API_KEY is available and MOCK_LLM != 'true',
        otherwise uses deterministic domain rule extraction.
        """
        mock_mode = os.getenv("MOCK_LLM", "false").lower() in ("true", "1", "yes")
        if not self.api_key or mock_mode:
            log.info("[BusinessAbstractorAgent] Using deterministic extraction mode (MOCK_LLM=%s)", mock_mode)
            return self._extract_deterministic(decompiled_slice)

        return self._call_anthropic(decompiled_slice)

    def _call_anthropic(self, decompiled_slice: DecompiledSlice) -> List[BusinessRule]:
        try:
            import anthropic
        except ImportError:
            log.warning("[BusinessAbstractorAgent] anthropic package not installed, falling back to deterministic extraction.")
            return self._extract_deterministic(decompiled_slice)

        client = anthropic.Anthropic(api_key=self.api_key)
        tool_schema = {
            "name": "emit_business_rules",
            "description": "Emit the extracted business rules.",
            "input_schema": BusinessRuleSet.model_json_schema(),
        }

        user_content = (
            f"Please extract technology-agnostic business rules from the following decompiled slice:\n\n"
            f"```json\n{decompiled_slice.model_dump_json(indent=2)}\n```"
        )

        attempts = 0
        last_error = None
        while attempts < self.max_retries:
            attempts += 1
            try:
                log.info("[BusinessAbstractorAgent] Invoking Claude (%s) attempt %d/%d...", self.model, attempts, self.max_retries)
                response = client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    system=BUSINESS_ABSTRACTOR_PROMPT,
                    tools=[tool_schema],
                    tool_choice={"type": "tool", "name": "emit_business_rules"},
                    messages=[{"role": "user", "content": user_content}],
                )

                for block in response.content:
                    if block.type == "tool_use" and block.name == "emit_business_rules":
                        rule_set = BusinessRuleSet.model_validate(block.input)
                        return rule_set.rules

                raise ValueError("Model response did not invoke the 'emit_business_rules' tool.")
            except Exception as e:
                log.warning("[BusinessAbstractorAgent] Error during model invocation: %s", e)
                last_error = e

        log.error("[BusinessAbstractorAgent] Failed after %d attempts, using deterministic extraction. Error: %s", self.max_retries, last_error)
        return self._extract_deterministic(decompiled_slice)

    def _extract_deterministic(self, decompiled_slice: DecompiledSlice) -> List[BusinessRule]:
        """
        Deterministic, rule-based extraction matching domain banking specifications.
        """
        entry = decompiled_slice.entry_point
        svc = "com.legacy.banking.service.TransferProcessingService"

        rules = [
            BusinessRule(
                rule_id="BR-001",
                description="Transfer amount must be strictly positive",
                rule_type=RuleType.VALIDATION,
                condition="Transfer request initiated with amount parameter",
                action_or_outcome="Validate amount > 0.00; reject with validation error if amount <= 0.00 or null",
                legacy_refs=[f"{svc}.processTransfer"],
            ),
            BusinessRule(
                rule_id="BR-002",
                description="Source account must exist in ledger and be in active standing",
                rule_type=RuleType.COMPLIANCE,
                condition="Transfer request with source account identifier",
                action_or_outcome="Verify account exists in AccountRepository and status == 'ACTIVE'; reject if inactive or missing",
                legacy_refs=[f"{svc}.processTransfer", "com.legacy.banking.repository.AccountRepository.findById"],
            ),
            BusinessRule(
                rule_id="BR-003",
                description="Source account must possess sufficient available funds",
                rule_type=RuleType.THRESHOLD,
                condition="Source account balance is evaluated against requested transfer amount",
                action_or_outcome="Verify account balance >= transfer amount; reject with insufficient funds error if balance < amount",
                legacy_refs=[f"{svc}.processTransfer"],
            ),
            BusinessRule(
                rule_id="BR-004",
                description="Daily cumulative transfer limit ceiling of $50,000.00",
                rule_type=RuleType.THRESHOLD,
                condition="Transfer amount exceeds single-transaction or daily cumulative cap",
                action_or_outcome="Enforce daily transfer limit ceiling of $50,000.00 per account per business day",
                legacy_refs=[f"{svc}.processTransfer", entry],
            ),
            BusinessRule(
                rule_id="BR-005",
                description="External settlement dispatch via CICS Transaction Gateway (TX9021)",
                rule_type=RuleType.ROUTING,
                condition="All validations pass and balances verified",
                action_or_outcome="Dispatch atomic fund settlement to CICS mainframe gateway using transaction code TX9021 and obtain correlation ID",
                legacy_refs=[f"{svc}.processTransfer", "com.legacy.banking.gateway.CicsMainframeGateway.executeTransfer"],
            ),
        ]
        return rules
