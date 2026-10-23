#!/usr/bin/env python3
"""Core Overlap & Known-Issue Annotation Engine for Pack E Triage Workflows.

Meta-Persona: CANTINA-PACK-E (Cantina Bounty Security Analyst - Pack E)
Phases:
  Phase A — Parse and validate
  Phase B — Inventory evidence
  Phase C — Normalize candidate findings
  Phase D — Compare against known issues
  Phase E — Corroborate and qualify
  Phase F — Produce the overlap report
  Phase G — Validate and commit the artifact

Artifact: bounties/<slug>/scans/overlap_analysis.json
"""

import argparse
import datetime
import glob
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

SLUG_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")

VERIFIED_SCANNERS = {
    "slither": "Slither 0.11.6",
    "mythril": "Mythril 0.24.8",
    "echidna": "Echidna 2.3.3",
    "medusa": "Medusa 1.5.1",
    "halmos": "Halmos 0.3.3",
    "aderyn": "Aderyn 0.6.8",
    "semgrep": "Semgrep 1.182.1",
    "heimdall": "Heimdall 0.9.2",
}


def log_event(
    level: str,
    event: str,
    message: str,
    component: str = "overlap_analyzer",
    slug: Optional[str] = None,
    processed_count: int = 0,
    error_code: Optional[str] = None,
) -> None:
    """Emit a structured JSON Lines event record to stderr."""
    payload = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "level": level,
        "event": event,
        "component": component,
        "slug": slug,
        "processed_count": processed_count,
        "error_code": error_code,
        "message": message,
    }
    sys.stderr.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stderr.flush()


def find_repo_root(start_dir: Optional[Path] = None) -> Path:
    """Find git repository root or fallback to environment/current dir."""
    env_root = os.environ.get("REPO_ROOT")
    if env_root and os.path.isdir(env_root):
        return Path(env_root).resolve()

    cur = start_dir or Path.cwd()
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(cur),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        return Path(res.stdout.strip()).resolve()
    except Exception:
        check = cur.resolve()
        while check != check.parent:
            if (check / ".git").exists():
                return check
            check = check.parent
        return cur.resolve()


