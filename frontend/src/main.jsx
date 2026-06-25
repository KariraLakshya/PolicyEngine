import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  AlertTriangle,
  Check,
  CircleSlash,
  Clock,
  FileText,
  Link2,
  RefreshCcw,
  Save,
  Send,
  Settings,
  Shield,
  SlidersHorizontal,
  Trash2,
  X
} from "lucide-react";
import { api } from "./api";
import "./styles.css";

const emptyRule = {
  name: "",
  type: "block",
  target: { tool: "*", server: "" },
  condition: null,
  action: "block",
  priority: 10,
  enabled: true,
  reason: ""
};

function App() {
  const [activeView, setActiveView] = useState("rules");
  const [status, setStatus] = useState("checking");
  const [rulesPayload, setRulesPayload] = useState({ version: 0, rules: [] });
  const [tools, setTools] = useState([]);
  const [approvals, setApprovals] = useState([]);
  const [logs, setLogs] = useState([]);
  const [settings, setSettings] = useState({ default_policy: "allow", version: 0 });
  const [error, setError] = useState("");

  async function refreshAll() {
    setError("");
    try {
      const [health, rules, approvalsPayload, logsPayload, settingsPayload] =
        await Promise.all([
          api.health(),
          api.rules(),
          api.approvals(),
          api.logs(),
          api.settings()
        ]);
      setStatus(health.status);
      setRulesPayload(rules);
      setApprovals(approvalsPayload.approvals);
      setLogs(logsPayload.logs);
      setSettings(settingsPayload);
      try {
        const toolsPayload = await api.tools();
        setTools(toolsPayload.tools);
      } catch {
        setTools([]);
      }
    } catch (err) {
      setStatus("offline");
      setError(err.message);
    }
  }

  useEffect(() => {
    refreshAll();
    const timer = window.setInterval(refreshAll, 3000);
    return () => window.clearInterval(timer);
  }, []);

  const views = [
    { id: "rules", label: "Rules", icon: Shield },
    { id: "approvals", label: "Approvals", icon: Clock },
    { id: "logs", label: "Logs", icon: FileText },
    { id: "settings", label: "Settings", icon: Settings },
    { id: "agent", label: "Agent", icon: Send }
  ];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <Shield size={24} />
          <div>
            <strong>ArmorIQ</strong>
            <span>Guarded Agent</span>
          </div>
        </div>
        <nav>
          {views.map((view) => {
            const Icon = view.icon;
            return (
              <button
                key={view.id}
                className={activeView === view.id ? "nav-item active" : "nav-item"}
                onClick={() => setActiveView(view.id)}
                title={view.label}
              >
                <Icon size={18} />
                <span>{view.label}</span>
              </button>
            );
          })}
        </nav>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <h1>{views.find((view) => view.id === activeView)?.label}</h1>
            <p>Policy version {rulesPayload.version || settings.version || 0}</p>
          </div>
          <div className="status-row">
            <span className={`status-pill ${status === "ok" ? "online" : "offline"}`}>
              <Activity size={14} />
              {status}
            </span>
            <button className="icon-button" onClick={refreshAll} title="Refresh">
              <RefreshCcw size={18} />
            </button>
          </div>
        </header>

        {error && <div className="banner error">{error}</div>}

        {activeView === "rules" && (
          <RulesView rulesPayload={rulesPayload} tools={tools} onChanged={refreshAll} />
        )}
        {activeView === "approvals" && (
          <ApprovalsView approvals={approvals} onChanged={refreshAll} />
        )}
        {activeView === "logs" && <LogsView initialLogs={logs} />}
        {activeView === "settings" && (
          <SettingsView settings={settings} tools={tools} onChanged={refreshAll} />
        )}
        {activeView === "agent" && <AgentView onChanged={refreshAll} />}
      </main>
    </div>
  );
}

