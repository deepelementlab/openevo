from __future__ import annotations

from typing import Any

from openevo.connectors.base import ExperienceAdapter
from openevo.core.experience_models import RawExperience


class ToolAdapter(ExperienceAdapter):
    """Tool / API invocation patterns as experience."""

    @property
    def source_type(self) -> str:
        return "tool"

    def extract(self, raw: Any) -> list[RawExperience]:
        if not isinstance(raw, dict):
            return []
        name = str(raw.get("tool_name") or raw.get("name") or "tool")
        return [
            RawExperience(
                content={
                    "summary": f"tool:{name}",
                    "modality": "structured",
                    "domain": raw.get("domain", "automation"),
                    "tool_name": name,
                    "arguments": raw.get("arguments") or raw.get("args"),
                    "result": raw.get("result"),
                },
                context={"phase": raw.get("phase"), "session_id": raw.get("session_id")},
                lessons=list(raw.get("lessons", [])),
                outcome=raw.get("outcome"),
            )
        ]
