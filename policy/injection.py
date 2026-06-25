from __future__ import annotations

import re
from typing import Any

from policy.models import InjectionResult


INJECTION_PATTERNS = [
    r"ignore (all |previous |prior )?instructions",
    r"you are now",
    r"new system prompt",
    r"disregard (your |all )?rules",
    r"override (policy|guardrail|rule)",
    r"pretend you (are|have no)",
    r"jailbreak",
    r"DAN mode",
]


def _flatten_string_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]

    if isinstance(value, dict):
        strings: list[str] = []
        for item in value.values():
            strings.extend(_flatten_string_values(item))
        return strings

    if isinstance(value, list):
        strings = []
        for item in value:
            strings.extend(_flatten_string_values(item))
        return strings

    return []


def detect_injection(tool_input: dict[str, Any]) -> InjectionResult:
    payload = " ".join(_flatten_string_values(tool_input))

    for pattern in INJECTION_PATTERNS:
        match = re.search(pattern, payload, flags=re.IGNORECASE)
        if match:
            start = max(0, match.start() - 30)
            end = min(len(payload), match.end() + 30)
            return InjectionResult(
                detected=True,
                matched_pattern=pattern,
                payload_excerpt=payload[start:end],
            )

    return InjectionResult(detected=False)
