# ArmorIQ — Guarded AI Agent with MCP Support

A miniature implementation of ArmorIQ's core product: an AI agent that talks to MCP servers with a **policy engine** that sits between the agent and those servers, enforcing guardrails in real time.

**Live demo:** [policy-engine.vercel.app](https://policy-engine.vercel.app)

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Frontend Dashboard                 │
│         (Rules manager, approval queue,              │
│          conversation logs, policy editor)           │
└────────────────────┬────────────────────────────────┘
                     │ REST polling (3s)
┌────────────────────▼────────────────────────────────┐
│                  Backend (Agent Host)                │
│                                                      │
│   ┌──────────┐    ┌───────────────┐    ┌─────────┐  │
│   │ Groq LLM │───▶│ Policy Engine │───▶│   MCP   │  │
│   │          │◀───│   (enforcer)  │◀───│ Client  │  │
│   └──────────┘    └───────────────┘    └────┬────┘  │
│                                             │        │
└─────────────────────────────────────────────┼────────┘
                                              │
                               ┌──────────────┴──────────────┐
                               │                             │
                  ┌────────────▼────────┐      ┌────────────▼────────┐
                  │  Custom MCP Server  │      │  Remote MCP Server  │
                  │  (dangerous-ops)    │      │  (Context7, Exa…)   │
                  └─────────────────────┘      └─────────────────────┘
```

**Tool-use loop (strict order):**
1. Send user message + conversation history + discovered tools to LLM
2. LLM responds with a tool call or final answer
3. If tool call → pass to Policy Engine **before** executing
4. Policy Engine returns: `ALLOW | BLOCK | REQUIRE_APPROVAL | INJECTION_DETECTED | HONEYPOT_TRIGGERED`
5. Execute or reject accordingly, feed result back to LLM, repeat

---

## Features

### Policy Engine
- **Rule-based guardrails** — block, require approval, or allow any tool by name or server
- **Priority ordering** — higher priority rules win; ties resolve to the stricter action
- **Conflict detection** — conflicting rules at the same priority are flagged in the dashboard
- **Default policy** — configurable allow-all or deny-all fallback when no rules match

### Prompt Injection Detection
Runs on 100% of tool call inputs before execution. Matches patterns like:
- `ignore previous instructions`
- `you are now`, `DAN mode`, `jailbreak`
- `override policy/guardrail`

Detected injections are logged as `INJECTION_DETECTED` security events. The LLM receives a generic error — it never learns what tripped the detector.

### Honeypot Tools
`escalate_privileges` and `exfiltrate_data` are discoverable via MCP but permanently blocked by the policy engine. Any attempt triggers a `HONEYPOT_TRIGGERED` event that cannot be approved or overridden.

### Cryptographic Audit Chain
Every policy decision (allowed or blocked) is written to an append-only audit log. Each entry has a SHA-256 `entry_hash` over its content, and a `chain_hash` chained from the previous entry — forming a tamper-evident log that can be verified from the dashboard.

### Human Approval Queue
Rules set to `require_approval` pause the agent loop and create a card in the dashboard. The approver sees the tool name, server, full input arguments, and conversation context. On approval the agent resumes exactly where it left off. Requests expire after a configurable TTL (default 30 min) and default to deny on timeout.

### Real-time Sync
Dashboard rule changes reach the running agent within 3 seconds via polling — no restart needed.

---

## Project Structure

```
/
├── agent/
│   ├── agent.py          # AgentHost — LLM loop, tool discovery, conversation management
│   ├── graph.py          # LangGraph StateGraph — 6-node agent loop
│   ├── mcp_client.py     # Multi-server MCP client, SSE + Streamable HTTP transport
│   ├── groq_planner.py   # Groq LLM integration (tool-use)
│   └── conversation.py   # Conversation state and history
│
├── policy/
│   ├── engine.py         # evaluate(tool_call) → PolicyDecision — pure logic, no I/O
│   ├── injection.py      # Prompt injection detector (regex pattern matching)
│   ├── honeypot.py       # Honeypot tool names (HONEYPOT_TOOLS frozenset)
│   ├── audit.py          # Audit log entry builder with SHA-256 entry_hash
│   ├── conflicts.py      # Rule conflict detection
│   └── models.py         # Pydantic models: PolicyRule, ToolCall, PolicyDecision, etc.
│
├── mcp_server/
│   ├── server.py         # MCP server (SSE/JSON-RPC 2.0) via Starlette + mcp SDK
│   └── tools/registry.py # 5 dangerous tools + 2 honeypot traps
│
├── api/
│   ├── server.py         # FastAPI app — all REST endpoints
│   ├── app_state.py      # Singleton instances (policy store, audit store, MCP client)
│   ├── audit_store.py    # In-memory audit log with cryptographic chain
│   ├── policy_store.py   # In-memory rule store with version counter
│   └── approvals.py      # Approval queue with TTL expiry
│
├── frontend/             # React + Vite dashboard
│   └── src/
│       ├── main.jsx      # All views: Rules, Approvals, Logs, Settings, Agent
│       ├── api.js        # Typed API client
│       └── styles.css    # CSS (no framework)
│
├── tests/
│   ├── test_policy_engine.py   # Unit tests: rule evaluation, conflicts, injection
│   ├── test_mcp_server.py      # MCP spec compliance tests
│   └── test_agent_loop.py      # Integration: full loop with mock LLM + mock MCP
│
├── railway.toml          # Railway deployment config (backend)
├── start.sh              # Startup dispatcher (backend vs MCP server via SERVICE_TYPE)
└── docker-compose.yml    # Local dev — all four services in one command
```

---

## Running Locally

**Prerequisites:** Python 3.11+, Node.js 18+

```bash
# 1. Clone and set up Python env
git clone https://github.com/KariraLakshya/PolicyEngine.git
cd PolicyEngine
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env — add your GROQ_API_KEY

# 3. Start the MCP server (terminal 1)
python -m mcp_server.server

# 4. Start the backend API (terminal 2)
uvicorn api.server:app --reload --port 8000

# 5. Start the frontend (terminal 3)
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

---

## Deployed URLs

| Service | URL |
|---|---|
| Dashboard (Vercel) | https://policy-engine.vercel.app |
| Backend API (Railway) | https://policyengine-production.up.railway.app |
| MCP Server (Railway) | https://illustrious-reflection-production.up.railway.app |

---

## Deployment

See [CLAUDE.md](CLAUDE.md) for full deployment instructions.

**Quick summary:**
- **Backend** → Railway, auto-deploys from `main`, reads `railway.toml`
- **MCP Server** → Railway (separate service, same repo), `SERVICE_TYPE=mcp` env var triggers `python -m mcp_server.server`
- **Frontend** → Vercel, root directory `frontend`, env var `VITE_API_URL=<backend URL>`

---

## Adding a New MCP Server

The agent discovers tools dynamically — no code changes required.

1. Deploy your MCP server (must expose `/sse` for SSE transport or `/mcp` for Streamable HTTP)
2. Add its URL to the backend's environment variables:
   ```
   REMOTE_MCP_URL=https://your-mcp-server.example.com
   ```
3. Restart the backend — tools appear automatically in the Settings → Connected Tools list
4. Create policy rules targeting the new server's tool names from the dashboard

---

## API Reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/api/tools` | List all discovered tools |
| `GET` | `/api/policy/rules` | List all policy rules |
| `POST` | `/api/policy/rules` | Create or update a rule |
| `DELETE` | `/api/policy/rules/{id}` | Delete a rule |
| `GET` | `/api/policy/version` | Current policy version (for polling) |
| `GET` | `/api/settings` | Global settings |
| `POST` | `/api/settings` | Update global settings |
| `GET` | `/api/approvals` | List pending approvals |
| `POST` | `/api/approvals/{id}/decision` | Approve or deny |
| `GET` | `/api/logs` | Audit log (filterable by outcome, tool, server) |
| `DELETE` | `/api/logs` | Clear audit log |
| `GET` | `/api/logs/verify` | Verify cryptographic chain integrity |
| `POST` | `/api/agent/message` | Send a message to the agent |

---

## Key Design Decisions

**Policy engine is a pure module** — `policy/engine.py` has zero imports from `agent/`. It takes a `ToolCall` and `PolicyState` and returns a `PolicyDecision`. Independently testable, no side effects.

**No hardcoded tool names** — the agent discovers tools dynamically from all connected MCP servers at startup. Adding a new server requires zero agent-side code changes.

**Injection detection is always-on** — runs on 100% of tool inputs, not opt-in. Cannot be disabled via rules.

**Honeypot outcome cannot be approved** — `HONEYPOT_TRIGGERED` is terminal. The approval queue rejects honeypot requests server-side.

**In-memory state** — the policy store, audit log, and approval queue are in-memory for simplicity. On Railway, state resets on redeploy. For production, replace with Redis (Railway Redis plugin is one click).
