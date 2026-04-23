from __future__ import annotations

from typing import Any

from openevo.connectors.base import ExperienceAdapter
from openevo.core.experience_models import RawExperience


class ErrorAdapter(ExperienceAdapter):
    """Captures debugging knowledge from errors and stack traces."""

    @property
    def source_type(self) -> str:
        return "error"

    def extract(self, raw: Any) -> list[RawExperience]:
        if not isinstance(raw, dict):
            return []
        payload = raw.get("content") if isinstance(raw.get("content"), dict) else raw
        if not isinstance(payload, dict):
            return []
        return [self._from_error({**payload, "lessons": raw.get("lessons", [])})]

    def _from_error(self, err: dict[str, Any]) -> RawExperience:
        stack = str(err.get("stacktrace") or err.get("stack") or "")
        msg = str(err.get("message") or err.get("error") or "error")
        resolution = err.get("resolution")
        lessons = list(err.get("lessons") or [])
        if resolution:
            lessons.append(f"resolution: {resolution}")
        if not lessons:
            lessons = ["capture failure context for future retrieval"]
        return RawExperience(
            content={
                "summary": msg[:2000],
                "modality": "structured",
                "domain": err.get("domain", "reliability"),
                "stacktrace": stack[:8000],
                "environment": err.get("environment"),
            },
            context={"component": err.get("component")},
            lessons=lessons,
            outcome=resolution,
        )
