import unittest

from mcp_server.errors import MCPError
from mcp_server.tools.registry import call_tool, list_tools, reset_demo_state


class DangerousOpsMCPTests(unittest.TestCase):
    def setUp(self):
        reset_demo_state()

    def test_tools_list_returns_full_schemas(self):
        payload = list_tools()

        self.assertEqual(payload["server"], "dangerous-ops")
        self.assertEqual(len(payload["tools"]), 5)

        for tool in payload["tools"]:
            self.assertIn("name", tool)
            self.assertIn("description", tool)
            self.assertIn("inputSchema", tool)
            self.assertEqual(tool["inputSchema"]["type"], "object")
            self.assertIn("properties", tool["inputSchema"])
            self.assertIn("required", tool["inputSchema"])

    def test_unknown_tool_returns_structured_error(self):
        with self.assertRaises(MCPError) as context:
            call_tool("unknown", {})

        self.assertEqual(context.exception.code, "unknown_tool")
        self.assertIn("tool", context.exception.data)

    def test_call_validates_missing_required_input(self):
        with self.assertRaises(MCPError) as context:
            call_tool("delete_record", {})

        self.assertEqual(context.exception.code, "invalid_input")
        self.assertEqual(context.exception.data["field"], "id")

    def test_call_validates_unknown_input_fields(self):
        with self.assertRaises(MCPError) as context:
            call_tool("delete_record", {"id": "customer-1", "extra": "nope"})

        self.assertEqual(context.exception.code, "invalid_input")
        self.assertEqual(context.exception.data["field"], "extra")

    def test_delete_record_executes_and_then_record_is_gone(self):
        first = call_tool("delete_record", {"id": "customer-1"})

        self.assertTrue(first["result"]["deleted"])

        with self.assertRaises(MCPError) as context:
            call_tool("delete_record", {"id": "customer-1"})

        self.assertEqual(context.exception.code, "record_not_found")

    def test_write_and_read_file_are_sandboxed(self):
        call_tool("write_file", {"path": "notes/demo.txt", "content": "hello"})
        result = call_tool("read_file", {"path": "notes/demo.txt"})

        self.assertEqual(result["result"]["content"], "hello")

    def test_path_traversal_is_rejected(self):
        with self.assertRaises(MCPError) as context:
            call_tool("read_file", {"path": "../secret.txt"})

        self.assertEqual(context.exception.code, "path_traversal")

    def test_send_email_is_simulated(self):
        result = call_tool(
            "send_email",
            {
                "to": "admin@example.com",
                "subject": "Approval",
                "body": "Please review.",
            },
        )

        self.assertTrue(result["result"]["sent"])
        self.assertEqual(result["result"]["delivery"], "simulated")


if __name__ == "__main__":
    unittest.main()
