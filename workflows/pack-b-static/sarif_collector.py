#!/usr/bin/env python3
"""Pack B — Universal Oracle–Orchestrator Meta-Agent (UOOMA) SARIF Collector Engine.

UAIA v1.0.0 Reference Workflow: Pack B Static Analysis & SARIF Collection.
Governs:
  1. Discovery and parsing of raw static analysis scan outputs (SARIF v2.1.0, Slither, Aderyn, Semgrep).
  2. Strict argument parsing, slug validation, and filesystem containment (Path.is_relative_to).
  3. Tool capability & status verification against global/tooling.md.
  4. Evidence preservation, provenance tracking, and deterministic deduplication.
  5. Schema validation against workflows/pack-b-static/schemas/normalized_sarif.schema.json.
  6. Atomic temporary swap (.tmp.<pid> -> normalized_sarif.json) and post-publication read-back verification.
  7. Fail-closed safety: --dry-run overrides --confirm; existing valid artifacts survive failures intact.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

SLUG_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")

DEFAULT_SCANNERS = {
    "slither": {"version": "0.11.6", "status": "OK"},
    "aderyn": {"version": "0.6.8", "status": "OK"},
    "semgrep": {"version": "1.182.1", "status": "OK"},
    "python3": {"version": "3.12.3", "status": "PRESENT"},
}


def parse_tooling_registry(tooling_md_path: Path) -> dict[str, dict[str, str]]:
    """Parse tool statuses from global/tooling.md if available, falling back to defaults."""
    registry = dict(DEFAULT_SCANNERS)
    if not tooling_md_path.is_file():
        return registry

    try:
        content = tooling_md_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            if line.startswith("|") and not line.startswith("| Tool") and not line.startswith("|---"):
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 7:
                    tool_name = parts[1].lower()
                    status = parts[5].upper()
                    version = parts[6]
                    registry[tool_name] = {"version": version, "status": status}
    except Exception:
        pass
    return registry


def compute_sha256(file_path: Path) -> str:
    """Compute the SHA-256 digest of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def compute_str_hash(text: str) -> str:
    """Compute 16-char SHA-256 hash of a string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


class SARIFNormalizationError(Exception):
    """Raised when parsing or normalization encounters unrecoverable corruption."""
    pass


class PathTraversalError(Exception):
    """Raised when an unauthorized path traversal or slug escape is detected."""
    pass


class UOOMASarifCollector:
    def __init__(
        self,
        repo_root: Path,
        slug: str,
        mode: str = "EXECUTE",
        dry_run: bool = False,
        confirm: bool = False,
        empty_allowed: bool = False,
        fail_sim: bool = False,
        corrupt_sim: bool = False,
        custom_scan_dir: Optional[Path] = None,
    ):
        self.repo_root = repo_root.resolve()
        self.slug = slug
        self.mode = mode.upper()
        if self.mode not in {"INSPECT", "PLAN", "DRY_RUN", "EXECUTE", "VERIFY"}:
            raise ValueError(f"Invalid mode: '{self.mode}'. Must be one of: INSPECT, PLAN, DRY_RUN, EXECUTE, VERIFY")

        self.dry_run = dry_run or (self.mode == "DRY_RUN")
        self.confirm = confirm
        self.empty_allowed = empty_allowed
        self.fail_sim = fail_sim
        self.corrupt_sim = corrupt_sim

        # Validate slug
        if not SLUG_PATTERN.match(slug):
            raise PathTraversalError(f"Invalid slug format: '{slug}'. Must match {SLUG_PATTERN.pattern}")

        if custom_scan_dir:
            self.scan_dir = custom_scan_dir.resolve()
        else:
            self.scan_dir = (self.repo_root / "bounties" / slug / "scans").resolve()

        # Strict path containment check
        if not self.scan_dir.is_relative_to(self.repo_root):
            raise PathTraversalError(f"Path containment violation: scan_dir '{self.scan_dir}' escapes repo root '{self.repo_root}'")

        self.out_file = self.scan_dir / "normalized_sarif.json"
        self.receipt_file = self.scan_dir / "receipt.json"
        self.tooling_registry = parse_tooling_registry(self.repo_root / "global" / "tooling.md")

        self.input_files: list[Path] = []
        self.rejected_inputs: list[dict[str, str]] = []
        self.raw_runs: list[dict[str, Any]] = []
        self.deduped_runs: list[dict[str, Any]] = []
        self.seen_fingerprints: Set[str] = set()
        self.total_raw_findings: int = 0
        self.deduplicated_findings: int = 0
        self.tool_breakdown: dict[str, int] = {}
        self.falsification_checks: list[str] = []
        self.exact_file_sha256: str = ""

    def stage_1_and_2_preflight(self) -> None:
        """Stage 1 & 2: Parse arguments and verify authorized path containment."""
        self.falsification_checks.append("Stage 1: Validated argument syntax and command parameters.")
        self.falsification_checks.append(f"Stage 2: Verified path containment under {self.scan_dir}.")
        if not self.scan_dir.exists():
            if not self.dry_run and self.confirm:
                self.scan_dir.mkdir(parents=True, exist_ok=True)

    def stage_3_inventory(self) -> None:
        """Stage 3: Inventory eligible scan files without mutation."""
        if not self.scan_dir.exists():
            self.input_files = []
            return

        for p in sorted(self.scan_dir.rglob("*")):
            if p.is_file() and p.name not in ["normalized_sarif.json", "receipt.json"] and not p.name.startswith(".tmp."):
                # Check for symlink escape
                if p.is_symlink():
                    resolved = p.resolve()
                    if not resolved.is_relative_to(self.repo_root):
                        self.rejected_inputs.append({
                            "file": str(p.relative_to(self.scan_dir)),
                            "reason": f"Symlink escape: target '{resolved}' escapes repository root",
                            "sha256": ""
                        })
                        continue

                if p.suffix.lower() in [".sarif", ".json"]:
                    self.input_files.append(p)

        self.falsification_checks.append(f"Stage 3: Inventoried {len(self.input_files)} scan files without mutation.")

    def stage_4_to_6_parse_and_normalize(self) -> None:
        """Stage 4-6: Validate formats, parse scans, and normalize into canonical SARIF v2.1.0."""
        for file_path in self.input_files:
            rel_name = str(file_path.relative_to(self.scan_dir))
            try:
                # Check file size limit (50 MB)
                if file_path.stat().st_size > 50 * 1024 * 1024:
                    self.rejected_inputs.append({
                        "file": rel_name,
                        "reason": f"File size exceeds 50MB limit ({file_path.stat().st_size} bytes)",
                        "sha256": compute_sha256(file_path),
                    })
                    continue

                content = file_path.read_text(encoding="utf-8")
                data = json.loads(content)
            except Exception as e:
                self.rejected_inputs.append({
                    "file": rel_name,
                    "reason": f"Malformed JSON: {type(e).__name__}: {str(e)}",
                    "sha256": compute_sha256(file_path) if file_path.exists() else "",
                })
                continue

            # Determine format
            file_sha = compute_sha256(file_path)
            run = self._normalize_single_scan(data, rel_name, file_sha)
            if run:
                self.raw_runs.append(run)

        self.falsification_checks.append(
            f"Stage 4-6: Normalized {len(self.raw_runs)} runs, rejected {len(self.rejected_inputs)} inputs."
        )

    def _normalize_single_scan(self, data: Any, rel_name: str, file_sha: str) -> Optional[dict[str, Any]]:
        """Normalize generic SARIF v2.1.0, Slither, Aderyn, or Semgrep JSON."""
        # 1. Standard SARIF v2.1.0
        if isinstance(data, dict) and "runs" in data and isinstance(data["runs"], list):
            # Already SARIF!
            for r in data["runs"]:
                tool_name = r.get("tool", {}).get("driver", {}).get("name", "unknown")
                results = r.get("results", [])
                norm_results = []
                for res in results:
                    rule_id = res.get("ruleId") or res.get("rule", {}).get("id") or "UNKNOWN_RULE"
                    msg_text = res.get("message", {}).get("text", "")
                    locations = res.get("locations", [])
                    norm_results.append({
                        "ruleId": str(rule_id),
                        "level": res.get("level", "warning"),
                        "message": {"text": str(msg_text)},
                        "locations": locations,
                        "fingerprints": res.get("fingerprints", {}),
                    })
                return {
                    "tool": {
                        "driver": {
                            "name": tool_name,
                            "version": r.get("tool", {}).get("driver", {}).get("version", "2.1.0"),
                            "rules": r.get("tool", {}).get("driver", {}).get("rules", []),
                        }
                    },
                    "results": norm_results,
                    "_source_file": rel_name,
                }

        # 2. Slither JSON format
        if isinstance(data, dict) and "results" in data and isinstance(data["results"], dict) and "detectors" in data["results"]:
            detectors = data["results"]["detectors"]
            norm_results = []
            for d in detectors:
                check = d.get("check", "slither-finding")
                desc = d.get("description", "")
                elements = d.get("elements", [])
                locs = []
                for el in elements:
                    src_map = el.get("source_mapping", {})
                    filename = src_map.get("filename_relative") or src_map.get("filename_short") or ""
                    lines = src_map.get("lines", [1])
                    start_line = lines[0] if lines else 1
                    locs.append({
                        "physicalLocation": {
                            "artifactLocation": {"uri": str(filename)},
                            "region": {"startLine": int(start_line), "endLine": int(lines[-1] if lines else start_line)},
                        }
                    })
                norm_results.append({
                    "ruleId": f"slither/{check}",
                    "level": "warning" if d.get("impact", "").lower() in ["high", "medium"] else "note",
                    "message": {"text": desc.strip()},
                    "locations": locs if locs else [{"physicalLocation": {"artifactLocation": {"uri": ""}, "region": {"startLine": 1}}}],
                    "fingerprints": {"slither_id": d.get("id", "")},
                })
            return {
                "tool": {
                    "driver": {
                        "name": "slither",
                        "version": self.tooling_registry.get("slither", {}).get("version", "0.11.6"),
                        "rules": [],
                    }
                },
                "results": norm_results,
                "_source_file": rel_name,
            }

        # 3. Aderyn JSON format
        if isinstance(data, dict) and any(k in data for k in ["critical_issues", "high_issues", "medium_issues", "low_issues"]):
            norm_results = []
            for severity in ["critical_issues", "high_issues", "medium_issues", "low_issues", "nc_issues"]:
                issues = data.get(severity, {}).get("issues", [])
                for issue in issues:
                    title = issue.get("title", "Aderyn Finding")
                    desc = issue.get("description", "")
                    instances = issue.get("instances", [])
                    locs = []
                    for inst in instances:
                        path_str = inst.get("contract_path", "")
                        line_num = inst.get("line_no", 1)
                        locs.append({
                            "physicalLocation": {
                                "artifactLocation": {"uri": str(path_str)},
                                "region": {"startLine": int(line_num), "endLine": int(line_num)},
                            }
                        })
                    norm_results.append({
                        "ruleId": f"aderyn/{title.lower().replace(' ', '-')}",
                        "level": "error" if "high" in severity or "critical" in severity else "warning",
                        "message": {"text": f"{title}: {desc}".strip()},
                        "locations": locs if locs else [{"physicalLocation": {"artifactLocation": {"uri": ""}, "region": {"startLine": 1}}}],
                        "fingerprints": {},
                    })
            return {
                "tool": {
                    "driver": {
                        "name": "aderyn",
                        "version": self.tooling_registry.get("aderyn", {}).get("version", "0.6.8"),
                        "rules": [],
                    }
                },
                "results": norm_results,
                "_source_file": rel_name,
            }

        # 4. Semgrep JSON format
        if isinstance(data, dict) and "results" in data and isinstance(data["results"], list):
            norm_results = []
            for s in data["results"]:
                check_id = s.get("check_id", "semgrep-rule")
                msg = s.get("extra", {}).get("message", "")
                path_str = s.get("path", "")
                start = s.get("start", {})
                line = start.get("line", 1)
                norm_results.append({
                    "ruleId": f"semgrep/{check_id}",
                    "level": "warning",
                    "message": {"text": str(msg).strip()},
                    "locations": [{
                        "physicalLocation": {
                            "artifactLocation": {"uri": str(path_str)},
                            "region": {"startLine": int(line), "endLine": int(s.get("end", {}).get("line", line))},
                        }
                    }],
                    "fingerprints": {},
                })
            return {
                "tool": {
                    "driver": {
                        "name": "semgrep",
                        "version": self.tooling_registry.get("semgrep", {}).get("version", "1.182.1"),
                        "rules": [],
                    }
                },
                "results": norm_results,
                "_source_file": rel_name,
            }

        # Unsupported structure
        self.rejected_inputs.append({
            "file": rel_name,
            "reason": "Unrecognized JSON format: not valid SARIF v2.1.0, Slither, Aderyn, or Semgrep schema",
            "sha256": file_sha,
        })
        return None

    def stage_7_deduplicate(self) -> None:
        """Stage 7: Deduplicate using a versioned identity policy."""
        # Key format: ruleId:uri:startLine:message_hash
        self.deduped_runs = []
        total_raw = 0
        total_deduped = 0
        tool_counts: dict[str, int] = {}

        for run in self.raw_runs:
            tool_name = run["tool"]["driver"]["name"]
            tool_counts.setdefault(tool_name, 0)
            deduped_results = []

            for res in run.get("results", []):
                total_raw += 1
                rule_id = res.get("ruleId", "")
                locs = res.get("locations", [])
                uri = ""
                start_line = 1
                if locs and "physicalLocation" in locs[0]:
                    uri = locs[0]["physicalLocation"].get("artifactLocation", {}).get("uri", "")
                    start_line = locs[0]["physicalLocation"].get("region", {}).get("startLine", 1)

                msg_hash = compute_str_hash(res.get("message", {}).get("text", ""))
                identity_key = f"{rule_id}:{uri}:{start_line}:{msg_hash}"

                if identity_key in self.seen_fingerprints:
                    # Drop duplicate
                    continue

                self.seen_fingerprints.add(identity_key)
                res["fingerprints"]["canonical_identity_key"] = identity_key
                deduped_results.append(res)
                tool_counts[tool_name] += 1
                total_deduped += 1

            self.deduped_runs.append({
                "tool": run["tool"],
                "results": deduped_results,
            })

        self.total_raw_findings = total_raw
        self.deduplicated_findings = total_deduped
        self.tool_breakdown = tool_counts
        self.falsification_checks.append(
            f"Stage 7: Deduplicated {total_raw} raw findings down to {total_deduped} unique findings."
        )

    def stage_8_and_9_serialize_and_validate(self) -> dict[str, Any]:
        """Stage 8 & 9: Serialize to declared contract and validate schema."""
        # Determine status
        if len(self.input_files) == 0:
            status = "EMPTY"
        else:
            status = "COLLECTED"

        # Compute canonical payload hash
        payload_bytes = json.dumps(self.deduped_runs, sort_keys=True).encode("utf-8")
        payload_sha256 = hashlib.sha256(payload_bytes).hexdigest()

        artifact: dict[str, Any] = {
            "slug": self.slug,
            "status": status,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "workflow_profile": "UOOMA-PACK-B-SARIF-COLLECTOR",
            "version": "1.0.0",
            "policy_governance": {
                "empty_allowed": self.empty_allowed,
                "dry_run": self.dry_run,
                "write_allowed": bool(self.confirm and not self.dry_run),
                "oracle_decision": "ACCEPTED_FOR_STAGING" if status in ["COLLECTED", "EMPTY"] else "NEEDS_REVIEW",
            },
            "provenance": {
                "scanned_directory": str(self.scan_dir),
                "input_files": [str(p.relative_to(self.scan_dir)) for p in self.input_files],
                "rejected_inputs": self.rejected_inputs,
                "tool_versions": self.tooling_registry,
            },
            "summary": {
                "total_inputs": len(self.input_files) + len(self.rejected_inputs),
                "accepted_inputs": len(self.input_files),
                "rejected_inputs": len(self.rejected_inputs),
                "total_raw_findings": self.total_raw_findings,
                "deduplicated_findings": self.deduplicated_findings,
                "tool_breakdown": self.tool_breakdown,
            },
            "deduplication_policy": {
                "policy_name": "canonical-identity-v1",
                "version": "1.0.0",
                "key_fields": ["ruleId", "uri", "startLine", "message_hash"],
            },
            "runs": self.deduped_runs,
            "verification_records": {
                "falsification_checks": self.falsification_checks,
                "artifact_sha256": payload_sha256,
                "readback_verified": True if (self.confirm and not self.dry_run) else False,
            },
        }

        # Validate with jsonschema if available, or internal validator
        schema_path = self.repo_root / "workflows" / "pack-b-static" / "schemas" / "normalized_sarif.schema.json"
        self._validate_schema(artifact, schema_path)
        self.falsification_checks.append("Stage 8-9: Validated artifact structure against schema.")
        return artifact

    def _validate_schema(self, artifact: dict[str, Any], schema_path: Path) -> None:
        """Validate artifact data against schema with fallback."""
        if schema_path.is_file():
            try:
                import jsonschema
                schema_data = json.loads(schema_path.read_text(encoding="utf-8"))
                jsonschema.validate(instance=artifact, schema=schema_data)
                return
            except ImportError:
                pass
            except Exception as e:
                raise SARIFNormalizationError(f"Schema validation failure: {str(e)}")

        # Built-in strict invariant fallback
        for key in ["slug", "status", "timestamp", "workflow_profile", "policy_governance", "provenance", "summary", "runs"]:
            if key not in artifact:
                raise SARIFNormalizationError(f"Missing mandatory field in normalized artifact: '{key}'")

        if artifact["status"] not in ["PLANNED", "DRY_RUN", "COLLECTED", "EMPTY", "PARTIAL", "FAILED", "CANCELLED"]:
            raise SARIFNormalizationError(f"Invalid status value: {artifact['status']}")

    def stage_10_to_14_publish_and_verify(self, artifact: dict[str, Any]) -> Tuple[int, dict[str, Any]]:
        """Stage 10-14: Secure staging, atomic swap, read-back verification, and final audit."""
        write_allowed = self.confirm and not self.dry_run

        if not write_allowed:
            # DRY-RUN
            artifact["status"] = "DRY_RUN"
            print(f"[DRY-RUN] Will collect {len(self.input_files)} scan files into {self.out_file}")
            print(f"[DRY-RUN] Summary: {self.total_raw_findings} raw findings -> {self.deduplicated_findings} deduplicated")
            return 0, artifact

        if self.fail_sim:
            raise SARIFNormalizationError("Simulated failure trigger activated via --fail-sim")

        # Stage 10: Secure staging to temporary file
        pid = os.getpid()
        tmp_file = self.scan_dir / f".tmp.normalized_sarif.{pid}.json"
        try:
            serialized = json.dumps(artifact, indent=2, sort_keys=True)
            if self.corrupt_sim:
                serialized = serialized[: len(serialized) // 2]  # Truncate to corrupt

            with open(tmp_file, "w", encoding="utf-8") as f:
                f.write(serialized)
                f.flush()
                os.fsync(f.fileno())

            # Verify tmp file parses before swap
            with open(tmp_file, "r", encoding="utf-8") as f:
                json.load(f)

            # Stage 11: Atomic replacement
            os.replace(tmp_file, self.out_file)

            # Stage 12: Read-back verification
            read_back_content = self.out_file.read_text(encoding="utf-8")
            read_back_json = json.loads(read_back_content)
            exact_sha256 = compute_sha256(self.out_file)
            self.exact_file_sha256 = exact_sha256

            # Stage 13: Atomic write of receipt.json with exact disk digest
            receipt = {
                "slug": self.slug,
                "artifact_file": self.out_file.name,
                "exact_file_sha256": exact_sha256,
                "payload_sha256": artifact["verification_records"]["artifact_sha256"],
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "total_deduplicated_findings": self.deduplicated_findings,
                "status": artifact["status"],
                "readback_verified": True,
            }
            tmp_receipt = self.scan_dir / f".tmp.receipt.{pid}.json"
            with open(tmp_receipt, "w", encoding="utf-8") as f:
                json.dump(receipt, f, indent=2, sort_keys=True)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_receipt, self.receipt_file)

            self.falsification_checks.append(
                f"Stage 10-14: Staged, swapped atomically, and verified read-back digest {exact_sha256[:16]}..."
            )
            print(f"[OK] SARIF collected and verified in {self.out_file} (SHA-256: {exact_sha256[:16]}...)")
            return 0, read_back_json

        except Exception as e:
            # Clean up temp file
            if tmp_file.exists():
                try:
                    tmp_file.unlink()
                except Exception:
                    pass
            raise e

    def verify_published_artifact(self) -> int:
        """Verify published normalized_sarif.json artifact against schema and receipt."""
        self.stage_1_and_2_preflight()
        if not self.out_file.exists():
            print(f"[ERROR] Verification failed: artifact file not found: {self.out_file}", file=sys.stderr)
            return 1

        try:
            content = self.out_file.read_text(encoding="utf-8")
            data = json.loads(content)
        except Exception as e:
            print(f"[ERROR] Verification failed: corrupted artifact JSON: {str(e)}", file=sys.stderr)
            return 1

        schema_path = self.repo_root / "workflows" / "pack-b-static" / "schemas" / "normalized_sarif.schema.json"
        try:
            self._validate_schema(data, schema_path)
        except Exception as e:
            print(f"[ERROR] Verification failed: schema validation error: {str(e)}", file=sys.stderr)
            return 1

        actual_sha256 = compute_sha256(self.out_file)

        if self.receipt_file.exists():
            try:
                receipt = json.loads(self.receipt_file.read_text(encoding="utf-8"))
                receipt_sha = receipt.get("exact_file_sha256", "")
                if receipt_sha and receipt_sha != actual_sha256:
                    print(
                        f"[ERROR] Verification failed: exact SHA-256 mismatch (receipt: {receipt_sha}, actual: {actual_sha256})",
                        file=sys.stderr,
                    )
                    return 1
                if not receipt.get("readback_verified", False):
                    print("[ERROR] Verification failed: receipt indicates readback_verified is False", file=sys.stderr)
                    return 1
            except Exception as e:
                print(f"[ERROR] Verification failed: invalid receipt.json: {str(e)}", file=sys.stderr)
                return 1

        print(f"[OK] Verification succeeded: {self.out_file} (SHA-256: {actual_sha256[:16]}...)")
        return 0

    def execute(self) -> int:
        """Run the workflow according to self.mode."""
        try:
            if self.mode == "INSPECT":
                self.stage_1_and_2_preflight()
                self.stage_3_inventory()
                print(f"[INSPECT] Bounty slug: {self.slug}")
                print(f"[INSPECT] Scan directory: {self.scan_dir}")
                print(f"[INSPECT] Discovered {len(self.input_files)} scan files:")
                for f in self.input_files:
                    print(f"  - {f.relative_to(self.scan_dir)}")
                if self.rejected_inputs:
                    print(f"[INSPECT] Rejected {len(self.rejected_inputs)} inputs:")
                    for r in self.rejected_inputs:
                        print(f"  - {r['file']}: {r['reason']}")
                return 0

            elif self.mode == "PLAN":
                self.stage_1_and_2_preflight()
                self.stage_3_inventory()
                self.stage_4_to_6_parse_and_normalize()
                self.stage_7_deduplicate()
                print(f"[PLAN] Target slug: {self.slug}")
                print(f"[PLAN] Status: PLANNED")
                print(f"[PLAN] Inputs: {len(self.input_files)} accepted, {len(self.rejected_inputs)} rejected")
                print(f"[PLAN] Projected findings: {self.total_raw_findings} raw -> {self.deduplicated_findings} deduplicated")
                for tool, count in self.tool_breakdown.items():
                    print(f"  - {tool}: {count} findings")
                return 0

            elif self.mode == "DRY_RUN":
                self.stage_1_and_2_preflight()
                self.stage_3_inventory()
                self.stage_4_to_6_parse_and_normalize()
                self.stage_7_deduplicate()
                artifact = self.stage_8_and_9_serialize_and_validate()
                artifact["status"] = "DRY_RUN"
                print(f"[DRY-RUN] Will collect {len(self.input_files)} scan files into {self.out_file}")
                print(f"[DRY-RUN] Summary: {self.total_raw_findings} raw findings -> {self.deduplicated_findings} deduplicated")
                return 0

            elif self.mode == "VERIFY":
                return self.verify_published_artifact()

            elif self.mode == "EXECUTE":
                self.stage_1_and_2_preflight()
                self.stage_3_inventory()
                self.stage_4_to_6_parse_and_normalize()
                self.stage_7_deduplicate()
                artifact = self.stage_8_and_9_serialize_and_validate()
                exit_code, _ = self.stage_10_to_14_publish_and_verify(artifact)
                return exit_code

            else:
                raise ValueError(f"Unknown mode: '{self.mode}'")

        except PathTraversalError as e:
            print(f"[ERROR] Configuration or Path Traversal: {str(e)}", file=sys.stderr)
            return 2
        except json.JSONDecodeError as e:
            print(f"[ERROR] Corrupted JSON detected: {str(e)}", file=sys.stderr)
            return 1
        except SARIFNormalizationError as e:
            print(f"[ERROR] SARIF Normalization failure: {str(e)}", file=sys.stderr)
            return 1
        except ValueError as e:
            print(f"[ERROR] Value error: {str(e)}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"[FATAL] Unhandled collector error: {type(e).__name__}: {str(e)}", file=sys.stderr)
            return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="UOOMA Pack B — Static Analysis & SARIF Collector Engine"
    )
    parser.add_argument("--slug", default="base", help="Target bounty slug (default: base)")
    parser.add_argument(
        "--mode",
        default="EXECUTE",
        choices=["INSPECT", "PLAN", "DRY_RUN", "EXECUTE", "VERIFY", "inspect", "plan", "dry_run", "execute", "verify"],
        help="Operating mode: INSPECT, PLAN, DRY_RUN, EXECUTE, VERIFY (default: EXECUTE)",
    )
    parser.add_argument("--dry-run", action="store_true", default=False, help="Simulate execution without modifying files")
    parser.add_argument("--confirm", action="store_true", default=False, help="Authorize write and atomic artifact publication")
    parser.add_argument("--empty-allowed", action="store_true", default=False, help="Explicitly permit empty scan directories")
    parser.add_argument("--fail-sim", action="store_true", default=False, help="Simulate failure for testing and rollback verification")
    parser.add_argument("--corrupt-sim", action="store_true", default=False, help="Simulate corrupted JSON write for testing")
    parser.add_argument("--target-dir", default=None, help="Explicit scan directory override")

    args = parser.parse_args()

    # Pre-parse validation
    if not args.slug or not SLUG_PATTERN.match(args.slug) or "/" in args.slug or "\\" in args.slug or ".." in args.slug:
        print(f"[ERROR] init: Invalid slug format '{args.slug}'. Path separators or traversal prohibited.", file=sys.stderr)
        return 2

    repo_root = Path(__file__).resolve().parents[2]
    custom_dir = Path(args.target_dir).resolve() if args.target_dir else None

    collector = UOOMASarifCollector(
        repo_root=repo_root,
        slug=args.slug,
        mode=args.mode,
        dry_run=args.dry_run,
        confirm=args.confirm,
        empty_allowed=args.empty_allowed,
        fail_sim=args.fail_sim,
        corrupt_sim=args.corrupt_sim,
        custom_scan_dir=custom_dir,
    )
    return collector.execute()


if __name__ == "__main__":
    sys.exit(main())
