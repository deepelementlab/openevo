from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openevo.config.settings import OpenEvoConfig, get_settings


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clip(v: object, limit: int = 1200) -> str:
    s = str(v or "")
    return s if len(s) <= limit else s[:limit] + "..."


class EvoObserver:
    """Record tool/API observations for learning loops."""

    def __init__(self, cfg: OpenEvoConfig | None = None) -> None:
        self._cfg = cfg or get_settings()
        self._lock = threading.Lock()
        self._listeners: list[Callable[[dict[str, Any]], None]] = []

    def subscribe(self, fn: Callable[[dict[str, Any]], None]) -> None:
        self._listeners.append(fn)

    def record(
        self,
        *,
        phase: str,
        session_id: str,
        tool_name: str,
        tool_input: object | None = None,
        tool_output: object | None = None,
        is_error: bool = False,
        source: str = "openevo",
    ) -> None:
        row = {
            "timestamp": _now_iso(),
            "event": phase,
            "session": session_id,
            "tool": tool_name,
            "input": _clip(tool_input),
            "output": _clip(tool_output),
            "is_error": bool(is_error),
            "source": source,
        }
        path = get_settings().resolve_data_dir() / "learning" / "observations.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            try:
                with path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            except OSError:
                return
        for fn in self._listeners:
            try:
                fn(row)
            except Exception:
                pass


_default_observer: EvoObserver | None = None
_obs_lock = threading.Lock()


def get_observer() -> EvoObserver:
    global _default_observer
    with _obs_lock:
        if _default_observer is None:
            _default_observer = EvoObserver()
        return _default_observer
