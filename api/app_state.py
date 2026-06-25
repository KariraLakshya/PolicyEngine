from __future__ import annotations

import os

from agent.agent import AgentHost
from agent.mcp_client import MCPClient
from api.approvals import ApprovalQueue
from api.audit_store import AuditStore
from api.policy_store import PolicyStore


policy_store = PolicyStore()
audit_store = AuditStore()
approval_queue = ApprovalQueue(
    ttl_seconds=int(os.environ.get("APPROVAL_TTL_SECONDS", "1800"))
)
_server_urls: list[str] = [os.environ.get("MCP_SERVER_URL", "http://localhost:8001")]
_remote_url = os.environ.get("REMOTE_MCP_URL", "").strip()
if _remote_url:
    _server_urls.append(_remote_url)

mcp_client = MCPClient(_server_urls)
agent_host = AgentHost(
    mcp_client=mcp_client,
    policy_store=policy_store,
    approval_queue=approval_queue,
    audit_store=audit_store,
)
