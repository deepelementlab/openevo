from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from openevo.core.experience_models import CanonicalExperience, RawExperience


class ExperienceAdapter(ABC):
    """Maps external payloads into one or more ``RawExperience`` records."""

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Connector name: code, doc, chat, tool, error."""

    def extract(self, raw: Any) -> list[RawExperience]:
        """Override in subclasses for structured ingestion."""
        raise NotImplementedError

    def canonicalize(self, raw: RawExperience) -> CanonicalExperience:
        lessons = raw.lessons or raw.content.get("lessons") or []
        if isinstance(lessons, str):
            lessons = [lessons]
        modality = raw.content.get("modality") or self.source_type
        domain = raw.content.get("domain") or raw.context.get("domain") or "general"
        summary = str(raw.content.get("summary") or raw.content)[:8000]
        return CanonicalExperience(
            summary=summary,
            payload={**raw.content, "context": raw.context, "lessons": lessons},
            modality=str(modality),
            domain=str(domain),
        )