function RulesView({ rulesPayload, tools, onChanged }) {
  const [form, setForm] = useState(emptyRule);
  const conflicts = useMemo(() => conflictTargets(rulesPayload.rules), [rulesPayload.rules]);
  const toolOptions = ["*", ...tools.map((tool) => tool.name)];

  function edit(rule) {
    setForm({
      ...rule,
      target: {
        tool: rule.target?.tool || "*",
        server: rule.target?.server || ""
      },
      condition: rule.condition
    });
  }

  async function save(event) {
    event.preventDefault();
    const payload = {
      ...form,
      target: {
        tool: form.target.tool || "*",
        server: form.target.server || undefined
      },
      reason: form.reason || "Matched policy rule."
    };
    await api.saveRule(payload);
    setForm(emptyRule);
    onChanged();
  }

  async function remove(id) {
    await api.deleteRule(id);
    onChanged();
  }

  return (
    <section className="split">
      <div className="panel wide">
        <div className="panel-heading">
          <h2>Policy Rules</h2>
          <span>{rulesPayload.rules.length} total</span>
        </div>
        <div className="table">
          <div className="table-row header">
            <span>Name</span>
            <span>Action</span>
            <span>Target</span>
            <span>Priority</span>
            <span>Status</span>
            <span></span>
          </div>
          {rulesPayload.rules.map((rule) => {
            const target = `${rule.target?.server || "*"}:${rule.target?.tool || "*"}`;
            const conflict = conflicts.has(target);
            return (
              <div className={conflict ? "table-row conflict" : "table-row"} key={rule.id}>
                <span>
                  <button className="link-button" onClick={() => edit(rule)}>
                    {rule.name}
                  </button>
                  {conflict && <small>Conflict</small>}
                </span>
                <span className={`outcome ${rule.action}`}>{rule.action}</span>
                <span>{target}</span>
                <span>{rule.priority}</span>
                <span>{rule.enabled ? "enabled" : "disabled"}</span>
                <button className="icon-button danger" onClick={() => remove(rule.id)} title="Delete">
                  <Trash2 size={16} />
                </button>
              </div>
            );
          })}
          {rulesPayload.rules.length === 0 && <div className="empty">No rules yet.</div>}
        </div>
      </div>

      <form className="panel form-panel" onSubmit={save}>
        <div className="panel-heading">
          <h2>{form.id ? "Edit Rule" : "Create Rule"}</h2>
          <SlidersHorizontal size={18} />
        </div>
        <label>
          Name
          <input
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
            required
          />
        </label>
        <div className="grid-2">
          <label>
            Action
            <select
              value={form.action}
              onChange={(event) =>
                setForm({ ...form, action: event.target.value, type: event.target.value })
              }
            >
              <option value="block">block</option>
              <option value="require_approval">require_approval</option>
              <option value="allow">allow</option>
            </select>
          </label>
          <label>
            Priority
            <input
              type="number"
              value={form.priority}
              onChange={(event) => setForm({ ...form, priority: Number(event.target.value) })}
            />
          </label>
        </div>
        <div className="grid-2">
          <label>
            Tool
            <select
              value={form.target.tool}
              onChange={(event) =>
                setForm({ ...form, target: { ...form.target, tool: event.target.value } })
              }
            >
              {toolOptions.map((tool) => (
                <option key={tool} value={tool}>
                  {tool}
                </option>
              ))}
            </select>
          </label>
          <label>
            Server
            <input
              value={form.target.server}
              placeholder="optional"
              onChange={(event) =>
                setForm({ ...form, target: { ...form.target, server: event.target.value } })
              }
            />
          </label>
        </div>
        <label>
          Reason
          <textarea
            value={form.reason}
            onChange={(event) => setForm({ ...form, reason: event.target.value })}
            rows={3}
          />
        </label>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={form.enabled}
            onChange={(event) => setForm({ ...form, enabled: event.target.checked })}
          />
          Enabled
        </label>
        <div className="button-row">
          <button className="primary" type="submit">
            <Save size={16} />
            Save
          </button>
          <button className="secondary" type="button" onClick={() => setForm(emptyRule)}>
            <X size={16} />
            Clear
          </button>
        </div>
      </form>
    </section>
  );
}

function ApprovalsView({ approvals, onChanged }) {
  async function decide(id, decision) {
    await api.decideApproval(id, decision);
    onChanged();
  }

  return (
    <section className="cards-grid">
      {approvals.map((approval) => (
        <article className="panel approval-card" key={approval.id}>
          <div className="panel-heading">
            <h2>{approval.tool_call.tool_name}</h2>
            <span>{approval.tool_call.server}</span>
          </div>
          <pre>{JSON.stringify(approval.tool_call.tool_input, null, 2)}</pre>
          <p>{approval.context_snippet}</p>
          <div className="button-row">
            <button className="primary" onClick={() => decide(approval.id, "approved")}>
              <Check size={16} />
              Approve
            </button>
            <button className="danger-button" onClick={() => decide(approval.id, "denied")}>
              <CircleSlash size={16} />
              Deny
            </button>
          </div>
        </article>
      ))}
      {approvals.length === 0 && <div className="empty large">No pending approvals.</div>}
    </section>
  );
}

