import { createEngine } from "./src/engine.js";

const pluginMeta = { id: "openevo-context", version: "0.1.0" };

export default function register(api) {
  const log = api.logger || console;
  log.info?.(`[${pluginMeta.id}] registering OpenEvo context engine`);
  api.registerContextEngine?.(pluginMeta.id, (pluginConfig) =>
    createEngine(pluginMeta, pluginConfig || {}, log)
  );
}
