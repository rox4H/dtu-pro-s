from __future__ import annotations

import copy
import threading


class StateStore:
    """Publish complete samples atomically for cheap, read-only API snapshots."""

    def __init__(self):
        self._lock = threading.RLock()
        self._state: dict = {}

    def set(self, state: dict) -> None:
        # Polling builds a fresh dict each cycle and never mutates it afterwards.
        with self._lock:
            self._state = state

    def read(self) -> dict:
        """Return the current immutable-by-convention sample without copying it.

        The HTTP server only serializes this object. Writers replace the root
        dictionary instead of mutating a published sample, so readers never
        need to deep-copy a large inverter list for small endpoints.
        """
        with self._lock:
            return self._state

    def snapshot(self) -> dict:
        """Return an independent copy for callers that need to mutate the data."""
        with self._lock:
            return copy.deepcopy(self._state)

    def mark_error(self, exc: Exception) -> None:
        with self._lock:
            state = dict(self._state)
            state["status"] = "error"
            state["error"] = str(exc)
            self._state = state
