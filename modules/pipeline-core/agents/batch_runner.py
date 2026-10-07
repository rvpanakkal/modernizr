"""
Batch Runner for Concurrent Vertical Slice Extraction.
Orchestrates multi-slice extraction workflows using an asyncio semaphore worker pool,
manages batch lifecycle, and persists batch execution states.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import time
import uuid
from typing import Any, Dict, List, Optional

from agents.cognitive_chain import cognitive_chain
from schemas.batch import BatchRunRequest, BatchRunStatus, SliceRunSummary

log = logging.getLogger("BatchRunner")

# Global in-memory registry of batches
BATCHES_REGISTRY: Dict[str, BatchRunStatus] = {}


class BatchRunner:
    """Orchestrates concurrent 3-pass extraction across multiple vertical slices."""

    def __init__(self, concurrency_limit: int = 3, repo_root: Optional[Path] = None) -> None:
        self.concurrency_limit = concurrency_limit
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        if repo_root:
            self.repo_root = repo_root
        else:
            self.repo_root = Path(__file__).resolve().parent.parent

        self.batches_dir = self.repo_root / "artifacts" / "batches"
        self.batches_dir.mkdir(parents=True, exist_ok=True)

    def create_batch(self, request: BatchRunRequest) -> BatchRunStatus:
        """Initializes a new batch with individual QUEUED slice runs."""
        batch_id = f"batch-{uuid.uuid4().hex[:8]}"
        slices: List[SliceRunSummary] = []

        now_utc = datetime.now(timezone.utc)
        for fqn in request.entry_fqns:
            run_id = f"run-{uuid.uuid4().hex[:8]}"
            class_name = fqn.split(".")[-1]
            slices.append(
                SliceRunSummary(
                    run_id=run_id,
                    entry_fqn=fqn,
                    class_name=class_name,
                    status="QUEUED",
                    current_pass=None,
                    tokens_consumed=0,
                    duration_ms=0,
                )
            )

        status_obj = BatchRunStatus(
            batch_id=batch_id,
            total_slices=len(slices),
            completed_slices=0,
            failed_slices=0,
            status="PROCESSING",
            created_at=now_utc,
            slices=slices,
        )

        BATCHES_REGISTRY[batch_id] = status_obj
        self._persist_batch(status_obj)
        log.info("[BatchRunner] Initialized batch %s with %d slices", batch_id, len(slices))
        return status_obj

    def _persist_batch(self, batch: BatchRunStatus) -> None:
        """Persists batch status to artifacts/batches/{batch_id}.json."""
        try:
            batch_file = self.batches_dir / f"{batch.batch_id}.json"
            batch_file.write_text(batch.model_dump_json(indent=2), encoding="utf-8")
        except Exception as exc:
            log.warning("[BatchRunner] Failed to persist batch %s: %s", batch.batch_id, exc)

    async def execute_batch(
        self,
        batch_id: str,
        max_depth: int = 5,
        tracker_type: str = "jira",
        runs_registry_ref: Optional[Dict[str, Any]] = None,
    ) -> BatchRunStatus:
        """
        Executes all slices in the batch under bounded concurrency (Semaphore).
        Updates individual slice states and overall batch completion.
        """
        batch = BATCHES_REGISTRY.get(batch_id)
        if not batch:
            raise ValueError(f"Batch {batch_id} not found.")

        # Register runs in the shared runs registry if reference is passed
        now_iso = datetime.now(timezone.utc).isoformat()
        if runs_registry_ref is not None:
            for s in batch.slices:
                runs_registry_ref[s.run_id] = {
                    "run_id": s.run_id,
                    "entry_fqn": s.entry_fqn,
                    "status": "QUEUED",
                    "created_at": now_iso,
                    "spec_available": False,
                    "sha256_hash": None,
                    "batch_id": batch_id,
                }

        async def _execute_single_slice(slice_summary: SliceRunSummary) -> None:
            async with self.semaphore:
                log.info(
                    "[BatchRunner] Starting slice execution: %s (run: %s)",
                    slice_summary.entry_fqn,
                    slice_summary.run_id,
                )
                slice_summary.status = "RUNNING"
                slice_summary.current_pass = 1

                if runs_registry_ref is not None:
                    runs_registry_ref[slice_summary.run_id]["status"] = "RUNNING"

                self._persist_batch(batch)
                start_time = time.perf_counter()

                try:
                    spec = await cognitive_chain.execute(
                        run_id=slice_summary.run_id,
                        entry_fqn=slice_summary.entry_fqn,
                        max_depth=max_depth,
                        tracker_type=tracker_type,
                    )
                    duration_ms = int((time.perf_counter() - start_time) * 1000)
                    slice_summary.duration_ms = duration_ms
                    slice_summary.status = "COMPLETED"
                    slice_summary.current_pass = 3
                    slice_summary.spec_path = f"artifacts/specs/{slice_summary.run_id}.json"

                    # Estimate token tally
                    slice_summary.tokens_consumed = 2450

                    if runs_registry_ref is not None:
                        runs_registry_ref[slice_summary.run_id]["status"] = "HITL_PENDING"
                        runs_registry_ref[slice_summary.run_id]["spec_available"] = True
                        runs_registry_ref[slice_summary.run_id]["sha256_hash"] = spec.sha256_hash

                    batch.completed_slices += 1
                    log.info(
                        "[BatchRunner] Completed slice %s in %dms",
                        slice_summary.entry_fqn,
                        duration_ms,
                    )

                except Exception as exc:
                    duration_ms = int((time.perf_counter() - start_time) * 1000)
                    slice_summary.duration_ms = duration_ms
                    slice_summary.status = "FAILED"
                    slice_summary.error_message = str(exc)

                    if runs_registry_ref is not None:
                        runs_registry_ref[slice_summary.run_id]["status"] = "FAILED"
                        runs_registry_ref[slice_summary.run_id]["error"] = str(exc)

                    batch.failed_slices += 1
                    log.exception(
                        "[BatchRunner] Slice %s failed after %dms: %s",
                        slice_summary.entry_fqn,
                        duration_ms,
                        exc,
                    )

                finally:
                    # Update aggregate status
                    if batch.completed_slices + batch.failed_slices >= batch.total_slices:
                        if batch.failed_slices == 0:
                            batch.status = "COMPLETED"
                        elif batch.completed_slices > 0:
                            batch.status = "PARTIAL_FAILURE"
                        else:
                            batch.status = "FAILED"
                    else:
                        batch.status = "PROCESSING"

                    self._persist_batch(batch)

        # Launch all slice tasks concurrently governed by semaphore
        await asyncio.gather(*(_execute_single_slice(s) for s in batch.slices))
        self._persist_batch(batch)
        return batch

    def get_batch(self, batch_id: str) -> Optional[BatchRunStatus]:
        """Returns the current batch status from memory or disk."""
        if batch_id in BATCHES_REGISTRY:
            return BATCHES_REGISTRY[batch_id]

        batch_file = self.batches_dir / f"{batch_id}.json"
        if batch_file.exists():
            try:
                data = json.loads(batch_file.read_text(encoding="utf-8"))
                status_obj = BatchRunStatus.model_validate(data)
                BATCHES_REGISTRY[batch_id] = status_obj
                return status_obj
            except Exception as exc:
                log.warning("[BatchRunner] Failed to read batch file %s: %s", batch_file, exc)
        return None

    def list_batches(self) -> List[BatchRunStatus]:
        """Returns list of recent batches sorted newest first."""
        results: Dict[str, BatchRunStatus] = dict(BATCHES_REGISTRY)

        if self.batches_dir.exists():
            for f in self.batches_dir.glob("*.json"):
                b_id = f.stem
                if b_id not in results:
                    try:
                        data = json.loads(f.read_text(encoding="utf-8"))
                        status_obj = BatchRunStatus.model_validate(data)
                        results[b_id] = status_obj
                    except Exception:
                        pass

        sorted_batches = sorted(results.values(), key=lambda b: b.created_at, reverse=True)
        return sorted_batches


# Global singleton instance
batch_runner = BatchRunner()
