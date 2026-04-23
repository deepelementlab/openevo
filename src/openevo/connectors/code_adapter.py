from __future__ import annotations

from typing import Any

from openevo.connectors.base import ExperienceAdapter
from openevo.core.experience_models import RawExperience


class CodeAdapter(ExperienceAdapter):
    """Derives experiences from commit / diff shaped dicts."""

    @property
    def source_type(self) -> str:
        return "code"

    def extract(self, raw: Any) -> list[RawExperience]:
        if not isinstance(raw, dict):
            return []
        payload = raw
        if "diff" not in raw and "message" not in raw:
            inner = raw.get("content")
            if isinstance(inner, dict):
                payload = {**inner, **{k: v for k, v in raw.items() if k != "content"}}
        if "diff" in payload or "message" in payload:
            return [self._from_commit(payload)]
        return []

    def _from_commit(self, commit: dict[str, Any]) -> RawExperience:
        msg = str(commit.get("message", ""))
        diff = str(commit.get("diff", ""))[:12000]
        files = commit.get("files") or commit.get("changed_files") or []
        lessons = []
        if commit.get("lessons"):
            lessons = list(commit["lessons"])
        elif msg:
            lessons = [f"commit: {msg[:500]}"]
        return RawExperience(
            content={
                "summary": msg or "code change",
                "modality": "code",
                "domain": commit.get("domain", "engineering"),
                "diff": diff,
                "files": files,
            },
            context={
                "author": commit.get("author"),
                "branch": commit.get("branch"),
                "sha": commit.get("sha"),
            },
            lessons=lessons,
            outcome=commit.get("outcome"),
        )
