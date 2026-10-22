#!/usr/bin/env python3
"""Immutable, evidence-linked Cantina case snapshots.

This validates lineage and artifact integrity. It does not decide whether a
vulnerability is real, assign severity, or authorize a submission.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA_VERSION = 1
PHASES = {"OPEN", "STABILIZED", "SEALED"}
NODE_KINDS = {"HYPOTHESIS", "FINDING", "SOURCE", "TOOL", "POC", "REPORT", "NOTE"}
RELATIONS = {"SUPPORTS", "REFUTES", "DERIVED_FROM", "DEPENDS_ON"}
ID_RE = re.compile(r"^[A-Z][A-Z0-9_-]{0,31}$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


class CaseValidationError(ValueError):
    """Raised when a case snapshot violates its contract."""


@dataclass(frozen=True)
class CaseIdentity:
    bounty: str
    scope_sha256: str
    source_commit: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "bounty": self.bounty,
            "scope_sha256": self.scope_sha256,
            "source_commit": self.source_commit,
        }


@dataclass(frozen=True)
class CaseNode:
    id: str
    kind: str
    path: str
    sha256: str

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "kind": self.kind, "path": self.path, "sha256": self.sha256}


@dataclass(frozen=True)
class CaseEdge:
    source: str
    target: str
    relation: str

    def to_dict(self) -> dict[str, str]:
        return {"source": self.source, "target": self.target, "relation": self.relation}


@dataclass(frozen=True)
class CaseState:
    identity: CaseIdentity
    phase: str
    sequence: int
    parent_digest: str | None
    nodes: tuple[CaseNode, ...] = ()
    edges: tuple[CaseEdge, ...] = ()

    def to_dict(self, include_digest: bool = True) -> dict[str, Any]:
        data = {
            "schema_version": SCHEMA_VERSION,
            "identity": self.identity.to_dict(),
            "phase": self.phase,
            "sequence": self.sequence,
            "parent_digest": self.parent_digest,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
        }
        if include_digest:
            data["digest"] = self.digest
        return data

    @property
    def digest(self) -> str:
        canonical = json.dumps(
            self.to_dict(include_digest=False),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, raw: Any) -> "CaseState":
        if not isinstance(raw, dict):
            raise CaseValidationError("case must be a JSON object")
        expected = {
            "schema_version", "identity", "phase", "sequence", "parent_digest",
            "nodes", "edges", "digest",
        }
        if set(raw) != expected:
            raise CaseValidationError("case fields do not match schema version 1")
        if isinstance(raw["schema_version"], bool) or raw["schema_version"] != SCHEMA_VERSION:
            raise CaseValidationError("unsupported schema_version")
        identity = raw["identity"]
        if not isinstance(identity, dict) or set(identity) != {"bounty", "scope_sha256", "source_commit"}:
            raise CaseValidationError("identity fields are invalid")
        if not isinstance(raw["nodes"], list) or not isinstance(raw["edges"], list):
            raise CaseValidationError("nodes and edges must be arrays")
        try:
            if any(not isinstance(item, dict) for item in raw["nodes"] + raw["edges"]):
                raise CaseValidationError("every node and edge must be an object")
            state = cls(
                identity=CaseIdentity(**identity),
                phase=raw["phase"],
                sequence=raw["sequence"],
                parent_digest=raw["parent_digest"],
                nodes=tuple(CaseNode(**node) for node in raw["nodes"]),
                edges=tuple(CaseEdge(**edge) for edge in raw["edges"]),
            )
        except (TypeError, ValueError) as exc:
            raise CaseValidationError(f"invalid case record: {exc}") from exc
        if raw["digest"] != state.digest:
            raise CaseValidationError("case digest mismatch")
        return state

    def successor(
        self,
        *,
        nodes: tuple[CaseNode, ...] = (),
        edges: tuple[CaseEdge, ...] = (),
        phase: str | None = None,
    ) -> "CaseState":
        """Create a new immutable revision; the parent is never modified."""
        child = CaseState(
            identity=self.identity,
            phase=phase or self.phase,
            sequence=self.sequence + 1,
            parent_digest=self.digest,
            nodes=self.nodes + tuple(nodes),
            edges=self.edges + tuple(edges),
        )
        child.validate(parent=self)
        return child

    def validate(self, *, parent: "CaseState | None" = None, bounty_root: Path | None = None) -> None:
        identity = self.identity
        if not isinstance(identity.bounty, str) or not SLUG_RE.fullmatch(identity.bounty):
            raise CaseValidationError("identity.bounty must be a safe slug")
        if not isinstance(identity.scope_sha256, str) or not SHA256_RE.fullmatch(identity.scope_sha256):
            raise CaseValidationError("identity.scope_sha256 must be lowercase SHA-256")
        if identity.source_commit is not None and (
            not isinstance(identity.source_commit, str) or not COMMIT_RE.fullmatch(identity.source_commit)
        ):
            raise CaseValidationError("identity.source_commit must be null or a lowercase 40-hex commit")
        if not isinstance(self.phase, str) or self.phase not in PHASES:
            raise CaseValidationError("phase must be OPEN, STABILIZED, or SEALED")
        if not isinstance(self.sequence, int) or isinstance(self.sequence, bool) or self.sequence < 0:
            raise CaseValidationError("sequence must be a non-negative integer")
        if self.sequence == 0 and self.parent_digest is not None:
            raise CaseValidationError("initial state must not have a parent digest")
        if self.sequence > 0 and not (
            isinstance(self.parent_digest, str) and SHA256_RE.fullmatch(self.parent_digest)
        ):
            raise CaseValidationError("successor state requires a lowercase parent digest")
        if self.sequence == 0 and self.phase != "OPEN":
            raise CaseValidationError("initial state must be OPEN")

        node_ids = [node.id for node in self.nodes]
        if any(not isinstance(node_id, str) for node_id in node_ids):
            raise CaseValidationError("node IDs must be strings")
        if len(node_ids) != len(set(node_ids)):
            raise CaseValidationError("node IDs must be unique")
        for node in self.nodes:
            if (
                not isinstance(node.id, str) or not ID_RE.fullmatch(node.id)
                or not isinstance(node.kind, str) or node.kind not in NODE_KINDS
            ):
                raise CaseValidationError(f"invalid node identity or kind: {node.id}")
            if not isinstance(node.sha256, str) or not SHA256_RE.fullmatch(node.sha256):
                raise CaseValidationError(f"node {node.id} must have a lowercase SHA-256 digest")
            if not isinstance(node.path, str):
                raise CaseValidationError(f"node {node.id} path must be a string")
            rel = PurePosixPath(node.path)
            if rel.is_absolute() or not node.path or ".." in rel.parts or "\\" in node.path or ":" in node.path:
                raise CaseValidationError(f"node {node.id} path must be a safe bounty-relative path")
            if bounty_root is not None:
                root = bounty_root.resolve()
                original = root / Path(*rel.parts)
                current = root
                for part in rel.parts:
                    current = current / part
                    if current.is_symlink():
                        raise CaseValidationError(f"node {node.id} path contains a symlink")
                candidate = original.resolve()
                try:
                    candidate.relative_to(root)
                except ValueError as exc:
                    raise CaseValidationError(f"node {node.id} path escapes bounty root") from exc
                if not candidate.is_file():
                    raise CaseValidationError(f"node {node.id} artifact is missing or is a symlink")
                actual = hashlib.sha256(candidate.read_bytes()).hexdigest()
                if actual != node.sha256:
                    raise CaseValidationError(f"node {node.id} artifact digest mismatch")

        adjacency: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
        in_degree = {node_id: 0 for node_id in node_ids}
        edge_keys: set[tuple[str, str, str]] = set()
        for edge in self.edges:
            if not all(isinstance(value, str) for value in (edge.source, edge.target, edge.relation)):
                raise CaseValidationError("edge fields must be strings")
            key = (edge.source, edge.target, edge.relation)
            if key in edge_keys:
                raise CaseValidationError("duplicate edges are not allowed")
            edge_keys.add(key)
            if edge.source not in adjacency or edge.target not in adjacency:
                raise CaseValidationError(f"edge references a missing node: {edge.source} -> {edge.target}")
            if edge.source == edge.target or edge.relation not in RELATIONS:
                raise CaseValidationError("self-edges and unknown relations are not allowed")
            adjacency[edge.source].append(edge.target)
            in_degree[edge.target] += 1
        ready = [node_id for node_id, degree in in_degree.items() if degree == 0]
        visited_count = 0
        while ready:
            node_id = ready.pop()
            visited_count += 1
            for target in adjacency[node_id]:
                in_degree[target] -= 1
                if in_degree[target] == 0:
                    ready.append(target)
        if visited_count != len(node_ids):
            raise CaseValidationError("evidence topology contains a cycle")

        if bounty_root is not None and bounty_root.name != identity.bounty:
            raise CaseValidationError("case identity does not match bounty root")
        if bounty_root is not None:
            scope_file = bounty_root / "scope.md"
            snapshot_file = bounty_root / "snapshots" / "scope.sha256"
            if not scope_file.is_file() or not snapshot_file.is_file():
                raise CaseValidationError("scope.md and snapshots/scope.sha256 are required")
            actual_scope = normalized_scope_digest(scope_file)
            saved_scope = snapshot_file.read_text(encoding="utf-8").strip().split()
            if not saved_scope or saved_scope[0].lower() != actual_scope:
                raise CaseValidationError("current scope does not match its saved scope snapshot")
            if actual_scope != identity.scope_sha256:
                raise CaseValidationError("case identity does not match current scope snapshot")
        if parent is None:
            if self.sequence != 0:
                raise CaseValidationError("parent case is required to validate successor lineage")
            return
        if parent.digest != self.parent_digest or self.sequence != parent.sequence + 1:
            raise CaseValidationError("parent digest or sequence linkage is invalid")
        if parent.identity != identity:
            raise CaseValidationError("bounty identity changed across successor states")
        transitions = {
            "OPEN": {"OPEN", "STABILIZED"},
            "STABILIZED": {"STABILIZED", "SEALED"},
            "SEALED": {"OPEN"},
        }
        if self.phase not in transitions[parent.phase]:
            raise CaseValidationError(f"invalid lifecycle transition: {parent.phase} -> {self.phase}")
        if not set(parent.nodes).issubset(self.nodes) or not set(parent.edges).issubset(self.edges):
            raise CaseValidationError("successor must preserve all parent nodes and edges")


def normalized_scope_digest(scope_file: Path) -> str:
    """Match the project's marker-delimited LF-normalized scope-lock convention."""
    content = scope_file.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    lines = content.splitlines(keepends=True)
    start_marker = b"<!-- SCOPE START -->"
    end_marker = b"<!-- SCOPE END -->"
    starts = [i for i, line in enumerate(lines) if line.strip() == start_marker]
    ends = [i for i, line in enumerate(lines) if line.strip() == end_marker]
    if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
        raise CaseValidationError("scope markers must each occur exactly once and in order")
    normalized = b"".join(lines[starts[0]:ends[0] + 1])
    if not normalized.endswith(b"\n"):
        normalized += b"\n"
    return hashlib.sha256(normalized).hexdigest()


def load_case(path: Path) -> CaseState:
    try:
        return CaseState.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise CaseValidationError(f"cannot read case file: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate immutable Cantina case-state snapshots")
    parser.add_argument("--case", required=True, type=Path, help="case-state JSON file")
    parser.add_argument("--bounty-root", required=True, type=Path, help="active bounty directory containing artifacts")
    parser.add_argument("--parent", type=Path, help="optional previous case-state JSON for lineage validation")
    args = parser.parse_args(argv)
    try:
        state = load_case(args.case)
        parent = load_case(args.parent) if args.parent else None
        state.validate(parent=parent, bounty_root=args.bounty_root)
    except (CaseValidationError, OSError) as exc:
        print(json.dumps({"status": "INVALID", "error": str(exc), "authorization_granted": False}))
        return 1
    print(json.dumps({
        "status": "VALIDATED",
        "phase": state.phase,
        "sequence": state.sequence,
        "digest": state.digest,
        "authorization_granted": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
