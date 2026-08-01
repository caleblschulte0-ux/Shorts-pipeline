"""Artifact and report lineage graph prototype."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping


@dataclass(frozen=True)
class LineageNode:
    node_id: str
    artifact_type: str
    sha256: str
    manifest_sha256: str
    parent_ids: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.node_id.strip() or not self.artifact_type.strip():
            raise ValueError("node_id and artifact_type must be nonempty")
        for name, digest in (("sha256", self.sha256), ("manifest_sha256", self.manifest_sha256)):
            if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest.lower()):
                raise ValueError(f"{name} must be a lowercase-compatible SHA-256 digest")
        if self.node_id in self.parent_ids:
            raise ValueError("a lineage node cannot parent itself")
        if len(self.parent_ids) != len(set(self.parent_ids)):
            raise ValueError("parent_ids must be unique")


@dataclass(frozen=True)
class LineageValidation:
    valid: bool
    missing_parents: tuple[str, ...]
    cycles: tuple[tuple[str, ...], ...]
    manifest_mismatches: tuple[str, ...]
    duplicate_hashes: tuple[tuple[str, tuple[str, ...]], ...]


@dataclass(frozen=True)
class ImpactReport:
    changed_nodes: tuple[str, ...]
    affected_nodes: tuple[str, ...]
    affected_types: tuple[str, ...]
    terminal_nodes: tuple[str, ...]


class LineageGraph:
    def __init__(self, nodes: Iterable[LineageNode] = ()) -> None:
        self._nodes: dict[str, LineageNode] = {}
        for node in nodes:
            self.add(node)

    def add(self, node: LineageNode) -> None:
        if node.node_id in self._nodes:
            raise ValueError(f"duplicate lineage node {node.node_id!r}")
        self._nodes[node.node_id] = node

    def get(self, node_id: str) -> LineageNode:
        return self._nodes[node_id]

    def nodes(self) -> tuple[LineageNode, ...]:
        return tuple(self._nodes[node_id] for node_id in sorted(self._nodes))

    def children_map(self) -> dict[str, set[str]]:
        children: dict[str, set[str]] = {node_id: set() for node_id in self._nodes}
        for node in self._nodes.values():
            for parent_id in node.parent_ids:
                if parent_id in children:
                    children[parent_id].add(node.node_id)
        return children

    def validate(self) -> LineageValidation:
        missing = sorted({
            parent_id
            for node in self._nodes.values()
            for parent_id in node.parent_ids
            if parent_id not in self._nodes
        })
        mismatches: list[str] = []
        for node in self._nodes.values():
            for parent_id in node.parent_ids:
                parent = self._nodes.get(parent_id)
                if parent and parent.manifest_sha256 != node.manifest_sha256:
                    mismatches.append(f"{parent_id}->{node.node_id}")

        cycles: set[tuple[str, ...]] = set()
        visiting: list[str] = []
        visited: set[str] = set()

        def walk(node_id: str) -> None:
            if node_id in visiting:
                index = visiting.index(node_id)
                cycle = tuple(visiting[index:] + [node_id])
                rotations = [cycle[i:-1] + cycle[:i] + (cycle[i],) for i in range(len(cycle) - 1)]
                cycles.add(min(rotations))
                return
            if node_id in visited:
                return
            visiting.append(node_id)
            for parent_id in self._nodes[node_id].parent_ids:
                if parent_id in self._nodes:
                    walk(parent_id)
            visiting.pop()
            visited.add(node_id)

        for node_id in sorted(self._nodes):
            walk(node_id)

        by_hash: dict[str, list[str]] = {}
        for node in self._nodes.values():
            by_hash.setdefault(node.sha256, []).append(node.node_id)
        duplicates = tuple(
            (digest, tuple(sorted(node_ids)))
            for digest, node_ids in sorted(by_hash.items())
            if len(node_ids) > 1
        )

        return LineageValidation(
            valid=not missing and not cycles and not mismatches,
            missing_parents=tuple(missing),
            cycles=tuple(sorted(cycles)),
            manifest_mismatches=tuple(sorted(set(mismatches))),
            duplicate_hashes=duplicates,
        )

    def impact(self, changed_node_ids: Iterable[str]) -> ImpactReport:
        requested = tuple(sorted(set(changed_node_ids)))
        unknown = [node_id for node_id in requested if node_id not in self._nodes]
        if unknown:
            raise KeyError(",".join(unknown))
        children = self.children_map()
        affected: set[str] = set(requested)
        frontier = list(requested)
        while frontier:
            current = frontier.pop()
            for child in children.get(current, set()):
                if child not in affected:
                    affected.add(child)
                    frontier.append(child)
        terminals = sorted(node_id for node_id in affected if not children.get(node_id))
        types = sorted({self._nodes[node_id].artifact_type for node_id in affected})
        return ImpactReport(requested, tuple(sorted(affected)), tuple(types), tuple(terminals))

    def stale_nodes(self, current_hashes: Mapping[str, str]) -> tuple[str, ...]:
        changed_roots = [
            node_id for node_id, expected in current_hashes.items()
            if node_id in self._nodes and self._nodes[node_id].sha256 != expected
        ]
        if not changed_roots:
            return ()
        return self.impact(changed_roots).affected_nodes
