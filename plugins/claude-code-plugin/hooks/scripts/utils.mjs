const baseUrl = process.env.OPENEVO_BASE_URL || process.env.SADDLE_BASE_URL || "http://127.0.0.1:8765";
const userId = process.env.OPENEVO_USER_ID || "claude-code-user";

export async function readStdinJson() {
  let input = "";
  for await (const chunk of process.stdin) input += chunk;
  try {
    return JSON.parse(input || "{}");
  } catch {
    return {};
  }
}

export function groupIdFromCwd(cwd) {
  return `claude-code:${cwd || "unknown"}`;
}

export async function searchMemories(query, groupId) {
  const resp = await fetch(`${baseUrl}/api/v1/memories/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, top_k: 8, filters: { group_id: groupId } }),
  });
  if (!resp.ok) return [];
  const data = await resp.json();
  return data?.data?.memories || [];
}

export async function saveMessages(groupId, messages) {
  const resp = await fetch(`${baseUrl}/api/v1/memories/group`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ group_id: groupId, user_id: userId, messages }),
  });
  return resp.ok;
}

export function formatMemories(rows) {
  if (!rows.length) return "";
  const lines = rows.map((r) => `- (${r.role || "?"}) ${String(r.content || "").slice(0, 500)}`);
  return "## OpenEvo memory (retrieved)\n\n" + lines.join("\n");
}