function LogsView({ initialLogs }) {
  const [filters, setFilters] = useState({ outcome: "", tool_name: "", server: "" });
  const [logs, setLogs] = useState(initialLogs);
  const [chainStatus, setChainStatus] = useState(null);

  useEffect(() => setLogs(initialLogs), [initialLogs]);

  async function applyFilters() {
    const payload = await api.logs(filters);
    setLogs(payload.logs);
  }

  async function verifyChain() {
    const result = await api.verifyChain();
    setChainStatus(result);
  }

  function rowClass(entry) {
    if (entry.outcome === "HONEYPOT_TRIGGERED") return "log-row honeypot";
    if (entry.outcome === "INJECTION_DETECTED") return "log-row security";
    return "log-row";
  }

  return (
    <section className="panel">
      <div className="filters">
        <select
          value={filters.outcome}
          onChange={(event) => setFilters({ ...filters, outcome: event.target.value })}
        >
          <option value="">All outcomes</option>
          <option value="ALLOW">ALLOW</option>
          <option value="BLOCK">BLOCK</option>
          <option value="REQUIRE_APPROVAL">REQUIRE_APPROVAL</option>
          <option value="INJECTION_DETECTED">INJECTION_DETECTED</option>
          <option value="HONEYPOT_TRIGGERED">HONEYPOT_TRIGGERED</option>
        </select>
        <input
          placeholder="tool"
          value={filters.tool_name}
          onChange={(event) => setFilters({ ...filters, tool_name: event.target.value })}
        />
        <input
          placeholder="server"
          value={filters.server}
          onChange={(event) => setFilters({ ...filters, server: event.target.value })}
        />
        <button className="secondary" onClick={applyFilters}>
          <RefreshCcw size={16} />
          Apply
        </button>
        <button className="secondary" onClick={verifyChain} title="Verify audit chain integrity">
          <Link2 size={16} />
          Verify Chain
        </button>
        <button
          className="danger-button"
          onClick={async () => {
            if (!window.confirm("Clear all audit logs?")) return;
            await api.clearLogs();
            setLogs([]);
            setChainStatus(null);
          }}
          title="Clear all logs"
        >
          <Trash2 size={16} />
          Clear
        </button>
      </div>

      {chainStatus && (
        <div className={`chain-status ${chainStatus.valid ? "valid" : "invalid"}`}>
          <Link2 size={15} />
          {chainStatus.valid
            ? `Chain intact — ${chainStatus.entries_verified} entries verified`
            : `Chain broken at entry ${chainStatus.broken_at}: ${chainStatus.reason}`}
        </div>
      )}

      <div className="log-list">
        {logs.map((entry) => (
          <details className={rowClass(entry)} key={entry.event_id}>
            <summary>
              <span className={`outcome ${entry.outcome.toLowerCase()}`}>
                {entry.outcome === "HONEYPOT_TRIGGERED" && <AlertTriangle size={12} style={{ marginRight: 4 }} />}
                {entry.outcome}
              </span>
              <strong>{entry.tool_name}</strong>
              <span>{entry.server}</span>
              <time>{new Date(entry.timestamp).toLocaleString()}</time>
            </summary>
            <pre>{JSON.stringify(entry, null, 2)}</pre>
          </details>
        ))}
        {logs.length === 0 && <div className="empty">No log events.</div>}
      </div>
    </section>
  );
}

