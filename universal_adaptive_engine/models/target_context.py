"""Target Context and Universal Skill Adaptation Protocol (USAP) data models."""
from __future__ import annotations
import os
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class TargetResultStatus(str, Enum):
    """The 5-state result taxonomy required by the Universal Skill Adaptation Protocol."""
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_VERIFIED = "NOT_VERIFIED"


@dataclass(frozen=True)
class TargetFinding:
    """A structured, evidence-backed security finding."""
    finding_id: str
    target_id: str
    architecture: str
    property_violated: str
    affected_artifact: str
    status: TargetResultStatus
    summary: str
    evidence_refs: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    severity: str = "MEDIUM"


@dataclass(frozen=True)
class TargetContext:
    """Normalized, architecture-aware target context contract.

    Serves as the single immutable input contract to all specialist skills,
    workflows, and verification oracles.
    """
    workspace_root: Path
    target_root: Path
    target_id: str
    bounty_slug: Optional[str]

    architecture: str              # e.g., "evm", "solana", "move", "cosmwasm", "rust", "generic"
    languages: tuple[str, ...]     # e.g., ("solidity",), ("rust",), ("solidity", "rust")
    runtimes: tuple[str, ...]      # e.g., ("foundry",), ("anchor",), ("cargo",)

    source_roots: tuple[Path, ...]
    test_roots: tuple[Path, ...]
    manifests: tuple[Path, ...]

    scope_manifest: Optional[Path]
    session_id: str

    capabilities: frozenset[str] = frozenset()
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        """A target context is valid if target_root exists on disk."""
        return self.target_root.exists()

    def has_capability(self, capability: str) -> bool:
        """Check if target runtime or workspace supports a specific capability."""
        return capability in self.capabilities

    def to_dict(self) -> dict[str, Any]:
        """Serialize target context for evidence and audit manifests."""
        return {
            "workspace_root": str(self.workspace_root),
            "target_root": str(self.target_root),
            "target_id": self.target_id,
            "bounty_slug": self.bounty_slug,
            "architecture": self.architecture,
            "languages": list(self.languages),
            "runtimes": list(self.runtimes),
            "source_roots": [str(p) for p in self.source_roots],
            "test_roots": [str(p) for p in self.test_roots],
            "manifests": [str(p) for p in self.manifests],
            "scope_manifest": str(self.scope_manifest) if self.scope_manifest else None,
            "session_id": self.session_id,
            "capabilities": sorted(list(self.capabilities)),
            "metadata": dict(self.metadata),
        }


