"""
Pipeline Step 2B — GraphRAG Vertical Slice Extractor
=====================================================
Provides driver-based query functions for retrieving isolated vertical execution
paths (presentation → service → integration boundary) from the Neo4j graph.

All returned dictionaries are compact, token-efficient structures designed for
direct injection into LLM prompts (Step 3 extraction nodes).

Token budget enforced: slices exceeding MAX_SLICE_TOKENS are truncated with a
warning, preserving entry-point and boundary information.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# Maximum estimated tokens allowed per LLM context slice (AGENTS.md §5)
MAX_SLICE_TOKENS = 6_000

# Presentation / entry-point annotations that mark UI layer entry classes
ENTRY_POINT_ANNOTATIONS = frozenset({
    "ManagedBean", "Path", "Controller", "RestController",
    "Named", "ViewScoped", "SessionScoped", "RequestScoped",
    "FacesComponent", "FacesConverter", "FacesValidator",
})

# Annotation names that mark integration boundary components
BOUNDARY_ANNOTATIONS = frozenset({
    "Stateless", "Singleton", "Service", "Repository", "Component",
    "PersistenceContext",
})

# Name fragments that identify integration boundary classes
BOUNDARY_NAME_FRAGMENTS = ("Gateway", "Repository", "Dao", "DAO", "Adapter",
                           "Client", "Queue", "Publisher", "Sink", "Stub")

# Legacy Cypher query catalog for GraphRAG vertical slice retrieval
GRAPH_RAG_QUERIES = {
    "VERTICAL_SLICE_BY_CLASS": """
        MATCH (c:Class {name: $className})
        OPTIONAL MATCH (c)-[:INJECTS]->(dep:Class)
        OPTIONAL MATCH (c)-[:CALLS]->(m:Method)
        OPTIONAL MATCH (m)-[:CALLS]->(depMethod:Method)
        RETURN c.name AS class_name,
               c.kind AS class_kind,
               labels(c) AS labels,
               collect(DISTINCT dep.name) AS injected_dependencies,
               collect(DISTINCT m.name) AS methods,
               collect(DISTINCT depMethod.name) AS downstream_calls
    """,
    "ALL_ENDPOINTS_AND_SERVICES": """
        MATCH (c:Class)
        WHERE 'Stateless' IN c.annotations OR 'Path' IN c.annotations OR 'Named' IN c.annotations
        OPTIONAL MATCH (c)-[:INJECTS]->(svc:Class)
        RETURN c.name AS component_name,
               c.annotations AS annotations,
               collect(DISTINCT svc.name) AS service_dependencies
    """,
    "DEPENDENCY_CALL_GRAPH": """
        MATCH p = (start:Class {name: $rootClass})-[:INJECTS|CALLS*1..3]->(target:Class)
        RETURN p
        LIMIT 25
    """
}


# =============================================================================
# Query Functions
# =============================================================================

def find_entry_points(session) -> List[Dict[str, Any]]:
    """
    Find all presentation-layer entry point classes annotated with JSF / JAX-RS
    or Spring MVC annotations.

    Returns a list of dicts, each containing:
        fqn                  – fully qualified class name
        simpleName           – simple class name
        kind                 – "CLASS" | "INTERFACE"
        annotations          – list of annotation names on this class
        injectedDependencies – list of FQNs directly injected into this class

    Example Cypher path:
        (:Class)-[:ANNOTATED_WITH]->(:Annotation {name: 'ManagedBean'})
    """
    result = session.run(
        """
        MATCH (c:Class)-[:ANNOTATED_WITH]->(a:Annotation)
        WHERE a.name IN $annotations
        WITH c, collect(DISTINCT a.name) AS annNames
        OPTIONAL MATCH (c)-[:INJECTS]->(dep:Class)
        RETURN c.fqn         AS fqn,
               c.simpleName  AS simpleName,
               c.kind        AS kind,
               annNames      AS annotations,
               collect(DISTINCT dep.fqn) AS injectedDependencies
        ORDER BY c.simpleName
        """,
        annotations=list(ENTRY_POINT_ANNOTATIONS),
    )
    entry_points = [dict(r) for r in result]
    log.info("[GraphRAG] Found %d entry points.", len(entry_points))
    return entry_points


def extract_vertical_slice(
    session,
    entry_class_fqn: str,
    max_depth: int = 5,
) -> Dict[str, Any]:
    """
    Trace the full execution path from an entry-point class downward through
    INJECTS and CALLS relationships to integration boundaries.

    Args:
        session:         Active Neo4j driver session.
        entry_class_fqn: FQN of the JSF / REST entry class (e.g. 'com.legacy.banking.web.TransferManagedBean').
        max_depth:       Maximum traversal depth for INJECTS edges (default 5).

    Returns a compact, token-budgeted context dictionary:
        sliceId              – entry class FQN
        entryPoint           – {fqn, simpleName, kind, annotations, methods}
        executionPaths       – list of {"path": "A → B → C", "depth": N}
        componentSummary     – ordered list of {fqn, simpleName, role, annotations}
        callFlows            – list of {callerClass, callerMethod, calleeClass, calleeMethod, returnType}
        integrationBoundaries – list of boundary component dicts
        estimatedTokens      – int (approximate LLM token count)
        withinBudget         – bool (True if under MAX_SLICE_TOKENS)
    """
    log.info("[GraphRAG] Extracting vertical slice for: %s (max_depth=%d)",
             entry_class_fqn, max_depth)

    # ── 1. Entry point details ─────────────────────────────────────────────────
    entry_result = session.run(
        """
        MATCH (entry:Class {fqn: $fqn})
        OPTIONAL MATCH (entry)-[:ANNOTATED_WITH]->(a:Annotation)
        OPTIONAL MATCH (entry)-[:DECLARES]->(m:Method)
        RETURN entry.fqn        AS fqn,
               entry.simpleName AS simpleName,
               entry.kind       AS kind,
               collect(DISTINCT a.name)                        AS annotations,
               collect(DISTINCT {name: m.name,
                                 returnType: m.returnType,
                                 signature:  m.signature})     AS methods
        """,
        fqn=entry_class_fqn,
    ).single()

    if not entry_result:
        return {
            "error": f"Entry class '{entry_class_fqn}' not found in graph.",
            "hint":  "Ensure Step 2 ingestion completed successfully.",
        }

    entry = dict(entry_result)
    # Filter out empty method dicts (from OPTIONAL MATCH with no results)
    entry["methods"] = [m for m in entry["methods"] if m.get("name")]

    # ── 2. Traverse INJECTS paths downward ────────────────────────────────────
    path_result = session.run(
        f"""
        MATCH path = (entry:Class {{fqn: $fqn}})-[:INJECTS*1..{max_depth}]->(component:Class)
        WITH path, component,
             [node IN nodes(path) | node.fqn]        AS fqnPath,
             [node IN nodes(path) | node.simpleName] AS namePath
        OPTIONAL MATCH (component)-[:ANNOTATED_WITH]->(ba:Annotation)
        OPTIONAL MATCH (component)-[:DECLARES]->(bm:Method)
        RETURN fqnPath,
               namePath,
               component.fqn        AS componentFqn,
               component.simpleName AS componentSimpleName,
               collect(DISTINCT ba.name)                      AS componentAnnotations,
               collect(DISTINCT {{name:       bm.name,
                                  returnType: bm.returnType}}) AS componentMethods,
               length(path)         AS depth
        ORDER BY depth, component.simpleName
        LIMIT 30
        """,
        fqn=entry_class_fqn,
    )
    paths: List[Dict[str, Any]] = [dict(r) for r in path_result]

    # ── 3. Collect all class FQNs in slice for call-flow query ────────────────
    all_fqns: set[str] = {entry_class_fqn}
    for p in paths:
        all_fqns.update(p.get("fqnPath", []))

    # ── 4. Call flows within the slice ────────────────────────────────────────
    call_result = session.run(
        """
        MATCH (callerClass:Class)-[:DECLARES]->(cm:Method)-[:CALLS]->(tm:Method)
              <-[:DECLARES]-(calleeClass:Class)
        WHERE callerClass.fqn IN $fqns AND calleeClass.fqn IN $fqns
        RETURN callerClass.simpleName AS callerClass,
               cm.name               AS callerMethod,
               calleeClass.simpleName AS calleeClass,
               tm.name               AS calleeMethod,
               tm.returnType         AS returnType
        ORDER BY callerClass.simpleName, cm.name
        LIMIT 50
        """,
        fqns=list(all_fqns),
    )
    call_flows: List[Dict[str, Any]] = [dict(r) for r in call_result]

    # ── 5. Method implementations in the slice ────────────────────────────────
    method_impl_result = session.run(
        """
        MATCH (c:Class)-[:DECLARES]->(m:Method)
        WHERE c.fqn IN $fqns AND m.body IS NOT NULL
        RETURN c.simpleName         AS className,
               m.signature          AS signature,
               m.name               AS name,
               m.returnType         AS returnType,
               m.paramTypes         AS paramTypes,
               m.annotations        AS annotations,
               m.thrownExceptions   AS thrownExceptions,
               m.branchCount        AS branchCount,
               m.body               AS body
        ORDER BY c.simpleName, m.name
        LIMIT 25
        """,
        fqns=list(all_fqns),
    )
    method_implementations: List[Dict[str, Any]] = [dict(r) for r in method_impl_result]

    # ── 6. Identify integration boundaries ────────────────────────────────────
    boundaries = _extract_boundaries(paths)

    # ── 7. Build component summary ────────────────────────────────────────────
    component_summary = _build_component_summary(entry, paths)

    # ── 8. Assemble execution path strings ────────────────────────────────────
    seen_paths: set[str] = set()
    execution_paths: List[Dict[str, Any]] = []
    for p in paths:
        path_str = " → ".join(p.get("namePath", []))
        if path_str not in seen_paths:
            seen_paths.add(path_str)
            execution_paths.append({"path": path_str, "depth": p["depth"]})

    # ── 9. Compile final slice context ────────────────────────────────────────
    slice_context: Dict[str, Any] = {
        "sliceId":               entry_class_fqn,
        "entryPoint":            entry,
        "executionPaths":        execution_paths,
        "componentSummary":      component_summary,
        "callFlows":             call_flows,
        "methodImplementations": method_implementations,
        "integrationBoundaries": boundaries,
    }

    # ── 10. Token budget check ────────────────────────────────────────────────
    estimated_tokens = _estimate_tokens(slice_context)
    slice_context["estimatedTokens"] = estimated_tokens
    slice_context["withinBudget"]    = estimated_tokens <= MAX_SLICE_TOKENS

    if not slice_context["withinBudget"]:
        log.warning(
            "[GraphRAG] Slice for '%s' exceeds token budget: %d > %d. "
            "Consider reducing max_depth.",
            entry_class_fqn, estimated_tokens, MAX_SLICE_TOKENS,
        )
        # Truncate call flows, paths, and implementations to fit budget
        slice_context = _truncate_to_budget(slice_context)

    log.info(
        "[GraphRAG] Slice extracted. Components=%d, CallFlows=%d, Impls=%d, Boundaries=%d, ~%d tokens.",
        len(component_summary), len(call_flows), len(method_implementations), len(boundaries), estimated_tokens,
    )
    return slice_context


# =============================================================================
# Helper Functions
# =============================================================================

def _extract_boundaries(paths: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Identify integration boundary components from traversal paths."""
    seen:       set[str]          = set()
    boundaries: List[Dict[str, Any]] = []

    for p in paths:
        fqn  = p.get("componentFqn", "")
        name = p.get("componentSimpleName", "")
        if fqn in seen:
            continue

        is_boundary = any(fragment in name for fragment in BOUNDARY_NAME_FRAGMENTS)
        if is_boundary:
            seen.add(fqn)
            boundaries.append({
                "fqn":         fqn,
                "simpleName":  name,
                "annotations": p.get("componentAnnotations", []),
                "methods":     [m for m in p.get("componentMethods", []) if m.get("name")],
                "depth":       p["depth"],
                "role":        _infer_role(name, p.get("componentAnnotations", [])),
            })

    return boundaries


