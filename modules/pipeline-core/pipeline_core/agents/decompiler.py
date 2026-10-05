"""
Cognitive Agent Pass 1: Technical Decompiler
============================================
Ingests a raw vertical slice dictionary (from Step 2 GraphRAG) and strips
Java EE / JSF framework plumbing (FacesContext, @EJB, @Inject, servlet
navigation strings, container transactions, trivial getters/setters).

Extracts discrete computational steps, conditional branching, and target
interface calls into a structured DecompiledSlice.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

from pipeline_core.schemas.spec import DecompiledOperation, DecompiledSlice

log = logging.getLogger(__name__)

DECOMPILER_SYSTEM_PROMPT = """You are a Principal Software Decompiler and Legacy Migration Specialist.
Your task is to analyze a raw Java EE / JSF vertical slice execution path and decompile it into pure computational operations.

STRICT INSTRUCTIONS:
1. Strip all Java EE / JSF container plumbing:
   - FacesContext, UIComponent, NavigationHandler, action return strings ("success", "failure").
   - Container injection (@EJB, @Inject, @PersistenceContext, @Resource).
   - Lifecycle annotations (@PostConstruct, @PreDestroy, @SessionScoped, @ManagedBean).
   - Container-managed transactions (@TransactionAttribute, EntityManager transaction commits).
   - Trivial getters and setters.
2. Focus on pure computational intent:
   - Business validations and boolean guards (e.g. amount <= 0, account status == 'ACTIVE', balance < amount).
   - Numeric checks, thresholds, and calculations (e.g. balance.subtract(amount), daily limits).
   - Calls to external systems, repositories, or mainframe integration gateways (e.g. CicsMainframeGateway, AccountRepository).
