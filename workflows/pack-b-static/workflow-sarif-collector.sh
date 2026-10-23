#!/usr/bin/env bash
# ==============================================================================
# Pack B — Universal Oracle–Orchestrator Meta-Agent (UOOMA) SARIF Collector
# Version: 1.0.0
# Agent ID: UOOMA-PACK-B
# Mission: Discover, normalize, deduplicate, and atomically publish static
#          analysis SARIF artifacts under strict evidence and schema governance.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd -- "${BASH_SOURCE[0]%/*}" >/dev/null 2>&1 && pwd -P)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd -P)"

DRY_RUN=false
CONFIRM=false
SLUG="base"
MODE="EXECUTE"
EMPTY_ALLOWED=false
FAIL_SIM=false
CORRUPT_SIM=false

usage() {
  cat >&2 <<EOF
Usage: $(basename "$0") [--mode MODE] [--dry-run] [--confirm] [--slug SLUG] [--empty-allowed] [-h|--help]

Pack B — Universal Oracle–Orchestrator Meta-Agent SARIF Collector (UOOMA-PACK-B)

Options:
  --mode MODE           Operating mode: INSPECT, PLAN, DRY_RUN, EXECUTE, VERIFY (default: EXECUTE)
  --dry-run             Simulate workflow operations without writing files (default if --confirm omitted)
  --confirm             Authorize verified SARIF collection execution and atomic write
  --slug SLUG           Target bounty workspace under bounties/ (default: base)
  --empty-allowed       Explicitly permit an empty scan directory without failure
  --fail-sim            Simulate collection failure (for adversarial verification testing)
  --corrupt-sim         Simulate corrupted JSON write (for verification testing)
  -h, --help            Show this help message and exit 0

Exit codes:
  0  Success (including verified dry-run preview)
  1  Execution, schema validation, or normalization failure
  2  Invalid command-line arguments or path traversal
  3  Missing bounty directory or unresolvable scope
EOF
  exit "${1:-0}"
}

# --- Strict Option Parsing ---
while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      if [[ $# -lt 2 || -z "${2:-}" || "${2:-}" == --* ]]; then
        echo "Error: --mode requires a non-empty value (INSPECT, PLAN, DRY_RUN, EXECUTE, VERIFY)" >&2
        usage 2
      fi
      MODE="$(echo "$2" | tr '[:lower:]' '[:upper:]')"
      case "$MODE" in
        INSPECT|PLAN|DRY_RUN|EXECUTE|VERIFY)
          ;;
        *)
          echo "Error: Invalid mode '$2'. Must be one of: INSPECT, PLAN, DRY_RUN, EXECUTE, VERIFY" >&2
          usage 2
          ;;
      esac
      shift 2
      ;;
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
    --empty-allowed)
      EMPTY_ALLOWED=true
      shift
      ;;
    --fail-sim)
      FAIL_SIM=true
      shift
      ;;
    --corrupt-sim)
      CORRUPT_SIM=true
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

if [[ "$SLUG" == *"/"* || "$SLUG" == *"\\"* || "$SLUG" == *".."* ]]; then
  echo "Error: Path separators or traversal components prohibited in slug: $SLUG" >&2
  exit 2
fi

SLUG_REGEX='^[A-Za-z0-9][A-Za-z0-9_-]*$'
if [[ ! "$SLUG" =~ $SLUG_REGEX ]]; then
  echo "Error: --slug '$SLUG' contains invalid characters. Must match $SLUG_REGEX" >&2
  exit 2
fi

BOUNTY_DIR="$REPO_ROOT/bounties/$SLUG"
SCAN_DIR="$BOUNTY_DIR/scans"
OUT_FILE="$SCAN_DIR/normalized_sarif.json"

echo "=== [Pack B] Workflow: SARIF Collector ($SLUG) ==="

# Check target bounty directory exists
if [[ ! -d "$BOUNTY_DIR" ]]; then
  echo "Error: Target bounty directory does not exist: $BOUNTY_DIR" >&2
  exit 3
fi

# Prepare arguments for python engine
PYTHON_ARGS=(
  "--slug" "$SLUG"
  "--mode" "$MODE"
)

if [[ "$DRY_RUN" == true || "$CONFIRM" == false ]]; then
  PYTHON_ARGS+=("--dry-run")
else
  PYTHON_ARGS+=("--confirm")
fi

if [[ "$EMPTY_ALLOWED" == true ]]; then
  PYTHON_ARGS+=("--empty-allowed")
fi

if [[ "$FAIL_SIM" == true ]]; then
  PYTHON_ARGS+=("--fail-sim")
fi

if [[ "$CORRUPT_SIM" == true ]]; then
  PYTHON_ARGS+=("--corrupt-sim")
fi

# Execute python engine
python3 "$SCRIPT_DIR/sarif_collector.py" "${PYTHON_ARGS[@]}"
