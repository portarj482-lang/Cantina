"""Evidence Store managing provenance records, digests, and trace links."""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any, Optional

from universal_adaptive_engine.models.enums import EvidenceType, ConfidenceLevel
from universal_adaptive_engine.models.evidence import EvidenceRecord, EvidenceValidationError


class EvidenceStore:
    """Stores, indexes, and verifies evidence records against artifacts."""

    def __init__(self, storage_path: Optional[Path | str] = None):
        self.storage_path = Path(storage_path) if storage_path else None
        self._records: dict[str, EvidenceRecord] = {}
        if self.storage_path and self.storage_path.exists():
            self.load()

    def record_evidence(self, evidence: EvidenceRecord) -> EvidenceRecord:
        """Register and validate an evidence record."""
        evidence.validate()
        self._records[evidence.evidence_id] = evidence
        self.save()
        return evidence

    def create_artifact_evidence(
        self,
        evidence_id: str,
        artifact_path: Path | str,
        source_ref: str,
        acquisition_method: str,
        observed_result: str,
        confidence: ConfidenceLevel = ConfidenceLevel.VERIFIED,
        related_task_id: Optional[str] = None,
        limitations: Optional[list[str]] = None,
    ) -> EvidenceRecord:
        """Create and record evidence from a physical file artifact on disk."""
        path = Path(artifact_path)
        sha256 = EvidenceRecord.hash_artifact(path)
        rec = EvidenceRecord(
            evidence_id=evidence_id,
            evidence_type=EvidenceType.OBSERVED,
            source_ref=source_ref,
            artifact_path=str(path.resolve()),
            sha256=sha256,
            acquisition_method=acquisition_method,
            observed_result=observed_result,
            confidence=confidence,
            related_task_id=related_task_id,
            limitations=limitations or [],
        )
        return self.record_evidence(rec)

    def get_evidence(self, evidence_id: str) -> Optional[EvidenceRecord]:
        return self._records.get(evidence_id)

    def list_evidence(self, task_id: Optional[str] = None) -> list[EvidenceRecord]:
        if task_id is None:
            return list(self._records.values())
        return [r for r in self._records.values() if r.related_task_id == task_id]

    def verify_all_artifacts(self) -> dict[str, Any]:
        """Verify that all recorded artifacts with digests match their current disk state."""
        results = {"verified": [], "mismatched": [], "missing": []}
        for eid, rec in self._records.items():
            if rec.artifact_path and rec.sha256:
                path = Path(rec.artifact_path)
                if not path.exists():
                    results["missing"].append({"evidence_id": eid, "path": rec.artifact_path})
                else:
                    curr_hash = EvidenceRecord.hash_artifact(path)
                    if curr_hash.lower() == rec.sha256.lower():
                        results["verified"].append(eid)
                    else:
                        results["mismatched"].append({
                            "evidence_id": eid,
                            "expected": rec.sha256,
                            "found": curr_hash,
                        })
        return results

    def save(self) -> None:
        """Atomically persist evidence records to disk."""
        if not self.storage_path:
            return
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {eid: rec.to_dict() for eid, rec in self._records.items()}
        temp_file = self.storage_path.with_suffix(f".tmp.{os.getpid()}")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(temp_file, self.storage_path)
        except Exception:
            if temp_file.exists():
                temp_file.unlink()
            raise

    def load(self) -> None:
        """Load evidence records from disk with corruption resilience."""
        if not self.storage_path or not self.storage_path.exists():
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._records = {eid: EvidenceRecord.from_dict(rdata) for eid, rdata in data.items()}
        except (json.JSONDecodeError, OSError):
            self._records = {}
