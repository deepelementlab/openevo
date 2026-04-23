import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OPENCLAW_CONFIG = path.join(os.homedir(), ".openclaw", "openclaw.json");
const PLUGIN_ROOT = path.resolve(__dirname);

let config = { plugins: { load: { paths: [] } } };
if (fs.existsSync(OPENCLAW_CONFIG)) {
  try {
    config = JSON.parse(fs.readFileSync(OPENCLAW_CONFIG, "utf8"));
  } catch (e) {
    console.error("Error reading OpenClaw config:", e.message);
  }
}
if (!config.plugins) config.plugins = {};
if (!config.plugins.load) config.plugins.load = {};
if (!Array.isArray(config.plugins.load.paths)) config.plugins.load.paths = [];

if (!config.plugins.load.paths.includes(PLUGIN_ROOT)) {
  config.plugins.load.paths.push(PLUGIN_ROOT);
  console.log("Added plugin path:", PLUGIN_ROOT);
} else {
  console.log("Plugin path already present:", PLUGIN_ROOT);
}

fs.mkdirSync(path.dirname(OPENCLAW_CONFIG), { recursive: true });
fs.writeFileSync(OPENCLAW_CONFIG, JSON.stringify(config, null, 2));
console.log("\nOpenEvo OpenClaw plugin registered.");
console.log("Config:", OPENCLAW_CONFIG);
console.log("OPENEVO_BASE_URL=", process.env.OPENEVO_BASE_URL || "http://127.0.0.1:8765");
console.log("\nRestart gateway: openclaw gateway restart");
