from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class JSONFormatter(logging.Formatter):
    """Structured JSON logs for production."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if getattr(record, "request_id", None):
            log_obj["request_id"] = record.request_id
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj, ensure_ascii=False)


def setup_logging(
    *,
    level: str = "INFO",
    json_format: bool = True,
    log_file: str | None = None,
) -> None:
    """Configure the ``openevo`` logger tree."""
    root = logging.getLogger("openevo")
    root.handlers.clear()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    stream = logging.StreamHandler(sys.stdout)
    if json_format:
        stream.setFormatter(JSONFormatter())
    else:
        stream.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
    root.addHandler(stream)

    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(JSONFormatter() if json_format else logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        root.addHandler(fh)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
