from __future__ import annotations

from typing import Any

from policy.honeypot import HONEYPOT_TOOLS
from policy.injection import detect_injection
from policy.models import (
    ACTION_STRICTNESS,
    DefaultPolicy,
    PolicyDecision,
    PolicyOutcome,
    PolicyRule,
    PolicyState,
    RuleAction,
    ToolCall,
)


def evaluate(tool_call: ToolCall, policy_state: PolicyState) -> PolicyDecision:
    # Honeypot check — runs before everything else, cannot be overridden or approved
    if tool_call.tool_name in HONEYPOT_TOOLS:
        return PolicyDecision(
            outcome=PolicyOutcome.HONEYPOT_TRIGGERED,
            reason=f"Honeypot trap triggered: '{tool_call.tool_name}' is a canary tool. "
            "This event has been flagged as a security incident.",
            matched_rules=[],
        )

    injection = detect_injection(tool_call.tool_input)
    if injection.detected:
        return PolicyDecision(
            outcome=PolicyOutcome.INJECTION_DETECTED,
            reason="Tool input matched a prompt-injection pattern.",
            matched_rules=[],
            injection=injection,
        )

    matched_rules = sorted(
        [
            rule
            for rule in policy_state.rules
            if rule.enabled
            and _target_matches(rule, tool_call)
            and _condition_matches(rule, tool_call.tool_input)
        ],
        key=lambda rule: rule.priority,
        reverse=True,
    )

    if not matched_rules:
        if policy_state.default_policy == DefaultPolicy.DENY:
            return PolicyDecision(
                outcome=PolicyOutcome.BLOCK,
                reason="No policy rule matched; default policy is deny.",
                matched_rules=[],
            )

        return PolicyDecision(
            outcome=PolicyOutcome.ALLOW,
            reason="No policy rule matched; default policy is allow.",
            matched_rules=[],
        )

    highest_priority = matched_rules[0].priority
    top_rules = [rule for rule in matched_rules if rule.priority == highest_priority]
    conflict = len({rule.action for rule in top_rules}) > 1

    action = _strictest_action([rule.action for rule in matched_rules])
    selected_rule = next(
        (rule for rule in matched_rules if rule.action == action),
        matched_rules[0],
    )

    return PolicyDecision(
        outcome=_outcome_for_action(action),
        reason=(
            "Conflicting rules at the same priority; stricter action was selected."
            if conflict
            else selected_rule.reason
        ),
        matched_rules=[rule.id for rule in matched_rules],
        conflict=conflict,
    )


def _target_matches(rule: PolicyRule, tool_call: ToolCall) -> bool:
    tool_matches = rule.target.tool == "*" or rule.target.tool == tool_call.tool_name
    server_matches = rule.target.server is None or rule.target.server == tool_call.server
    return tool_matches and server_matches


def _condition_matches(rule: PolicyRule, tool_input: dict[str, Any]) -> bool:
    if rule.condition is None:
        return True

    actual = _get_nested_value(tool_input, rule.condition.input_field)
    expected = rule.condition.value

    if rule.condition.operator == "equals":
        return actual == expected
    if rule.condition.operator == "not_equals":
        return actual != expected
    if rule.condition.operator == "contains":
        return isinstance(actual, str) and str(expected) in actual
    if rule.condition.operator == "not_contains":
        return not isinstance(actual, str) or str(expected) not in actual
    if rule.condition.operator == "starts_with":
        return isinstance(actual, str) and actual.startswith(str(expected))
    if rule.condition.operator == "not_starts_with":
        return not isinstance(actual, str) or not actual.startswith(str(expected))
    if rule.condition.operator == "exists":
        return actual is not None

    return False


def _get_nested_value(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _strictest_action(actions: list[RuleAction]) -> RuleAction:
    return max(actions, key=lambda action: ACTION_STRICTNESS[action])


def _outcome_for_action(action: RuleAction) -> PolicyOutcome:
    if action == RuleAction.BLOCK:
        return PolicyOutcome.BLOCK
    if action == RuleAction.REQUIRE_APPROVAL:
        return PolicyOutcome.REQUIRE_APPROVAL
    return PolicyOutcome.ALLOW
