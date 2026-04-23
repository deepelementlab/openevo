import { readStdinJson, groupIdFromCwd, saveMessages } from "./utils.mjs";

const input = await readStdinJson();
const cwd = input.cwd || process.cwd();
const gid = groupIdFromCwd(cwd);
await saveMessages(gid, [
  {
    role: "user",
    content: "[session end] " + String(input.summary || "session closed").slice(0, 2000),
    timestamp: Date.now(),
  },
]);
process.stdout.write(JSON.stringify({ ok: true }));
