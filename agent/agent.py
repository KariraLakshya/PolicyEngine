from __future__ import annotations

import os
from typing import Any

from agent.conversation import Conversation
from agent.graph import AgentGraphRunner
from agent.groq_planner import GroqPlanner
from agent.mcp_client import MCPClient
from agent.planner import DemoPlanner
from api.approvals import ApprovalQueue
from api.audit_store import AuditStore
from api.policy_store import PolicyStore


class AgentHost:
    def __init__(
        self,
        *,
        mcp_client: MCPClient,
        policy_store: PolicyStore,
        approval_queue: ApprovalQueue,
        audit_store: AuditStore,
        planner: Any | None = None,
    ) -> None:
        self.mcp_client = mcp_client
        selected_planner = planner or self._default_planner()
        self.graph_runner = AgentGraphRunner(
            mcp_client=mcp_client,
            policy_store=policy_store,
            approval_queue=approval_queue,
            audit_store=audit_store,
            planner=selected_planner,
        )
        self._tools = []
        self._conversations: dict[str, Conversation] = {}

    def refresh_tools(self) -> list[dict[str, Any]]:
        self._tools = self.mcp_client.discover_tools()
        return [tool.__dict__ for tool in self._tools]

    def tools(self) -> list[dict[str, Any]]:
        if not self._tools:
            self.refresh_tools()
        return [tool.__dict__ for tool in self._tools]

    def start_conversation(self) -> Conversation:
        conversation = Conversation()
        self._conversations[conversation.id] = conversation
        return conversation

    def get_conversation(self, conversation_id: str) -> Conversation:
        return self._conversations[conversation_id]

    def send_message(
        self,
        user_message: str,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        conversation = (
            self.get_conversation(conversation_id)
            if conversation_id
            else self.start_conversation()
        )
        conversation.add_message("user", user_message)

        if not self._tools:
            self.refresh_tools()

        return self.graph_runner.run(
            conversation=conversation,
            user_message=user_message,
            discovered_tools=self._tools,
        )

    def _default_planner(self):
        if os.environ.get("GROQ_API_KEY"):
            return GroqPlanner()
        return DemoPlanner()
