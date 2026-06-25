from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class PolicyOutcome(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    INJECTION_DETECTED = "INJECTION_DETECTED"
    HONEYPOT_TRIGGERED = "HONEYPOT_TRIGGERED"


class RuleAction(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    REQUIRE_APPROVAL = "require_approval"


class RuleType(str, Enum):
    BLOCK = "block"
    REQUIRE_APPROVAL = "require_approval"
    INPUT_VALIDATION = "input_validation"
    TOKEN_BUDGET = "token_budget"


class DefaultPolicy(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


ACTION_STRICTNESS = {
    RuleAction.ALLOW: 0,
    RuleAction.REQUIRE_APPROVAL: 1,
    RuleAction.BLOCK: 2,
}


@dataclass(frozen=True)
class RuleTarget:
    tool: str
    server: str | None = None


@dataclass(frozen=True)
class RuleCondition:
    input_field: str
    operator: str
    value: Any


@dataclass(frozen=True)
class PolicyRule:
    name: str
    rule_type: RuleType
    target: RuleTarget
    action: RuleAction
    priority: int
    reason: str
    enabled: bool = True
    condition: RuleCondition | None = None
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass(frozen=True)
class ToolCall:
    tool_name: str
    server: str
    tool_input: dict[str, Any]


@dataclass(frozen=True)
class InjectionResult:
    detected: bool
    matched_pattern: str | None = None
    payload_excerpt: str | None = None


@dataclass(frozen=True)
class PolicyDecision:
    outcome: PolicyOutcome
    reason: str
    matched_rules: list[str]
    conflict: bool = False
    injection: InjectionResult | None = None


@dataclass(frozen=True)
class PolicyState:
    rules: list[PolicyRule]
    default_policy: DefaultPolicy = DefaultPolicy.ALLOW
