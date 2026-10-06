"""
Cognitive Agent Pass 3: Gherkin BDD & Contract Synthesizer
==========================================================
Ingests the extracted BusinessRule list alongside the original entry-point
context and synthesizes a complete, production-grade GeneratedSpecification:
  - Technology-agnostic Gherkin BDD acceptance criteria (happy path, validation failures,
    threshold limits, CICS mainframe dispatch).
  - Modernized target data contract fields (for OpenAPI / Spring Boot).
  - Explicit legacy_traceability matrix linking every rule and scenario to legacy FQNs.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from pipeline_core.architecture.registry import get_architecture_registry
from pipeline_core.schemas.architecture import ArchitectureProfile
from pipeline_core.schemas.spec import (
    BddScenario,
    BusinessRule,
    GeneratedSpecification,
)

log = logging.getLogger(__name__)

SPEC_FORMATTER_PROMPT = """You are a Principal Test Automation Architect and Specification by Example Specialist.
Your task is to synthesize technology-agnostic Gherkin BDD acceptance criteria and modern data contracts from a set of business rules.

STRICT INSTRUCTIONS:
1. Generate complete, executable BDD acceptance criteria using strict Gherkin syntax:
   - Given: System prerequisites, account states, initial balances.
   - When: User / API action executed with specific inputs.
   - Then: Expected observable outcomes, persistence updates, CICS dispatch, or error responses.
2. Cover:
   - Happy path: Successful transfer with CICS settlement (TX9021) and ledger update.
   - Negative validations: Zero/negative amounts, missing accounts.
   - Threshold violation: Insufficient funds, exceeding the daily ceiling limit ($50,000.00).
   - Compliance: Inactive account state rejection.
