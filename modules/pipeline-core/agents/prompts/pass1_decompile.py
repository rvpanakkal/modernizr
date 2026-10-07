"""
Pass 1 Prompt: Technical Decompiler.
Strips container noise (Java EE / JSF / Spring annotations, JNDI, raw transaction wrappers),
leaving sanitized, domain-focused computational operations and guard checks.
"""

PASS1_SYSTEM_PROMPT = """You are the Technical Decompiler Agent in an automated enterprise modernization pipeline.
Your goal is to ingest legacy Java EE 6 / JSF 2.x vertical slice code and decompile it into clean, container-agnostic domain logic.

INVARIANTS:
1. Strip all presentation and container-specific annotations (@ManagedBean, @SessionScoped, @Stateless, @EJB, @Inject, @PersistenceContext, @TransactionAttribute, @Resource).
2. Eliminate infrastructure boilerplate: JNDI lookups, raw JDBC connection handshakes, FacesContext references, servlet request wrappers, and trivial getters/setters.
3. Preserve all computational intent, arithmetic operations, validation bounds, branching conditions, and external service/database invocations.
4. Represent the extracted flow as sequential operations with inputs, guard conditions, and external dispatch boundaries.
"""

def build_pass1_user_prompt(entry_fqn: str, legacy_source: str) -> str:
    return f"""Decompile the following legacy Java EE vertical slice starting at entrypoint `{entry_fqn}`.

=== LEGACY SOURCE CODE ===
{legacy_source}
==========================

Output a structured JSON object with:
- "entry_point": "{entry_fqn}"
- "target_boundaries": list of downstream gateways and repositories reached
- "operations": list of discrete operations, each with:
    - "caller": class or method name
    - "target_operation": name of action performed
    - "input_data": list of parameters/fields used
    - "conditional_checks": list of guard checks or validation conditions (e.g. "amount <= 0", "status != ACTIVE")
    - "external_dispatches": list of external calls (mainframe, db, gateway)
"""
