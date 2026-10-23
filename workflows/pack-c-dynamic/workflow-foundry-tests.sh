#!/usr/bin/env bash
# ==============================================================================
# Pack C — Dynamic Analysis & Verification Workflow: Foundry Unit Tests
# Version: 2.0.0
# Architecture: Glassbox Mirror Plane / Universal Adaptive Engineering
# Mission: Execute bounded Foundry unit test suites through the repository adapter,
#          strictly enforcing authorization, path containment, and leaf symlink safety.
# ==============================================================================
set -Eeuo pipefail
IFS=$'\n\t'

readonly SCRIPT_NAME="${0##*/}"
readonly DEFAULT_TARGET="bounties/base"
readonly DEFAULT_OUTPUT_DIR="bounties/base/scans/foundry"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly DEFAULT_REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd -P)"
readonly ADAPTER_RELATIVE_PATH=".agents/skills/qrpe/adapters/foundry_adapter.py"

DRY_RUN=false
CONFIRM=false
TARGET="$DEFAULT_TARGET"
OUTPUT_DIR="$DEFAULT_OUTPUT_DIR"
REPO_ROOT="${REPO_ROOT:-$DEFAULT_REPO_ROOT}"
MATCH_TEST=""
FORK_URL_ENV=""
FORK_BLOCK=""

usage() {
  cat <<EOF
Usage: $SCRIPT_NAME [OPTIONS]

Run the Foundry unit-test workflow through the repository adapter.

Options:
  --dry-run             Validate and preview without executing changes.
  --confirm             Explicitly authorize the adapter's execution mode.
  --target PATH         Target directory, relative to the repository root (default: $DEFAULT_TARGET).
  --output-dir PATH     Output directory, relative to the repository root (default: $DEFAULT_OUTPUT_DIR).
  --repo-root PATH      Repository root (default: $DEFAULT_REPO_ROOT).
  --match-test FILTER   Filter tests by regex/pattern (passed to forge --match-test).
  --fork-url-env VAR    Name of environment variable containing RPC URL (never pass raw URL).
  --fork-block NUM      Pinned fork block number.
  -h, --help            Show this help message and exit 0.

Safety:
  Dry-run is the default. --confirm enables the adapter's confirmed mode
  unless --dry-run is also specified. Dry-run always takes precedence.
EOF
}

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

log() {
  printf '[%s] %s\n' "$SCRIPT_NAME" "$*"
}

require_value() {
  local option="$1"
  local value="${2-}"

  [[ -n "$value" && "$value" != --* ]] ||
    fail "$option requires a value."
}

