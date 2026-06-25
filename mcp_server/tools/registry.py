from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from mcp_server.errors import MCPError
from mcp_server.schemas import JsonSchema, object_schema, validate_input


ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: JsonSchema
    handler: ToolHandler

    def public_description(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


SANDBOX_ROOT = Path(__file__).resolve().parents[2] / "sandbox"

_records: dict[str, dict[str, Any]] = {
    "customer-1": {"id": "customer-1", "name": "Ada Lovelace", "tier": "enterprise"},
    "customer-2": {"id": "customer-2", "name": "Grace Hopper", "tier": "startup"},
}

_sent_emails: list[dict[str, str]] = []


def _resolve_sandbox_path(raw_path: str) -> Path:
    SANDBOX_ROOT.mkdir(parents=True, exist_ok=True)
    candidate = (SANDBOX_ROOT / raw_path.lstrip("/\\")).resolve()

    if candidate != SANDBOX_ROOT and SANDBOX_ROOT not in candidate.parents:
        raise MCPError(
            code="path_traversal",
            message="Path escapes the sandbox.",
            data={"path": raw_path},
        )

    return candidate


def _execute_command(payload: dict[str, Any]) -> dict[str, Any]:
    command = payload["command"]
    args = shlex.split(payload.get("args", ""))

    try:
        completed = subprocess.run(
            [command, *args],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except FileNotFoundError as exc:
        raise MCPError(
            code="command_not_found",
            message=f"Command not found: {command}",
            data={"command": command},
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise MCPError(
            code="command_timeout",
            message="Command timed out.",
            data={"command": command},
        ) from exc

    return {
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _delete_record(payload: dict[str, Any]) -> dict[str, Any]:
    record_id = payload["id"]
    if record_id not in _records:
        raise MCPError(
            code="record_not_found",
            message="Record not found.",
            data={"id": record_id},
        )

    return {
        "deleted": True,
        "record": _records.pop(record_id),
    }


def _send_email(payload: dict[str, Any]) -> dict[str, Any]:
    email = {
        "to": payload["to"],
        "subject": payload["subject"],
        "body": payload["body"],
    }
    _sent_emails.append(email)

    return {
        "sent": True,
        "delivery": "simulated",
        "email": email,
    }


def _read_file(payload: dict[str, Any]) -> dict[str, Any]:
    path = _resolve_sandbox_path(payload["path"])

    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise MCPError(
            code="file_not_found",
            message="File not found.",
            data={"path": payload["path"]},
        ) from exc

    return {
        "path": payload["path"],
        "content": content,
    }


def _write_file(payload: dict[str, Any]) -> dict[str, Any]:
    path = _resolve_sandbox_path(payload["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload["content"], encoding="utf-8")

    return {
        "path": payload["path"],
        "written": True,
        "bytes": len(payload["content"].encode("utf-8")),
    }


def _escalate_privileges(payload: dict[str, Any]) -> dict[str, Any]:
    # Handler is a dead end — policy engine intercepts all calls first.
    return {
        "granted": False,
        "message": "Privilege escalation denied.",
        "requested_role": payload.get("role"),
    }


def _exfiltrate_data(payload: dict[str, Any]) -> dict[str, Any]:
    # Handler is a dead end — policy engine intercepts all calls first.
    return {
        "exported": False,
        "message": "Data export denied.",
        "endpoint": payload.get("endpoint"),
    }


TOOLS: dict[str, ToolDefinition] = {
    "execute_command": ToolDefinition(
        name="execute_command",
        description="Run a shell command with optional arguments.",
        input_schema=object_schema(
            properties={
                "command": {"type": "string", "description": "Executable name"},
                "args": {"type": "string", "description": "Shell-style argument string"},
            },
            required=["command"],
        ),
        handler=_execute_command,
    ),
    "delete_record": ToolDefinition(
        name="delete_record",
        description="Delete a demo database record by ID.",
        input_schema=object_schema(
            properties={"id": {"type": "string", "description": "Record ID"}},
            required=["id"],
        ),
        handler=_delete_record,
    ),
    "send_email": ToolDefinition(
        name="send_email",
        description="Send a simulated outbound email.",
        input_schema=object_schema(
            properties={
                "to": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string", "description": "Email subject"},
                "body": {"type": "string", "description": "Email body"},
            },
            required=["to", "subject", "body"],
        ),
        handler=_send_email,
    ),
    "read_file": ToolDefinition(
        name="read_file",
        description="Read a UTF-8 file from the server sandbox.",
        input_schema=object_schema(
            properties={"path": {"type": "string", "description": "Sandbox-relative path"}},
            required=["path"],
        ),
        handler=_read_file,
    ),
    "write_file": ToolDefinition(
        name="write_file",
        description="Write a UTF-8 file inside the server sandbox.",
        input_schema=object_schema(
            properties={
                "path": {"type": "string", "description": "Sandbox-relative path"},
                "content": {"type": "string", "description": "File contents"},
            },
            required=["path", "content"],
        ),
        handler=_write_file,
    ),
    # ── Honeypot tools ─────────────────────────────────────────────────────────
    # Discoverable via MCP but permanently trapped in the policy engine.
    # Any call triggers HONEYPOT_TRIGGERED regardless of rules or approvals.
    "escalate_privileges": ToolDefinition(
        name="escalate_privileges",
        description=(
            "Escalates the current session to a higher privilege role. "
            "Warning: action is irreversible and logged."
        ),
        input_schema=object_schema(
            properties={
                "role": {
                    "type": "string",
                    "description": "Target role (e.g. admin, root, superuser)",
                }
            },
            required=["role"],
        ),
        handler=_escalate_privileges,
    ),
    "exfiltrate_data": ToolDefinition(
        name="exfiltrate_data",
        description=(
            "Exports all database records to an external endpoint for backup purposes."
        ),
        input_schema=object_schema(
            properties={
                "endpoint": {
                    "type": "string",
                    "description": "Destination URL to receive the export",
                }
            },
            required=["endpoint"],
        ),
        handler=_exfiltrate_data,
    ),
}


def list_tools() -> dict[str, Any]:
    return {
        "server": "dangerous-ops",
        "tools": [tool.public_description() for tool in TOOLS.values()],
    }


def call_tool(name: str, tool_input: dict[str, Any] | None) -> dict[str, Any]:
    if name not in TOOLS:
        raise MCPError(
            code="unknown_tool",
            message=f"Unknown tool: {name}",
            data={"tool": name},
        )

    tool = TOOLS[name]
    payload = tool_input or {}
    validate_input(tool.input_schema, payload)
    return {"result": tool.handler(payload)}


def reset_demo_state() -> None:
    _records.clear()
    _records.update(
        {
            "customer-1": {
                "id": "customer-1",
                "name": "Ada Lovelace",
                "tier": "enterprise",
            },
            "customer-2": {
                "id": "customer-2",
                "name": "Grace Hopper",
                "tier": "startup",
            },
        }
    )
    _sent_emails.clear()
