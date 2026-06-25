from __future__ import annotations

import hashlib
import json
from threading import RLock
from typing import Any

GENESIS_HASH = "0" * 64


class AuditStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._entries: list[dict[str, Any]] = []
        self._last_chain_hash: str = GENESIS_HASH

    def append(self, entry: dict[str, Any]) -> None:
        with self._lock:
            entry_hash = entry.get("entry_hash", "")
            chain_hash = _sha256(self._last_chain_hash + entry_hash)
            entry["chain_hash"] = chain_hash
            self._last_chain_hash = chain_hash
            self._entries.append(entry)

    def list_entries(self, filters: dict[str, str] | None = None) -> list[dict[str, Any]]:
        filters = filters or {}

        with self._lock:
            entries = list(self._entries)

        if filters.get("outcome"):
            entries = [entry for entry in entries if entry["outcome"] == filters["outcome"]]
        if filters.get("tool_name"):
            entries = [
                entry for entry in entries if entry["tool_name"] == filters["tool_name"]
            ]
        if filters.get("server"):
            entries = [entry for entry in entries if entry["server"] == filters["server"]]

        return entries

    def verify_chain(self) -> dict[str, Any]:
        with self._lock:
            entries = list(self._entries)

        prev_chain = GENESIS_HASH
        for i, entry in enumerate(entries):
            # Re-derive entry_hash from all content fields (excluding the two hash fields)
            content = {
                k: v for k, v in entry.items() if k not in ("entry_hash", "chain_hash")
            }
            serialized = json.dumps(content, sort_keys=True, separators=(",", ":"), default=str)
            expected_entry_hash = hashlib.sha256(serialized.encode()).hexdigest()

            if entry.get("entry_hash") != expected_entry_hash:
                return {
                    "valid": False,
                    "broken_at": i,
                    "event_id": entry.get("event_id"),
                    "reason": "entry_hash mismatch — entry content may have been tampered with",
                }

            expected_chain = _sha256(prev_chain + entry["entry_hash"])
            if entry.get("chain_hash") != expected_chain:
                return {
                    "valid": False,
                    "broken_at": i,
                    "event_id": entry.get("event_id"),
                    "reason": "chain_hash mismatch — chain continuity is broken",
                }

            prev_chain = entry["chain_hash"]

        return {
            "valid": True,
            "entries_verified": len(entries),
            "tip": prev_chain,
        }


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()
