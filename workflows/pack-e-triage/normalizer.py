#!/usr/bin/env python3
"""Pack E — Findings Normalization Engine.

Meta Persona: Cantina Security Findings Normalization Orchestrator
Governs:
  1. Discovery and parsing of raw security scanner reports (Slither, Semgrep, Aderyn, SARIF, Mythril).
  2. Capability & authorization governance per global/tooling.md.
  3. Evidence preservation, finding classification, and deduplication.
  4. Atomic persistence of bounties/<slug>/scans/findings_normalized.json adhering to canonical schema.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SLUG_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")

# Tool Registry baseline capabilities
APPROVED_SCANNERS = {
    "slither": {"version": "0.11.6", "status": "OK"},
    "myth": {"version": "0.24.8", "status": "OK"},
    "mythril": {"version": "0.24.8", "status": "OK"},
    "echidna": {"version": "2.3.3", "status": "OK"},
    "medusa": {"version": "1.5.1", "status": "OK"},
    "forge": {"version": "1.8.5", "status": "OK"},
    "halmos": {"version": "0.3.3", "status": "OK"},
    "aderyn": {"version": "0.6.8", "status": "OK"},
    "semgrep": {"version": "1.182.1", "status": "OK"},
    "heimdall": {"version": "0.9.2", "status": "OK"},
    "solana": {"version": "1.18.4", "status": "OK"},
    "anchor": {"version": "1.0.0", "status": "OK"},
}

EXCLUDED_FROM_CONSENSUS = {"solhint"}


def parse_tooling_registry(tooling_md_path: Path) -> dict[str, dict[str, str]]:
    """Parse tool statuses from global/tooling.md if available, falling back to baseline."""
    registry = dict(APPROVED_SCANNERS)
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


def parse_slither_json(file_path: Path, rel_path: str, tool_version: str) -> list[dict[str, Any]]:
    """Parse findings from a Slither JSON report."""
    findings: list[dict[str, Any]] = []
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return findings

    results = data.get("results", {})
    detectors = results.get("detectors", [])
    if not isinstance(detectors, list):
        return findings

    for idx, d in enumerate(detectors):
        if not isinstance(d, dict):
            continue
        check = d.get("check", f"detector-{idx}")
        impact = str(d.get("impact", "UNKNOWN")).upper()
        description = d.get("description", "")
        finding_id = f"slither-{check}-{idx+1}"

        loc_file = None
        line_start = None
        line_end = None
        contract = None

        elements = d.get("elements", [])
        if isinstance(elements, list) and elements:
            first_el = elements[0]
            if isinstance(first_el, dict):
                src_map = first_el.get("source_mapping", {})
                if isinstance(src_map, dict):
                    loc_file = src_map.get("filename_relative") or src_map.get("filename_short")
                    lines = src_map.get("lines", [])
                    if lines and isinstance(lines, list):
                        line_start = lines[0]
                        line_end = lines[-1]
                contract = first_el.get("name") if first_el.get("type") == "contract" else None

        findings.append({
            "schema_version": "1.0",
            "id": finding_id,
            "title": f"Slither: {check}",
            "severity": impact,
            "classification": "STATIC_ANALYSIS",
            "description": description.strip(),
            "location": {
                "file": loc_file,
                "line_start": line_start,
                "line_end": line_end,
                "contract_or_program": contract,
            },
            "provenance": [{
                "tool": "slither",
                "tool_version": tool_version,
                "source_report": rel_path,
                "source_finding_id": check,
            }],
            "evidence": elements if isinstance(elements, list) else [],
            "validation": {
                "status": "NOT_VALIDATED",
                "method": None,
                "reproduction": None,
            },
            "deduplication": {
                "group_id": None,
                "rationale": None,
            },
        })
    return findings


def parse_semgrep_json(file_path: Path, rel_path: str, tool_version: str) -> list[dict[str, Any]]:
    """Parse findings from a Semgrep JSON report."""
    findings: list[dict[str, Any]] = []
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return findings

    results = data.get("results", [])
    if not isinstance(results, list):
        return findings

    for idx, r in enumerate(results):
        if not isinstance(r, dict):
            continue
        check_id = r.get("check_id", f"rule-{idx}")
        extra = r.get("extra", {})
        severity = str(extra.get("severity", "UNKNOWN")).upper() if isinstance(extra, dict) else "UNKNOWN"
        message = extra.get("message", "") if isinstance(extra, dict) else ""
        finding_id = f"semgrep-{check_id.split('.')[-1]}-{idx+1}"

        loc_file = r.get("path")
        start = r.get("start", {})
        end = r.get("end", {})
        line_start = start.get("line") if isinstance(start, dict) else None
        line_end = end.get("line") if isinstance(end, dict) else None

        findings.append({
            "schema_version": "1.0",
            "id": finding_id,
            "title": f"Semgrep: {check_id}",
            "severity": severity,
            "classification": "STATIC_ANALYSIS",
            "description": message.strip(),
            "location": {
                "file": loc_file,
                "line_start": line_start,
                "line_end": line_end,
                "contract_or_program": None,
            },
            "provenance": [{
                "tool": "semgrep",
                "tool_version": tool_version,
                "source_report": rel_path,
                "source_finding_id": check_id,
            }],
            "evidence": [r],
            "validation": {
                "status": "NOT_VALIDATED",
                "method": None,
                "reproduction": None,
            },
            "deduplication": {
                "group_id": None,
                "rationale": None,
            },
        })
    return findings


def parse_aderyn_json(file_path: Path, rel_path: str, tool_version: str) -> list[dict[str, Any]]:
    """Parse findings from an Aderyn JSON report."""
    findings: list[dict[str, Any]] = []
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return findings

    for sev_level in ["critical_issues", "high_issues", "medium_issues", "low_issues", "nc_issues"]:
        issues = data.get(sev_level, {}).get("issues", []) if isinstance(data.get(sev_level), dict) else []
        for idx, issue in enumerate(issues):
            if not isinstance(issue, dict):
                continue
            title = issue.get("title", f"aderyn-issue-{idx}")
            desc = issue.get("description", "")
            severity = sev_level.replace("_issues", "").upper()
            finding_id = f"aderyn-{title.lower().replace(' ', '-')}-{idx+1}"

            instances = issue.get("instances", [])
            loc_file = None
            line_start = None
            line_end = None
            if instances and isinstance(instances, list) and isinstance(instances[0], dict):
                loc_file = instances[0].get("contract_path")
                line_start = instances[0].get("line_no")
                line_end = line_start

            findings.append({
                "schema_version": "1.0",
                "id": finding_id,
                "title": f"Aderyn: {title}",
                "severity": severity,
                "classification": "STATIC_ANALYSIS",
                "description": desc.strip(),
                "location": {
                    "file": loc_file,
                    "line_start": line_start,
                    "line_end": line_end,
                    "contract_or_program": None,
                },
                "provenance": [{
                    "tool": "aderyn",
                    "tool_version": tool_version,
                    "source_report": rel_path,
                    "source_finding_id": title,
                }],
                "evidence": instances,
                "validation": {
                    "status": "NOT_VALIDATED",
                    "method": None,
                    "reproduction": None,
                },
                "deduplication": {
                    "group_id": None,
                    "rationale": None,
                },
            })
    return findings


def parse_sarif_json(file_path: Path, rel_path: str, tool_version: str) -> list[dict[str, Any]]:
    """Parse findings from a standard SARIF JSON report."""
    findings: list[dict[str, Any]] = []
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return findings

    runs = data.get("runs", [])
    if not isinstance(runs, list):
        return findings

    for r_idx, run in enumerate(runs):
        if not isinstance(run, dict):
            continue
        driver = run.get("tool", {}).get("driver", {})
        tool_name = driver.get("name", "sarif-tool").lower()
        t_version = driver.get("version", tool_version)

        results = run.get("results", [])
        if not isinstance(results, list):
            continue

        for idx, res in enumerate(results):
            if not isinstance(res, dict):
                continue
            rule_id = res.get("ruleId", f"rule-{idx}")
            msg = res.get("message", {}).get("text", "")
            level = str(res.get("level", "UNKNOWN")).upper()
            finding_id = f"sarif-{tool_name}-{rule_id}-{idx+1}"

            loc_file = None
            line_start = None
            line_end = None
            locs = res.get("locations", [])
            if locs and isinstance(locs, list) and isinstance(locs[0], dict):
                phys = locs[0].get("physicalLocation", {})
                if isinstance(phys, dict):
                    loc_file = phys.get("artifactLocation", {}).get("uri")
                    region = phys.get("region", {})
                    if isinstance(region, dict):
                        line_start = region.get("startLine")
                        line_end = region.get("endLine") or line_start

            findings.append({
                "schema_version": "1.0",
                "id": finding_id,
                "title": f"{tool_name}: {rule_id}",
                "severity": level,
                "classification": "STATIC_ANALYSIS",
                "description": msg.strip(),
                "location": {
                    "file": loc_file,
                    "line_start": line_start,
                    "line_end": line_end,
                    "contract_or_program": None,
                },
                "provenance": [{
                    "tool": tool_name,
                    "tool_version": t_version,
                    "source_report": rel_path,
                    "source_finding_id": rule_id,
                }],
                "evidence": [res],
                "validation": {
                    "status": "NOT_VALIDATED",
                    "method": None,
                    "reproduction": None,
                },
                "deduplication": {
                    "group_id": None,
                    "rationale": None,
                },
            })
    return findings


def discover_and_ingest_reports(
    scans_dir: Path,
    registry: dict[str, dict[str, str]],
) -> Tuple[List[Dict[str, Any]], List[str], List[str]]:
    """Scan directory for available reports and parse them."""
    ingested_findings: list[dict[str, Any]] = []
    discovered_reports: list[str] = []
    unsupported_or_errors: list[str] = []

    if not scans_dir.is_dir():
        return ingested_findings, discovered_reports, unsupported_or_errors

    # Find JSON and SARIF candidate files
    for root, _, files in os.walk(scans_dir):
        for f in sorted(files):
            if f in ("findings_normalized.json", "overlap_analysis.json", "triage_summary.json", "hallucination_audit.json", "hallucination_audit.provenance.json"):
                continue
            if not (f.endswith(".json") or f.endswith(".sarif")):
                continue

            file_path = Path(root) / f
            rel_path = str(file_path.relative_to(scans_dir.parent))
            discovered_reports.append(rel_path)

            file_lower = f.lower()
            try:
                if "slither" in file_lower:
                    ver = registry.get("slither", {}).get("version", "0.11.6")
                    findings = parse_slither_json(file_path, rel_path, ver)
                    ingested_findings.extend(findings)
                elif "semgrep" in file_lower:
                    ver = registry.get("semgrep", {}).get("version", "1.182.1")
                    findings = parse_semgrep_json(file_path, rel_path, ver)
                    ingested_findings.extend(findings)
                elif "aderyn" in file_lower:
                    ver = registry.get("aderyn", {}).get("version", "0.6.8")
                    findings = parse_aderyn_json(file_path, rel_path, ver)
                    ingested_findings.extend(findings)
                elif f.endswith(".sarif") or "sarif" in file_lower:
                    findings = parse_sarif_json(file_path, rel_path, "1.0.0")
                    ingested_findings.extend(findings)
                else:
                    # Generic report probe
                    data = json.loads(file_path.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        if "results" in data and "detectors" in data.get("results", {}):
                            findings = parse_slither_json(file_path, rel_path, "0.11.6")
                            ingested_findings.extend(findings)
                        elif "runs" in data:
                            findings = parse_sarif_json(file_path, rel_path, "1.0.0")
                            ingested_findings.extend(findings)
            except Exception as e:
                unsupported_or_errors.append(f"{rel_path}: {e}")

    return ingested_findings, discovered_reports, unsupported_or_errors


def deduplicate_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate findings sharing identical file and start line while preserving provenance."""
    deduped: dict[str, dict[str, Any]] = {}
    for f in findings:
        loc = f.get("location", {})
        file_name = loc.get("file") or "unknown_file"
        line_start = loc.get("line_start") or 0
        rule_or_title = f.get("title", "")

        key = f"{file_name}:{line_start}:{rule_or_title}"
        if key not in deduped:
            deduped[key] = f
        else:
            existing = deduped[key]
            # Merge provenance records
            existing_provs = {p.get("tool"): p for p in existing.get("provenance", [])}
            for p in f.get("provenance", []):
                tool = p.get("tool")
                if tool not in existing_provs:
                    existing["provenance"].append(p)
            existing["deduplication"] = {
                "group_id": f"grp-{hash(key) & 0xffffffff:08x}",
                "rationale": f"Merged equivalent detector finding on {file_name}:{line_start}",
            }

    return list(deduped.values())


