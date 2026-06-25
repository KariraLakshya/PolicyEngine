import unittest

from agent.groq_planner import GroqPlanner
from agent.mcp_client import DiscoveredTool


class FakeGroqPlanner(GroqPlanner):
    def __init__(self):
        super().__init__(api_key="test-key", model="test-model")
        self.last_payload = None

    def _post_chat_completion(self, payload):
        self.last_payload = payload
        return {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "type": "function",
                                "function": {
                                    "name": "write_file",
                                    "arguments": '{"path":"demo.txt","content":"hello"}',
                                },
                            }
                        ]
                    }
                }
            ]
        }


class GroqPlannerTests(unittest.TestCase):
    def test_groq_response_is_converted_to_tool_call(self):
        planner = FakeGroqPlanner()
        tool = DiscoveredTool(
            server="dangerous-ops",
            name="write_file",
            description="Write content to a file.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        )

        tool_call = planner.plan("Create a demo file with hello inside.", [tool])

        self.assertEqual(tool_call.tool_name, "write_file")
        self.assertEqual(tool_call.server, "dangerous-ops")
        self.assertEqual(tool_call.tool_input["path"], "demo.txt")
        self.assertEqual(tool_call.tool_input["content"], "hello")
        self.assertEqual(planner.last_payload["tool_choice"], "auto")
        self.assertEqual(planner.last_payload["tools"][0]["function"]["name"], "write_file")

    def test_no_tool_calls_returns_none(self):
        class NoToolPlanner(FakeGroqPlanner):
            def _post_chat_completion(self, payload):
                return {"choices": [{"message": {"content": "No tool needed."}}]}

        planner = NoToolPlanner()
        tool = DiscoveredTool(
            server="dangerous-ops",
            name="read_file",
            description="Read a file.",
            input_schema={"type": "object", "properties": {}, "required": []},
        )

        self.assertIsNone(planner.plan("Hello", [tool]))


if __name__ == "__main__":
    unittest.main()