def _build_component_summary(
    entry: Dict[str, Any],
    paths: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Build an ordered, deduplicated list of all components in the slice."""
    seen:       set[str]          = set()
    components: List[Dict[str, Any]] = []

    # Entry point first
    seen.add(entry["fqn"])
    components.append({
        "fqn":         entry["fqn"],
        "simpleName":  entry["simpleName"],
        "role":        "ENTRY_POINT",
        "annotations": entry.get("annotations", []),
    })

    # Downstream components (ordered by discovery depth)
    for p in paths:
        fqn  = p.get("componentFqn", "")
        name = p.get("componentSimpleName", "")
        if fqn and fqn not in seen:
            seen.add(fqn)
            components.append({
                "fqn":         fqn,
                "simpleName":  name,
                "role":        _infer_role(name, p.get("componentAnnotations", [])),
                "annotations": p.get("componentAnnotations", []),
            })

    return components


def _infer_role(simple_name: str, annotations: List[str]) -> str:
    """Infer the architectural role of a component from its name and annotations."""
    name_lower = simple_name.lower()
    if any(k in name_lower for k in ("gateway", "adapter", "client", "stub", "sink")):
        return "INTEGRATION_BOUNDARY"
    if any(k in name_lower for k in ("repository", "dao", "repo")):
        return "DATA_ACCESS"
    if any(k in name_lower for k in ("service", "processor", "manager", "handler")):
        return "DOMAIN_SERVICE"
    if any(ann in annotations for ann in ("Stateless", "Service", "Component", "Singleton")):
        return "DOMAIN_SERVICE"
    return "COMPONENT"


def _estimate_tokens(slice_context: Dict[str, Any]) -> int:
    """
    Rough token estimation: ~4 characters per token (GPT-3/4 approximation).
    Used for budget enforcement only, not billing.
    """
    text = str(slice_context)
    return max(1, len(text) // 4)


def _truncate_to_budget(slice_context: Dict[str, Any]) -> Dict[str, Any]:
    """Truncate call flows, execution paths, and method implementations to fit within MAX_SLICE_TOKENS."""
    # Keep top call flows, paths, and method implementations to preserve structure within budget
    slice_context["callFlows"]             = slice_context.get("callFlows", [])[:10]
    slice_context["executionPaths"]        = slice_context.get("executionPaths", [])[:5]
    slice_context["methodImplementations"] = slice_context.get("methodImplementations", [])[:5]
    slice_context["estimatedTokens"]       = _estimate_tokens(slice_context)
    slice_context["truncated"]             = True
    return slice_context


# =============================================================================
# Standalone Verification CLI
# =============================================================================

def _run_verification(uri: str, user: str, password: str, entry_fqn: Optional[str] = None) -> None:
    """
    Verification mode: discovers entry points and prints the vertical slice
    for a given (or auto-discovered) entry class.
    """
    import json as _json
    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("[queries] ERROR: neo4j driver not installed. Run: pip install neo4j")
        return

    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session() as session:
            print("\n[GraphRAG] ── Finding Entry Points ───────────────────────────────")
            entry_points = find_entry_points(session)
            print(f"  Found {len(entry_points)} entry point(s):")
            for ep in entry_points:
                print(f"    • {ep['simpleName']} ({ep['fqn']})")
                print(f"      annotations: {ep['annotations']}")
                print(f"      injects:     {ep['injectedDependencies']}")

            target_fqn = entry_fqn
            if not target_fqn and entry_points:
                target_fqn = entry_points[0]["fqn"]

            if target_fqn:
                print(f"\n[GraphRAG] ── Extracting Vertical Slice for: {target_fqn} ──")
                slice_ctx = extract_vertical_slice(session, target_fqn, max_depth=5)
                print(_json.dumps(slice_ctx, indent=2, default=str))
    finally:
        driver.close()


if __name__ == "__main__":
    import argparse
    import os

    p = argparse.ArgumentParser(description="GraphRAG Slice Verification Query")
    p.add_argument("--uri",      default=os.getenv("NEO4J_URI",      "bolt://localhost:7687"))
    p.add_argument("--user",     default=os.getenv("NEO4J_USER",     "neo4j"))
    p.add_argument("--password", default=os.getenv("NEO4J_PASSWORD", "modernization_secret"))
    p.add_argument("--entry",    default=None, help="FQN of entry class to slice (auto-discovers if omitted)")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")
    _run_verification(args.uri, args.user, args.password, args.entry)
