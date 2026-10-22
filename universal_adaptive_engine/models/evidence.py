"""Canonical Evidence Record model and provenance hashing."""
from __future__ import annotations
import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import jsonschema

from universal_adaptive_engine.models.enums import EvidenceType, ConfidenceLevel

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "evidence_record.schema.json"


class EvidenceValidationError(Exception):
    """Raised when evidence record validation fails."""
    pass


@dataclass
class EvidenceRecord:
    evidence_id: str
    evidence_type: EvidenceType
    source_ref: str
    acquisition_method: str
    observed_result: str
    confidence: ConfidenceLevel
    artifact_path: Optional[str] = None
    sha256: Optional[str] = None
    tool_version: Optional[str] = None
    related_task_id: Optional[str] = None
    limitations: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "evidence_type": self.evidence_type.value if isinstance(self.evidence_type, EvidenceType) else str(self.evidence_type),
            "source_ref": self.source_ref,
            "artifact_path": self.artifact_path,
            "sha256": self.sha256,
            "acquisition_method": self.acquisition_method,
            "observed_result": self.observed_result,
            "tool_version": self.tool_version,
            "related_task_id": self.related_task_id,
            "confidence": self.confidence.value if isinstance(self.confidence, ConfidenceLevel) else str(self.confidence),
            "limitations": list(self.limitations),
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvidenceRecord:
        evidence_type = EvidenceType(data["evidence_type"])
        confidence = ConfidenceLevel(data["confidence"])
        return cls(
            evidence_id=str(data["evidence_id"]),
            evidence_type=evidence_type,
            source_ref=str(data["source_ref"]),
            artifact_path=data.get("artifact_path"),
            sha256=data.get("sha256"),
            acquisition_method=str(data["acquisition_method"]),
            observed_result=str(data["observed_result"]),
            tool_version=data.get("tool_version"),
            related_task_id=data.get("related_task_id"),
            confidence=confidence,
            limitations=list(data.get("limitations", [])),
            timestamp=str(data.get("timestamp", datetime.now(timezone.utc).isoformat())),
        )

    @staticmethod
    def hash_artifact(path: Path | str) -> str:
        """Compute SHA-256 hash of an artifact on disk (file or directory tree)."""
        target = Path(path)
        if not target.exists():
            raise FileNotFoundError(f"Artifact not found for hashing: {target}")
        h = hashlib.sha256()
        if target.is_dir():
            ignored_dirs = {".git", ".gemini", "node_modules", "cache", ".orchestrator_state", ".pytest_cache"}
            entries: list[tuple[str, Path, bool]] = []
            for root, dirs, files in os.walk(target, topdown=True, followlinks=False):
                dirs[:] = sorted([
                    d for d in dirs
                    if d not in ignored_dirs and not os.path.islink(os.path.join(root, d))
                ])
                for fname in sorted(files):
                    fpath = Path(root) / fname
                    rel = str(fpath.relative_to(target))
                    is_link = fpath.is_symlink()
                    entries.append((rel, fpath, is_link))

            entries.sort(key=lambda x: x[0])
            for rel_str, fpath, is_link in entries:
                h.update(rel_str.encode("utf-8"))
                if is_link:
                    link_target = os.readlink(fpath)
                    h.update(b"->")
                    h.update(link_target.encode("utf-8"))
                else:
                    h.update(b":")
                    with open(fpath, "rb") as f:
                        while chunk := f.read(65536):
                            h.update(chunk)
            return h.hexdigest()

        with open(target, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    def validate(self) -> None:
        """Validate against JSON schema and consistency rules."""
        data = self.to_dict()
        if SCHEMA_PATH.exists():
            with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
                schema = json.load(f)
            jsonschema.validate(instance=data, schema=schema)
        else:
            raise FileNotFoundError(f"Schema not found at {SCHEMA_PATH}")

        # Invariant checks
        if self.evidence_type == EvidenceType.OBSERVED and not self.observed_result.strip():
            raise EvidenceValidationError("OBSERVED evidence must contain non-empty observed result")
        if self.artifact_path and self.sha256:
            artifact = Path(self.artifact_path)
            if artifact.exists():
                computed = self.hash_artifact(artifact)
                if computed.lower() != self.sha256.lower():
                    raise EvidenceValidationError(
                        f"Evidence artifact digest mismatch: recorded {self.sha256}, computed {computed}"
                    )
