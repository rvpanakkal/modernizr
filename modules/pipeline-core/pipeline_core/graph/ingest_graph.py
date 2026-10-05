"""
Pipeline Step 2A — Neo4j Graph Ingestion
=========================================
Reads the LSTExportPayload JSON produced by ExtractorCli (Step 1),
validates it with Pydantic, and ingests it into Neo4j using idempotent
MERGE + batched UNWIND Cypher queries.

Emits a StepHandoffReceipt JSON upon completion.

CLI Usage:
    python -m pipeline_core.graph.ingest_graph \\
        --input artifacts/raw_lst/metadata_extracted.json \\
        --uri bolt://localhost:7687 \\
        --user neo4j \\
        --password modernization_secret \\
        --receipt-out artifacts/receipts/step2_receipt.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from pipeline_core.schemas.handoff import (
    ArtifactPointer,
    ArtifactType,
    ClassRecord,
    ExecutionStatus,
    LSTExportPayload,
    StepHandoffReceipt,
)

try:
    from neo4j import GraphDatabase, exceptions as neo4j_exc
    HAS_NEO4J = True
except ImportError:
    HAS_NEO4J = False

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)


# =============================================================================
# Neo4j Graph Ingestor
# =============================================================================

class Neo4jGraphIngestor:
    """
    Idempotent Neo4j ingestor for LST metadata.

    Graph schema:
        Nodes:          (:Class), (:Method), (:Annotation)
        Relationships:  (:Class)-[:DECLARES]->(:Method)
                        (:Class)-[:INJECTS]->(:Class)
                        (:Class)-[:ANNOTATED_WITH]->(:Annotation)
                        (:Method)-[:CALLS]->(:Method)
    """

    def __init__(
        self,
        uri:      Optional[str] = None,
        user:     Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        if not HAS_NEO4J:
            raise RuntimeError(
                "neo4j Python driver is not installed. "
                "Run: pip install neo4j  (or: poetry install)"
            )
        self.uri      = uri      or os.getenv("NEO4J_URI",      "bolt://localhost:7687")
        self.user     = user     or os.getenv("NEO4J_USER",     "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "modernization_secret")
        self.driver   = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        log.info("[Ingestor] Connected to Neo4j at %s", self.uri)

    def close(self) -> None:
        self.driver.close()

    # ── Public API ────────────────────────────────────────────────────────────

    def ingest(self, payload: LSTExportPayload) -> Dict[str, int]:
        """
        Main ingestion entry point.
        Returns a metrics dict with node and relationship counts.
        """
        metrics: Dict[str, int] = {
            "classes": 0, "methods": 0, "annotations": 0,
            "declares_edges": 0, "injects_edges": 0,
            "annotated_with_edges": 0, "calls_edges": 0,
        }

        with self.driver.session() as session:
            # ── 1. Idempotent schema setup ────────────────────────────────────
            self._setup_schema(session)

            # ── 2. Batch-ingest Class nodes ───────────────────────────────────
            n = self._ingest_class_nodes(session, payload.classes)
            metrics["classes"] = n

            # ── 3. Batch-ingest Annotation nodes + ANNOTATED_WITH edges ───────
            na, naw = self._ingest_annotations(session, payload.classes)
            metrics["annotations"]          = na
            metrics["annotated_with_edges"] = naw

            # ── 4. Batch-ingest Method nodes + DECLARES edges ─────────────────
            nm, nd = self._ingest_methods(session, payload.classes)
            metrics["methods"]        = nm
            metrics["declares_edges"] = nd

            # ── 5. Batch-ingest INJECTS edges (field injections) ──────────────
            ni = self._ingest_injection_edges(session, payload.classes)
            metrics["injects_edges"] = ni

            # ── 6. Batch-ingest CALLS edges (method invocations) ──────────────
            nc = self._ingest_call_edges(session, payload.classes)
            metrics["calls_edges"] = nc

        log.info(
            "[Ingestor] Ingestion complete. Metrics: %s", metrics
        )
        return metrics

    # ── Schema Setup (Idempotent) ─────────────────────────────────────────────

    def _setup_schema(self, session) -> None:
        """Create uniqueness constraints and indexes if they don't already exist."""
        log.info("[Ingestor] Setting up Neo4j constraints and indexes …")
        ddl_statements = [
            # Constraints
            "CREATE CONSTRAINT class_fqn_unique IF NOT EXISTS "
            "FOR (c:Class) REQUIRE c.fqn IS UNIQUE",

            "CREATE CONSTRAINT method_sig_unique IF NOT EXISTS "
            "FOR (m:Method) REQUIRE m.signature IS UNIQUE",

            "CREATE CONSTRAINT annotation_name_unique IF NOT EXISTS "
            "FOR (a:Annotation) REQUIRE a.name IS UNIQUE",

            # Lookup indexes
            "CREATE INDEX class_simple_name IF NOT EXISTS "
            "FOR (c:Class) ON (c.simpleName)",

            "CREATE INDEX method_name IF NOT EXISTS "
            "FOR (m:Method) ON (m.name)",
        ]
        for stmt in ddl_statements:
            try:
                session.run(stmt)
            except Exception as e:
                log.debug("[Ingestor] Schema stmt skipped (may already exist): %s", e)

    # ── Node Ingestion ────────────────────────────────────────────────────────

    def _ingest_class_nodes(self, session, classes: List[ClassRecord]) -> int:
        """MERGE :Class nodes with fqn, simpleName, kind."""
        batch = [
            {"fqn": c.fqn, "simpleName": c.simple_name, "kind": c.kind}
            for c in classes
        ]
        session.run(
            """
            UNWIND $batch AS cls
            MERGE (c:Class {fqn: cls.fqn})
            SET   c.simpleName = cls.simpleName,
                  c.kind       = cls.kind
            """,
            batch=batch,
        )
        log.info("[Ingestor] ✓ %d Class nodes merged.", len(batch))
        return len(batch)

    def _ingest_annotations(self, session, classes: List[ClassRecord]):
        """MERGE :Annotation nodes and (:Class)-[:ANNOTATED_WITH]->(:Annotation) edges."""
        items: List[Dict[str, str]] = []
        for c in classes:
            for ann in c.annotations:
                items.append({"classFqn": c.fqn, "annotation": ann})

        if not items:
            return 0, 0

        session.run(
            """
            UNWIND $items AS item
            MERGE (a:Annotation {name: item.annotation})
            WITH  a, item
            MATCH (c:Class {fqn: item.classFqn})
            MERGE (c)-[:ANNOTATED_WITH]->(a)
            """,
            items=items,
        )
        unique_annotations = len({i["annotation"] for i in items})
        log.info(
            "[Ingestor] ✓ %d Annotation nodes, %d ANNOTATED_WITH edges.",
            unique_annotations, len(items),
        )
        return unique_annotations, len(items)

    def _ingest_methods(self, session, classes: List[ClassRecord]):
        """MERGE :Method nodes and (:Class)-[:DECLARES]->(:Method) edges."""
        batch: List[Dict[str, Any]] = []
        for c in classes:
            for m in c.methods:
                sig = m.signature or f"{c.fqn}.{m.name}({','.join(m.parameter_types)})"
                batch.append({
                    "classFqn":         c.fqn,
                    "name":             m.name,
                    "returnType":       m.return_type,
                    "signature":        sig,
                    "paramTypes":       m.parameter_types,
                    "annotations":      m.annotations,
                    "thrownExceptions": m.thrown_exceptions,
                    "branchCount":      m.branch_count,
                    "body":             m.body_source,
                })

        if not batch:
            return 0, 0

        session.run(
            """
            UNWIND $batch AS meth
            MERGE (m:Method {signature: meth.signature})
            SET   m.name             = meth.name,
                  m.returnType       = meth.returnType,
                  m.paramTypes       = meth.paramTypes,
                  m.annotations      = meth.annotations,
                  m.thrownExceptions = meth.thrownExceptions,
                  m.branchCount      = meth.branchCount,
                  m.body             = meth.body
            WITH  m, meth
            MATCH (c:Class {fqn: meth.classFqn})
            MERGE (c)-[:DECLARES]->(m)
            """,
            batch=batch,
        )
        log.info("[Ingestor] ✓ %d Method nodes merged with DECLARES edges.", len(batch))
        return len(batch), len(batch)

    # ── Relationship Ingestion ────────────────────────────────────────────────

    def _ingest_injection_edges(self, session, classes: List[ClassRecord]) -> int:
        """
        Create (:Class)-[:INJECTS {annotation, fieldName}]->(:Class) edges.
        Target :Class nodes are MERGE-created if they don't yet exist (e.g., external libs).
        """
        items: List[Dict[str, Any]] = []
        for c in classes:
            for f in c.fields:
                target_fqn = f.type_fqn or f.type
                items.append({
                    "fromFqn":    c.fqn,
                    "toFqn":      target_fqn,
                    "toSimple":   f.type,
                    "annotation": f.annotation,
                    "fieldName":  f.name,
                })

        if not items:
            return 0

        session.run(
            """
            UNWIND $items AS item
            MATCH  (from:Class {fqn: item.fromFqn})
            MERGE  (to:Class   {fqn: item.toFqn})
            ON CREATE SET to.simpleName = item.toSimple
            MERGE  (from)-[:INJECTS {annotation: item.annotation, fieldName: item.fieldName}]->(to)
            """,
            items=items,
        )
        log.info("[Ingestor] ✓ %d INJECTS edges merged.", len(items))
        return len(items)

    def _ingest_call_edges(self, session, classes: List[ClassRecord]) -> int:
        """
        Create (:Method)-[:CALLS]->(:Method) edges from method invocation records.
        Both caller and target Method/Class nodes are MERGE-created as needed.
        """
        items: List[Dict[str, Any]] = []
        for c in classes:
            for inv in c.invocations:
                if inv.target_class_fqn == "<unresolved>":
                    continue  # skip unresolvable invocations
                # Build a deterministic signature for the target method
                target_sig = (
                    f"{inv.target_class_fqn}.{inv.target_method_name}"
                    f"({','.join(inv.argument_types)})"
                )
                # Find the caller method signature from methods list
                caller_method = next(
                    (m for m in c.methods if m.name == inv.caller_method_name), None
                )
                caller_sig = (
                    caller_method.signature
                    if caller_method and caller_method.signature
                    else f"{c.fqn}.{inv.caller_method_name}()"
                )
                items.append({
                    "callerClassFqn":      c.fqn,
                    "callerSig":           caller_sig,
                    "targetClassFqn":      inv.target_class_fqn,
                    "targetClassSimple":   inv.target_class_fqn.split(".")[-1],
                    "targetMethodName":    inv.target_method_name,
                    "targetSig":           target_sig,
                    "returnType":          inv.return_type,
                    "argTypes":            inv.argument_types,
                })

        if not items:
            return 0

        session.run(
            """
            UNWIND $items AS item
            // Ensure target class exists
            MERGE (targetClass:Class {fqn: item.targetClassFqn})
            ON CREATE SET targetClass.simpleName = item.targetClassSimple
            // Ensure target method exists
            MERGE (targetMethod:Method {signature: item.targetSig})
            ON CREATE SET targetMethod.name       = item.targetMethodName,
                          targetMethod.returnType = item.returnType,
                          targetMethod.paramTypes = item.argTypes
            MERGE (targetClass)-[:DECLARES]->(targetMethod)
            // Create CALLS edge between caller method and target method
            WITH targetMethod, item
            MATCH (callerMethod:Method {signature: item.callerSig})
            MERGE (callerMethod)-[:CALLS]->(targetMethod)
            """,
            items=items,
        )
        log.info("[Ingestor] ✓ %d CALLS edges merged.", len(items))
        return len(items)