while (($#)); do
  case "$1" in
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --confirm)
      CONFIRM=true
      shift
      ;;
    --target)
      (($# >= 2)) || fail "--target requires a path."
      require_value "$1" "$2"
      TARGET="$2"
      shift 2
      ;;
    --output-dir)
      (($# >= 2)) || fail "--output-dir requires a path."
      require_value "$1" "$2"
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --repo-root)
      (($# >= 2)) || fail "--repo-root requires a path."
      require_value "$1" "$2"
      REPO_ROOT="$2"
      shift 2
      ;;
    --match-test)
      (($# >= 2)) || fail "--match-test requires a filter pattern."
      require_value "$1" "$2"
      MATCH_TEST="$2"
      shift 2
      ;;
    --fork-url-env)
      (($# >= 2)) || fail "--fork-url-env requires an environment variable name."
      require_value "$1" "$2"
      FORK_URL_ENV="$2"
      shift 2
      ;;
    --fork-block)
      (($# >= 2)) || fail "--fork-block requires a block number."
      require_value "$1" "$2"
      FORK_BLOCK="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "Unknown argument: $1. Use --help for usage."
      ;;
  esac
done

command -v python3 >/dev/null 2>&1 ||
  fail "python3 is not available on PATH."

[[ -d "$REPO_ROOT" ]] ||
  fail "Repository root does not exist: $REPO_ROOT"

REPO_ROOT="$(cd -- "$REPO_ROOT" && pwd -P)" ||
  fail "Cannot resolve repository root."

ADAPTER="$REPO_ROOT/$ADAPTER_RELATIVE_PATH"

[[ -f "$ADAPTER" && -r "$ADAPTER" ]] ||
  fail "Adapter is missing or unreadable: $ADAPTER"

# Resolve relative paths beneath the repository root. Reject absolute paths
# and traversal outside the repository, including existing leaf symlink escapes.
resolve_repo_path() {
  local input="$1"
  local parent candidate_parent resolved_parent name full_path canonical

  [[ "$input" != /* ]] ||
    fail "Paths must be relative to the repository root: $input"

  # Canonicalize the existing parent so symlinks cannot escape the root.
  parent="$(dirname -- "$input")"
  candidate_parent="$REPO_ROOT/$parent"

  [[ -d "$candidate_parent" ]] ||
    fail "Parent directory does not exist: $candidate_parent"

  resolved_parent="$(cd -P -- "$candidate_parent" 2>/dev/null && pwd -P)" ||
    fail "Cannot resolve parent directory: $candidate_parent"

  case "$resolved_parent" in
    "$REPO_ROOT"|"$REPO_ROOT"/*) ;;
    *) fail "Path escapes repository root: $input" ;;
  esac

  name="$(basename -- "$input")"

  [[ "$name" != "." && "$name" != ".." && -n "$name" ]] ||
    fail "Invalid path: $input"

  full_path="$resolved_parent/$name"

  # Resolve leaf symlinks whether existing or prospective
  if [[ -e "$full_path" || -L "$full_path" ]]; then
    canonical="$(realpath -e -- "$full_path" 2>/dev/null)" ||
      fail "Cannot resolve target path: $input"
  else
    canonical="$(realpath -m -- "$full_path" 2>/dev/null)" ||
      fail "Cannot resolve path: $input"
  fi

  case "$canonical" in
    "$REPO_ROOT"|"$REPO_ROOT"/*) ;;
    *) fail "Path escapes repository root: $input" ;;
  esac

  printf '%s\n' "$canonical"
}

RESOLVED_TARGET="$(resolve_repo_path "$TARGET")"
RESOLVED_OUTPUT_DIR="$(resolve_repo_path "$OUTPUT_DIR")"

[[ -d "$RESOLVED_TARGET" ]] ||
  fail "Target directory does not exist: $RESOLVED_TARGET"

# Existing output paths must be directories. The adapter may create the
# output directory if it does not exist.
if [[ -e "$RESOLVED_OUTPUT_DIR" && ! -d "$RESOLVED_OUTPUT_DIR" ]]; then
  fail "Output path exists but is not a directory: $RESOLVED_OUTPUT_DIR"
fi

ARGS=(
  --target "$RESOLVED_TARGET"
  --output-dir "$RESOLVED_OUTPUT_DIR"
)

if [[ -n "$MATCH_TEST" ]]; then
  ARGS+=(--match-test "$MATCH_TEST")
fi
if [[ -n "$FORK_URL_ENV" ]]; then
  ARGS+=(--fork-url-env "$FORK_URL_ENV")
fi
if [[ -n "$FORK_BLOCK" ]]; then
  ARGS+=(--fork-block "$FORK_BLOCK")
fi

# Dry-run always wins if both flags are supplied.
if [[ "$DRY_RUN" == true || "$CONFIRM" == false ]]; then
  ARGS+=(--dry-run)
  MODE="DRY-RUN"
else
  ARGS+=(--confirm)
  MODE="CONFIRMED"
fi

log "=== [Pack C] Workflow: Foundry Unit Tests ==="
log "Repository: $REPO_ROOT"
log "Target: $RESOLVED_TARGET"
log "Output: $RESOLVED_OUTPUT_DIR"
log "Mode: $MODE"

if [[ "$MODE" == "CONFIRMED" ]]; then
  log "Confirmed mode requested; adapter-level authorization remains required."
fi

# Preserve the adapter's exit status and avoid shell-string command execution.
exec python3 "$ADAPTER" "${ARGS[@]}"
