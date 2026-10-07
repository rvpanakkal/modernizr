"""
In-memory async SSE event broker for streaming pipeline telemetry.
Supports multiple subscribers per run_id and maintains a recent event buffer.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict, deque
from typing import Any, AsyncGenerator, Dict, List, Set

log = logging.getLogger(__name__)


class EventBus:
    """
    Asynchronous Publish-Subscribe event broker.
    Routes live telemetry, token deltas, pass transitions, and logs to connected SSE clients.
    """

    def __init__(self, history_limit: int = 150) -> None:
        self._subscribers: Dict[str, Set[asyncio.Queue[Dict[str, Any]]]] = defaultdict(set)
        self._history: Dict[str, deque[Dict[str, Any]]] = defaultdict(lambda: deque(maxlen=history_limit))
        self._lock = asyncio.Lock()

    async def publish(
        self,
        run_id: str,
        event_type_or_dict: Any,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Publish an event to all active subscribers for the given run_id.
        Supports both signatures:
          - publish(run_id, event_type="TOKEN_CHUNK", data={"token": chunk})
          - publish(run_id, event={"type": "TOKEN_CHUNK", ...})
        """
        from datetime import datetime, timezone

        if isinstance(event_type_or_dict, str):
            event = {
                "type": event_type_or_dict,
                "run_id": run_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **(data or {}),
            }
        elif isinstance(event_type_or_dict, dict):
            event = dict(event_type_or_dict)
            if "run_id" not in event:
                event["run_id"] = run_id
            if "timestamp" not in event:
                event["timestamp"] = datetime.now(timezone.utc).isoformat()
            if data:
                event.update(data)
        else:
            event = {"type": str(event_type_or_dict), "run_id": run_id, **(data or {})}

        async with self._lock:
            self._history[run_id].append(event)
            queues = list(self._subscribers.get(run_id, set()))

        for q in queues:
            try:
                await q.put(event)
            except Exception as exc:
                log.warning("[EventBus] Failed to enqueue event for run_id %s: %s", run_id, exc)

    async def subscribe(self, run_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Subscribes to events for a specific run_id.
        Immediately yields any past events recorded in the buffer, then yields live events.
        """
        queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()

        async with self._lock:
            # Replay historical events
            past_events: List[Dict[str, Any]] = list(self._history.get(run_id, []))
            self._subscribers[run_id].add(queue)

        try:
            # First replay existing events so UI is in sync
            for past_evt in past_events:
                yield past_evt
                if past_evt.get("type") in ("EXTRACTION_COMPLETE", "PIPELINE_ERROR", "STREAM_CLOSED"):
                    return

            # Now stream live events
            while True:
                event = await queue.get()
                yield event
                event_type = event.get("type", "")
                if event_type in ("EXTRACTION_COMPLETE", "PIPELINE_ERROR", "STREAM_CLOSED"):
                    break
        except asyncio.CancelledError:
            log.info("[EventBus] Client disconnected from run_id: %s", run_id)
            raise
        finally:
            async with self._lock:
                if run_id in self._subscribers and queue in self._subscribers[run_id]:
                    self._subscribers[run_id].remove(queue)
                    if not self._subscribers[run_id]:
                        del self._subscribers[run_id]

    def get_history(self, run_id: str) -> List[Dict[str, Any]]:
        """Returns the current buffered event history for a run."""
        return list(self._history.get(run_id, []))


# Global singleton instance
event_bus = EventBus()
