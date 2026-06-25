const API_BASE = import.meta.env.VITE_API_URL || "";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "content-type": "application/json",
      ...(options.headers || {})
    },
    ...options
  });

  const payload = await response.json();
  if (!response.ok || payload.error) {
    throw new Error(payload.error?.message || `Request failed: ${response.status}`);
  }
  return payload;
}

export const api = {
  health: () => request("/health"),
  tools: () => request("/api/tools"),
  rules: () => request("/api/policy/rules"),
  saveRule: (rule) =>
    request("/api/policy/rules", {
      method: "POST",
      body: JSON.stringify(rule)
    }),
  deleteRule: (id) =>
    request(`/api/policy/rules/${id}`, {
      method: "DELETE"
    }),
  settings: () => request("/api/settings"),
  saveSettings: (settings) =>
    request("/api/settings", {
      method: "POST",
      body: JSON.stringify(settings)
    }),
  approvals: () => request("/api/approvals"),
  decideApproval: (id, decision) =>
    request(`/api/approvals/${id}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision })
    }),
  logs: (filters = {}) => {
    const params = new URLSearchParams(
      Object.entries(filters).filter(([, value]) => value)
    );
    return request(`/api/logs${params.toString() ? `?${params}` : ""}`);
  },
  verifyChain: () => request("/api/logs/verify"),
  sendMessage: (message, conversationId) =>
    request("/api/agent/message", {
      method: "POST",
      body: JSON.stringify({
        message,
        conversation_id: conversationId || undefined
      })
    })
};
