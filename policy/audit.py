from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from policy.models import PolicyDecision, ToolCall


def build_audit_entry(
    *,
    conversation_id: str,
    tool_call: ToolCall,
    decision: PolicyDecision,
    token_count: int = 0,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "event_id": str(uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "conversation_id": conversation_id,
        "tool_name": tool_call.tool_name,
        "server": tool_call.server,
        "tool_input": tool_call.tool_input,
        "matched_rules": decision.matched_rules,
        "outcome": decision.outcome.value,
        "reason": decision.reason,
        "token_count": token_count,
    }
    # entry_hash covers all content fields; chain_hash is added by AuditStore
    entry["entry_hash"] = _sha256_dict(entry)
    return entry


def _sha256_dict(data: dict[str, Any]) -> str:
    serialized = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()
