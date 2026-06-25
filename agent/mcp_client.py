from __future__ import annotations

import asyncio
import json
import threading
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from mcp.client.session import ClientSession
from mcp.client.sse import sse_client


class MCPClientError(Exception):
    pass


@dataclass(frozen=True)
class DiscoveredTool:
    server: str
    name: str
    description: str
    input_schema: dict[str, Any]

    @property
    def key(self) -> str:
        return f"{self.server}:{self.name}"


class MCPClient:
    """Multi-server MCP client.

    Accepts a list of server base URLs. On discover_tools() it connects to each
    server, collects tools, and builds a routing table (server-name → URL) so
    that subsequent call_tool() calls reach the right server.
    """

    def __init__(self, server_urls: list[str], timeout_seconds: int = 10) -> None:
        self._server_urls = server_urls
        self.timeout_seconds = timeout_seconds
        # Populated during discover_tools(); maps server-reported name → base URL
        self._name_to_url: dict[str, str] = {}

    def discover_tools(self) -> list[DiscoveredTool]:
        all_tools: list[DiscoveredTool] = []
        for url in self._server_urls:
            try:
                tools = _run_async(self._discover_from_url(url))
                for tool in tools:
                    self._name_to_url[tool.server] = url
                all_tools.extend(tools)
            except Exception as exc:
                print(f"[MCPClient] Discovery failed for {url}: {exc}")
        return all_tools

    def call_tool(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        server: str,
    ) -> dict[str, Any]:
        url = self._name_to_url.get(server)
        if url is None:
            # Routing table not yet built — trigger discovery first
            self.discover_tools()
            url = self._name_to_url.get(server)
        if url is None:
            raise MCPClientError(
                f"No URL found for server '{server}'. "
                f"Known servers: {list(self._name_to_url)}"
            )
        try:
            return _run_async(self._call_tool_on_url(url, tool_name, tool_input))
        except MCPClientError:
            raise
        except Exception as exc:
            raise MCPClientError(f"Tool call failed: {exc}") from exc

    # ------------------------------------------------------------------ async helpers

    async def _discover_from_url(self, url: str) -> list[DiscoveredTool]:
        async with _open_session(url) as session:
            init_result = await session.initialize()
            server_name = (
                init_result.serverInfo.name if init_result.serverInfo else "unknown"
            )
            result = await session.list_tools()
            return [
                DiscoveredTool(
                    server=server_name,
                    name=tool.name,
                    description=tool.description or "",
                    input_schema=_schema_to_dict(tool.inputSchema),
                )
                for tool in result.tools
            ]

    async def _call_tool_on_url(
        self,
        url: str,
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> dict[str, Any]:
        async with _open_session(url) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, tool_input)

            if not result.content:
                return {}

            first = result.content[0]
            text = first.text if hasattr(first, "text") else str(first)

            if result.isError:
                raise MCPClientError(f"Tool error: {text}")

            try:
                parsed = json.loads(text)
                # Our custom registry wraps results as {"result": {...}} — unwrap
                return parsed.get("result", parsed)
            except json.JSONDecodeError:
                return {"output": text}


# ------------------------------------------------------------------ transport helpers

@asynccontextmanager
async def _open_session(url: str):
    """Open a ClientSession using the right transport, detected from the URL.

    - URL ending in /mcp  → Streamable HTTP (falls back to SSE if SDK too old)
    - URL ending in /sse  → SSE (used as-is)
    - anything else       → SSE (appends /sse)
    """
    clean = url.rstrip("/")

    if clean.endswith("/mcp"):
        try:
            from mcp.client.streamable_http import streamable_http_client  # mcp >= 1.2

            async with streamable_http_client(clean) as (read, write):
                async with ClientSession(read, write) as session:
                    yield session
                    return
        except ImportError:
            pass  # SDK too old — fall through to SSE

    sse_url = clean if clean.endswith("/sse") else f"{clean}/sse"
    async with sse_client(sse_url) as (read, write):
        async with ClientSession(read, write) as session:
            yield session


# ------------------------------------------------------------------ sync wrapper

def _run_async(coro: Any) -> Any:
    """Run an async coroutine safely from synchronous code.

    Always spawns a fresh thread so it never conflicts with an existing event
    loop (e.g. uvicorn's loop running in the API thread pool).
    """
    result_holder: list[Any] = [None]
    error_holder: list[BaseException | None] = [None]

    def _target() -> None:
        try:
            result_holder[0] = asyncio.run(coro)
        except BaseException as exc:  # noqa: BLE001
            error_holder[0] = exc

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join(timeout=30)

    if error_holder[0] is not None:
        raise error_holder[0]
    return result_holder[0]


def _schema_to_dict(schema: Any) -> dict[str, Any]:
    if isinstance(schema, dict):
        return schema
    if hasattr(schema, "model_dump"):
        return schema.model_dump()
    return dict(schema)