def get_git_commit(repo_root: Path) -> Optional[str]:
    """Retrieve pinned git commit hash if available."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD^{commit}"],
            cwd=str(repo_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        commit = res.stdout.strip()
        if re.match(r"^[0-9a-fA-F]{40,64}$", commit):
            return commit
    except Exception:
        pass
    return None


def check_symlink_traversal(target: Path, boundary: Path) -> bool:
    """Return True if target is a symlink or escapes boundary."""
    try:
        if target.is_symlink():
            return True
        resolved = target.resolve()
        resolved_boundary = boundary.resolve()
        return not resolved.is_relative_to(resolved_boundary)
    except Exception:
        return True


def check_device_boundary(dir_a: Path, dir_b: Path) -> bool:
    """Check if both paths are on the same filesystem device."""
    try:
        if dir_a.exists() and dir_b.exists():
            return os.stat(dir_a).st_dev == os.stat(dir_b).st_dev
    except Exception:
        pass
    return True


def extract_text(val: Any) -> str:
    """Recursively extract clean string content from any object (str, list, dict, int, etc.)."""
    if val is None:
        return ""
    if isinstance(val, str):
        return val
    if isinstance(val, (list, tuple, set)):
        return " ".join(extract_text(x) for x in val if x is not None)
    if isinstance(val, dict):
        return " ".join(f"{k} {extract_text(v)}" for k, v in val.items() if v is not None)
    return str(val)


# ----------------------------------------------------------------------
# Phase B & C: Discovery and Normalization
# ----------------------------------------------------------------------

def discover_candidate_findings(
    bounty_dir: Path, repo_root: Path
) -> Tuple[List[Dict[str, Any]], Set[str], Set[str], Set[str]]:
    """Discover candidate findings in the bounty workspace."""
    candidates: List[Dict[str, Any]] = []
    sources_inspected: Set[str] = set()
    sources_unavailable: Set[str] = set()
    tools_used: Set[str] = set()

    # 1. Scans directory JSON reports
    scans_dir = bounty_dir / "scans"
    potential_scan_files = [
        ("findings_normalized.json", "normalization"),
        ("normalized_sarif.json", "sarif"),
        ("sarif_output.json", "sarif"),
        ("triage_summary.json", "triage"),
    ]

    for fname, ftype in potential_scan_files:
        fpath = scans_dir / fname
        rel_path = str(fpath.relative_to(repo_root)) if fpath.is_relative_to(repo_root) else str(fpath)
        if fpath.is_file() and not fpath.is_symlink():
            sources_inspected.add(rel_path)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if ftype == "normalization":
                    items = data.get("normalized_findings", data.get("findings", []))
                    if isinstance(items, list):
                        for idx, item in enumerate(items):
                            cid = item.get("id") or item.get("finding_id") or f"NORM-{idx+1:03d}"
                            loc = item.get("location") or {}
                            if not isinstance(loc, dict):
                                loc = {}
                            target_obj = item.get("target") or {}
                            target_str = target_obj.get("slug", "") if isinstance(target_obj, dict) else str(target_obj or "")

                            affected_code = (
                                item.get("affected_contract")
                                or loc.get("contract_or_program")
                                or loc.get("file")
                                or target_str
                                or ""
                            )
                            candidates.append({
                                "candidate_id": str(cid),
                                "title": str(item.get("title") or f"Normalized Finding {cid}"),
                                "vulnerability_class": str(item.get("classification") or item.get("vulnerability_class") or item.get("category") or "Unknown"),
                                "affected_code": str(affected_code),
                                "root_cause": str(item.get("description") or item.get("root_cause") or ""),
                                "exploit_path": str(item.get("exploit_path") or ""),
                                "preconditions": str(item.get("preconditions") or ""),
                                "impact": str(item.get("severity") or item.get("impact") or ""),
                                "source_ref": rel_path,
                            })
                elif ftype == "sarif":
                    tools_used.add("sarif_collector")
                    runs = data.get("runs", [])
                    for r in runs:
                        driver_name = r.get("tool", {}).get("driver", {}).get("name", "").lower()
                        for vtool in VERIFIED_SCANNERS:
                            if vtool in driver_name:
                                tools_used.add(VERIFIED_SCANNERS[vtool])
                        results = r.get("results", [])
                        for idx, res in enumerate(results):
                            rule_id = res.get("ruleId", f"RULE-{idx+1:03d}")
                            msg = res.get("message", {}).get("text", "")
                            loc = ""
                            locations = res.get("locations", [])
                            if locations:
                                uri = locations[0].get("physicalLocation", {}).get("artifactLocation", {}).get("uri", "")
                                loc = uri
                            candidates.append({
                                "candidate_id": f"SARIF-{rule_id}-{idx+1:03d}",
                                "title": f"SARIF: {rule_id}",
                                "vulnerability_class": str(rule_id),
                                "affected_code": str(loc),
                                "root_cause": str(msg),
                                "exploit_path": "",
                                "preconditions": "",
                                "impact": str(res.get("level", "warning")),
                                "source_ref": rel_path,
                            })
                elif ftype == "triage":
                    triage_cands = data.get("candidates", [])
                    if isinstance(triage_cands, list):
                        for idx, tc in enumerate(triage_cands):
                            cid = tc.get("id", f"TRIAGE-{idx+1:03d}")
                            comps = tc.get("affected_components", [])
                            affected_code = ", ".join(comps) if isinstance(comps, list) else str(comps or tc.get("affected_code", ""))
                            imp = tc.get("impact")
                            imp_str = imp.get("description", "") if isinstance(imp, dict) else str(imp or "")
                            exp = tc.get("exploitability")
                            pre_str = ""
                            if isinstance(exp, dict):
                                pre_items = exp.get("prerequisites", []) + exp.get("attacker_capabilities", [])
                                pre_str = " ".join(extract_text(x) for x in pre_items)
                            candidates.append({
                                "candidate_id": str(cid),
                                "title": str(tc.get("title") or f"Triage Candidate {cid}"),
                                "vulnerability_class": str(tc.get("vulnerability_class") or tc.get("disposition") or "Unknown"),
                                "affected_code": affected_code,
                                "root_cause": str(tc.get("root_cause") or tc.get("description") or ""),
                                "exploit_path": str(tc.get("exploit_path") or ""),
                                "preconditions": pre_str or str(tc.get("preconditions") or ""),
                                "impact": imp_str,
                                "source_ref": rel_path,
                            })
            except Exception as e:
                log_event("WARNING", "SCAN_FILE_PARSE_ERROR", f"Could not parse {rel_path}: {e}")
        else:
            sources_unavailable.add(rel_path)

    # 2. Markdown reports, findings, hypotheses
    md_dirs = [
        bounty_dir / "findings",
        bounty_dir / "reports",
        bounty_dir / "hypotheses",
    ]

    for d in md_dirs:
        rel_d = str(d.relative_to(repo_root)) if d.is_relative_to(repo_root) else str(d)
        if d.is_dir() and not d.is_symlink():
            for md_file in sorted(d.glob("*.md")):
                if md_file.is_file() and not md_file.is_symlink():
                    rel_f = str(md_file.relative_to(repo_root)) if md_file.is_relative_to(repo_root) else str(md_file)
                    sources_inspected.add(rel_f)
                    try:
                        content = md_file.read_text(encoding="utf-8", errors="replace")
                        cid = md_file.stem
                        title = md_file.stem
                        affected_code = ""
                        root_cause = content[:300].strip()
                        for line in content.splitlines():
                            line_s = line.strip()
                            if line.startswith("# ") and title == md_file.stem:
                                title = line[2:].strip()
                            elif re.match(r"^(affected|target|contract|file)\s*:\s*", line_s, re.I):
                                affected_code = re.sub(r"^(affected|target|contract|file)\s*:\s*", "", line_s, flags=re.I).strip()
                            elif re.match(r"^(root\s*cause|description)\s*:\s*", line_s, re.I):
                                root_cause = re.sub(r"^(root\s*cause|description)\s*:\s*", "", line_s, flags=re.I).strip()
                        if not affected_code:
                            contract_match = re.search(r"\b([A-Z][A-Za-z0-9_]+(?:\.sol)?)\b", title)
                            if contract_match:
                                matched_name = contract_match.group(1)
                                if matched_name.lower() not in {"hypothesis", "finding", "vulnerability", "issue", "security", "review"}:
                                    affected_code = matched_name
                        candidates.append({
                            "candidate_id": f"DOC-{cid}",
                            "title": title,
                            "vulnerability_class": "Manual Report / Hypothesis",
                            "affected_code": affected_code,
                            "root_cause": root_cause,
                            "exploit_path": "",
                            "preconditions": "",
                            "impact": "Security Concern",
                            "source_ref": rel_f,
                        })
                    except Exception as e:
                        log_event("WARNING", "MD_FILE_PARSE_ERROR", f"Could not parse {rel_f}: {e}")
        else:
            sources_unavailable.add(f"{rel_d}/*.md")

    return candidates, sources_inspected, sources_unavailable, tools_used


def discover_known_issues(
    bounty_dir: Path, repo_root: Path
) -> Tuple[List[Dict[str, Any]], Set[str], Set[str], bool]:
    """Discover known issues, accepted risks, and prior disclosures."""
    known_issues: List[Dict[str, Any]] = []
    sources_inspected: Set[str] = set()
    sources_unavailable: Set[str] = set()
    known_issues_checked = False

    # 1. Check MEMORY.md
    memory_path = bounty_dir / "MEMORY.md"
    rel_mem = str(memory_path.relative_to(repo_root)) if memory_path.is_relative_to(repo_root) else str(memory_path)
    if memory_path.is_file() and not memory_path.is_symlink():
        sources_inspected.add(rel_mem)
        known_issues_checked = True
        try:
            content = memory_path.read_text(encoding="utf-8", errors="replace")
            # Parse sections
            current_section = ""
            for line in content.splitlines():
                if line.startswith("#"):
                    current_section = line.strip("# ").strip()
                elif line.strip().startswith("- ") and len(line.strip()) > 3:
                    item_text = line.strip()[2:].strip()
                    kid = f"MEM-{len(known_issues)+1:03d}"
                    known_issues.append({
                        "issue_id": kid,
                        "title": item_text[:80],
                        "vulnerability_class": current_section or "Accepted Risk / Known Issue",
                        "affected_component": "",
                        "description": item_text,
                        "remediation_status": "documented_known_issue",
                        "source_ref": rel_mem,
                    })
        except Exception as e:
            log_event("WARNING", "MEMORY_PARSE_ERROR", f"Could not parse {rel_mem}: {e}")
    else:
        sources_unavailable.add(rel_mem)

    # 2. Check scope.md (Known issues / out of scope sections)
    scope_path = bounty_dir / "scope.md"
    rel_scope = str(scope_path.relative_to(repo_root)) if scope_path.is_relative_to(repo_root) else str(scope_path)
    if scope_path.is_file() and not scope_path.is_symlink():
        sources_inspected.add(rel_scope)
        try:
            content = scope_path.read_text(encoding="utf-8", errors="replace")
            in_known_section = False
            for line in content.splitlines():
                lower = line.lower()
                if line.startswith("#"):
                    if any(k in lower for k in ["known issue", "out of scope", "accepted risk", "previous audit", "known vulnerability"]):
                        in_known_section = True
                        known_issues_checked = True
                    else:
                        in_known_section = False
                elif in_known_section and line.strip().startswith("- "):
                    item_text = line.strip()[2:].strip()
                    if item_text:
                        kid = f"SCOPE-KNOWN-{len(known_issues)+1:03d}"
                        known_issues.append({
                            "issue_id": kid,
                            "title": item_text[:80],
                            "vulnerability_class": "Known Issue / Scope Exclusion",
                            "affected_component": "",
                            "description": item_text,
                            "remediation_status": "accepted_risk",
                            "source_ref": rel_scope,
                        })
        except Exception as e:
            log_event("WARNING", "SCOPE_PARSE_ERROR", f"Could not parse {rel_scope}: {e}")
    else:
        sources_unavailable.add(rel_scope)

    # 3. Check global/refutations.md
    refutations_path = repo_root / "global" / "refutations.md"
    rel_ref = "global/refutations.md"
    if refutations_path.is_file() and not refutations_path.is_symlink():
        sources_inspected.add(rel_ref)
        try:
            content = refutations_path.read_text(encoding="utf-8", errors="replace")
            for line in content.splitlines():
                if line.startswith("## ") or (line.startswith("- ") and "refuted" in line.lower()):
                    item_text = line.strip("#- ").strip()
                    if item_text:
                        kid = f"REFUTED-{len(known_issues)+1:03d}"
                        known_issues.append({
                            "issue_id": kid,
                            "title": item_text[:80],
                            "vulnerability_class": "Refuted Hypothesis / Known Non-Issue",
                            "affected_component": "",
                            "description": item_text,
                            "remediation_status": "refuted",
                            "source_ref": rel_ref,
                        })
        except Exception as e:
            log_event("WARNING", "REFUTATIONS_PARSE_ERROR", f"Could not parse {rel_ref}: {e}")
    else:
        sources_unavailable.add(rel_ref)

    # 4. Check references directory
    refs_dir = bounty_dir / "references"
    rel_refs = str(refs_dir.relative_to(repo_root)) if refs_dir.is_relative_to(repo_root) else str(refs_dir)
    if refs_dir.is_dir() and not refs_dir.is_symlink():
        for rfile in sorted(refs_dir.glob("*.md")):
            if rfile.is_file() and not rfile.is_symlink():
                rel_rf = str(rfile.relative_to(repo_root)) if rfile.is_relative_to(repo_root) else str(rfile)
                sources_inspected.add(rel_rf)
                known_issues_checked = True
                kid = f"REF-{rfile.stem}"
                known_issues.append({
                    "issue_id": kid,
                    "title": f"Reference: {rfile.stem}",
                    "vulnerability_class": "Prior Disclosure / Audit Reference",
                    "affected_component": rfile.stem,
                    "description": f"Historical reference file {rel_rf}",
                    "remediation_status": "reference",
                    "source_ref": rel_rf,
                })
    else:
        sources_unavailable.add(f"{rel_refs}/*.md")

    return known_issues, sources_inspected, sources_unavailable, known_issues_checked


# ----------------------------------------------------------------------
# Phase D: Multidimensional Comparison
# ----------------------------------------------------------------------

def tokenize(text: Any) -> Set[str]:
    """Tokenize text into alphanumeric lowercase keywords (ignoring small stop words)."""
    raw = extract_text(text).lower()
    words = set(re.findall(r"[A-Za-z0-9_]{3,}", raw))
    stop_words = {"the", "and", "for", "with", "this", "that", "from", "contract", "issue"}
    return words - stop_words


def compare_candidate_to_known(
    candidate: Dict[str, Any], known: Dict[str, Any]
) -> Tuple[str, str, str, Dict[str, Any]]:
    """Compare candidate against a known issue across 7 dimensions.

    Returns:
      (classification, rationale, confidence, comparison_dimensions)
    """
    c_title = extract_text(candidate.get("title", ""))
    c_desc = extract_text(candidate.get("root_cause", ""))
    c_code = extract_text(candidate.get("affected_code", ""))
    c_class = extract_text(candidate.get("vulnerability_class", ""))
    c_id = extract_text(candidate.get("candidate_id", ""))

    k_title = extract_text(known.get("title", ""))
    k_desc = extract_text(known.get("description", ""))
    k_code = extract_text(known.get("affected_component", ""))
    k_class = extract_text(known.get("vulnerability_class", ""))
    k_id = extract_text(known.get("issue_id", ""))
    k_status = extract_text(known.get("remediation_status", "unknown"))

    c_tokens = tokenize(f"{c_title} {c_desc} {c_class}")
    k_tokens = tokenize(f"{k_title} {k_desc} {k_class}")

    # Insufficient / empty evidence check
    has_real_evidence = bool(c_desc.strip() or (c_code.strip() and len(c_code.strip()) >= 3))
    if not has_real_evidence:
        return (
            "UNABLE_TO_DETERMINE",
            f"Evidence for candidate '{c_id}' is empty or insufficient; cannot establish overlap with '{k_id}'.",
            "LOW",
            {
                "root_cause_match": None,
                "affected_code_match": None,
                "exploit_path_match": None,
                "preconditions_match": None,
                "impact_match": None,
                "remediation_status": k_status,
            },
        )

    # 1. Issue ID match
    explicit_id_match = bool(k_id and (k_id.lower() in c_title.lower() or k_id.lower() in c_desc.lower()))

    # 2. Affected code overlap
    code_match = False
    c_components = [x.strip() for x in re.split(r"[,;\s]+", c_code) if x.strip()]
    k_components = [x.strip() for x in re.split(r"[,;\s]+", k_code) if x.strip()]

    if c_code and k_code and (c_code.lower() in k_code.lower() or k_code.lower() in c_code.lower()):
        code_match = True
    else:
        for comp in c_components:
            comp_base = re.sub(r"\.(sol|rs|ts|js|py)$", "", comp, flags=re.I).lower().strip()
            comp_name = Path(comp_base).name.lower()
            if len(comp_name) >= 3:
                if (
                    comp_name in k_desc.lower()
                    or comp_name in k_title.lower()
                    or any(comp_name in re.sub(r"\.(sol|rs|ts|js|py)$", "", kc, flags=re.I).lower() for kc in k_components)
                ):
                    code_match = True
                    break

        if not code_match:
            for kcomp in k_components:
                kcomp_base = re.sub(r"\.(sol|rs|ts|js|py)$", "", kcomp, flags=re.I).lower().strip()
                kcomp_name = Path(kcomp_base).name.lower()
                if len(kcomp_name) >= 3:
                    if (
                        kcomp_name in c_desc.lower()
                        or kcomp_name in c_title.lower()
                        or any(kcomp_name in re.sub(r"\.(sol|rs|ts|js|py)$", "", cc, flags=re.I).lower() for cc in c_components)
                    ):
                        code_match = True
                        break

    # 3. Root cause / keyword equivalence
    common_tokens = c_tokens & k_tokens
    c_overlap_ratio = len(common_tokens) / max(len(c_tokens), 1)
    k_overlap_ratio = len(common_tokens) / max(len(k_tokens), 1)

    root_cause_match = (
        len(common_tokens) >= 3
        or k_overlap_ratio >= 0.35
        or c_overlap_ratio >= 0.35
        or (len(common_tokens) >= 2 and code_match)
    )

    # 4. Exploit path / preconditions
    exploit_path_match = None
    preconditions_match = None
    if candidate.get("exploit_path") and known.get("description"):
        c_exp = tokenize(candidate.get("exploit_path", ""))
        exploit_path_match = len(c_exp & k_tokens) >= 2

    # 5. Impact equivalence
    impact_match = None
    if candidate.get("impact"):
        c_imp = tokenize(candidate.get("impact", ""))
        impact_match = len(c_imp & k_tokens) >= 1

    comparison_dimensions = {
        "root_cause_match": root_cause_match,
        "affected_code_match": code_match,
        "exploit_path_match": exploit_path_match,
        "preconditions_match": preconditions_match,
        "impact_match": impact_match,
        "remediation_status": k_status,
    }

    if explicit_id_match or (code_match and root_cause_match and (impact_match is not False)):
        classification = "CONFIRMED_OVERLAP"
        confidence = "HIGH"
        rationale = (
            f"Strong alignment with known issue '{k_id}': affected component matched ({code_match}) "
            f"and root-cause semantic overlap ({len(common_tokens)} common keywords: {', '.join(sorted(list(common_tokens))[:4])})."
        )
    elif code_match and (root_cause_match or len(common_tokens) >= 1):
        classification = "PROBABLE_OVERLAP"
        confidence = "MEDIUM"
        rationale = (
            f"Component match on '{c_code or k_code}' with probable semantic correlation to '{k_id}', "
            f"though complete exploit-path or precondition equivalence remains unverified."
        )
    elif code_match or root_cause_match:
        classification = "RELATED_DISTINCT"
        confidence = "MEDIUM"
        rationale = (
            f"Shares affected component or vulnerability category with '{k_id}', but material facts "
            f"(root cause or exploit path) differ materially."
        )
    else:
        classification = "NO_OVERLAP_FOUND"
        confidence = "HIGH"
        rationale = f"Evaluated against known issue '{k_id}'; no material root cause or component overlap found."

    return classification, rationale, confidence, comparison_dimensions


def analyze_overlaps(
    candidates: List[Dict[str, Any]],
    known_issues: List[Dict[str, Any]],
    known_issues_checked: bool,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Execute multidimensional comparison across all candidates and known issues."""
    relationships: List[Dict[str, Any]] = []

    confirmed_count = 0
    probable_count = 0
    distinct_count = 0
    indeterminate_count = 0

    if not known_issues or not known_issues_checked:
        for c in candidates:
            c_id = extract_text(c.get("candidate_id", ""))
            rel = {
                "candidate_id": c_id,
                "related_issue_id": None,
                "classification": "NO_OVERLAP_FOUND" if known_issues_checked else "UNABLE_TO_DETERMINE",
                "rationale": (
                    "No known issues exist in the bounty scope or historical corpus for comparison."
                    if known_issues_checked
                    else "Known-issue corpus was not checked or is unavailable for comparison."
                ),
                "evidence_refs": [c["source_ref"]],
                "confidence": "UNKNOWN" if known_issues_checked else "LOW",
                "comparison_dimensions": {
                    "root_cause_match": None,
                    "affected_code_match": None,
                    "exploit_path_match": None,
                    "preconditions_match": None,
                    "impact_match": None,
                    "remediation_status": None,
                },
            }
            relationships.append(rel)
            if not known_issues_checked:
                indeterminate_count += 1
            else:
                distinct_count += 1

        return {
            "candidate_count": len(candidates),
            "known_issue_count": 0,
            "confirmed_overlap_count": 0,
            "probable_overlap_count": 0,
            "distinct_finding_count": distinct_count,
            "indeterminate_count": indeterminate_count,
            "relationships": relationships,
        }, relationships

    for c in candidates:
        best_rel = None
        best_priority = -1  # 4=CONFIRMED, 3=PROBABLE, 2=RELATED, 1=NO_OVERLAP, 0=UNABLE_TO_DETERMINE

        for k in known_issues:
            classification, rationale, confidence, dims = compare_candidate_to_known(c, k)
            priority = {
                "CONFIRMED_OVERLAP": 4,
                "PROBABLE_OVERLAP": 3,
                "RELATED_DISTINCT": 2,
                "NO_OVERLAP_FOUND": 1,
                "UNABLE_TO_DETERMINE": 0,
            }.get(classification, -1)

            if priority > best_priority or best_rel is None:
                best_priority = priority
                best_rel = {
                    "candidate_id": c["candidate_id"],
                    "related_issue_id": k["issue_id"] if classification in ["CONFIRMED_OVERLAP", "PROBABLE_OVERLAP", "RELATED_DISTINCT"] else None,
                    "classification": classification,
                    "rationale": rationale,
                    "evidence_refs": [c["source_ref"], k["source_ref"]],
                    "confidence": confidence,
                    "comparison_dimensions": dims,
                }

        if best_rel:
            if best_rel["classification"] == "NO_OVERLAP_FOUND":
                best_rel["rationale"] = (
                    f"Evaluated against {len(known_issues)} known issue(s) in bounty corpus; "
                    "no material root-cause or component overlap found."
                )
            relationships.append(best_rel)
            cls = best_rel["classification"]
            if cls == "CONFIRMED_OVERLAP":
                confirmed_count += 1
            elif cls == "PROBABLE_OVERLAP":
                probable_count += 1
            elif cls == "RELATED_DISTINCT":
                distinct_count += 1
            elif cls == "UNABLE_TO_DETERMINE":
                indeterminate_count += 1

    analysis_summary = {
        "candidate_count": len(candidates),
        "known_issue_count": len(known_issues),
        "confirmed_overlap_count": confirmed_count,
        "probable_overlap_count": probable_count,
        "distinct_finding_count": distinct_count,
        "indeterminate_count": indeterminate_count,
        "relationships": relationships,
    }

    return analysis_summary, relationships


