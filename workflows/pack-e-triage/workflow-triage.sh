#!/usr/bin/env bash
# Pack E Workflow: Vulnerability Triage
# Meta Persona: Cantina Vulnerability Triage & Security Research Engineer (CANTINA-SEC-TRIAGE-001)
set -euo pipefail

DRY_RUN=false
CONFIRM=false
SLUG="base"
REPO_ROOT="/home/nova/projects/cantina"

usage() {
  cat <<'EOF' >&2
Usage: workflow-triage.sh [--slug SLUG] [--dry-run] [--confirm] [-h|--help]

Options:
  --slug SLUG    Target bounty slug (default: base, pattern: ^[A-Za-z0-9][A-Za-z0-9_-]*$)
  --dry-run      Preview triage destination without writing (default behavior if unconfirmed)
  --confirm      Authorize triage summary creation and durable write
  -h, --help     Show this help message
EOF
}

# Phase A — Initialize & Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --confirm)
      CONFIRM=true
      shift
      ;;
    --slug)
      if [[ $# -lt 2 || "$2" == --* ]]; then
        echo "[ERROR] init: Missing value for --slug" >&2
        usage
        exit 1
      fi
      SLUG="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[ERROR] init: Malformed or unsupported option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

# Argument validation: slug policy & path traversal prevention
SLUG_REGEX='^[A-Za-z0-9][A-Za-z0-9_-]*$'
if [[ ! "$SLUG" =~ $SLUG_REGEX ]]; then
  echo "[ERROR] init: Invalid slug format '$SLUG'. Must match $SLUG_REGEX without path traversal." >&2
  exit 1
fi

if [[ "$SLUG" == *"/"* || "$SLUG" == *"\\"* || "$SLUG" == *".."* ]]; then
  echo "[ERROR] init: Path separators or traversal components prohibited in slug." >&2
  exit 1
fi

BOUNTY_DIR="$REPO_ROOT/bounties/$SLUG"
SCANS_DIR="$BOUNTY_DIR/scans"
OUT_FILE="$SCANS_DIR/triage_summary.json"

echo "=== [Pack E] Workflow: Vulnerability Triage ($SLUG) ==="

# Authorization Invariant:
# Write allowed only when DRY_RUN=false AND CONFIRM=true.
# If --dry-run is specified, it overrides --confirm.
if [[ "$DRY_RUN" == true || "$CONFIRM" == false ]]; then
  echo "[DRY-RUN] Will triage candidate findings into $OUT_FILE"
  exit 0
fi

# Phase B & F — Prepare destination & Path Containment Assertion
mkdir -p "$SCANS_DIR"

RESOLVED_SCANS_DIR="$(cd "$SCANS_DIR" && pwd -P)"
RESOLVED_REPO_ROOT="$(cd "$REPO_ROOT" && pwd -P)"
if [[ "$RESOLVED_SCANS_DIR" != "$RESOLVED_REPO_ROOT"/bounties/* ]]; then
  echo "[ERROR] persist: Destination path escaped workspace boundary." >&2
  exit 1
fi

TEMP_FILE="$(mktemp "$SCANS_DIR/triage_summary.tmp.XXXXXX")"
trap 'rm -f "$TEMP_FILE"' EXIT INT TERM

# Execute Python serializer for candidate discovery, orthogonal scoring, dynamic counters, and atomic serialization
python3 - "$REPO_ROOT" "$SLUG" "$TEMP_FILE" "$OUT_FILE" <<'PYEOF'
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

repo_root_arg = sys.argv[1]
slug_arg = sys.argv[2]
temp_file_arg = sys.argv[3]
out_file_arg = sys.argv[4]

repo_root = Path(repo_root_arg).resolve()
bounty_dir = repo_root / "bounties" / slug_arg
scans_dir = bounty_dir / "scans"
findings_dir = bounty_dir / "findings"

# Source revision discovery
git_rev = None
try:
    res = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if res.returncode == 0:
        git_rev = res.stdout.strip()
except Exception:
    git_rev = None

candidates = []
input_artifacts = []
tools_executed = []
tools_skipped = ["certoraRun", "kontrol"]  # Kept optional pending environment verification
limitations = []
errors = []

# Discover candidate scan artifacts
candidate_scan_names = [
    "findings_normalized.json",
    "slither.json",
    "aderyn.json",
    "semgrep.json",
    "overlap_analysis.json",
    "hallucination_audit.json",
]

for name in candidate_scan_names:
    p = scans_dir / name
    if p.is_file():
        rel = str(p.relative_to(repo_root))
        input_artifacts.append(rel)

# Parse normalized findings if present
norm_file = scans_dir / "findings_normalized.json"
if norm_file.is_file():
    tools_executed.append("findings-normalization-oracle")
    try:
        with open(norm_file, "r", encoding="utf-8") as f:
            norm_data = json.load(f)
            raw_findings = norm_data.get("normalized_findings", [])
            for idx, raw in enumerate(raw_findings, start=1):
                cid = raw.get("id") or f"candidate-{idx:03d}"
                title = raw.get("title") or raw.get("name") or f"Finding {cid}"
                disp = raw.get("disposition") or "NEEDS_INVESTIGATION"
                if disp not in [
                    "VALIDATED",
                    "LIKELY_VALID",
                    "NEEDS_INVESTIGATION",
                    "FALSE_POSITIVE",
                    "DUPLICATE",
                    "OUT_OF_SCOPE",
                    "INFORMATIONAL",
                    "UNVERIFIED",
                ]:
                    disp = "NEEDS_INVESTIGATION"

                sev = raw.get("severity")
                if isinstance(sev, str):
                    sev = sev.upper()
                    if sev not in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"]:
                        sev = None
                else:
                    sev = None

                conf = raw.get("confidence")
                if isinstance(conf, str):
                    conf = conf.upper()
                    if conf not in ["HIGH", "MEDIUM", "LOW", "UNVERIFIED"]:
                        conf = "LOW"
                else:
                    conf = "LOW"

                components = raw.get("affected_components") or []
                if not isinstance(components, list):
                    components = [str(components)]

                evidence = raw.get("evidence") or []
                if not isinstance(evidence, list):
                    evidence = [evidence]

                candidate_record = {
                    "id": str(cid),
                    "title": str(title),
                    "disposition": disp,
                    "severity": sev,
                    "confidence": conf,
                    "root_cause": raw.get("root_cause"),
                    "affected_components": components,
                    "evidence": evidence,
                    "exploitability": {
                        "prerequisites": raw.get("prerequisites", []) if isinstance(raw.get("prerequisites"), list) else [],
                        "attacker_capabilities": raw.get("attacker_capabilities", []) if isinstance(raw.get("attacker_capabilities"), list) else [],
                        "reproduction_status": raw.get("reproduction_status", "NOT_ATTEMPTED") if raw.get("reproduction_status") in ["NOT_ATTEMPTED", "REPRODUCED", "FAILED_REPRODUCTION", "THEORETICAL"] else "NOT_ATTEMPTED",
                    },
                    "impact": {
                        "description": str(raw.get("impact")) if raw.get("impact") and isinstance(raw.get("impact"), str) else None,
                        "demonstrated": bool(raw.get("impact_demonstrated", False)),
                    },
                    "duplicate_of": raw.get("duplicate_of"),
                    "scope_status": raw.get("scope_status", "UNVERIFIED") if raw.get("scope_status") in ["IN_SCOPE", "OUT_OF_SCOPE", "UNVERIFIED"] else "UNVERIFIED",
                    "remediation": raw.get("remediation"),
                    "limitations": raw.get("limitations", []) if isinstance(raw.get("limitations"), list) else [],
                }
                candidates.append(candidate_record)
    except Exception as e:
        err_msg = f"Failed to parse findings_normalized.json: {e}"
        limitations.append(err_msg)
        errors.append(err_msg)

# Determine truthful status semantics based on evidence
if not candidates:
    status = "TRIAGE_INCOMPLETE"
    limitations.append(f"No candidate findings available for assessment in bounties/{slug_arg}/scans/")
else:
    # If any candidate remains needs_investigation or unverified, mark complete with limitations
    all_resolved = all(c["disposition"] in ["VALIDATED", "FALSE_POSITIVE", "DUPLICATE", "OUT_OF_SCOPE", "INFORMATIONAL"] for c in candidates)
    if all_resolved:
        status = "TRIAGE_COMPLETE"
    else:
        status = "TRIAGE_COMPLETE_WITH_LIMITATIONS"
        limitations.append("Contains candidate findings requiring further exploitability reproduction or scope verification.")

# Compute dynamic summary counters
summary = {
    "total_candidates": len(candidates),
    "validated": sum(1 for c in candidates if c["disposition"] == "VALIDATED"),
    "likely_valid": sum(1 for c in candidates if c["disposition"] == "LIKELY_VALID"),
    "needs_investigation": sum(1 for c in candidates if c["disposition"] == "NEEDS_INVESTIGATION"),
    "false_positive": sum(1 for c in candidates if c["disposition"] == "FALSE_POSITIVE"),
    "duplicates": sum(1 for c in candidates if c["disposition"] == "DUPLICATE"),
    "out_of_scope": sum(1 for c in candidates if c["disposition"] == "OUT_OF_SCOPE"),
    "informational": sum(1 for c in candidates if c["disposition"] == "INFORMATIONAL"),
    "unverified": sum(1 for c in candidates if c["disposition"] == "UNVERIFIED"),
}

output_doc = {
    "schema_version": "1.0",
    "slug": slug_arg,
    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "status": status,
    "summary": summary,
    "environment": {
        "repository_root": str(repo_root),
        "source_revision": git_rev,
        "tool_registry_baseline": "2026-10-23",
        "tools_executed": tools_executed,
        "tools_skipped": tools_skipped,
        "limitations": limitations,
    },
    "candidates": candidates,
    "errors": errors,
    "provenance": {
        "input_artifacts": input_artifacts,
        "output_artifact": f"bounties/{slug_arg}/scans/triage_summary.json",
    },
}

with open(temp_file_arg, "w", encoding="utf-8") as f:
    json.dump(output_doc, f, indent=2)

PYEOF

# Phase G — Validate generated JSON artifact against schema
VALIDATOR="$REPO_ROOT/workflows/pack-e-triage/validate_schemas.py"
if [[ -f "$VALIDATOR" ]]; then
  if ! python3 "$VALIDATOR" --triage "$TEMP_FILE" >/dev/null 2>&1; then
    rm -f "$TEMP_FILE"
    echo "[ERROR] verify: Schema validation failed on generated triage artifact." >&2
    exit 1
  fi
else
  # Inline fallback validation
  if ! python3 -c "import json, sys; data = json.load(open(sys.argv[1])); assert data['slug'] == sys.argv[2]; assert isinstance(data['summary'], dict); assert isinstance(data['candidates'], list)" "$TEMP_FILE" "$SLUG" 2>/dev/null; then
    rm -f "$TEMP_FILE"
    echo "[ERROR] verify: Fallback JSON validation failed for generated artifact." >&2
    exit 1
  fi
fi

# Move atomically into destination
mv "$TEMP_FILE" "$OUT_FILE"
trap - EXIT INT TERM

echo "[OK] Triage summary saved to $OUT_FILE"