def normalize_findings_artifact(
    repo_root: Path,
    slug: str,
    target_revision: Optional[str] = None,
) -> dict[str, Any]:
    """Execute logical phases B through E to produce canonical findings artifact."""
    bounty_dir = repo_root / "bounties" / slug
    scans_dir = bounty_dir / "scans"
    tooling_md = repo_root / "global" / "tooling.md"

    # Tool registry status resolution
    registry = parse_tooling_registry(tooling_md)

    # Ingestion & Discovery
    raw_findings, discovered_reports, errors = discover_and_ingest_reports(scans_dir, registry)

    # Map target context
    for f in raw_findings:
        f["target"] = {
            "repository": "cantina",
            "slug": slug,
            "revision": target_revision,
        }

    # Deduplicate
    deduped_findings = deduplicate_findings(raw_findings)

    # Section 7 Canonical contract
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "slug": slug,
        "normalized_findings": deduped_findings,
        "timestamp": timestamp,
        "status": "NORMALIZATION_COMPLETE",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Pack E Findings Normalization Engine.")
    parser.add_argument("--slug", default="base", help="Target bounty slug")
    parser.add_argument("--repo-root", default="/home/nova/projects/cantina", help="Cantina repo root")
    parser.add_argument("--dry-run", action="store_true", help="Preview normalization without writing")
    parser.add_argument("--confirm", action="store_true", help="Authorize normalization write")
    parser.add_argument("--commit", default=None, help="Pinned revision hash")
    args = parser.parse_args()

    slug = args.slug
    if not SLUG_PATTERN.match(slug) or "/" in slug or "\\" in slug or ".." in slug:
        sys.stderr.write(f"[ERROR] init: Invalid slug format '{slug}'.\n")
        return 1

    repo_root = Path(args.repo_root).resolve()
    scans_dir = repo_root / "bounties" / slug / "scans"
    out_file = scans_dir / "findings_normalized.json"

    sys.stdout.write(f"=== [Pack E] Workflow: Normalize Findings ({slug}) ===\n")

    if args.dry_run or not args.confirm:
        sys.stdout.write(f"[DRY-RUN] Will normalize findings into {out_file}\n")
        return 0

    # Ensure scans dir exists and check containment
    scans_dir.mkdir(parents=True, exist_ok=True)
    resolved_scans_dir = scans_dir.resolve()
    bounties_dir = (repo_root / "bounties").resolve()
    if not resolved_scans_dir.is_relative_to(bounties_dir):
        sys.stderr.write("[ERROR] persist: Destination path escaped workspace boundary.\n")
        return 1

    # Normalize findings
    payload = normalize_findings_artifact(repo_root, slug, target_revision=args.commit)

    # Atomic write
    tmp_path = scans_dir / f"findings_normalized.tmp.{os.getpid()}"
    try:
        tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp_path.replace(out_file)
    except Exception as e:
        if tmp_path.exists():
            tmp_path.unlink()
        sys.stderr.write(f"[ERROR] persist: Atomic write failure: {e}\n")
        return 1

    finding_count = len(payload["normalized_findings"])
    if finding_count == 0:
        sys.stdout.write(f"[OK] Normalized findings saved to {out_file} (0 ingested findings; does not establish vulnerability absence per Section 13)\n")
    else:
        sys.stdout.write(f"[OK] Normalized findings saved to {out_file} ({finding_count} findings ingested and normalized)\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
