from __future__ import annotations

import json
import re
from typing import Any

from agent.mcp_client import DiscoveredTool
from policy.models import ToolCall


class DemoPlanner:
    """Small local stand-in for Claude tool selection.

    It uses only discovered tool names and schemas. A real Claude adapter can replace
    this class without changing policy, MCP, approval, or audit boundaries.
    """

    def plan(
        self,
        user_message: str,
        discovered_tools: list[DiscoveredTool],
    ) -> ToolCall | None:
        lower_message = user_message.lower()

        for tool in discovered_tools:
            tokens = set(re.split(r"[_\W]+", tool.name.lower())) - {""}
            direct_name_match = tool.name.lower() in lower_message
            token_match = tokens and all(token in lower_message for token in tokens)

            if direct_name_match or token_match:
                return ToolCall(
                    tool_name=tool.name,
                    server=tool.server,
                    tool_input=self._extract_input(user_message, tool.input_schema),
                )

        return None

    def _extract_input(
        self,
        user_message: str,
        input_schema: dict[str, Any],
    ) -> dict[str, Any]:
        json_payload = self._extract_json_object(user_message)
        if json_payload is not None:
            return json_payload

        properties = input_schema.get("properties", {})
        required = input_schema.get("required", [])
        payload = {}

        for field in required:
            value = self._extract_named_value(user_message, field)
            if value is not None:
                payload[field] = value

        for field in properties:
            if field in payload:
                continue
            value = self._extract_named_value(user_message, field)
            if value is not None:
                payload[field] = value

        return payload

    def _extract_json_object(self, text: str) -> dict[str, Any] | None:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None

        try:
            payload = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None

        return payload if isinstance(payload, dict) else None

    def _extract_named_value(self, text: str, field: str) -> str | None:
        pattern = rf"{re.escape(field)}\s*[:=]\s*['\"]?([^,'\"\n]+)"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None
