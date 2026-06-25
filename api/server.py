from __future__ import annotations

import os
from typing import Literal

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from api.app_state import agent_host, approval_queue, audit_store, policy_store
from policy.honeypot import HONEYPOT_TOOLS


class SettingsUpdate(BaseModel):
    default_policy: Literal["allow", "deny"]


class AgentMessageRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: str | None = None


class ApprovalDecisionRequest(BaseModel):
    decision: Literal["approved", "denied"]


app = FastAPI(
    title="ArmorIQ Guarded Agent API",
    version="0.1.0",
    description="Backend host for policy-governed MCP tool execution.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/tools")
def get_tools() -> dict:
    try:
        tools = agent_host.tools()
        for tool in tools:
            tool["is_honeypot"] = tool.get("name") in HONEYPOT_TOOLS
        return {"tools": tools}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/policy/version")
def get_policy_version() -> dict[str, int]:
    return {"version": policy_store.version}


@app.get("/api/policy/rules")
def list_policy_rules() -> dict:
    return {
        "version": policy_store.version,
        "rules": policy_store.list_rules(),
    }


@app.post("/api/policy/rules")
def save_policy_rule(rule: dict) -> dict:
    try:
        saved_rule = policy_store.upsert_rule(rule)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "rule": saved_rule,
        "version": policy_store.version,
    }


@app.delete("/api/policy/rules/{rule_id}")
def delete_policy_rule(rule_id: str) -> dict:
    return {
        "deleted": policy_store.delete_rule(rule_id),
        "version": policy_store.version,
    }


@app.get("/api/settings")
def get_settings() -> dict:
    return policy_store.settings()


@app.post("/api/settings")
def save_settings(settings: SettingsUpdate) -> dict:
    return policy_store.update_settings(settings.model_dump())


@app.get("/api/approvals")
def list_approvals() -> dict:
    return {"approvals": approval_queue.pending()}


@app.post("/api/approvals/{approval_id}/decision")
def decide_approval(approval_id: str, payload: ApprovalDecisionRequest) -> dict:
    try:
        request = approval_queue.decide(approval_id, payload.decision)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Approval request not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"approval": request.to_dict()}


@app.delete("/api/logs")
def clear_logs() -> dict:
    count = audit_store.clear()
    return {"cleared": count}


@app.get("/api/logs/verify")
def verify_audit_chain() -> dict:
    return audit_store.verify_chain()


@app.get("/api/logs")
def list_logs(
    outcome: str | None = Query(default=None),
    tool_name: str | None = Query(default=None),
    server: str | None = Query(default=None),
) -> dict:
    return {
        "logs": audit_store.list_entries(
            {
                "outcome": outcome or "",
                "tool_name": tool_name or "",
                "server": server or "",
            }
        )
    }


@app.post("/api/agent/message")
def send_agent_message(payload: AgentMessageRequest) -> dict:
    try:
        return agent_host.send_message(
            user_message=payload.message,
            conversation_id=payload.conversation_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Conversation not found.") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def run() -> None:
    uvicorn.run(
        "api.server:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        reload=False,
    )


if __name__ == "__main__":
    run()
