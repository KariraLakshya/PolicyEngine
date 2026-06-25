from __future__ import annotations

from dataclasses import dataclass

from policy.models import PolicyRule


@dataclass(frozen=True)
class RuleConflict:
    target: str
    rule_ids: list[str]
    actions: list[str]


def detect_conflicts(rules: list[PolicyRule]) -> list[RuleConflict]:
    grouped: dict[str, list[PolicyRule]] = {}

    for rule in rules:
        if not rule.enabled:
            continue

        server = rule.target.server or "*"
        target = f"{server}:{rule.target.tool}"
        grouped.setdefault(target, []).append(rule)

    conflicts = []
    for target, group in grouped.items():
        if len(group) <= 1:
            continue

        conflicts.append(
            RuleConflict(
                target=target,
                rule_ids=[rule.id for rule in group],
                actions=sorted({rule.action.value for rule in group}),
            )
        )

    return conflicts
