#!/usr/bin/env python3
"""bounty_cli.py - Cantina Bug Bounty Pipeline Automation CLI.

Zero-dependency Python 3 CLI adhering to workflow-skill-creator Rule 3 and GEMINI.md v4.0.
Subcommands:
  - scope-lock: Normalizes line endings, hashes the full marker-delimited scope block, writes snapshot.
  - scope-verify: Fail-closed verification of scope integrity.
  - envelope-check: Validates agent response envelopes against CONTRACT.md.
  - fact-record: Enforces provenance tags and auto-increments FACT-### entries.
  - gate-check: Reports limited syntax checks and blockers for six manual readiness gates.

Run via: python .agents/skills/cantina-bug-bounty/scripts/bounty_cli.py <subcommand> [options]
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import sys
from pathlib import Path

REQUIRED_ENVELOPE_FIELDS = [
    "agent",
    "stage",
    "status",
    "thought",
    "plan",
    "evidence",
    "result_files",
    "stop_reason",
]
VALID_ENVELOPE_STATUSES = {
    "ok",
    "fail",
    "tool_missing",
    "stopped",
    "skipped",
    "no_tests",
}
VALID_EVIDENCE_TYPES = {
    "SRC",
    "LOCAL",
    "TOOL",
    "POC",
    "WEB",
    "USER",
    "ASSUMPTION",
    "UNKNOWN",
}
HEX40_RE = re.compile(r"^[0-9a-f]{40}$", re.I)
HEX64_RE = re.compile(r"^[0-9a-f]{64}$", re.I)
SRC_PATH_RE = re.compile(r"^[^:\s]+:\d+$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

SECRET_PATTERNS = [
    re.compile(r"alch_[A-Za-z0-9]{8,}"),
    re.compile(r"rnd_[A-Za-z0-9]{8,}"),
    re.compile(
        r"https?://[^\s\"']*(alchemy|infura|quiknode|drpc)[^\s\"']*/[A-Za-z0-9_\-]{16,}",
        re.I,
    ),
    re.compile(r"\b0x[0-9a-fA-F]{64}\b"),  # 64-hex private key candidate
]

PROVENANCE_TAG_RE = re.compile(
    r"\[(SRC|LOCAL|TOOL|POC|WEB|USER|ASSUMPTION|UNKNOWN)(?::[^\]]+)?\]"
)


def write_json_output(output_path: Path, data: dict):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Success! Output written to: {output_path}")


def extract_normalized_scope(scope_file: Path) -> tuple[bytes, str]:
    if not scope_file.exists():
        raise FileNotFoundError(f"Scope file not found: {scope_file}")

    raw_bytes = scope_file.read_bytes()
    # Normalize both CRLF and bare CR, then hash the complete marker-delimited block.
    normalized = raw_bytes.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    start_marker = b"<!-- SCOPE START -->"
    end_marker = b"<!-- SCOPE END -->"
    lines = normalized.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.rstrip(b"\n") == start_marker]
    ends = [i for i, line in enumerate(lines) if line.rstrip(b"\n") == end_marker]
    if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
        raise ValueError(
            "Scope must contain exactly one SCOPE START line followed by one SCOPE END line."
        )
    scope_slice = b"".join(lines[starts[0] : ends[0] + 1])
    if not scope_slice.endswith(b"\n"):
        scope_slice += b"\n"
    digest = hashlib.sha256(scope_slice).hexdigest()
    return scope_slice, digest


# ----------------------------------------------------------------------
# Subcommand: scope-lock
# ----------------------------------------------------------------------
def cmd_scope_lock(args):
    scope_file = Path(args.scope_file).resolve()
    snapshot_file = Path(args.snapshot_file).resolve()
    output_file = Path(args.output).resolve()

    try:
        _, digest = extract_normalized_scope(scope_file)
        snapshot_file.parent.mkdir(parents=True, exist_ok=True)
        snapshot_file.write_text(digest + "\n", encoding="utf-8")

        result = {
            "status": "OK",
            "action": "scope-lock",
            "scope_file": str(scope_file),
            "snapshot_file": str(snapshot_file),
            "sha256_lf": digest,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        write_json_output(output_file, result)
        sys.exit(0)
    except Exception as e:
        err_res = {
            "status": "ERROR",
            "action": "scope-lock",
            "error": str(e),
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        write_json_output(output_file, err_res)
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


# ----------------------------------------------------------------------
# Subcommand: scope-verify
# ----------------------------------------------------------------------
def cmd_scope_verify(args):
    scope_file = Path(args.scope_file).resolve()
    snapshot_file = Path(args.snapshot_file).resolve()
    output_file = Path(args.output).resolve()

    if not snapshot_file.exists():
        err_res = {
            "status": "ERROR",
            "action": "scope-verify",
            "error": f"Snapshot file not found: {snapshot_file}",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        write_json_output(output_file, err_res)
        print(f"FAIL: Snapshot missing: {snapshot_file}", file=sys.stderr)
        sys.exit(1)

    expected = snapshot_file.read_text(encoding="utf-8").strip()

    try:
        _, actual = extract_normalized_scope(scope_file)
    except Exception as e:
        err_res = {
            "status": "ERROR",
            "action": "scope-verify",
            "error": str(e),
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        write_json_output(output_file, err_res)
        print(f"FAIL: {e}", file=sys.stderr)
        sys.exit(1)

    matched = expected.lower() == actual.lower()
    result = {
        "status": "OK" if matched else "SCOPE_CHANGED",
        "action": "scope-verify",
        "matched": matched,
        "expected_sha256": expected,
        "actual_sha256": actual,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    write_json_output(output_file, result)

    if matched:
        print("Scope verification PASSED (LF-normalized SHA-256 match).")
        sys.exit(0)
    else:
        print(
            f"SCOPE CHANGED! Expected {expected}, got {actual}.",
            file=sys.stderr,
        )
        sys.exit(1)


# ----------------------------------------------------------------------
# Subcommand: envelope-check
# ----------------------------------------------------------------------
def cmd_envelope_check(args):
    envelope_file = Path(args.envelope).resolve()
    contract_file = (
        Path(args.contract_file).resolve()
        if args.contract_file
        else next(
            (
                parent / "global" / "agents" / "CONTRACT.md"
                for parent in Path(__file__).resolve().parents
                if (parent / "global" / "agents" / "CONTRACT.md").is_file()
            ),
            Path("global/agents/CONTRACT.md").resolve(),
        )
    )
    output_file = Path(args.output).resolve()

    errors = []

    if not envelope_file.exists():
        errors.append(f"Envelope file not found: {envelope_file}")
        write_json_output(
            output_file, {"status": "ERROR", "errors": errors}
        )
        sys.exit(1)

    raw_text = envelope_file.read_text(encoding="utf-8")

    # 1. Secret check
    for pattern in SECRET_PATTERNS:
        if pattern.search(raw_text):
            errors.append(
                "SECRET_EXPOSED: secret-like string found in envelope payload"
            )
            break

    # 2. JSON parsing
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON: {e}")
        write_json_output(
            output_file, {"status": "ERROR", "errors": errors}
        )
        sys.exit(1)

    # 3. Required top-level fields
    for field in REQUIRED_ENVELOPE_FIELDS:
        if field not in data:
            errors.append(f"Missing required field: '{field}'")

    if data.get("status") not in VALID_ENVELOPE_STATUSES:
        errors.append(
            f"Invalid status: '{data.get('status')}'. Must be one of {sorted(VALID_ENVELOPE_STATUSES)}"
        )

    # 4. Evidence validations
    evidence_list = data.get("evidence", [])
    if not isinstance(evidence_list, list):
        errors.append("'evidence' must be a list")
    else:
        for idx, item in enumerate(evidence_list):
            if not isinstance(item, dict):
                errors.append(f"evidence[{idx}] must be an object")
                continue
            etype = item.get("type")
            if etype not in VALID_EVIDENCE_TYPES:
                errors.append(
                    f"evidence[{idx}] unknown type: '{etype}'. Valid: {sorted(VALID_EVIDENCE_TYPES)}"
                )
            if etype == "SRC":
                if not (
                    isinstance(item.get("path"), str)
                    and SRC_PATH_RE.match(item["path"])
                ):
                    errors.append(
                        f"evidence[{idx}] SRC path must be 'path:line'"
                    )
                if not (
                    isinstance(item.get("commit"), str)
                    and HEX40_RE.match(item["commit"])
                ):
                    errors.append(
                        f"evidence[{idx}] SRC commit must be 40-hex commit"
                    )
            elif etype in ("TOOL", "POC"):
                if not (
                    isinstance(item.get("sha256"), str)
                    and HEX64_RE.match(item["sha256"])
                ):
                    errors.append(
                        f"evidence[{idx}] {etype} needs a 64-hex sha256"
                    )

    is_valid = len(errors) == 0
    res = {
        "status": "OK" if is_valid else "INVALID",
        "action": "envelope-check",
        "envelope_file": str(envelope_file),
        "contract_file": str(contract_file),
        "valid": is_valid,
        "errors": errors,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    write_json_output(output_file, res)

    if is_valid:
        print("Envelope validation PASSED.")
        sys.exit(0)
    else:
        print(f"Envelope validation FAILED with {len(errors)} error(s).", file=sys.stderr)
        sys.exit(1)


# ----------------------------------------------------------------------
# Subcommand: fact-record
# ----------------------------------------------------------------------
def cmd_fact_record(args):
    facts_file = Path(args.facts_file).resolve()
    output_file = Path(args.output).resolve()
    fact_text = args.fact.strip()
    tag = args.tag.strip()
    status = args.status.strip() if args.status else "CURRENT"
    date_str = datetime.date.today().isoformat()

    if not PROVENANCE_TAG_RE.search(tag):
        print(
            f"ERROR: Invalid provenance tag '{tag}'. Must match [TYPE: ...] format.",
            file=sys.stderr,
        )
        sys.exit(1)

    facts_file.parent.mkdir(parents=True, exist_ok=True)
    existing_content = facts_file.read_text(encoding="utf-8") if facts_file.exists() else ""

    # Find highest FACT-###
    existing_ids = [int(m) for m in re.findall(r"FACT-(\d{3})", existing_content)]
    next_id = max(existing_ids, default=0) + 1
    fact_id_str = f"FACT-{next_id:03d}"

    new_line = f"- {fact_id_str}: {fact_text} {tag} Status: {status}, captured {date_str}.\n"

    with open(facts_file, "a", encoding="utf-8") as f:
        f.write(new_line)

    res = {
        "status": "OK",
        "action": "fact-record",
        "fact_id": fact_id_str,
        "fact_line": new_line.strip(),
        "facts_file": str(facts_file),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    write_json_output(output_file, res)
    print(f"Recorded {fact_id_str} in {facts_file}")
    sys.exit(0)


# ----------------------------------------------------------------------
# Subcommand: gate-check
# ----------------------------------------------------------------------
def cmd_gate_check(args):
    finding_file = Path(args.finding).resolve()
    bounty_root = Path(args.bounty_root).resolve()
    output_file = Path(args.output).resolve()

    if not finding_file.exists():
        err = {"status": "ERROR", "error": f"Finding file not found: {finding_file}"}
        write_json_output(output_file, err)
        sys.exit(1)

    content = finding_file.read_text(encoding="utf-8")
    lines = content.splitlines()

    gates = {
        "gate_1_source": {"pass": False, "detail": ""},
        "gate_2_reproduction": {"pass": False, "detail": ""},
        "gate_3_scope": {"pass": False, "detail": ""},
        "gate_4_duplicate": {"pass": False, "detail": ""},
        "gate_5_severity": {"pass": False, "detail": ""},
        "gate_6_provenance": {"pass": False, "detail": ""},
    }

    # This utility has no source checkout/commit mapping, so citation syntax alone
    # cannot establish that the cited line exists or supports the claim.
    src_tags = re.findall(r"\[SRC:\s*([^:\s]+):(\d+)\s*@([0-9a-fA-F]{7,40})\]", content)
    gates["gate_1_source"]["detail"] = (
        f"Found {len(src_tags)} citation(s), but source lines and commits require manual verification."
        if src_tags else "No valid [SRC: path:line @commit] citation found."
    )

    # A PASS tag and configured URLs are not evidence that either provider ran.
    poc_match = re.search(r"\[POC:\s*(PASS|FAIL)[^\]]*\]", content)
    gates["gate_2_reproduction"]["detail"] = (
        f"Finding cites POC {poc_match.group(1)}, but this command does not execute or verify provider logs."
        if poc_match else "No PoC result cited; reproduction requires manual verification."
    )

    # Presence of a scope file does not prove that the finding's target is in scope.
    scope_path = bounty_root / "scope.md"
    gates["gate_3_scope"]["detail"] = (
        "scope.md exists, but this command does not compare the finding target with its in-scope assets."
        if scope_path.is_file() else "scope.md not found in bounty root."
    )

    # A ledger file must exist, and its contents still need human review.
    known_ledger = bounty_root / "logs" / "known_issues.jsonl"
    gates["gate_4_duplicate"]["detail"] = (
        f"Review record exists at {known_ledger.relative_to(bounty_root)}, but this command cannot validate its coverage or conclusion."
        if known_ledger.is_file() else "No known-issues review record found."
    )

    # A label is not a severity calculation against the program matrix.
    gates["gate_5_severity"]["detail"] = (
        "Severity label is present; impact and likelihood have not been checked against the program matrix."
        if "Severity (program scale):" in content
        else "Missing 'Severity (program scale):' header."
    )

    # Gate 6: Provenance tag audit on substantive claim lines
    in_substantive = False
    substantive_sections = 0
    untagged_lines = []
    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("## Summary") or stripped.startswith("## Root cause") or stripped.startswith("## Impact"):
            in_substantive = True
            substantive_sections += 1
            continue
        elif stripped.startswith("## ") or stripped.startswith("# "):
            in_substantive = False

        if in_substantive and stripped and not stripped.startswith("- **") and not stripped.startswith("```"):
            if not PROVENANCE_TAG_RE.search(stripped):
                untagged_lines.append((line_no, stripped))

    if untagged_lines:
        gates["gate_6_provenance"]["pass"] = False
        gates["gate_6_provenance"]["detail"] = (
            f"Found {len(untagged_lines)} untagged claim line(s), e.g. line {untagged_lines[0][0]}."
        )
    elif not substantive_sections:
        gates["gate_6_provenance"]["pass"] = False
        gates["gate_6_provenance"]["detail"] = (
            "No Summary, Root cause, or Impact sections were found; no claim lines were audited."
        )
    else:
        gates["gate_6_provenance"]["pass"] = True
        gates["gate_6_provenance"]["detail"] = (
            "Audited claim lines in Summary, Root cause, and Impact sections for tags. "
            "Other fields and tag accuracy are not checked."
        )

    passed_count = sum(1 for g in gates.values() if g["pass"])
    pass_rate = f"{passed_count}/6"

    res = {
        "status": "READY" if passed_count == 6 else "NOT_READY",
        "action": "gate-check",
        "finding": str(finding_file),
        "pass_rate": pass_rate,
        "gates": gates,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    write_json_output(output_file, res)
    print(f"Readiness check complete: {pass_rate} gates passed.")
    sys.exit(0 if passed_count == 6 else 1)


# ----------------------------------------------------------------------
# CLI Argument Parser Setup
# ----------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Cantina Bug Bounty Pipeline Automation CLI."
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # scope-lock
    p_lock = subparsers.add_parser("scope-lock", help="Hash scope and write snapshot.")
    p_lock.add_argument("--scope-file", required=True, help="Path to scope.md")
    p_lock.add_argument(
        "--snapshot-file", required=True, help="Path to snapshots/scope.sha256"
    )
    p_lock.add_argument("--output", required=True, help="Path to output JSON")
    p_lock.set_defaults(func=cmd_scope_lock)

    # scope-verify
    p_ver = subparsers.add_parser(
        "scope-verify", help="Verify scope integrity against snapshot."
    )
    p_ver.add_argument("--scope-file", required=True, help="Path to scope.md")
    p_ver.add_argument(
        "--snapshot-file", required=True, help="Path to snapshots/scope.sha256"
    )
    p_ver.add_argument("--output", required=True, help="Path to output JSON")
    p_ver.set_defaults(func=cmd_scope_verify)

    # envelope-check
    p_env = subparsers.add_parser(
        "envelope-check", help="Validate agent envelope against CONTRACT.md."
    )
    p_env.add_argument("--envelope", required=True, help="Path to envelope JSON")
    p_env.add_argument(
        "--contract-file", required=False, help="Path to CONTRACT.md"
    )
    p_env.add_argument("--output", required=True, help="Path to output JSON")
    p_env.set_defaults(func=cmd_envelope_check)

    # fact-record
    p_fact = subparsers.add_parser(
        "fact-record", help="Append provenance-tagged fact to facts.md."
    )
    p_fact.add_argument("--facts-file", required=True, help="Path to facts.md")
    p_fact.add_argument("--fact", required=True, help="Fact description text")
    p_fact.add_argument("--tag", required=True, help="Provenance tag [TYPE: ...]")
    p_fact.add_argument(
        "--status", default="CURRENT", help="Fact status (default: CURRENT)"
    )
    p_fact.add_argument("--output", required=True, help="Path to output JSON")
    p_fact.set_defaults(func=cmd_fact_record)

    # gate-check
    p_gate = subparsers.add_parser(
        "gate-check", help="Evaluate 6 readiness gates for finding file."
    )
    p_gate.add_argument("--finding", required=True, help="Path to findings/F-###.md")
    p_gate.add_argument("--bounty-root", required=True, help="Path to bounty directory")
    p_gate.add_argument("--output", required=True, help="Path to output JSON")
    p_gate.set_defaults(func=cmd_gate_check)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
