#!/usr/bin/env bash
# workflow-pathway-scout.sh — Pack A Pathway Scout Orchestrator
# Version: 2.0.0
# Persona: PACK-A-PATHWAY-SCOUT-001
# Evidence-driven smart-contract attack-surface and execution-pathway reconnaissance agent.
# WRITE_ALLOWED = CONFIRM && !DRY_RUN
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd -P)}"
SCHEMA_PATH="$SCRIPT_DIR/schemas/pathways.schema.json"
VALIDATOR="$REPO_ROOT/workflows/pack-e-triage/validate_schemas.py"

# --- Defaults ---
DRY_RUN=false
CONFIRM=false
SLUG="base"

usage() {
  cat >&2 <<EOF
Usage: $(basename "$0") [--dry-run] [--confirm] [--slug SLUG] [-h|--help]

Options:
  --dry-run       Plan operations without writing artifacts (default behaviour when --confirm absent)
  --confirm       Authorize artifact writes for this run
  --slug SLUG     Bounty slug under bounties/ (pattern: ^[A-Za-z0-9][A-Za-z0-9_-]*$)
  -h, --help      Show this help and exit 0

Exit codes:
  0  Success (including dry-run plan)
  1  Operational or artifact-validation failure
  2  Invalid command-line arguments
  3  Blocked — missing prerequisites or unresolved scope
  4  Partial — reconnaissance ran but coverage criteria not met
EOF
  exit "${1:-0}"
}

# --- Argument parsing ---
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)   DRY_RUN=true;  shift ;;
    --confirm)   CONFIRM=true;  shift ;;
    --slug)
      if [[ $# -lt 2 || -z "${2:-}" ]]; then
        echo "Error: --slug requires a non-empty value" >&2
        usage 2
      fi
      SLUG="$2"; shift 2 ;;
    -h|--help)   usage 0 ;;
    --*)
      echo "Error: Unknown argument: $1" >&2
      usage 2 ;;
    *)
      echo "Error: Unexpected positional argument: $1" >&2
      usage 2 ;;
  esac
done

# --- Slug validation ---
if [[ -z "$SLUG" ]]; then
  echo "Error: --slug value must not be empty" >&2
  usage 2
