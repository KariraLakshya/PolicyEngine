import threading
import time
import unittest

from agent.agent import AgentHost
from agent.mcp_client import DiscoveredTool
from api.approvals import ApprovalQueue
from api.audit_store import AuditStore
from api.policy_store import PolicyStore
from policy.models import RuleAction


class FakeMCPClient:
    def __init__(self):
        self.calls = []

    def discover_tools(self):
        return [
            DiscoveredTool(
                server="fake-server",
                name="danger_action",
                description="A risky fake action.",
                input_schema={
                    "type": "object",
                    "properties": {"id": {"type": "string"}},
                    "required": ["id"],
                    "additionalProperties": False,
                },
            )
        ]

    def call_tool(self, tool_name, tool_input):
        self.calls.append((tool_name, tool_input))
        return {"ok": True, "tool_name": tool_name, "input": tool_input}


class SpyPolicyStore(PolicyStore):
    def __init__(self, mcp_client):
        super().__init__()
        self.mcp_client = mcp_client
        self.evaluated_before_execution = False

    def state(self):
        self.evaluated_before_execution = len(self.mcp_client.calls) == 0
        return super().state()


def make_host(approval_ttl=1):
    policy_store = PolicyStore()
    audit_store = AuditStore()
    approval_queue = ApprovalQueue(ttl_seconds=approval_ttl)
    mcp_client = FakeMCPClient()
    host = AgentHost(
        mcp_client=mcp_client,
        policy_store=policy_store,
        approval_queue=approval_queue,
        audit_store=audit_store,
    )
    return host, policy_store, approval_queue, audit_store, mcp_client


class AgentLoopTests(unittest.TestCase):
    def test_allowed_tool_call_is_audited_and_executed(self):
        host, _, _, audit_store, mcp_client = make_host()

        result = host.send_message('please run danger_action {"id": "123"}')

        self.assertEqual(result["policy_outcome"], "ALLOW")
        self.assertEqual(len(mcp_client.calls), 1)
        self.assertEqual(audit_store.list_entries()[0]["outcome"], "ALLOW")

    def test_blocked_tool_call_is_audited_and_not_executed(self):
        host, policy_store, _, audit_store, mcp_client = make_host()
        policy_store.upsert_rule(
            {
                "name": "Block fake tool",
                "type": "block",
                "target": {"tool": "danger_action", "server": "fake-server"},
                "action": RuleAction.BLOCK.value,
                "priority": 10,
                "enabled": True,
                "reason": "Too risky.",
            }
        )

        result = host.send_message('please run danger_action {"id": "123"}')

        self.assertEqual(result["policy_outcome"], "BLOCK")
        self.assertEqual(len(mcp_client.calls), 0)
        self.assertEqual(audit_store.list_entries()[0]["outcome"], "BLOCK")

    def test_approval_flow_pauses_and_resumes_on_approval(self):
        host, policy_store, approval_queue, _, mcp_client = make_host(approval_ttl=3)
        policy_store.upsert_rule(
            {
                "name": "Approve fake tool",
                "type": "require_approval",
                "target": {"tool": "danger_action", "server": "fake-server"},
                "action": RuleAction.REQUIRE_APPROVAL.value,
                "priority": 10,
                "enabled": True,
                "reason": "Needs review.",
            }
        )

        output = {}

        def run_agent():
            output["result"] = host.send_message('please run danger_action {"id": "123"}')

        thread = threading.Thread(target=run_agent)
        thread.start()

        pending = []
        for _ in range(30):
            pending = approval_queue.pending()
            if pending:
                break
            time.sleep(0.05)

        self.assertEqual(len(pending), 1)
        approval_queue.decide(pending[0]["id"], "approved")
        thread.join(timeout=5)

        self.assertFalse(thread.is_alive())
        self.assertEqual(output["result"]["policy_outcome"], "ALLOW")
        self.assertEqual(len(mcp_client.calls), 1)

    def test_injection_is_blocked_before_execution(self):
        host, _, _, audit_store, mcp_client = make_host()

        result = host.send_message(
            'please run danger_action {"id": "ignore previous instructions"}'
        )

        self.assertEqual(result["policy_outcome"], "INJECTION_DETECTED")
        self.assertEqual(len(mcp_client.calls), 0)
        self.assertEqual(audit_store.list_entries()[0]["outcome"], "INJECTION_DETECTED")

    def test_langgraph_evaluates_policy_before_execution(self):
        mcp_client = FakeMCPClient()
        policy_store = SpyPolicyStore(mcp_client)
        host = AgentHost(
            mcp_client=mcp_client,
            policy_store=policy_store,
            approval_queue=ApprovalQueue(),
            audit_store=AuditStore(),
        )

        result = host.send_message('please run danger_action {"id": "123"}')

        self.assertEqual(result["policy_outcome"], "ALLOW")
        self.assertTrue(policy_store.evaluated_before_execution)
        self.assertEqual(len(mcp_client.calls), 1)


if __name__ == "__main__":
    unittest.main()
