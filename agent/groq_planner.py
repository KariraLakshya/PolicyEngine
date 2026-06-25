from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

from agent.mcp_client import DiscoveredTool
from policy.models import ToolCall


class GroqPlanner:
    """Uses Groq tool calling to let the model choose MCP tools.

    The planner only proposes a tool call. LangGraph still routes that proposal
    through the policy engine before any MCP execution can happen.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str = "https://api.groq.com/openai/v1",
        timeout_seconds: int = 30,
    ) -> None:
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        self.model = model or os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

        if not self.api_key:
            raise ValueError("GROQ_API_KEY is required to use GroqPlanner.")

    def plan(
        self,
        user_message: str,
        discovered_tools: list[DiscoveredTool],
    ) -> ToolCall | None:
        if not discovered_tools:
            return None

        tools, function_map = self._build_groq_tools(discovered_tools)
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a guarded AI agent. Use the provided tools only when "
                        "they are necessary to satisfy the user's request. If no tool is "
                        "needed, answer normally. Do not invent tool names or arguments."
                    ),
                },
                {"role": "user", "content": user_message},
            ],
            "tools": tools,
            "tool_choice": "auto",
            "temperature": 0,
        }

        response = self._post_chat_completion(payload)
        message = response["choices"][0]["message"]
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            return None

        function = tool_calls[0]["function"]
        function_name = function["name"]
        selected_tool = function_map[function_name]
        arguments = self._parse_arguments(function.get("arguments", "{}"))

        return ToolCall(
            tool_name=selected_tool.name,
            server=selected_tool.server,
            tool_input=arguments,
        )

    def _post_chat_completion(self, payload: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "authorization": f"Bearer {self.api_key}",
                    "content-type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    def _build_groq_tools(
        self,
        discovered_tools: list[DiscoveredTool],
    ) -> tuple[list[dict[str, Any]], dict[str, DiscoveredTool]]:
        duplicate_names = {
            tool.name
            for tool in discovered_tools
            if sum(1 for candidate in discovered_tools if candidate.name == tool.name) > 1
        }

        function_map: dict[str, DiscoveredTool] = {}
        groq_tools = []

        for tool in discovered_tools:
            function_name = (
                self._safe_function_name(f"{tool.server}__{tool.name}")
                if tool.name in duplicate_names
                else self._safe_function_name(tool.name)
            )
            function_map[function_name] = tool
            groq_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": function_name,
                        "description": f"[server: {tool.server}] {tool.description}",
                        "parameters": tool.input_schema,
                    },
                }
            )

        return groq_tools, function_map

    def _safe_function_name(self, value: str) -> str:
        safe = re.sub(r"[^a-zA-Z0-9_-]", "_", value)
        return safe[:64]

    def _parse_arguments(self, arguments: str | dict[str, Any]) -> dict[str, Any]:
        if isinstance(arguments, dict):
            return arguments

        try:
            parsed = json.loads(arguments or "{}")
        except json.JSONDecodeError:
            return {}

        return parsed if isinstance(parsed, dict) else {}