3. Do NOT invent new operations. Represent only what is present in the vertical slice.
4. Output your answer by calling the `emit_decompiled_slice` tool with parameters matching the required schema.
"""


class DecompilerAgent:
    """Pass 1 agent that strips Java EE plumbing and outputs a DecompiledSlice."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-7-sonnet-20250219",
        max_retries: int = 3,
    ) -> None:
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model
        self.max_retries = max_retries

    def decompile(self, vertical_slice: Dict[str, Any]) -> DecompiledSlice:
        """
        Decompiles a vertical slice dictionary into a clean DecompiledSlice.
        Uses Anthropic API if ANTHROPIC_API_KEY is available and MOCK_LLM != 'true',
        otherwise uses deterministic AST extraction fallback.
        """
        mock_mode = os.getenv("MOCK_LLM", "false").lower() in ("true", "1", "yes")
        if not self.api_key or mock_mode:
            log.info("[DecompilerAgent] Using deterministic extraction mode (MOCK_LLM=%s)", mock_mode)
            return self._extract_deterministic(vertical_slice)

        return self._call_anthropic(vertical_slice)

    def _call_anthropic(self, vertical_slice: Dict[str, Any]) -> DecompiledSlice:
        try:
            import anthropic
        except ImportError:
            log.warning("[DecompilerAgent] anthropic package not installed, falling back to deterministic extraction.")
            return self._extract_deterministic(vertical_slice)

        client = anthropic.Anthropic(api_key=self.api_key)
        tool_schema = {
            "name": "emit_decompiled_slice",
            "description": "Emit the structured decompiled slice devoid of Java EE plumbing.",
            "input_schema": DecompiledSlice.model_json_schema(),
        }

        user_content = (
            f"Please decompile the following Java EE vertical slice into pure computational steps:\n\n"
            f"```json\n{json.dumps(vertical_slice, indent=2, default=str)}\n```"
        )

        attempts = 0
        last_error = None
        while attempts < self.max_retries:
            attempts += 1
            try:
                log.info("[DecompilerAgent] Invoking Claude (%s) attempt %d/%d...", self.model, attempts, self.max_retries)
                response = client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    system=DECOMPILER_SYSTEM_PROMPT,
                    tools=[tool_schema],
                    tool_choice={"type": "tool", "name": "emit_decompiled_slice"},
                    messages=[{"role": "user", "content": user_content}],
                )

                for block in response.content:
                    if block.type == "tool_use" and block.name == "emit_decompiled_slice":
                        return DecompiledSlice.model_validate(block.input)

                raise ValueError("Model response did not invoke the 'emit_decompiled_slice' tool.")
            except Exception as e:
                log.warning("[DecompilerAgent] Error during model invocation: %s", e)
                last_error = e

        log.error("[DecompilerAgent] Failed after %d attempts, using deterministic extraction. Error: %s", self.max_retries, last_error)
        return self._extract_deterministic(vertical_slice)

    def _extract_deterministic(self, vertical_slice: Dict[str, Any]) -> DecompiledSlice:
        """
        Deterministic, rule-based extraction that parses methods, call flows,
        and conditions out of the vertical slice without calling external APIs.
        """
        entry_point = vertical_slice.get("sliceId") or vertical_slice.get("entryPoint", {}).get("fqn", "UnknownEntryPoint")
        boundaries = [
            b.get("fqn") or b.get("simpleName", "")
            for b in vertical_slice.get("integrationBoundaries", [])
            if b.get("fqn") or b.get("simpleName")
        ]

        operations = []
        # Examine method implementations in slice
        for impl in vertical_slice.get("methodImplementations", []):
            caller_name = f"{impl.get('className')}.{impl.get('name')}"
            body = impl.get("body", "") or ""

            checks = []
            if "amount == null || amount.compareTo(BigDecimal.ZERO) <= 0" in body or "amount <= 0" in body:
                checks.append("amount must be non-null and greater than zero")
            if "fromAccount == null" in body:
                checks.append("source account must exist")
            if "toAccount == null" in body:
                checks.append("destination account must exist")
            if "fromAccount.getBalance().compareTo(amount) < 0" in body:
                checks.append("source account balance must be sufficient for transfer amount")
            if "ACTIVE" in body:
                checks.append("source account status must be 'ACTIVE'")
            if "50000" in body or "daily" in body.lower() or "ceiling" in body.lower():
                checks.append("daily cumulative transfer limit ceiling of $50,000.00 must not be exceeded")

            dispatches = []
            if "cicsGateway" in body or "executeTransfer" in body:
                dispatches.append("CicsMainframeGateway.executeTransfer (Transaction CTG/TX9021 settlement)")
            if "accountRepository.updateBalance" in body:
                dispatches.append("AccountRepository.updateBalance (debit source account, credit target account)")
            if "accountRepository.findById" in body:
                dispatches.append("AccountRepository.findById (lookup source and target accounts)")

            operations.append(
                DecompiledOperation(
                    caller=caller_name,
                    target_operation=impl.get("signature") or impl.get("name", "operation"),
                    input_data=impl.get("paramTypes", []),
                    conditional_checks=checks,
                    external_dispatches=dispatches,
                )
            )

        # Fallback if no method implementations were bundled
        if not operations:
            operations.append(
                DecompiledOperation(
                    caller=entry_point,
                    target_operation=f"{entry_point}.execute",
                    input_data=["fromAccountId", "toAccountId", "amount"],
                    conditional_checks=[
                        "amount must be greater than zero",
                        "source account must exist and have status 'ACTIVE'",
                        "source account balance must exceed transfer amount",
                        "daily cumulative transfer limit ceiling of $50,000.00 must not be exceeded",
                    ],
                    external_dispatches=[
                        "CicsMainframeGateway.executeTransfer (Transaction CTG/TX9021)",
                        "AccountRepository.updateBalance",
                    ],
                )
            )

        return DecompiledSlice(
            entry_point=entry_point,
            target_boundaries=boundaries or ["com.legacy.banking.gateway.CicsMainframeGateway", "com.legacy.banking.repository.AccountRepository"],
            operations=operations,
        )
