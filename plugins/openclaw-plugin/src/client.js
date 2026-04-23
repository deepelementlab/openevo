const baseUrl =
  process.env.OPENEVO_BASE_URL || globalThis.OPENEVO_BASE_URL || "http://127.0.0.1:8765";

export async function searchMemories(query, groupId, topK = 8) {
  const resp = await fetch(`${baseUrl}/api/v1/memories/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, top_k: topK, filters: { group_id: groupId } }),
  });
  if (!resp.ok) return [];
  const data = await resp.json();
  return data?.data?.memories || [];
}

export async function saveMessages(groupId, userId, messages) {
  const resp = await fetch(`${baseUrl}/api/v1/memories/group`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ group_id: groupId, user_id: userId, messages }),
  });
  return resp.ok;
}

export async function wikiQuery(query) {
  const resp = await fetch(`${baseUrl}/api/v1/notes/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, limit: 6 }),
  });
  if (!resp.ok) return [];
  const data = await resp.json();
  return data?.results || [];
}