# ----------------------------------------------------------------------
# Phase G: Durable Atomic Replacement & Validation
# ----------------------------------------------------------------------

def validate_artifact_schema(data: Dict[str, Any], schema_path: Path) -> Tuple[bool, Optional[str]]:
    """Validate output artifact against overlap_analysis.schema.json."""
    if not schema_path.is_file():
        return False, f"Schema file not found at {schema_path}"
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
    except Exception as e:
        return False, f"Failed to load schema: {e}"

    try:
        import jsonschema
        try:
            jsonschema.validate(instance=data, schema=schema)
            return True, None
        except jsonschema.ValidationError as e:
            return False, f"Schema validation error: {e.message}"
    except ImportError:
        # Fallback basic schema validation
        required_keys = [
            "schema_version",
            "slug",
            "known_issues_checked",
            "timestamp",
            "status",
            "analysis",
            "evidence",
            "limitations",
            "write",
        ]
        for k in required_keys:
            if k not in data:
                return False, f"Missing required top-level key: {k}"
        return True, None


def durable_atomic_write(
    out_file: Path,
    content: str,
    schema_path: Path,
) -> None:
    """Perform atomic replacement with 0600 permissions, fsync, and read-back validation."""
    if out_file.is_symlink():
        raise PermissionError(f"Destination output file '{out_file}' is a symlink.")

    scans_dir = out_file.parent
    if scans_dir.is_symlink():
        raise PermissionError(f"Output scans directory '{scans_dir}' is a symlink.")
    scans_dir.mkdir(parents=True, exist_ok=True)

    temp_path = scans_dir / f".overlap_analysis.tmp-{os.getpid()}-{int(datetime.datetime.now().timestamp())}"
    try:
        # Open with 0600 mode and write
        flags = os.O_CREAT | os.O_WRONLY | os.O_TRUNC
        fd = os.open(str(temp_path), flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(fd)

        # Enforce strict 0600 permissions
        os.chmod(temp_path, 0o600)

        # Read back and validate JSON and schema
        with open(temp_path, "r", encoding="utf-8") as f:
            read_back_data = json.load(f)

        valid, err_msg = validate_artifact_schema(read_back_data, schema_path)
        if not valid:
            raise ValueError(f"Post-write validation failed: {err_msg}")

        # Atomic replace
        os.replace(str(temp_path), str(out_file))
        os.chmod(out_file, 0o600)

        # Sync parent directory
        try:
            dir_fd = os.open(str(scans_dir), os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except Exception:
            pass

    except Exception:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass
        raise


# ----------------------------------------------------------------------
# Main Execution Pipeline (Phases A through G)
# ----------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Pack E Overlap & Known-Issue Annotation Engine.")
    parser.add_argument("--repo-root", help="Repository root path")
    parser.add_argument("--slug", default="base", help="Target bounty slug (default: base)")
    parser.add_argument("--dry-run", action="store_true", help="Preview mode; do not write artifacts")
    parser.add_argument("--confirm", action="store_true", help="Authorize write and atomic artifact creation")
    parser.add_argument("--schemas-dir", help="Explicit path to schemas directory")

    args, unknown = parser.parse_known_args()
    if unknown:
        log_event("ERROR", "UNKNOWN_FLAG", f"Unknown argument(s): {' '.join(unknown)}", error_code="INVALID_ARGUMENTS")
        sys.stderr.write(f"Error: Unknown argument(s): {' '.join(unknown)}\n")
        return 4

    # Phase A — Parse and validate
    slug = args.slug.strip() if args.slug else ""
    if not slug:
        log_event("ERROR", "MISSING_SLUG", "Required argument --slug is empty", error_code="INVALID_ARGUMENTS")
        sys.stderr.write("Error: Required argument --slug is missing or empty.\n")
        return 4

    if not SLUG_PATTERN.match(slug) or ".." in slug or "/" in slug or "\\" in slug:
        log_event("ERROR", "INVALID_SLUG", f"Slug '{slug}' violates naming policy", slug=slug, error_code="INVALID_SLUG")
        sys.stderr.write(f"Error: Invalid slug '{slug}'. Must match ^[A-Za-z0-9][A-Za-z0-9_-]{{0,99}}$ without path traversal.\n")
        return 4

    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root()
    if not repo_root.exists() or not repo_root.is_dir():
        log_event("ERROR", "INVALID_REPO_ROOT", f"Repository root does not exist: {repo_root}", error_code="FILESYSTEM_FAILURE")
        sys.stderr.write(f"Error: Repository root does not exist: {repo_root}\n")
        return 2

    bounties_dir = repo_root / "bounties"
    bounty_dir = bounties_dir / slug
    scans_dir = bounty_dir / "scans"
    out_file = scans_dir / "overlap_analysis.json"

    # Symlink and containment validation
    if check_symlink_traversal(bounty_dir, bounties_dir):
        log_event("ERROR", "SYMLINK_BOUNTY_DIR", f"Bounty directory '{bounty_dir}' is a symlink or escapes boundary.", slug=slug, error_code="UNSAFE_OUTPUT_DIR")
        sys.stderr.write(f"Error: Bounty directory '{bounty_dir}' is a symlink or escapes repository boundary.\n")
        return 2

    if scans_dir.exists() and check_symlink_traversal(scans_dir, bounty_dir):
        log_event("ERROR", "SYMLINK_SCANS_DIR", f"Scans directory '{scans_dir}' is a symlink or escapes boundary.", slug=slug, error_code="UNSAFE_OUTPUT_DIR")
        sys.stderr.write(f"Error: Scans directory '{scans_dir}' is a symlink or escapes bounty boundary.\n")
        return 2

    if out_file.is_symlink():
        log_event("ERROR", "SYMLINK_OUTPUT_FILE", f"Output file '{out_file}' is a symlink.", slug=slug, error_code="UNSAFE_OUTPUT_DIR")
        sys.stderr.write(f"Error: Output file '{out_file}' is a symlink.\n")
        return 2

    if not bounty_dir.exists():
        log_event("ERROR", "MISSING_BOUNTY_DIR", f"Bounty directory does not exist: {bounty_dir}", slug=slug, error_code="FILESYSTEM_FAILURE")
        sys.stderr.write(f"Error: Bounty directory does not exist: {bounty_dir}\n")
        return 2

    # Cross-device check
    if bounty_dir.exists() and not check_device_boundary(repo_root, bounty_dir):
        log_event("ERROR", "CROSS_DEVICE_DETECTED", f"Bounty directory '{bounty_dir}' is on a different filesystem device.", slug=slug, error_code="FILESYSTEM_FAILURE")
        sys.stderr.write(f"Error: Bounty directory '{bounty_dir}' diverges from repository filesystem device.\n")
        return 2

    if scans_dir.exists() and not check_device_boundary(repo_root, scans_dir):
        log_event("ERROR", "CROSS_DEVICE_DETECTED", f"Output scans directory '{scans_dir}' is on a different filesystem device.", slug=slug, error_code="FILESYSTEM_FAILURE")
        sys.stderr.write(f"Error: Scans directory '{scans_dir}' diverges from repository filesystem device.\n")
        return 2

    script_dir = Path(__file__).resolve().parent
    schemas_dir = Path(args.schemas_dir).resolve() if args.schemas_dir else (script_dir / "schemas")
    schema_path = schemas_dir / "overlap_analysis.schema.json"

    is_confirmed = args.confirm
    is_dry_run = args.dry_run
    write_allowed = is_confirmed and not is_dry_run

    try:
        # Phase B — Inventory evidence
        commit_sha = get_git_commit(repo_root)

        candidates, c_inspected, c_unavail, c_tools = discover_candidate_findings(bounty_dir, repo_root)
        known_issues, k_inspected, k_unavail, known_issues_checked = discover_known_issues(bounty_dir, repo_root)

        all_sources_inspected = sorted(list(c_inspected | k_inspected))
        all_sources_unavailable = sorted(list(c_unavail | k_unavail))
        all_tools_used = sorted(list(c_tools))

        limitations: List[str] = []
        if not known_issues_checked:
            limitations.append(
                f"No known-issue corpus or prior disclosure records found for bounty slug '{slug}'; "
                "overlap check evaluated against empty corpus."
            )

        if not candidates:
            limitations.append(f"No candidate findings found in bounty workspace for slug '{slug}'.")

        # Phase C & D — Normalize candidate findings and compare against known issues
        analysis_summary, relationships = analyze_overlaps(candidates, known_issues, known_issues_checked)
        indeterminate_count = analysis_summary.get("indeterminate_count", 0)

        # Phase E & F — Produce the overlap report
        if not candidates and not known_issues_checked:
            status_str = "OVERLAP_CHECK_INCOMPLETE"
        elif not known_issues_checked or indeterminate_count > 0:
            status_str = "OVERLAP_CHECK_PARTIAL"
        elif candidates:
            status_str = "OVERLAP_CHECK_COMPLETE"
        else:
            status_str = "OVERLAP_CHECK_PARTIAL"

        now_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        report_payload = {
            "schema_version": "1.0",
            "slug": slug,
            "known_issues_checked": known_issues_checked,
            "timestamp": now_utc,
            "status": status_str,
            "analysis": analysis_summary,
            "evidence": {
                "sources_inspected": all_sources_inspected,
                "sources_unavailable": all_sources_unavailable,
                "tools_used": all_tools_used,
                "source_revision": commit_sha,
            },
            "limitations": limitations,
            "write": {
                "authorized": write_allowed,
                "written": False,
                "validated_after_write": False,
            },
        }
    except Exception as e:
        log_event(
            level="ERROR",
            event="ANALYSIS_FAILURE",
            message=f"Overlap analysis execution failed: {e}",
            slug=slug,
            error_code="ANALYSIS_FAILURE",
        )
        sys.stderr.write(f"Error: Overlap analysis execution failed: {e}\n")
        return 1

    # Phase G — Validate and commit or preview
    if not write_allowed:
        log_event(
            level="INFO",
            event="PREVIEW_COMPLETE",
            message=f"Preview completed for '{slug}': candidates={len(candidates)}, known_issues={len(known_issues)}. No files written.",
            slug=slug,
            processed_count=len(candidates),
        )
        sys.stdout.write(f"[DRY-RUN] Will annotate overlaps into {out_file}\n")
        sys.stdout.flush()
        return 0

    # Confirmed execution: update write status and persist
    report_payload["write"]["written"] = True
    report_payload["write"]["validated_after_write"] = True

    try:
        content_str = json.dumps(report_payload, ensure_ascii=False, indent=2) + "\n"
        durable_atomic_write(out_file, content_str, schema_path)
    except ValueError as ve:
        log_event(
            level="ERROR",
            event="VALIDATION_FAILURE",
            message=f"Post-write schema validation failed: {ve}",
            slug=slug,
            error_code="SCHEMA_VIOLATION",
        )
        sys.stderr.write(f"Error: Post-write schema validation failed: {ve}\n")
        return 1
    except (OSError, IOError, PermissionError) as fe:
        log_event(
            level="ERROR",
            event="WRITE_FAILURE",
            message=f"Filesystem error during write: {fe}",
            slug=slug,
            error_code="FILESYSTEM_FAILURE",
        )
        sys.stderr.write(f"Error: Filesystem error during write: {fe}\n")
        return 2
    except Exception as ge:
        log_event(
            level="ERROR",
            event="UNKNOWN_FAILURE",
            message=f"Unexpected error writing artifact: {ge}",
            slug=slug,
            error_code="ANALYSIS_FAILURE",
        )
        sys.stderr.write(f"Error: Unexpected error writing artifact: {ge}\n")
        return 1

    log_event(
        level="INFO",
        event="AUDIT_COMMITTED",
        message=f"Overlap analysis artifact successfully saved to {out_file}",
        slug=slug,
        processed_count=len(candidates),
    )

    sys.stdout.write(f"[OK] Overlap analysis saved to {out_file}\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
