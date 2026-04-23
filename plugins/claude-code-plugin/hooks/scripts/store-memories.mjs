import { readStdinJson, groupIdFromCwd, saveMessages } from "./utils.mjs";

const input = await readStdinJson();
const cwd = input.cwd || process.cwd();
const gid = groupIdFromCwd(cwd);
const transcript = input.transcript || input.messages || [];
const last = Array.isArray(transcript) ? transcript.slice(-6) : [];
const messages = last
  .filter((m) => m && (m.role === "user" || m.role === "assistant"))
  .map((m) => ({
    role: m.role,
    content: String(m.content || "").slice(0, 12000),
    timestamp: Date.now(),
  }));
if (messages.length) {
  await saveMessages(gid, messages);
}
process.stdout.write(JSON.stringify({ ok: true, saved: messages.length }));
