from __future__ import annotations

import json
import os

import uvicorn
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import TextContent, Tool
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from mcp_server.errors import MCPError
from mcp_server.tools.registry import TOOLS, call_tool


server = Server("dangerous-ops")


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return [
        Tool(
            name=tool.name,
            description=tool.description,
            inputSchema=tool.input_schema,
        )
        for tool in TOOLS.values()
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    try:
        result = call_tool(name, arguments or {})
        return [TextContent(type="text", text=json.dumps(result))]
    except MCPError as exc:
        return [TextContent(type="text", text=json.dumps({"error": exc.to_response()}))]


async def _health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "server": "dangerous-ops", "tools": len(TOOLS)})


def create_app() -> Starlette:
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request) -> None:
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await server.run(
                streams[0],
                streams[1],
                server.create_initialization_options(),
            )

    return Starlette(
        routes=[
            Route("/health", _health),
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
        middleware=[
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_methods=["*"],
                allow_headers=["*"],
            )
        ],
    )


def run() -> None:
    port = int(os.environ.get("PORT", "8001"))
    print(f"Dangerous Ops MCP server (SSE/JSON-RPC 2.0) on http://localhost:{port}")
    uvicorn.run(create_app(), host="0.0.0.0", port=port)


if __name__ == "__main__":
    run()
