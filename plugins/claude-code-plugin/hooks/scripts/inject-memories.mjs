import { readStdinJson, groupIdFromCwd, searchMemories, formatMemories } from "./utils.mjs";

const input = await readStdinJson();
const cwd = input.cwd || process.cwd();
const gid = groupIdFromCwd(cwd);
const prompt = String(input.prompt || input.message || "").trim();
const q = prompt.slice(0, 500) || "context";
const rows = await searchMemories(q, gid);
const addition = formatMemories(rows);
process.stdout.write(JSON.stringify({ systemPromptAddition: addition || "" }));
