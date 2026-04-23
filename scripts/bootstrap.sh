#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
pip install -e .
echo "Run: evo serve"
echo "Or: uvicorn openevo.api.server:app --host 127.0.0.1 --port 8765"
