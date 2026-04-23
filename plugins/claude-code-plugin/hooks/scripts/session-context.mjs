import { readStdinJson, groupIdFromCwd, searchMemories, formatMemories } from "./utils.mjs";

const input = await readStdinJson();
const cwd = input.cwd || process.cwd();
const gid = groupIdFromCwd(cwd);
const rows = await searchMemories("session context resume", gid);
const addition = formatMemories(rows.slice(0, 3));
process.stdout.write(JSON.stringify({ systemPromptAddition: addition || "" }));