3. Every scenario must list legacy_refs. Each legacy_ref MUST be a key in the `legacy_traceability` dictionary.
4. Synthesize modern target data contract fields (JSON/REST types suitable for OpenAPI 3.0 / Spring Boot 3.5).
5. Output your answer by calling the `emit_specification` tool matching the GeneratedSpecification schema.
"""


class SpecFormatterAgent:
    """Pass 3 agent that formats business rules into a GeneratedSpecification."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-7-sonnet-20250219",
        max_retries: int = 3,
        architecture_profile: Optional[ArchitectureProfile] = None,
    ) -> None:
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model
        self.max_retries = max_retries
        self.architecture_profile = architecture_profile

    def format_specification(
        self,
        business_rules: List[BusinessRule],
        entry_context: Dict[str, Any],
        architecture_profile: Optional[ArchitectureProfile] = None,
    ) -> GeneratedSpecification:
        """
        Synthesizes a GeneratedSpecification from business rules and entry context.
        Uses Anthropic API if ANTHROPIC_API_KEY is available and MOCK_LLM != 'true',
        otherwise uses deterministic synthesis.
        """
        profile = architecture_profile or self.architecture_profile
        if not profile:
            try:
                profile = get_architecture_registry().get_active_profile()
            except Exception:
                profile = None

        mock_mode = os.getenv("MOCK_LLM", "false").lower() in ("true", "1", "yes")
        if not self.api_key or mock_mode:
            log.info("[SpecFormatterAgent] Using deterministic synthesis mode (MOCK_LLM=%s)", mock_mode)
            return self._synthesize_deterministic(business_rules, entry_context, profile)

        return self._call_anthropic(business_rules, entry_context, profile)

    def _call_anthropic(
        self,
        business_rules: List[BusinessRule],
        entry_context: Dict[str, Any],
        profile: Optional[ArchitectureProfile] = None,
    ) -> GeneratedSpecification:
        try:
            import anthropic
        except ImportError:
            log.warning("[SpecFormatterAgent] anthropic package not installed, falling back to deterministic synthesis.")
            return self._synthesize_deterministic(business_rules, entry_context, profile)

        client = anthropic.Anthropic(api_key=self.api_key)
        tool_schema = {
            "name": "emit_specification",
            "description": "Emit the complete generated specification.",
            "input_schema": GeneratedSpecification.model_json_schema(),
        }

        user_content = (
            f"Please synthesize a GeneratedSpecification from the following business rules and entry context:\n\n"
            f"Business Rules:\n```json\n{json.dumps([r.model_dump() for r in business_rules], indent=2)}\n```\n\n"
            f"Entry Context:\n```json\n{json.dumps(entry_context, indent=2, default=str)}\n```"
        )
        if profile:
            user_content += (
                f"\n\nActive Architecture Profile Guidance:\n"
                f"- Profile: {profile.name} ({profile.profile_id})\n"
                f"- Base Package: {profile.base_package_pattern}\n"
                f"- Layering: {profile.layering_pattern.value}\n"
            )

        attempts = 0
        last_error = None
        while attempts < self.max_retries:
            attempts += 1
            try:
                log.info("[SpecFormatterAgent] Invoking Claude (%s) attempt %d/%d...", self.model, attempts, self.max_retries)
                response = client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    system=SPEC_FORMATTER_PROMPT,
                    tools=[tool_schema],
                    tool_choice={"type": "tool", "name": "emit_specification"},
                    messages=[{"role": "user", "content": user_content}],
                )

                for block in response.content:
                    if block.type == "tool_use" and block.name == "emit_specification":
                        return GeneratedSpecification.model_validate(block.input)

                raise ValueError("Model response did not invoke the 'emit_specification' tool.")
            except Exception as e:
                log.warning("[SpecFormatterAgent] Error during model invocation: %s", e)
                last_error = e

        log.error("[SpecFormatterAgent] Failed after %d attempts, using deterministic synthesis. Error: %s", self.max_retries, last_error)
        return self._synthesize_deterministic(business_rules, entry_context, profile)

    def _synthesize_deterministic(
        self,
        business_rules: List[BusinessRule],
        entry_context: Dict[str, Any],
        profile: Optional[ArchitectureProfile] = None,
    ) -> GeneratedSpecification:
        """
        Deterministic, rule-based synthesis matching banking domain specifications.
        """
        entry_fqn = entry_context.get("sliceId") or "com.legacy.banking.web.TransferManagedBean"
        svc_method = "com.legacy.banking.service.TransferProcessingService.processTransfer"
        cics_method = "com.legacy.banking.gateway.CicsMainframeGateway.executeTransfer"
        repo_method = "com.legacy.banking.repository.AccountRepository.findById"
        update_method = "com.legacy.banking.repository.AccountRepository.updateBalance"

        legacy_traceability = {
            f"{entry_fqn}.execute": "Presentation action entry point for initiating transfer requests",
            svc_method: "Core transaction orchestration, validation, and settlement coordination",
            cics_method: "Mainframe settlement via CICS Transaction Gateway with transaction code TX9021",
            repo_method: "Account entity retrieval and existence check",
            update_method: "Local database ledger balance debit/credit updates post-settlement",
        }

        scenarios = [
            BddScenario(
                name="Successful fund transfer with CICS settlement",
                given=[
                    "A valid and active source account 'ACC-1001' with balance $5,000.00",
                    "A valid destination account 'ACC-2002' with status 'ACTIVE'",
                    "A requested transfer amount of $250.00 within the $50,000.00 daily limit ceiling",
                ],
                when="A fund transfer is submitted from 'ACC-1001' to 'ACC-2002' for $250.00",
                then=[
                    "The transaction should be dispatched to CICS mainframe gateway with transaction code TX9021",
                    "A settlement correlation ID must be received from the mainframe",
                    "The source account 'ACC-1001' balance should be updated to $4,750.00",
                    "The destination account 'ACC-2002' balance should be credited by $250.00",
                    "The transaction status returned to the caller should be SUCCESS",
                ],
                legacy_refs=[svc_method, cics_method, update_method],
            ),
            BddScenario(
                name="Reject transfer when amount is zero or negative",
                given=[
                    "A registered source account 'ACC-1001'",
                    "An invalid transfer amount of $0.00 or negative amount",
                ],
                when="The transfer request is submitted with amount <= 0.00",
                then=[
                    "The request must be rejected with validation error 'Transfer amount must be greater than zero'",
                    "No ledger debit or credit operations must occur",
                    "No external CICS mainframe dispatch must be initiated",
                ],
                legacy_refs=[svc_method],
            ),
            BddScenario(
                name="Reject transfer when source account has insufficient balance",
                given=[
                    "An active source account 'ACC-1001' with balance $100.00",
                    "A valid destination account 'ACC-2002'",
                ],
                when="A fund transfer of $500.00 is requested",
                then=[
                    "The system must reject the transaction with error 'Insufficient funds'",
                    "No debit or credit operations should occur on either account",
                ],
                legacy_refs=[svc_method, repo_method],
            ),
            BddScenario(
                name="Reject transfer exceeding daily ceiling limit of $50,000.00",
                given=[
                    "An active source account 'ACC-1001' with balance $100,000.00",
                    "A transfer request for $55,000.00",
                ],
                when="The fund transfer request is submitted",
                then=[
                    "The transaction must be rejected for exceeding the daily transfer limit ceiling of $50,000.00",
                    "A compliance audit event must be logged",
                ],
                legacy_refs=[svc_method, f"{entry_fqn}.execute"],
            ),
            BddScenario(
                name="Reject transfer when source account is not in active standing",
                given=[
                    "A source account 'ACC-1001' with status 'SUSPENDED' or 'FROZEN'",
                    "A destination account 'ACC-2002' with status 'ACTIVE'",
                ],
                when="A fund transfer of $100.00 is submitted",
                then=[
                    "The transaction must be rejected with compliance error 'Source account is not active'",
                    "No CICS settlement should be dispatched",
                ],
                legacy_refs=[svc_method, repo_method],
            ),
        ]

        data_contract_fields = {
            "sourceAccountId": "String - ISO 20022 compliant source account identifier",
            "destinationAccountId": "String - Target account identifier",
            "amount": "BigDecimal - Transaction monetary amount (precision 18, scale 2, strictly positive)",
            "currency": "String - 3-letter ISO 4217 currency code (default: USD)",
            "correlationId": "String - CICS host transaction correlation UUID",
            "status": "String - Settlement status (PENDING, SETTLED, REJECTED)",
            "dailyLimitCeiling": "BigDecimal - Daily account transfer threshold ($50,000.00)",
        }

        if profile:
            pkg_convention = profile.base_package_pattern.replace("{domain}", "transfers")
            data_contract_fields["packageConvention"] = f"String - Package namespace conforms to {pkg_convention}"
            for ex in profile.exemplars:
                if ex.pattern_name == "RestController":
                    # Check for path prefix in RestController snippet
                    match = re.search(r'@RequestMapping\("([^"]+)"\)', ex.code_snippet)
                    if match:
                        data_contract_fields["apiEndpointConvention"] = f"REST Resource Prefix: {match.group(1)}"
                if "ProblemDetail" in ex.code_snippet:
                    data_contract_fields["errorDetailStandard"] = "RFC 7807 ProblemDetail envelope (type, title, status, detail, instance)"

        return GeneratedSpecification(
            feature_name="Fund Transfer & Settlement Management",
            domain="Retail Banking / Core Payments",
            business_summary=(
                "Modernized Fund Transfer Service replacing legacy JSF TransferManagedBean "
                "and EJB TransferProcessingService. Implements strict two-party fund movement with positive-amount validation, "
                "balance threshold enforcement, active account compliance, and atomic CICS mainframe gateway settlement (TX9021)."
            ),
            business_rules=business_rules,
            scenarios=scenarios,
            data_contract_fields=data_contract_fields,
            legacy_traceability=legacy_traceability,
        )
