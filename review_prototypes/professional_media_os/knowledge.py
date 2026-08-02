"""Temporal knowledge graph and institutional-memory helpers.

This graph is deliberately small and explicit. It stores observations and inferences as
separate nodes, preserves contradictory statements, and never overwrites history.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Set, Tuple

from .contracts import (
    ContractError,
    EvidenceRef,
    KnowledgeKind,
    Maturity,
    stable_hash,
    utc_now_iso,
)


@dataclass(frozen=True)
class KnowledgeNode:
    node_id: str
    node_type: str
    label: str
    properties: Mapping[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        if not self.node_id or not self.node_type or not self.label:
            raise ContractError("knowledge nodes require id, type, and label")


@dataclass(frozen=True)
class KnowledgeEdge:
    edge_id: str
    source_id: str
    relation: str
    target_id: str
    kind: KnowledgeKind
    confidence: float
    evidence_ids: Tuple[str, ...]
    maturity: Maturity
    observed_at: str
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    supersedes: Optional[str] = None
    properties: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not all((self.edge_id, self.source_id, self.relation, self.target_id)):
            raise ContractError("knowledge edges require id, endpoints, and relation")
        if not 0.0 <= self.confidence <= 1.0:
            raise ContractError("knowledge edge confidence must be between 0 and 1")
        if self.kind is not KnowledgeKind.OBSERVATION and not self.evidence_ids:
            raise ContractError("inferences, recommendations, and decisions require evidence")


@dataclass(frozen=True)
class Contradiction:
    left_edge_id: str
    right_edge_id: str
    reason: str


class KnowledgeGraph:
    """In-memory reference graph with explicit lineage and temporal filtering."""

    def __init__(self) -> None:
        self._nodes: Dict[str, KnowledgeNode] = {}
        self._edges: Dict[str, KnowledgeEdge] = {}
        self._evidence: Dict[str, EvidenceRef] = {}
        self._contradictions: Set[Contradiction] = set()

    def add_evidence(self, evidence: EvidenceRef) -> None:
        existing = self._evidence.get(evidence.evidence_id)
        if existing is not None and existing != evidence:
            raise ContractError(f"evidence id collision: {evidence.evidence_id}")
        self._evidence[evidence.evidence_id] = evidence

    def add_node(self, node: KnowledgeNode) -> None:
        existing = self._nodes.get(node.node_id)
        if existing is not None and existing != node:
            raise ContractError(f"node id collision: {node.node_id}")
        self._nodes[node.node_id] = node

    def add_edge(self, edge: KnowledgeEdge) -> None:
        if edge.source_id not in self._nodes or edge.target_id not in self._nodes:
            raise ContractError("edge endpoints must exist before the edge is added")
        missing = [item for item in edge.evidence_ids if item not in self._evidence]
        if missing:
            raise ContractError(f"edge references unknown evidence: {missing}")
        existing = self._edges.get(edge.edge_id)
        if existing is not None and existing != edge:
            raise ContractError(f"edge id collision: {edge.edge_id}")
        if edge.supersedes is not None and edge.supersedes not in self._edges:
            raise ContractError(f"superseded edge does not exist: {edge.supersedes}")
        self._edges[edge.edge_id] = edge

    def observe(
        self,
        *,
        source_id: str,
        relation: str,
        target_id: str,
        evidence_ids: Sequence[str],
        confidence: float,
        observed_at: Optional[str] = None,
        maturity: Maturity = Maturity.ANECDOTE,
        valid_from: Optional[str] = None,
        valid_until: Optional[str] = None,
        properties: Optional[Mapping[str, Any]] = None,
    ) -> KnowledgeEdge:
        return self._create_edge(
            source_id=source_id,
            relation=relation,
            target_id=target_id,
            kind=KnowledgeKind.OBSERVATION,
            evidence_ids=tuple(evidence_ids),
            confidence=confidence,
            observed_at=observed_at or utc_now_iso(),
            maturity=maturity,
            valid_from=valid_from,
            valid_until=valid_until,
            properties=properties or {},
        )

    def infer(
        self,
        *,
        source_id: str,
        relation: str,
        target_id: str,
        evidence_ids: Sequence[str],
        confidence: float,
        maturity: Maturity,
        observed_at: Optional[str] = None,
        valid_from: Optional[str] = None,
        valid_until: Optional[str] = None,
        properties: Optional[Mapping[str, Any]] = None,
    ) -> KnowledgeEdge:
        if maturity is Maturity.ESTABLISHED and len(set(evidence_ids)) < 2:
            raise ContractError("established inferences require at least two evidence records")
        return self._create_edge(
            source_id=source_id,
            relation=relation,
            target_id=target_id,
            kind=KnowledgeKind.INFERENCE,
            evidence_ids=tuple(evidence_ids),
            confidence=confidence,
            observed_at=observed_at or utc_now_iso(),
            maturity=maturity,
            valid_from=valid_from,
            valid_until=valid_until,
            properties=properties or {},
        )

    def _create_edge(self, **kwargs: Any) -> KnowledgeEdge:
        edge_seed = {
            "source_id": kwargs["source_id"],
            "relation": kwargs["relation"],
            "target_id": kwargs["target_id"],
            "kind": kwargs["kind"].value,
            "evidence_ids": sorted(kwargs["evidence_ids"]),
            "observed_at": kwargs["observed_at"],
        }
        edge = KnowledgeEdge(edge_id=f"edge-{stable_hash(edge_seed)[:20]}", **kwargs)
        self.add_edge(edge)
        return edge

    def mark_contradiction(self, left_edge_id: str, right_edge_id: str, reason: str) -> None:
        if left_edge_id not in self._edges or right_edge_id not in self._edges:
            raise ContractError("both contradiction edges must exist")
        if left_edge_id == right_edge_id:
            raise ContractError("an edge cannot contradict itself")
        pair = tuple(sorted((left_edge_id, right_edge_id)))
        self._contradictions.add(
            Contradiction(left_edge_id=pair[0], right_edge_id=pair[1], reason=reason)
        )

    def neighbors(
        self,
        node_id: str,
        *,
        relation: Optional[str] = None,
        as_of: Optional[str] = None,
        minimum_maturity: Optional[Maturity] = None,
    ) -> Tuple[KnowledgeEdge, ...]:
        if node_id not in self._nodes:
            raise ContractError(f"unknown node: {node_id}")
        maturity_rank = {
            Maturity.ANECDOTE: 0,
            Maturity.DIRECTIONAL: 1,
            Maturity.EXPERIMENTAL: 2,
            Maturity.ESTABLISHED: 3,
            Maturity.DEPRECATED: -1,
        }
        edges = []
        for edge in self._edges.values():
            if edge.source_id != node_id and edge.target_id != node_id:
                continue
            if relation is not None and edge.relation != relation:
                continue
            if as_of is not None:
                if edge.valid_from is not None and edge.valid_from > as_of:
                    continue
                if edge.valid_until is not None and edge.valid_until < as_of:
                    continue
            if minimum_maturity is not None:
                if maturity_rank[edge.maturity] < maturity_rank[minimum_maturity]:
                    continue
            edges.append(edge)
        return tuple(sorted(edges, key=lambda item: (item.relation, item.edge_id)))

    def contradictions(self) -> Tuple[Contradiction, ...]:
        return tuple(sorted(self._contradictions, key=lambda item: (item.left_edge_id, item.right_edge_id)))

    def lineage(self, edge_id: str) -> Tuple[EvidenceRef, ...]:
        edge = self._edges.get(edge_id)
        if edge is None:
            raise ContractError(f"unknown edge: {edge_id}")
        return tuple(self._evidence[item] for item in edge.evidence_ids)

    def node(self, node_id: str) -> KnowledgeNode:
        try:
            return self._nodes[node_id]
        except KeyError as exc:
            raise ContractError(f"unknown node: {node_id}") from exc

    def edge(self, edge_id: str) -> KnowledgeEdge:
        try:
            return self._edges[edge_id]
        except KeyError as exc:
            raise ContractError(f"unknown edge: {edge_id}") from exc

    def snapshot(self) -> Mapping[str, Any]:
        return {
            "nodes": tuple(self._nodes.values()),
            "edges": tuple(self._edges.values()),
            "evidence": tuple(self._evidence.values()),
            "contradictions": self.contradictions(),
        }