function SettingsView({ settings, tools, onChanged }) {
  const [defaultPolicy, setDefaultPolicy] = useState(settings.default_policy || "allow");

  useEffect(() => setDefaultPolicy(settings.default_policy || "allow"), [settings]);

  async function save() {
    await api.saveSettings({ default_policy: defaultPolicy });
    onChanged();
  }

  return (
    <section className="split">
      <div className="panel form-panel">
        <div className="panel-heading">
          <h2>Global Policy</h2>
          <Settings size={18} />
        </div>
        <label>
          Default policy
          <select value={defaultPolicy} onChange={(event) => setDefaultPolicy(event.target.value)}>
            <option value="allow">allow</option>
            <option value="deny">deny</option>
          </select>
        </label>
        <button className="primary" onClick={save}>
          <Save size={16} />
          Save
        </button>
      </div>
      <div className="panel wide">
        <div className="panel-heading">
          <h2>Connected Tools</h2>
          <span>{tools.length}</span>
        </div>
        <div className="tool-grid">
          {tools.map((tool) => (
            <div
              className={tool.is_honeypot ? "tool-item trap" : "tool-item"}
              key={`${tool.server}:${tool.name}`}
            >
              <strong>
                {tool.is_honeypot && <AlertTriangle size={13} style={{ marginRight: 5, color: "#d97706" }} />}
                {tool.name}
              </strong>
              <span>{tool.server}</span>
              <p>{tool.description}{tool.is_honeypot && " ⚠ Honeypot trap"}</p>
            </div>
          ))}
          {tools.length === 0 && <div className="empty">No tools discovered.</div>}
        </div>
      </div>
    </section>
  );
}

const OUTCOME_ORDER = ["ALLOW", "BLOCK", "REQUIRE_APPROVAL", "INJECTION_DETECTED", "HONEYPOT_TRIGGERED"];

function msgClass(msg) {
  if (msg.role === "user") return "msg user";
  if (msg.role === "tool") {
    const outcome = msg.metadata?.outcome || "";
    if (outcome === "BLOCK" || outcome === "INJECTION_DETECTED" || outcome === "HONEYPOT_TRIGGERED") return "msg tool blocked";
    if (outcome === "REQUIRE_APPROVAL") return "msg tool approval";
    if (outcome === "ALLOW") return "msg tool allowed";
    return "msg tool";
  }
  return "msg assistant";
}

function MsgBubble({ msg }) {
  const outcome = msg.metadata?.outcome;
  const toolName = msg.metadata?.tool_name;
  return (
    <div className={msgClass(msg)}>
      <div className="msg-meta">
        <span className="msg-role">{msg.role}</span>
        {toolName && <span className="msg-tool">{toolName}</span>}
        {outcome && <span className={`outcome ${outcome.toLowerCase()}`}>{outcome}</span>}
      </div>
      <p className="msg-content">{msg.content}</p>
    </div>
  );
}

function AgentView({ onChanged }) {
  const [message, setMessage] = useState(
    'Create a file named demo.txt with the text "hello from ArmorIQ".'
  );
  const [conversationId, setConversationId] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  async function send(event) {
    event.preventDefault();
    setLoading(true);
    try {
      const payload = await api.sendMessage(message, conversationId);
      setConversationId(payload.conversation.id);
      setResult(payload);
      onChanged();
    } finally {
      setLoading(false);
    }
  }

  const messages = result?.conversation?.messages || [];

  return (
    <section className="split">
      <form className="panel form-panel" onSubmit={send}>
        <div className="panel-heading">
          <h2>Agent Message</h2>
          <Send size={18} />
        </div>
        <label>
          Message
          <textarea
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            rows={6}
          />
        </label>
        <button className="primary" type="submit" disabled={loading}>
          <Send size={16} />
          {loading ? "Thinking…" : "Send"}
        </button>
        {conversationId && (
          <p style={{ fontSize: 12, color: "#667589", wordBreak: "break-all" }}>
            conv: {conversationId}
          </p>
        )}
      </form>

      <div className="panel wide">
        <div className="panel-heading">
          <h2>Conversation</h2>
          <span>{messages.length} messages</span>
        </div>
        {messages.length === 0 && <div className="empty">Send a message to start.</div>}
        <div className="msg-chain">
          {messages.map((msg, i) => (
            <MsgBubble key={i} msg={msg} />
          ))}
        </div>
        {result?.response && (
          <div className="agent-response">
            <strong>Agent:</strong> {result.response}
          </div>
        )}
      </div>
    </section>
  );
}

function conflictTargets(rules) {
  const counts = new Map();
  rules
    .filter((rule) => rule.enabled)
    .forEach((rule) => {
      const key = `${rule.target?.server || "*"}:${rule.target?.tool || "*"}`;
      counts.set(key, (counts.get(key) || 0) + 1);
    });
  return new Set([...counts.entries()].filter(([, count]) => count > 1).map(([key]) => key));
}

createRoot(document.getElementById("root")).render(<App />);
