from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("openevo.config.watcher")

_CONFIG_NAMES = frozenset({"config.json", "config.yaml", "config.yml"})


class DataDirConfigWatcher:
    """Watch data directory for config file changes."""

    def __init__(self, data_dir: Path, reload_fn: Callable[[], None]) -> None:
        self.data_dir = data_dir.resolve()
        self.reload_fn = reload_fn
        self._last_reload = 0.0
        self._lock = threading.Lock()
        self._observer: Any = None

    def start(self) -> None:
        try:
            from watchdog.events import FileModifiedEvent, FileSystemEventHandler
            from watchdog.observers import Observer
        except ImportError:
            log.warning("watchdog not installed; config hot-reload disabled")
            return

        self.data_dir.mkdir(parents=True, exist_ok=True)
        watcher = self

        class _Handler(FileSystemEventHandler):
            def on_modified(self, event: FileModifiedEvent) -> None:
                if event.is_directory:
                    return
                name = Path(event.src_path).name
                if name in _CONFIG_NAMES:
                    watcher._debounced_reload()

        self._observer = Observer()
        self._observer.schedule(_Handler(), str(self.data_dir), recursive=False)
        self._observer.start()
        log.info("watching %s for %s", self.data_dir, sorted(_CONFIG_NAMES))

    def stop(self) -> None:
        if self._observer is not None:
            try:
                self._observer.stop()
                self._observer.join(timeout=3.0)
            except Exception as e:
                log.warning("observer_stop_failed: %s", e)
            self._observer = None

    def _debounced_reload(self) -> None:
        with self._lock:
            now = time.time()
            if now - self._last_reload < 1.0:
                return
            self._last_reload = now
        try:
            self.reload_fn()
            log.info("config reloaded (file change under %s)", self.data_dir)
        except Exception:
            log.exception("config_reload_failed")
