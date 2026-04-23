from __future__ import annotations

from typing import Any

from openevo.connectors.base import ExperienceAdapter
from openevo.core.experience_models import RawExperience


class ChatAdapter(ExperienceAdapter):
    """Turns chat transcripts into decision / pattern experiences."""

    @property
    def source_type(self) -> str:
        return "chat"

    def extract(self, raw: Any) -> list[RawExperience]:
        if isinstance(raw, list):
            return [self._from_session({"messages": raw, "session_id": "inline"})]
        if isinstance(raw, dict):
            msgs = raw.get("messages")
            if msgs is None and isinstance(raw.get("content"), dict):
                msgs = raw["content"].get("messages")
            if msgs:
                ctx = raw.get("context") or {}
                sid = raw.get("session_id") or ctx.get("session_id") or "inline"
                domain = raw.get("domain") or (
                    raw.get("content") or {}
                ).get("domain")
                return [
                    self._from_session(
                        {
                            "messages": msgs,
                            "session_id": sid,
                            "domain": domain,
                            "summary": (raw.get("content") or {}).get("summary"),
                            "outcome": raw.get("outcome"),
                            "lessons": raw.get("lessons", []),
                        }
                    )
                ]
        return []

    def _from_session(self, session: dict[str, Any]) -> RawExperience:
        messages = session.get("messages") or []
        lines: list[str] = []
        for m in messages:
            if isinstance(m, dict):
                role = m.get("role", "user")
                content = m.get("content", "")
                lines.append(f"{role}: {content}")
            else:
                lines.append(str(m))
        transcript = "\n".join(lines)[:12000]
        return RawExperience(
            content={
                "summary": session.get("summary") or "chat session",
                "modality": "text",
                "domain": session.get("domain", "dialogue"),
                "transcript": transcript,
                "session_id": session.get("session_id"),
            },
            context={"turns": len(messages)},
            lessons=session.get("lessons", []),
            outcome=session.get("outcome"),
        )
