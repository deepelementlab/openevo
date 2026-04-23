from __future__ import annotations

import json
import re
import time
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from openevo.config.settings import OpenEvoConfig, get_settings


@dataclass
class Instinct:
    id: str
    trigger: str
    confidence: float
    domain: str
    source: str
    content: str


@dataclass
class LearningReport:
    observations_processed: int
    instincts_created: int
    evolved_files: list[str]
    messages: list[str]


def _update_confidence(base: float, *, success_count: int, failure_count: int) -> float:
    delta = 0.05 * success_count - 0.07 * failure_count
    return max(0.1, min(0.95, base + delta))


class LearningService:
    """Lightweight closed-loop: observations.jsonl -> instincts -> evolved markdown stubs."""

    def __init__(self, cfg: OpenEvoConfig | None = None) -> None:
        self._cfg = cfg or get_settings()
        self._root = self._cfg.resolve_data_dir() / "learning"
        self._root.mkdir(parents=True, exist_ok=True)
        self._obs = self._root / "observations.jsonl"
        self._instincts = self._root / "instincts"
        self._evolved = self._root / "evolved"
        self._capsules = self._root / "capsules"
        for d in (self._instincts, self._evolved, self._capsules):
            d.mkdir(parents=True, exist_ok=True)

    def read_recent_observations(self, limit: int = 400) -> list[dict[str, Any]]:
        if not self._obs.exists():
            return []
        lines = self._obs.read_text(encoding="utf-8").splitlines()
        out: list[dict[str, Any]] = []
        for one in lines[-limit:]:
            try:
                obj = json.loads(one)
                if isinstance(obj, dict):
                    out.append(obj)
            except Exception:
                continue
        return out

    def learn_from_observations(self) -> tuple[list[Instinct], str]:
        ls = self._cfg.learning
        rows = self.read_recent_observations()
        if not rows:
            return [], "No observations yet."
        counts: dict[str, int] = defaultdict(int)
        failures: dict[str, int] = defaultdict(int)
        for row in rows:
            tool = str(row.get("tool") or "").strip()
            if not tool:
                continue
            counts[tool] += 1
            if bool(row.get("is_error")):
                failures[tool] += 1
        instincts: list[Instinct] = []
        for tool, n in sorted(counts.items(), key=lambda kv: -kv[1])[:8]:
            if n < ls.min_tool_uses_for_instinct:
                continue
            instincts.append(
                Instinct(
                    id=f"use-{tool}-early",
                    trigger="similar tasks",
                    confidence=_update_confidence(0.35, success_count=n, failure_count=0),
                    domain="workflow",
                    source="observation",
                    content=f"Prefer `{tool}` early when appropriate (seen {n}x).",
                )
            )
        for tool, n in sorted(failures.items(), key=lambda kv: -kv[1])[:6]:
            if n < ls.min_failures_for_instinct:
                continue
            instincts.append(
                Instinct(
                    id=f"guard-{tool}",
                    trigger=f"`{tool}` failures",
                    confidence=_update_confidence(0.4, success_count=0, failure_count=n),
                    domain="debugging",
                    source="observation",
                    content=f"Add validation around `{tool}` ({n} failures seen).",
                )
            )
        instincts = instincts[: ls.max_instincts_per_learn]
        if not instincts:
            return [], "Not enough repeated patterns."
        stamp = time.strftime("%Y%m%d-%H%M%S")
        out = self._instincts / f"learned-{stamp}.json"
        out.write_text(
            json.dumps([asdict(i) for i in instincts], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return instincts, f"Wrote {len(instincts)} instinct(s) to {out}"

    def load_all_instincts(self) -> list[Instinct]:
        out: list[Instinct] = []
        for p in sorted(self._instincts.glob("*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get("id"):
                            out.append(
                                Instinct(
                                    id=str(item["id"]),
                                    trigger=str(item.get("trigger", "")),
                                    confidence=float(item.get("confidence", 0.5)),
                                    domain=str(item.get("domain", "general")),
                                    source=str(item.get("source", "file")),
                                    content=str(item.get("content", "")),
                                )
                            )
            except Exception:
                continue
        return out

    def evolve_skills(self, *, dry_run: bool = True) -> tuple[list[str], str]:
        rows = self.load_all_instincts()
        th = self._cfg.learning.evolve_min_instincts
        if len(rows) < th:
            return [], f"Need >= {th} instincts; have {len(rows)}."
        # cluster by domain
        by_dom: dict[str, list[Instinct]] = defaultdict(list)
        for r in rows:
            by_dom[r.domain].append(r)
        created: list[str] = []
        lines = [f"# Evolve ({'dry' if dry_run else 'execute'})\n"]
        for dom, group in sorted(by_dom.items(), key=lambda kv: -len(kv[1]))[:8]:
            if len(group) < self._cfg.learning.evolve_cluster_threshold:
                continue
            name = re.sub(r"[^a-z0-9]+", "-", dom.lower()).strip("-") or "cluster"
            lines.append(f"- {dom}: {len(group)} instincts -> skill `{name}`\n")
            if not dry_run:
                d = self._evolved / name
                d.mkdir(parents=True, exist_ok=True)
                body = "\n".join(f"- {x.id}: {x.content}" for x in group[:20])
                (d / "SKILL.md").write_text(
                    f"# {name}\n\nEvolved from {len(group)} instincts.\n\n## Rules\n\n{body}\n",
                    encoding="utf-8",
                )
                created.append(str(d / "SKILL.md"))
        return created, "".join(lines)

    def run_autonomous_cycle(self, *, dry_run: bool = False) -> LearningReport:
        msgs: list[str] = []
        instincts, m1 = self.learn_from_observations()
        msgs.append(m1)
        paths, m2 = self.evolve_skills(dry_run=dry_run)
        msgs.append(m2)
        return LearningReport(
            observations_processed=len(self.read_recent_observations()),
            instincts_created=len(instincts),
            evolved_files=paths,
            messages=msgs,
        )

    def save_ecap(self, payload: dict[str, Any]) -> Path:
        cid = str(payload.get("ecap_id") or f"ecap-{uuid.uuid4().hex[:12]}")
        payload = {**payload, "ecap_id": cid}
        path = self._capsules / f"{cid}.json"
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return path
