#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-${HOME}/.claude}"
PLUGIN_DIR="${CLAUDE_DIR}/plugins/openevo-memory"
BASE_URL="${OPENEVO_BASE_URL:-http://127.0.0.1:8765}"

mkdir -p "${PLUGIN_DIR}"
cp -r "${ROOT}/hooks" "${ROOT}/plugin.json" "${PLUGIN_DIR}/" 2>/dev/null || cp -r "${ROOT}"/* "${PLUGIN_DIR}/"

{
  echo "OPENEVO_BASE_URL=${BASE_URL}"
  echo "OPENEVO_USER_ID=${OPENEVO_USER_ID:-claude-code-user}"
} > "${PLUGIN_DIR}/.env.openevo"

echo "OpenEvo Claude Code plugin copied to: ${PLUGIN_DIR}"
echo "OPENEVO_BASE_URL=${BASE_URL}"
if command -v claude >/dev/null 2>&1; then
  echo "Attempting: claude plugin install ${PLUGIN_DIR}"
  claude plugin install "${PLUGIN_DIR}" || echo "If install failed, add this folder via Claude Code plugin UI."
else
  echo "Claude CLI not in PATH; register ${PLUGIN_DIR} manually in Claude Code."
fi
