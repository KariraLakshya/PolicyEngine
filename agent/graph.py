from __future__ import annotations

from typing import Any, Literal, TypedDict

from langgraph.graph import END, StateGraph

from agent.conversation import Conversation
from agent.mcp_client import DiscoveredTool, MCPClient
from agent.planner import DemoPlanner
from api.approvals import ApprovalQueue
from api.audit_store import AuditStore
from api.policy_store import PolicyStore
from policy.audit import build_audit_entry
from policy.engine import evaluate
from policy.models import PolicyDecision, PolicyOutcome, ToolCall


class AgentGraphState(TypedDict, total=False):
    conversation: Conversation
    user_message: str
    discovered_tools: list[DiscoveredTool]
    tool_call: ToolCall | None
    decision: PolicyDecision | None
    response: str
    tool_result: dict[str, Any]
    policy_outcome: str | None
    approval_reason: str | None


class AgentGraphRunner:
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
        self.policy_store = policy_store
        self.approval_queue = approval_queue
        self.audit_store = audit_store
        self.planner = planner or DemoPlanner()
        self.graph = self._build_graph()

    def run(
        self,
        *,
        conversation: Conversation,
        user_message: str,
        discovered_tools: list[DiscoveredTool],
    ) -> dict[str, Any]:
        final_state = self.graph.invoke(
            {
                "conversation": conversation,
                "user_message": user_message,
                "discovered_tools": discovered_tools,
            }
        )

        tool_call = final_state.get("tool_call")
        return {
            "conversation": conversation.to_dict(),
            "response": final_state["response"],
            "tool_call": self._tool_call_dict(tool_call) if tool_call else None,
            "tool_result": final_state.get("tool_result"),
            "policy_outcome": final_state.get("policy_outcome"),
        }

    def _build_graph(self):
        graph = StateGraph(AgentGraphState)
        graph.add_node("plan_tool_call", self._plan_tool_call)
        graph.add_node("finish_without_tool", self._finish_without_tool)
        graph.add_node("evaluate_policy", self._evaluate_policy)
        graph.add_node("wait_for_approval", self._wait_for_approval)
        graph.add_node("execute_tool", self._execute_tool)
        graph.add_node("reject_tool_call", self._reject_tool_call)

        graph.set_entry_point("plan_tool_call")
        graph.add_conditional_edges(
            "plan_tool_call",
            self._route_after_planning,
            {
                "no_tool": "finish_without_tool",
                "tool_call": "evaluate_policy",
            },
        )
        graph.add_conditional_edges(
            "evaluate_policy",
            self._route_after_policy,
            {
                "allow": "execute_tool",
                "approval": "wait_for_approval",
                "reject": "reject_tool_call",
            },
        )
        graph.add_conditional_edges(
            "wait_for_approval",
            self._route_after_approval,
            {
                "approved": "execute_tool",
                "denied": "reject_tool_call",
            },
        )
        graph.add_edge("finish_without_tool", END)
        graph.add_edge("execute_tool", END)
        graph.add_edge("reject_tool_call", END)
        return graph.compile()

    def _plan_tool_call(self, state: AgentGraphState) -> AgentGraphState:
        tool_call = self.planner.plan(
            state["user_message"],
            state["discovered_tools"],
        )
        return {"tool_call": tool_call}

    def _finish_without_tool(self, state: AgentGraphState) -> AgentGraphState:
        response = "No tool call was needed."
        state["conversation"].add_message("assistant", response)
        return {"response": response, "policy_outcome": None}

    def _evaluate_policy(self, state: AgentGraphState) -> AgentGraphState:
        tool_call = state["tool_call"]
        if tool_call is None:
            raise RuntimeError("Policy evaluation requires a tool call.")

        conversation = state["conversation"]
        decision = evaluate(tool_call, self.policy_store.state())
        self.audit_store.append(
            build_audit_entry(
                conversation_id=conversation.id,
                tool_call=tool_call,
                decision=decision,
                token_count=conversation.token_count(),
            )
        )
        return {"decision": decision, "policy_outcome": decision.outcome.value}

    def _wait_for_approval(self, state: AgentGraphState) -> AgentGraphState:
        conversation = state["conversation"]
        tool_call = state["tool_call"]
        decision = state["decision"]
        if tool_call is None or decision is None:
            raise RuntimeError("Approval requires a tool call and policy decision.")

        approval = self.approval_queue.enqueue(
            conversation_id=conversation.id,
            tool_call=self._tool_call_dict(tool_call),
            context_snippet=conversation.context_snippet(),
        )
        conversation.paused = True
        conversation.waiting_approval_id = approval.id

        approval_decision = self.approval_queue.wait_for_decision(approval.id)
        conversation.paused = False
        conversation.waiting_approval_id = None

        return {
            "policy_outcome": "ALLOW" if approval_decision == "approved" else "APPROVAL_DENIED",
            "approval_reason": decision.reason,
        }

    def _execute_tool(self, state: AgentGraphState) -> AgentGraphState:
        tool_call = state["tool_call"]
        if tool_call is None:
            raise RuntimeError("Tool execution requires a tool call.")

        result = self.mcp_client.call_tool(
            tool_call.tool_name, tool_call.tool_input, tool_call.server
        )
        state["conversation"].add_message(
            "tool",
            str(result),
            {"tool_name": tool_call.tool_name, "server": tool_call.server},
        )
        response = f"Tool executed: {tool_call.tool_name}"
        state["conversation"].add_message("assistant", response)
        return {
            "response": response,
            "tool_result": result,
            "policy_outcome": "ALLOW",
        }

    def _reject_tool_call(self, state: AgentGraphState) -> AgentGraphState:
        tool_call = state["tool_call"]
        decision = state.get("decision")
        policy_outcome = state.get("policy_outcome") or "BLOCK"

        if tool_call is None:
            raise RuntimeError("Rejection requires a tool call.")

        if policy_outcome == "APPROVAL_DENIED":
            reason = state.get("approval_reason") or "Approval was denied."
            response = f"Tool call denied by approval workflow: {reason}"
        else:
            reason = decision.reason if decision else "Tool call rejected."
            response = f"Tool call rejected by policy: {reason}"

        state["conversation"].add_message(
            "tool",
            response,
            {"outcome": policy_outcome, "tool_name": tool_call.tool_name},
        )
        state["conversation"].add_message("assistant", response)
        return {"response": response, "policy_outcome": policy_outcome}

    def _route_after_planning(
        self,
        state: AgentGraphState,
    ) -> Literal["no_tool", "tool_call"]:
        return "tool_call" if state.get("tool_call") else "no_tool"

    def _route_after_policy(
        self,
        state: AgentGraphState,
    ) -> Literal["allow", "approval", "reject"]:
        decision = state.get("decision")
        if decision is None:
            return "reject"
        if decision.outcome == PolicyOutcome.ALLOW:
            return "allow"
        if decision.outcome == PolicyOutcome.REQUIRE_APPROVAL:
            return "approval"
        return "reject"

    def _route_after_approval(
        self,
        state: AgentGraphState,
    ) -> Literal["approved", "denied"]:
        return "approved" if state.get("policy_outcome") == "ALLOW" else "denied"

    def _tool_call_dict(self, tool_call: ToolCall) -> dict[str, Any]:
        return {
            "tool_name": tool_call.tool_name,
            "server": tool_call.server,
            "tool_input": tool_call.tool_input,
        }
