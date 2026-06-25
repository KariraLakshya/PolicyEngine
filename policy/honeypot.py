from __future__ import annotations

# Tool names that are permanently trapped. Any call to these fires a
# HONEYPOT_TRIGGERED event regardless of policy rules or approvals.
# They are discoverable via MCP so an attacker or injected prompt can see
# them — the trap only springs at execution time.
HONEYPOT_TOOLS: frozenset[str] = frozenset(
    {
        "escalate_privileges",
        "exfiltrate_data",
    }
)
