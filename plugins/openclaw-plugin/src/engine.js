import { searchMemories, saveMessages, wikiQuery } from "./client.js";

function toText(v) {
  if (!v) return "";
  if (typeof v === "string") return v;
  if (Array.isArray(v)) return v.map((p) => (typeof p === "string" ? p : p?.text || "")).join(" ");
  return String(v);
}

export function createEngine(meta, cfg, log) {
  const userId = cfg.userId || "openclaw-user";
  const groupId = cfg.groupId || "openclaw-default";
  let savedUpTo = 0;

  return {
    async assemble({ messages, prompt }) {
      const q = toText(prompt) || toText([...messages].reverse().find((m) => m.role === "user")?.content);
      if (!q || q.length < 2) return { messages, estimatedTokens: 0 };
      try {
        const mem = await searchMemories(q.slice(0, 800), groupId, 6);
        const wiki = await wikiQuery(q.slice(0, 400));
        const lines = [];
        if (mem.length) {
          lines.push("## OpenEvo memories");
          mem.forEach((m) => lines.push(`- (${m.role}) ${String(m.content || "").slice(0, 400)}`));
        }
        if (wiki.length) {
          lines.push("## Wiki hits");
          wiki.forEach((w) => lines.push(`- ${w.title}: ${w.snippet || ""}`));
        }
        const ctx = lines.join("\n");
        if (!ctx) return { messages, estimatedTokens: 0 };
        return {
          messages,
          estimatedTokens: Math.floor(ctx.length / 4),
          systemPromptAddition: ctx,
        };
      } catch (e) {
        log.warn?.(`[${meta.id}] assemble failed: ${e}`);
        return { messages, estimatedTokens: 0 };
      }
    },

    async afterTurn({ messages, prePromptMessageCount }) {
      const sliceStart =
        prePromptMessageCount !== undefined ? Math.max(prePromptMessageCount, savedUpTo) : savedUpTo;
      const newMessages = sliceStart > 0 ? messages.slice(sliceStart) : messages.slice(-4);
      if (!newMessages.length) return;
      const converted = newMessages
        .filter((m) => m.role === "user" || m.role === "assistant")
        .map((m) => ({
          role: m.role,
          content: toText(m.content).slice(0, 12000),
          timestamp: Date.now(),
        }))
        .filter((m) => m.content);
      if (!converted.length) return;
      try {
        await saveMessages(groupId, userId, converted);
        savedUpTo = messages.length;
        log.info?.(`[${meta.id}] afterTurn saved ${converted.length}`);
      } catch (e) {
        log.warn?.(`[${meta.id}] afterTurn save failed: ${e}`);
      }
    },
  };
}
