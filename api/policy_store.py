from __future__ import annotations

from dataclasses import asdict
from threading import RLock
from typing import Any

from policy.models import (
    DefaultPolicy,
    PolicyRule,
    PolicyState,
    RuleAction,
    RuleCondition,
    RuleTarget,
    RuleType,
)


class PolicyStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._version = 1
        self._default_policy = DefaultPolicy.ALLOW
        self._rules: list[PolicyRule] = []

    @property
    def version(self) -> int:
        with self._lock:
            return self._version

    def state(self) -> PolicyState:
        with self._lock:
            return PolicyState(
                rules=list(self._rules),
                default_policy=self._default_policy,
            )

    def list_rules(self) -> list[dict[str, Any]]:
        with self._lock:
            return [self._serialize_rule(rule) for rule in self._rules]

    def upsert_rule(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            rule = self._parse_rule(payload)
            self._rules = [item for item in self._rules if item.id != rule.id]
            self._rules.append(rule)
            self._version += 1
            return self._serialize_rule(rule)

    def delete_rule(self, rule_id: str) -> bool:
        with self._lock:
            before = len(self._rules)
            self._rules = [rule for rule in self._rules if rule.id != rule_id]
            deleted = len(self._rules) != before
            if deleted:
                self._version += 1
            return deleted

    def settings(self) -> dict[str, Any]:
        with self._lock:
            return {
                "version": self._version,
                "default_policy": self._default_policy.value,
            }

    def update_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            if "default_policy" in payload:
                self._default_policy = DefaultPolicy(payload["default_policy"])
            self._version += 1
            return self.settings()

    def _parse_rule(self, payload: dict[str, Any]) -> PolicyRule:
        target = payload.get("target", {})
        condition_payload = payload.get("condition")
        condition = None

        if condition_payload:
            condition = RuleCondition(
                input_field=condition_payload["input_field"],
                operator=condition_payload["operator"],
                value=condition_payload.get("value"),
            )

        return PolicyRule(
            id=payload.get("id") or PolicyRule.__dataclass_fields__["id"].default_factory(),
            name=payload["name"],
            rule_type=RuleType(payload.get("type", payload["action"])),
            target=RuleTarget(
                tool=target.get("tool", "*"),
                server=target.get("server"),
            ),
            condition=condition,
            action=RuleAction(payload["action"]),
            priority=int(payload.get("priority", 0)),
            enabled=bool(payload.get("enabled", True)),
            created_at=payload.get("created_at")
            or PolicyRule.__dataclass_fields__["created_at"].default_factory(),
            reason=payload.get("reason", "Matched policy rule."),
        )

    def _serialize_rule(self, rule: PolicyRule) -> dict[str, Any]:
        data = asdict(rule)
        data["type"] = rule.rule_type.value
        data.pop("rule_type", None)
        data["action"] = rule.action.value
        data["target"] = asdict(rule.target)
        data["condition"] = asdict(rule.condition) if rule.condition else None
        return data
