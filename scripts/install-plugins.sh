#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE_URL="${OPENEVO_BASE_URL:-http://127.0.0.1:8765}"
export OPENEVO_BASE_URL="${BASE_URL}"

echo "=== OpenEvo Plugin Installer ==="

if [[ "${SKIP_HEALTH_CHECK:-}" != "1" ]]; then
  if command -v curl >/dev/null 2>&1; then
    if curl -sf "${BASE_URL}/health" >/dev/null; then
      echo "OpenEvo server OK at ${BASE_URL}"
    else
      echo "Warning: no response from ${BASE_URL}/health (start with: evo serve)"
      if [[ -t 0 ]]; then
        read -r -p "Continue? [y/N] " ans || true
        [[ "${ans:-}" =~ ^[Yy]$ ]] || exit 1
      fi
    fi
  fi
fi

echo ""
bash "${ROOT}/plugins/claude-code-plugin/install.sh"

echo ""
node "${ROOT}/plugins/openclaw-plugin/install.mjs"

echo ""
echo "Done. OPENEVO_BASE_URL=${BASE_URL}"
