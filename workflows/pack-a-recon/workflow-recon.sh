#!/usr/bin/env bash
# ==============================================================================
# Pack A — Smart Contract Reconnaissance Orchestrator
# Version: 2.0.0
# Agent ID: META-RECON-A
# Mission: Discover Solidity contracts, record provenance, validate schema,
#          and perform fail-closed, atomic reconnaissance writes.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd -- "${BASH_SOURCE[0]%/*}" >/dev/null 2>&1 && pwd -P)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd -P)"

DRY_RUN=false
CONFIRM=false
SLUG="base"
RUN_SCANNERS=false
FAIL_SCANNER_SIM=false
CORRUPT_JSON_SIM=false

usage() {
  cat >&2 <<EOF
Usage: $(basename "$0") [--dry-run] [--confirm] [--slug SLUG] [-h|--help]

Pack A — Smart Contract Reconnaissance Orchestrator (META-RECON-A)

Options:
  --dry-run             Simulate workflow operations without writing files (default if --confirm omitted)
  --confirm             Authorize verified reconnaissance execution and artifact write
  --slug SLUG           Target bounty workspace under bounties/ (default: base)
  --run-scanners        Run registered optional static analysis tools
  --fail-scanner-sim    Simulate optional scanner failure (for verification testing)
  --corrupt-json-sim    Simulate corrupted JSON write (for verification testing)
  -h, --help            Show this help message and exit 0

Exit codes:
  0  Success (including dry-run plan)
  1  Execution, traversal, or artifact validation failure
  2  Invalid command-line arguments or path traversal
  3  Missing bounty directory or unresolvable scope
EOF
  exit "${1:-0}"
}

# --- Strict Argument Parsing ---
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
      if [[ $# -lt 2 || -z "${2:-}" || "${2:-}" == --* ]]; then
        echo "Error: --slug requires a non-empty value" >&2
        usage 2
      fi
      SLUG="$2"
      shift 2
      ;;
    --run-scanners)
      RUN_SCANNERS=true
      shift
      ;;
    --fail-scanner-sim)
      FAIL_SCANNER_SIM=true
      shift
      ;;
    --corrupt-json-sim)
      CORRUPT_JSON_SIM=true
      shift
      ;;
    -h|--help)
      usage 0
      ;;
    --*)
      echo "Error: Unknown argument: $1" >&2
      usage 2
      ;;
    *)
      echo "Error: Unexpected positional argument: $1" >&2
      usage 2
      ;;
  esac
done

# --- Slug Validation & Path Traversal Prevention ---
if [[ -z "$SLUG" ]]; then
  echo "Error: --slug value must not be empty" >&2
  exit 2
fi

if [[ "$SLUG" == /* ]]; then
  echo "Error: --slug must not be an absolute path: $SLUG" >&2
  exit 2
fi

if [[ "$SLUG" =~ \.\. || "$SLUG" =~ / || "$SLUG" =~ \\ ]]; then
  echo "Error: --slug must not contain path traversal, slashes, or backslashes: $SLUG" >&2
  exit 2
fi

if ! [[ "$SLUG" =~ ^[A-Za-z0-9][A-Za-z0-9_-]*$ ]]; then
  echo "Error: --slug contains invalid characters. Pattern: ^[A-Za-z0-9][A-Za-z0-9_-]*$" >&2
  exit 2
fi

# --- Path Containment ---
BOUNTIES_ROOT="$REPO_ROOT/bounties"
BOUNTY_DIR="$BOUNTIES_ROOT/$SLUG"
RECON_OUT="$BOUNTY_DIR/scans/recon.json"

echo "=== [Pack A] Workflow: Reconnaissance ($SLUG) ==="

# --- Authorization Safety Gates ---
if [[ "$DRY_RUN" == true || "$CONFIRM" == false ]]; then
  echo "[DRY-RUN] Target output: $RECON_OUT"
  echo "[DRY-RUN] Planned operations:"
  echo "  - Target workspace: $BOUNTY_DIR"
  echo "  - Target artifact:  $RECON_OUT"
  echo "  - Mode: DRY-RUN (simulation only; no filesystem writes or scanners executed)"
  exit 0
fi

# --- Target Verification ---
if [[ ! -d "$BOUNTY_DIR" ]]; then
  echo "[FAIL] Bounty directory does not exist: $BOUNTY_DIR" >&2
  exit 3
fi

if [[ -L "$BOUNTY_DIR" ]]; then
  echo "[FAIL] Bounty directory is a symlink. Refusing to write." >&2
  exit 1
fi

# --- Delegate Core Execution to recon.py Engine ---
PYTHON_ARGS=(
  "--slug" "$SLUG"
  "--repo-root" "$REPO_ROOT"
  "--bounty-dir" "$BOUNTY_DIR"
  "--output" "$RECON_OUT"
  "--confirm"
)

if [[ "$RUN_SCANNERS" == true ]]; then
  PYTHON_ARGS+=("--run-scanners")
fi
if [[ "$FAIL_SCANNER_SIM" == true ]]; then
  PYTHON_ARGS+=("--fail-scanner-sim")
fi
if [[ "$CORRUPT_JSON_SIM" == true ]]; then
  PYTHON_ARGS+=("--corrupt-json-sim")
fi

export RECON_WRAPPER_ACTIVE=1
python3 "$SCRIPT_DIR/recon.py" "${PYTHON_ARGS[@]}"