fi
if [[ "$SLUG" == /* ]]; then
  echo "Error: --slug must not be an absolute path" >&2
  usage 2
fi
if [[ "$SLUG" =~ \.\. || "$SLUG" =~ / ]]; then
  echo "Error: --slug must not contain path traversal or slashes" >&2
  usage 2
fi
if ! [[ "$SLUG" =~ ^[A-Za-z0-9][A-Za-z0-9_-]*$ ]]; then
  echo "Error: --slug contains invalid characters. Pattern: ^[A-Za-z0-9][A-Za-z0-9_-]*$" >&2
  usage 2
fi

# --- Path resolution ---
REPO_ROOT_REAL="$(realpath -e "$REPO_ROOT")"
BOUNTIES_ROOT="$REPO_ROOT_REAL/bounties"
BOUNTY_DIR="$BOUNTIES_ROOT/$SLUG"
SCANS_DIR="$BOUNTY_DIR/scans"
PATHWAY_OUT="$SCANS_DIR/pathways.json"

echo "=== [Pack A] Pathway Scout v2.0.0 — PACK-A-PATHWAY-SCOUT-001 ==="
echo "  Slug:           $SLUG"
echo "  Repository:     $REPO_ROOT_REAL"
echo "  Target artifact: $PATHWAY_OUT"

# --- Write permission ---
WRITE_ALLOWED=false
if [[ "$CONFIRM" == true && "$DRY_RUN" == false ]]; then
  WRITE_ALLOWED=true
fi

# --- Dry-run plan ---
if [[ "$WRITE_ALLOWED" == false ]]; then
  echo ""
  echo "[DRY-RUN] Planned operations:"
  echo "  1. Validate slug and resolve paths"
  echo "  2. Inspect Git worktree state (read-only)"
  echo "  3. Discover scope documentation in bounties/$SLUG/"
  echo "  4. Enumerate source files (.sol, .rs, .ts, .js)"
  echo "  5. Classify entrypoints and construct pathway graph"
  echo "  6. Run available static analysis tools"
  echo "  7. Write pathways.json to: $PATHWAY_OUT"
  echo "  8. Validate artifact against: $SCHEMA_PATH"
  echo ""
  echo "[DRY-RUN] No files written. Re-run with --confirm (without --dry-run) to execute."
  exit 0
fi

# --- Safety checks for write mode ---
# Reject symlink at bounty dir
if [[ -L "$BOUNTY_DIR" ]]; then
  echo "Error: Bounty directory is a symlink. Refusing to write." >&2
  exit 1
fi
if [[ -L "$SCANS_DIR" ]]; then
  echo "Error: Scans directory is a symlink. Refusing to write." >&2
  exit 1
fi
# Refuse to overwrite existing artifact
if [[ -f "$PATHWAY_OUT" ]]; then
  echo "Error: Artifact already exists at $PATHWAY_OUT — will not overwrite without explicit approval." >&2
  exit 1
fi
# Containment: ensure BOUNTY_DIR is under BOUNTIES_ROOT
BOUNTY_DIR_REAL="$(realpath -m "$BOUNTY_DIR")"
if [[ "$BOUNTY_DIR_REAL" != "$BOUNTIES_ROOT"/* ]]; then
  echo "Error: Resolved bounty path escapes bounties root (path containment violation)." >&2
  exit 1
fi

mkdir -p "$SCANS_DIR"

# --- Reconnaissance engine ---
TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
GIT_COMMIT="$(git -C "$REPO_ROOT_REAL" rev-parse HEAD 2>/dev/null || echo null)"
GIT_CLEAN="$(git -C "$REPO_ROOT_REAL" status --porcelain 2>/dev/null | wc -l)"
WORKTREE_CLEAN="true"
if [[ "$GIT_CLEAN" -gt 0 ]]; then WORKTREE_CLEAN="false"; fi

TMPFILE="$(mktemp "$SCANS_DIR/pathways.XXXXXX.json")"
trap 'rm -f "$TMPFILE"' EXIT

python3 - <<PYEOF
import json, os, sys
from pathlib import Path
from datetime import datetime, timezone

bounty_dir = Path("$BOUNTY_DIR_REAL")
repo_root  = Path("$REPO_ROOT_REAL")
slug       = "$SLUG"
timestamp  = "$TIMESTAMP"
git_commit = "$GIT_COMMIT"
worktree_clean_str = "$WORKTREE_CLEAN"
tmpfile    = "$TMPFILE"

worktree_clean = worktree_clean_str.lower() == "true"
git_commit_val = None if git_commit == "null" else git_commit

# Phase B — Scope discovery
scope_patterns = ["README.md","scope.md","scope.json","SCOPE.md","bounty.json",".scope"]
scope_files_found = []
for pat in scope_patterns:
    candidate = bounty_dir / pat
    if candidate.is_file():
        scope_files_found.append(str(candidate.relative_to(repo_root)))

scope_status = "defined" if scope_files_found else "missing"

# Phase C — Source discovery
source_extensions = {".sol", ".rs", ".ts", ".js", ".vy"}
source_files = []
contracts    = []
programs     = []
if bounty_dir.exists():
    for root, dirs, files in os.walk(str(bounty_dir)):
        # Prune build/vendored dirs
        dirs[:] = [d for d in dirs if d not in
                   ("node_modules","target","artifacts","cache","out",".git","vendor","lib")]
        for f in files:
            p = Path(root) / f
            if p.suffix in source_extensions:
                rel = str(p.relative_to(repo_root))
                source_files.append(rel)
                if p.suffix == ".sol":
                    contracts.append({"file": rel, "type": "solidity", "status": "discovered"})
                elif p.suffix == ".rs":
                    programs.append({"file": rel, "type": "rust", "status": "discovered"})

# Phase D — Entrypoint mapping (stub: no AST analysis yet)
entrypoints_total = 0
entrypoints_verified = 0

# Phase E — Pathway construction (stub: no graph engine yet)
pathways_total = 0
pathways_verified = 0

# Determine status
if not bounty_dir.exists():
    status = "BLOCKED"
    completion_blocked_reason = "Bounty directory does not exist"
elif not source_files:
    status = "BLOCKED"
    completion_blocked_reason = "No source files found in bounty directory"
else:
    # Source files found but no analysis engine yet
    status = "PARTIAL"
    completion_blocked_reason = "Reconnaissance engine not yet implemented — manual review required"

tools = [
    {"name": "slither",       "status": "skipped", "reason": "Static analysis engine not yet integrated"},
    {"name": "semgrep",       "status": "skipped", "reason": "Semgrep rules not yet configured"},
    {"name": "aderyn",        "status": "skipped", "reason": "Aderyn runner not yet integrated"},
    {"name": "cargo-audit",   "status": "skipped", "reason": "Cargo audit not yet integrated"},
]

limitations = [
    "Entrypoint AST extraction not yet implemented — no function signatures discovered",
    "Pathway graph engine not yet implemented — cross-contract flows not traced",
    "Static analysis tools skipped — tool integration pending",
]

artifact = {
    "schema_version": "1.0.0",
    "slug": slug,
    "status": status,
    "timestamp": timestamp,
    "repository": {
        "root": str(repo_root),
        "commit": git_commit_val,
        "worktree_clean": worktree_clean,
    },
    "execution": {
        "mode": "confirmed",
        "write_authorized": True,
    },
    "scope": {
        "status": scope_status,
        "in_scope_assets": scope_files_found,
        "out_of_scope_assets": [],
        "assumptions": [],
        "limitations": ([] if scope_files_found else ["No scope documentation found in bounty directory"]),
    },
    "inventory": {
        "source_roots": ([str(bounty_dir.relative_to(repo_root))] if bounty_dir.exists() else []),
        "contracts": contracts,
        "programs": programs,
        "entrypoints": [],
        "external_dependencies": [],
    },
    "pathways": [],
    "priority_review_queue": [],
    "analysis": {
        "tools": tools,
        "tests": [],
        "coverage": {
            "entrypoints_total": entrypoints_total,
            "entrypoints_verified": entrypoints_verified,
            "pathways_total": pathways_total,
            "pathways_verified": pathways_verified,
        },
        "limitations": limitations,
    },
    "findings": [],
    "completion": {
        "entrypoints_mapped": False,
        "pathways_mapped": False,
        "evidence_validated": False,
        "complete": False,
    },
}

with open(tmpfile, "w", encoding="utf-8") as fh:
    json.dump(artifact, fh, indent=2, ensure_ascii=False)
    fh.write("\n")

print(f"[OK] Artifact prepared: {len(source_files)} source files discovered, status={status}")
sys.exit(0)
PYEOF
PYTHON_EXIT=$?

if [[ $PYTHON_EXIT -ne 0 ]]; then
  echo "Error: Reconnaissance engine failed (exit $PYTHON_EXIT)" >&2
  exit 1
fi

# --- Schema validation ---
if [[ -f "$VALIDATOR" ]]; then
  echo "[INFO] Validating artifact against schema..."
  if ! python3 "$VALIDATOR" --pathways "$TMPFILE"; then
    echo "Error: Schema validation failed" >&2
    exit 1
  fi
else
  echo "[WARN] Validator not found at $VALIDATOR — skipping schema validation" >&2
fi

# --- Atomic write ---
mv "$TMPFILE" "$PATHWAY_OUT"
trap - EXIT  # cancel tmpfile cleanup since we moved it

echo "[OK] Pathways artifact saved to $PATHWAY_OUT"
exit 0