# =============================================================================
# CLI Entry Point
# =============================================================================

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Pipeline Step 2: Ingest LST JSON metadata into Neo4j graph database.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--input", "-i",
        required=True,
        help="Path to the metadata_extracted.json file from Step 1.",
    )
    p.add_argument(
        "--uri",
        default=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        help="Neo4j Bolt URI.",
    )
    p.add_argument(
        "--user",
        default=os.getenv("NEO4J_USER", "neo4j"),
        help="Neo4j username.",
    )
    p.add_argument(
        "--password",
        default=os.getenv("NEO4J_PASSWORD", "modernization_secret"),
        help="Neo4j password.",
    )
    p.add_argument(
        "--receipt-out",
        default="artifacts/receipts/step2_receipt.json",
        help="Output path for the StepHandoffReceipt JSON.",
    )
    p.add_argument(
        "--jira-id",
        default="MOD-001",
        help="Jira story ID to embed in the receipt (e.g. MOD-101).",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    log.info("[Ingestor] ── Pipeline Step 2: Neo4j Graph Ingestion ─────────────────")
    started_at = datetime.now(timezone.utc)

    # ── 1. Load & validate JSON ────────────────────────────────────────────────
    input_path = Path(args.input)
    if not input_path.exists():
        log.error("[Ingestor] Input file not found: %s", input_path)
        sys.exit(1)

    log.info("[Ingestor] Loading LST JSON: %s", input_path)
    with open(input_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    try:
        payload = LSTExportPayload.model_validate(raw)
        log.info(
            "[Ingestor] ✓ Payload validated. Schema=%s, Classes=%d",
            payload.schema_version, len(payload.classes),
        )
    except ValidationError as exc:
        log.error("[Ingestor] JSON validation failed:\n%s", exc)
        sys.exit(1)

    # ── 2. Build input artifact pointer ───────────────────────────────────────
    input_pointer = ArtifactPointer.create_from_file(
        str(input_path), ArtifactType.RAW_LST_JSON
    )

    # ── 3. Run ingestion ───────────────────────────────────────────────────────
    ingestor = Neo4jGraphIngestor(uri=args.uri, user=args.user, password=args.password)
    metrics: Dict[str, int] = {}
    error_message: Optional[str] = None
    status = ExecutionStatus.COMPLETED

    try:
        metrics = ingestor.ingest(payload)
    except Exception as exc:
        log.error("[Ingestor] Fatal ingestion error: %s", exc)
        error_message = str(exc)
        status = ExecutionStatus.FAILED
    finally:
        ingestor.close()

    # ── 4. Emit StepHandoffReceipt ────────────────────────────────────────────
    completed_at  = datetime.now(timezone.utc)
    duration_ms   = int((completed_at - started_at).total_seconds() * 1000)

    receipt_data  = json.dumps({"step": 2, "metrics": metrics}, sort_keys=True)
    output_pointer = ArtifactPointer.create_from_content(
        content=receipt_data,
        uri=args.receipt_out,
        artifact_type=ArtifactType.GRAPH_NODE_EXPORT,
    )

    receipt = StepHandoffReceipt(
        receipt_id      = str(uuid.uuid4()),
        step_number     = 2,
        step_name       = "Neo4j Graph Ingestion",
        jira_story_id   = args.jira_id,
        input_pointers  = [input_pointer],
        output_pointers = [output_pointer],
        status          = status,
        started_at      = started_at,
        completed_at    = completed_at,
        duration_ms     = duration_ms,
        error_message   = error_message,
        metrics         = metrics,
    )

    receipt_path = Path(args.receipt_out)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    with open(receipt_path, "w", encoding="utf-8") as f:
        f.write(receipt.model_dump_json(indent=2, by_alias=False))

    log.info("[Ingestor] ✓ Receipt written to: %s", receipt_path)
    log.info("[Ingestor] ── Step 2 %s ─────────────────────────────────────────────", status.value)

    if status == ExecutionStatus.FAILED:
        sys.exit(1)


if __name__ == "__main__":
    main()
