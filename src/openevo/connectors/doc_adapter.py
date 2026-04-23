from __future__ import annotations

from typing import Any

from openevo.connectors.base import ExperienceAdapter
from openevo.core.experience_models import RawExperience


class DocAdapter(ExperienceAdapter):
    """Structured document / article to experience."""

    @property
    def source_type(self) -> str:
        return "doc"

    def extract(self, raw: Any) -> list[RawExperience]:
        if not isinstance(raw, dict):
            return []
        body = str(raw.get("body") or raw.get("text") or "")
        title = str(raw.get("title") or "document")
        return [
            RawExperience(
                content={
                    "summary": title,
                    "modality": "text",
                    "domain": raw.get("domain", "knowledge"),
                    "body": body[:12000],
                    "path": raw.get("path"),
                },
                context={"format": raw.get("format", "markdown")},
                lessons=list(raw.get("lessons", [])),
                outcome=raw.get("outcome"),
            )
        ]
