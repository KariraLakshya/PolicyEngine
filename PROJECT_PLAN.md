# ArmorIQ Build Plan

## Part 1: Policy Engine

Goal: build the standalone guardrail core.

Deliverables:
- Rule schema models
- Policy decision evaluator
- Prompt injection detector
- Conflict detector
- Audit log entry builder
- Unit tests

Completion criteria:
- `policy/engine.py` imports nothing from `agent/`
- Every decision returns a structured outcome
- Injection detection runs before normal rule evaluation
- Tests cover allow, block, approval, conflicts, default policy, and injection

## Part 2: Dangerous Ops MCP Server

Goal: build a custom MCP-style server with risky tools.

Deliverables:
- `tools/list`
- `tools/call`
- Tool schemas and input validation
- Risky demo tools: command execution, record deletion, email, file read/write
- Compliance tests

Status: completed in Python using a dependency-light HTTP server and importable tool
registry.

## Part 3: Backend Agent Host

Goal: connect LLM-style tool decisions to MCP through the policy engine.

Deliverables:
- Tool discovery
- Agent conversation loop
- Policy checks before every tool call
- Approval queue pause/resume
- Audit log persistence

Status: completed as an importable backend core plus a FastAPI HTTP API. The LLM
decision step is represented by a deterministic demo planner for local testing;
the policy/MCP/approval boundaries are the same boundaries a provider adapter
will use later.

## Part 4: Dashboard

Goal: create the admin UI.

Deliverables:
- Rules manager
- Approval queue
- Conversation/audit logs
- Global settings

Status: completed as a Vite React dashboard with API-backed rules,
approvals, logs, global settings, discovered tools, and an agent demo panel.

## Part 5: Integration And Demo

Goal: make the system easy to run and submit.

Deliverables:
- Real-time policy updates
- Docker Compose
- README
- Demo script support
- Deployment notes