class TargetContextResolver:
    """Authoritative resolver for discovering and validating TargetContext.

    Follows strict precedence:
    1. Explicit execution arguments (target_root, bounty_slug, architecture)
    2. Authoritative session configuration
    3. Validated environment variables (CANTINA_TARGET_ROOT, CANTINA_BOUNTY, CANTINA_ARCHITECTURE)
    4. Authoritative adapter-based workspace discovery
    5. Session-local state (MEMORY.md) as supporting evidence, not unquestioned authority
    6. Fail-closed: returns invalid TargetContext with status BLOCKED
    """

    @staticmethod
    def resolve(
        context: Optional[dict[str, Any]] = None,
        workspace_root: Optional[Path | str] = None,
    ) -> TargetContext:
        ctx = dict(context or {})
        ws = Path(workspace_root or ctx.get("workspace_root") or ".").resolve()
        session_id = ctx.get("session_id") or os.environ.get("ANTIGRAVITY_SESSION_ID") or uuid.uuid4().hex[:8]

        # 1. Resolve target root and bounty slug
        explicit_target = ctx.get("target_root") or os.environ.get("CANTINA_TARGET_ROOT")
        explicit_bounty = ctx.get("bounty_slug") or os.environ.get("CANTINA_BOUNTY")

        target_root: Optional[Path] = None
        target_file: Optional[Path] = None
        bounty_slug: Optional[str] = explicit_bounty

        if explicit_target:
            raw_path = Path(explicit_target)
            target_path = (ws / raw_path).resolve() if not raw_path.is_absolute() else raw_path.resolve()
            if target_path.is_file():
                target_file = target_path
                target_root = target_path.parent
            else:
                target_root = target_path

            if not bounty_slug:
                try:
                    bounties_dir = ws / "bounties"
                    if bounties_dir.exists() and target_root.is_relative_to(bounties_dir):
                        rel = target_root.relative_to(bounties_dir)
                        if rel.parts:
                            bounty_slug = rel.parts[0]
                    elif "bounties" in target_root.parts:
                        idx = target_root.parts.index("bounties")
                        if idx + 1 < len(target_root.parts):
                            bounty_slug = target_root.parts[idx + 1]
                        else:
                            bounty_slug = None
                    else:
                        bounty_slug = None
                except Exception:
                    bounty_slug = None
        elif explicit_bounty:
            target_root = (ws / "bounties" / explicit_bounty).resolve()
        else:
            # Check MEMORY.md as supporting evidence
            memory_file = ws / "MEMORY.md"
            if memory_file.exists():
                try:
                    for line in memory_file.read_text(encoding="utf-8").splitlines():
                        if "Active bounty:" in line or "Active Bounty:" in line:
                            parts = line.split(":", 1)
                            if len(parts) > 1 and parts[1].strip():
                                candidate = parts[1].strip()
                                cand_path = ws / "bounties" / candidate
                                if cand_path.exists() and cand_path.is_dir():
                                    bounty_slug = candidate
                                    target_root = cand_path
                                    break
                except OSError:
                    pass

        # Fallback to workspace root if no bounty specified and workspace exists
        if not target_root:
            target_root = ws

        # 2. Discover Architecture, Languages, and Runtimes
        manifests: list[Path] = []
        languages: list[str] = []
        runtimes: list[str] = []
        explicit_architecture = ctx.get("architecture") or os.environ.get("CANTINA_ARCHITECTURE")
        architecture = explicit_architecture
        capabilities: set[str] = set()

        if target_root.exists() and target_root.is_dir():
            # Manifest candidate directories (target_root + immediate non-hidden child directories)
            cand_dirs = [target_root]
            try:
                subs = [
                    sub for sub in target_root.iterdir()
                    if sub.is_dir() and not sub.name.startswith(".") and sub.name not in (
                        "node_modules", "dist", "build", "target", "cache", "out",
                        "snapshots", "logs", "evidence", "findings", "scans", "poc"
                    )
                ]
                cand_dirs.extend(sorted(subs, key=lambda d: d.name))
            except OSError:
                pass

            # Walk up ancestor directories towards workspace_root to detect root manifests
            curr = target_root
            while curr != ws and curr.parent != curr:
                if curr.is_relative_to(ws) and curr != ws:
                    curr = curr.parent
                    if curr not in cand_dirs:
                        cand_dirs.append(curr)
                else:
                    break

            for cand in cand_dirs:
                foundry_toml = cand / "foundry.toml"
                hardhat_config = cand / "hardhat.config.js"
                hardhat_ts = cand / "hardhat.config.ts"
                anchor_toml = cand / "Anchor.toml"
                cargo_toml = cand / "Cargo.toml"
                move_toml = cand / "Move.toml"

                if foundry_toml.exists() and foundry_toml not in manifests:
                    manifests.append(foundry_toml)
                    if "solidity" not in languages:
                        languages.append("solidity")
                    if "foundry" not in runtimes:
                        runtimes.append("foundry")
                    capabilities.update(["evm.foundry", "contracts.solidity", "tests.forge"])
                    if not architecture:
                        architecture = "evm"

                if hardhat_config.exists() or hardhat_ts.exists():
                    hh_p = hardhat_config if hardhat_config.exists() else hardhat_ts
                    if hh_p not in manifests:
                        manifests.append(hh_p)
                        if "solidity" not in languages:
                            languages.append("solidity")
                        if "hardhat" not in runtimes:
                            runtimes.append("hardhat")
                        capabilities.update(["evm.hardhat", "contracts.solidity", "tests.hardhat"])
                        if not architecture:
                            architecture = "evm"

                if anchor_toml.exists() and anchor_toml not in manifests:
                    manifests.append(anchor_toml)
                    if "rust" not in languages:
                        languages.append("rust")
                    if "anchor" not in runtimes:
                        runtimes.append("anchor")
                    capabilities.update(["solana.anchor", "programs.solana", "tests.anchor"])
                    if not architecture:
                        architecture = "solana"

                if cargo_toml.exists() and cargo_toml not in manifests:
                    manifests.append(cargo_toml)
                    if "rust" not in languages:
                        languages.append("rust")
                    if "cargo" not in runtimes:
                        runtimes.append("cargo")
                    capabilities.update(["rust.cargo", "tests.cargo"])
                    if (cand / "idls").exists() or (cand / "idl").exists() or (cand / "keys").exists() or "solana" in cand.name.lower() or "pump" in cand.name.lower():
                        capabilities.update(["solana.program", "programs.solana"])
                        if not architecture:
                            architecture = "solana"
                    elif not architecture:
                        architecture = "rust"

                if move_toml.exists() and move_toml not in manifests:
                    manifests.append(move_toml)
                    if "move" not in languages:
                        languages.append("move")
                    if "move" not in runtimes:
                        runtimes.append("move")
                    capabilities.update(["move.framework", "tests.move"])
                    if not architecture:
                        architecture = "move"

        if target_file:
            if target_file.suffix == ".sol":
                if "solidity" not in languages:
                    languages.append("solidity")
                if not architecture or architecture == "generic":
                    architecture = "evm"
            elif target_file.suffix == ".rs":
                if "rust" not in languages:
                    languages.append("rust")
                if not architecture or architecture == "generic":
                    architecture = "rust"
            elif target_file.suffix == ".move":
                if "move" not in languages:
                    languages.append("move")
                if not architecture or architecture == "generic":
                    architecture = "move"

        if not explicit_architecture and not target_file:
            if "solidity" in languages and architecture != "solana":
                architecture = "evm"

        if not architecture:
            architecture = "generic"

        # 3. Discover Source and Test Roots
        source_roots: list[Path] = []
        test_roots: list[Path] = []

        if target_root.exists() and target_root.is_dir():
            for d in cand_dirs:
                for src_cand in ["src", "contracts", "programs", "crates", "modules"]:
                    p = d / src_cand if d != target_root else target_root / src_cand
                    if p.exists() and p.is_dir() and p not in source_roots:
                        source_roots.append(p)

                for test_cand in ["test", "tests"]:
                    p = d / test_cand if d != target_root else target_root / test_cand
                    if p.exists() and p.is_dir() and p not in test_roots:
                        test_roots.append(p)

        # 4. Discover Scope Manifest
        scope_manifest: Optional[Path] = None
        if target_root.exists():
            scope_cand = target_root / "scope.md"
            if scope_cand.exists() and scope_cand.is_file():
                scope_manifest = scope_cand
            elif bounty_slug and (ws / "bounties" / bounty_slug / "scope.md").exists():
                scope_manifest = ws / "bounties" / bounty_slug / "scope.md"
            elif (target_root.parent / "scope.md").exists():
                scope_manifest = target_root.parent / "scope.md"
            elif target_root.exists() and target_root.is_dir():
                for cand in cand_dirs:
                    sc = cand / "scope.md"
                    if sc.exists() and sc.is_file():
                        scope_manifest = sc
                        break

        target_id = bounty_slug or (target_root.name if target_root else "unknown-target")

        meta = dict(ctx.get("metadata", {}))
        if target_file:
            meta["target_file"] = str(target_file)

        return TargetContext(
            workspace_root=ws,
            target_root=target_root,
            target_id=target_id,
            bounty_slug=bounty_slug,
            architecture=architecture,
            languages=tuple(languages) or ("unknown",),
            runtimes=tuple(runtimes) or ("unknown",),
            source_roots=tuple(source_roots),
            test_roots=tuple(test_roots),
            manifests=tuple(manifests),
            scope_manifest=scope_manifest,
            session_id=session_id,
            capabilities=frozenset(capabilities),
            metadata=meta,
        )
