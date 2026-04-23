from __future__ import annotations

import logging
from openevo.core.experience_models import Experience, ExperienceID, Relation
from openevo.core.stores.base import GraphStore

log = logging.getLogger("openevo.stores.neo4j")


class Neo4jGraphStore(GraphStore):
    def __init__(self, uri: str, user: str, password: str, database: str = "neo4j") -> None:
        self._driver = None
        self._database = database
        try:
            from neo4j import GraphDatabase

            self._driver = GraphDatabase.driver(uri, auth=(user, password))
            self._driver.verify_connectivity()
        except Exception as e:  # pragma: no cover
            log.warning("neo4j backend unavailable: %s", e)
            self._driver = None

    @property
    def is_available(self) -> bool:
        return self._driver is not None

    def _ensure(self) -> None:
        if self._driver is None:
            raise RuntimeError("neo4j backend unavailable")

    def add_node(self, exp: Experience) -> None:
        self._ensure()
        with self._driver.session(database=self._database) as s:
            s.run(
                """
                MERGE (e:Experience {id: $id})
                SET e.domain = $domain,
                    e.modality = $modality,
                    e.source_agent = $source_agent,
                    e.content_summary = $summary,
                    e.timestamp = $timestamp
                """,
                id=exp.id,
                domain=exp.domain,
                modality=exp.modality,
                source_agent=exp.source_agent,
                summary=exp.content_summary[:2000],
                timestamp=exp.timestamp.isoformat(),
            )

    def add_edge(
        self,
        from_id: ExperienceID,
        to_id: ExperienceID,
        relation: Relation,
        confidence: float,
    ) -> None:
        self._ensure()
        rel = relation.value.upper()
        with self._driver.session(database=self._database) as s:
            s.run(
                f"""
                MATCH (a:Experience {{id: $from_id}})
                MATCH (b:Experience {{id: $to_id}})
                MERGE (a)-[r:{rel}]->(b)
                SET r.confidence = $confidence
                """,
                from_id=from_id,
                to_id=to_id,
                confidence=confidence,
            )

    def out_edges(self, from_id: ExperienceID) -> list[tuple[ExperienceID, Relation, float]]:
        self._ensure()
        with self._driver.session(database=self._database) as s:
            recs = s.run(
                """
                MATCH (a:Experience {id: $from_id})-[r]->(b:Experience)
                RETURN b.id as id, type(r) as rel, coalesce(r.confidence, 1.0) as confidence
                """,
                from_id=from_id,
            )
            out = []
            for r in recs:
                rel = str(r["rel"]).lower()
                try:
                    rel_enum = Relation(rel)
                except ValueError:
                    continue
                out.append((str(r["id"]), rel_enum, float(r["confidence"])))
            return out

    def in_edges(self, to_id: ExperienceID) -> list[tuple[ExperienceID, Relation, float]]:
        self._ensure()
        with self._driver.session(database=self._database) as s:
            recs = s.run(
                """
                MATCH (a:Experience)-[r]->(b:Experience {id: $to_id})
                RETURN a.id as id, type(r) as rel, coalesce(r.confidence, 1.0) as confidence
                """,
                to_id=to_id,
            )
            out = []
            for r in recs:
                rel = str(r["rel"]).lower()
                try:
                    rel_enum = Relation(rel)
                except ValueError:
                    continue
                out.append((str(r["id"]), rel_enum, float(r["confidence"])))
            return out
