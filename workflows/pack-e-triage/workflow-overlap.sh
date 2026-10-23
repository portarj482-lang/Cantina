#!/usr/bin/env bash
# Pack E Workflow: Overlap & Known-Issue Annotation
# Meta-Persona: CANTINA-PACK-E (Cantina Bounty Security Analyst - Pack E)
set -euo pipefail

SCRIPT_DIR="$(cd -- "${BASH_SOURCE[0]%/*}" >/dev/null 2>&1 && pwd -P)"
PYTHON_ENGINE="$SCRIPT_DIR/overlap_analyzer.py"

usage() {
  cat <<'EOF' >&2
Usage: workflow-overlap.sh [--slug SLUG] [--dry-run] [--confirm] [-h|--help]

Options:
  --slug SLUG    Target bounty slug (default: base, pattern: ^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$)
  --dry-run      Preview overlap analysis without writing files (default behavior if unconfirmed)
  --confirm      Authorize durable write and atomic replacement of overlap_analysis.json
  -h, --help     Show this help message

Exit codes:
  0 - Analysis succeeded, or preview completed without operational errors
  1 - Analysis failure
  2 - Write / filesystem failure (symlink detected, unsafe path, cross-device error)
  3 - Required dependency is missing or unavailable
  4 - Invalid arguments, missing argument values, or invalid slug syntax
EOF
}

log_bash_event() {
  local level="$1" event="$2" msg="$3" err="${4:-null}"
  local ts
  ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date +"%Y-%m-%dT%H:%M:%SZ")"
  if command -v python3 >/dev/null 2>&1; then
    python3 -c "import json, sys; print(json.dumps({'timestamp': sys.argv[1], 'level': sys.argv[2], 'event': sys.argv[3], 'component': 'workflow_bash', 'slug': sys.argv[4] if sys.argv[4] else None, 'processed_count': 0, 'error_code': sys.argv[5] if sys.argv[5] != 'null' else None, 'message': sys.argv[6]}, ensure_ascii=False))" \
      "$ts" "$level" "$event" "${SLUG:-}" "$err" "$msg" >&2 || true
  else
    printf '{"timestamp":"%s","level":"%s","event":"%s","component":"workflow_bash","slug":%s,"processed_count":0,"error_code":%s,"message":"%s"}\n' \
      "$ts" "$level" "$event" \
      "$([[ -n "${SLUG:-}" ]] && printf '"%s"' "$SLUG" || printf 'null')" \
      "$([[ "$err" != "null" ]] && printf '"%s"' "$err" || printf 'null')" \
      "$msg" >&2
  fi
}

# 1. Dependency checks
check_deps() {
  local missing=()
  command -v git >/dev/null 2>&1 || missing+=("git")
  command -v python3 >/dev/null 2>&1 || missing+=("python3")
  if [[ ${#missing[@]} -gt 0 ]]; then
    local err_msg="Missing required dependencies: ${missing[*]}"
    log_bash_event "ERROR" "DEPENDENCY_MISSING" "$err_msg" "MISSING_DEPENDENCY"
    echo "Error: $err_msg" >&2
    exit 3
  fi
}

check_deps

# 2. Argument parsing
SLUG="base"
DRY_RUN=false
CONFIRM=false
SLUG_SPECIFIED=false

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
        log_bash_event "ERROR" "MISSING_ARG_VALUE" "Missing value for --slug" "INVALID_ARGUMENTS"
        echo "Error: Missing value for --slug" >&2
        usage
        exit 4
      fi
      if [[ "$SLUG_SPECIFIED" == true && "$SLUG" != "$2" ]]; then
        log_bash_event "ERROR" "CONFLICTING_OPTIONS" "Conflicting duplicate --slug options provided: '$SLUG' vs '$2'" "INVALID_ARGUMENTS"
        echo "Error: Conflicting duplicate --slug options provided." >&2
        usage
        exit 4
      fi
      SLUG="$2"
      SLUG_SPECIFIED=true
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      log_bash_event "ERROR" "UNKNOWN_FLAG" "Unknown flag: $1" "INVALID_ARGUMENTS"
      echo "Error: Unknown flag: $1" >&2
      usage
      exit 4
      ;;
  esac
done

# Slug syntax & traversal checks
SLUG_REGEX='^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$'
if [[ ! "$SLUG" =~ $SLUG_REGEX ]]; then
  log_bash_event "ERROR" "INVALID_SLUG" "Slug '$SLUG' violates contract ^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$" "INVALID_SLUG"
  echo "Error: Invalid slug '$SLUG'. Must match ^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$" >&2
  exit 4
fi

if [[ "$SLUG" == *"/"* || "$SLUG" == *"\\"* || "$SLUG" == *".."* ]]; then
  log_bash_event "ERROR" "INVALID_SLUG" "Path separators or traversal prohibited in slug." "INVALID_SLUG"
  echo "Error: Path separators or traversal prohibited in slug." >&2
  exit 4
fi

REPO_ROOT="${REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd -P)}"
BOUNTIES_DIR="$REPO_ROOT/bounties"
BOUNTY_DIR="$BOUNTIES_DIR/$SLUG"
OUT_DIR="$BOUNTY_DIR/scans"
OUT_FILE="$OUT_DIR/overlap_analysis.json"

# Symlink checks on bounty dir, scans dir, and output file
if [[ -L "$BOUNTY_DIR" ]]; then
  log_bash_event "ERROR" "SYMLINK_BOUNTY_DIR" "Bounty directory '$BOUNTY_DIR' is a symlink. Refusing execution." "UNSAFE_OUTPUT_DIR"
  echo "Error: Bounty directory '$BOUNTY_DIR' is a symlink. Refusing execution." >&2
  exit 2
fi

if [[ -L "$OUT_DIR" ]]; then
  log_bash_event "ERROR" "SYMLINK_OUTPUT_DIR" "Output directory '$OUT_DIR' is a symlink. Refusing execution." "UNSAFE_OUTPUT_DIR"
  echo "Error: Output directory '$OUT_DIR' is a symlink. Refusing execution." >&2
  exit 2
fi

if [[ -L "$OUT_FILE" ]]; then
  log_bash_event "ERROR" "SYMLINK_OUTPUT_FILE" "Output file '$OUT_FILE' is a symlink. Refusing execution." "UNSAFE_OUTPUT_DIR"
  echo "Error: Output file '$OUT_FILE' is a symlink. Refusing execution." >&2
  exit 2
fi

# Check if bounty directory exists
if [[ ! -d "$BOUNTY_DIR" ]]; then
  log_bash_event "ERROR" "MISSING_BOUNTY_DIR" "Bounty directory '$BOUNTY_DIR' does not exist." "FILESYSTEM_FAILURE"
  echo "Error: Bounty directory '$BOUNTY_DIR' does not exist." >&2
  exit 2
fi

# Device boundary check
DEV_REPO=$(stat -c %d "$REPO_ROOT" 2>/dev/null || true)
if [[ -n "$DEV_REPO" ]]; then
  DEV_BOUNTY=$(stat -c %d "$BOUNTY_DIR" 2>/dev/null || true)
  if [[ -n "$DEV_BOUNTY" && "$DEV_REPO" != "$DEV_BOUNTY" ]]; then
    log_bash_event "ERROR" "CROSS_DEVICE_DETECTED" "Bounty directory '$BOUNTY_DIR' is on a different filesystem device." "FILESYSTEM_FAILURE"
    echo "Error: Bounty directory '$BOUNTY_DIR' diverges from repository filesystem device." >&2
    exit 2
  fi
  if [[ -d "$OUT_DIR" ]]; then
    DEV_OUT=$(stat -c %d "$OUT_DIR" 2>/dev/null || true)
    if [[ -n "$DEV_OUT" && "$DEV_REPO" != "$DEV_OUT" ]]; then
      log_bash_event "ERROR" "CROSS_DEVICE_DETECTED" "Output directory '$OUT_DIR' is on a different filesystem device." "FILESYSTEM_FAILURE"
      echo "Error: Output directory '$OUT_DIR' diverges from repository filesystem device." >&2
      exit 2
    fi
  fi
fi

# Trap cleanup for temporary files
cleanup() {
  if [[ -d "$OUT_DIR" && ! -L "$OUT_DIR" && ! -L "$BOUNTY_DIR" ]]; then
    rm -f "$OUT_DIR"/.*overlap_analysis.tmp-* 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "=== [Pack E] Workflow: Overlap & Known-Issue Annotation ($SLUG) ==="

PY_ARGS=(
  "--repo-root" "$REPO_ROOT"
  "--slug" "$SLUG"
)

if [[ "$CONFIRM" == true ]]; then
  PY_ARGS+=("--confirm")
fi

if [[ "$DRY_RUN" == true ]]; then
  PY_ARGS+=("--dry-run")
fi

python3 "$PYTHON_ENGINE" "${PY_ARGS[@]}"
