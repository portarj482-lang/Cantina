#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
umask 077

readonly SCRIPT_NAME="${0##*/}"
readonly DEFAULT_TARGET="bounties/base/contracts"
readonly DEFAULT_OUTPUT_DIR="bounties/base/scans/slither"
DEFAULT_REPO_ROOT="$(pwd -P)"
REPO_ROOT="${REPO_ROOT:-$DEFAULT_REPO_ROOT}"

TARGET="$DEFAULT_TARGET"
OUTPUT_DIR="$DEFAULT_OUTPUT_DIR"
DRY_RUN=true
CONFIRM=false

usage() {
  cat <<EOF
Usage: $SCRIPT_NAME [OPTIONS]

Run the repository's Slither analysis adapter.

Options:
  --target PATH       Target directory relative to repository root
  --output-dir PATH   Output directory relative to repository root
  --dry-run           Do not authorize a real scan (default)
  --confirm           Permit execution, subject to adapter safeguards
  -h, --help          Show this help

Safety:
  Dry-run is the default. If both --dry-run and --confirm are supplied,
  dry-run wins. This wrapper does not guarantee that the adapter itself
  performs no writes during its dry-run path.
EOF
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 2
}

log() {
  printf '[%s] %s\n' "$SCRIPT_NAME" "$*"
}

while (($#)); do
  case "$1" in
    --target)
      (($# >= 2)) || die "--target requires a path"
      [[ -n "$2" ]] || die "--target cannot be empty"
      TARGET="$2"
      shift 2
      ;;
    --output-dir)
      (($# >= 2)) || die "--output-dir requires a path"
      [[ -n "$2" ]] || die "--output-dir cannot be empty"
      OUTPUT_DIR="$2"
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
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown argument: $1 (use --help)"
      ;;
  esac
done

# Locate the repository root from the caller's directory by default.
# CI and automation should set REPO_ROOT explicitly when appropriate.
[[ -d "$REPO_ROOT" ]] || die "Repository root does not exist: $REPO_ROOT"
REPO_ROOT="$(cd -- "$REPO_ROOT" && pwd -P)"

readonly ADAPTER="$REPO_ROOT/.agents/skills/qrpe/adapters/slither_adapter.py"

resolve_repo_path() {
  local relative_path="$1"
  local parent candidate

  # This wrapper intentionally accepts repository-relative paths only.
  [[ "$relative_path" != /* ]] ||
    die "Absolute paths are not allowed: $relative_path"

  # Resolve the existing parent directory physically. For an output path,
  # the parent must exist; create it separately only under an approved policy.
  parent="$(dirname -- "$relative_path")"
  candidate="$REPO_ROOT/$parent"

  [[ -d "$candidate" ]] ||
    die "Parent directory does not exist: $parent"

  parent="$(cd -- "$candidate" && pwd -P)"
  candidate="$parent/$(basename -- "$relative_path")"

  case "$candidate" in
    "$REPO_ROOT"/*) printf '%s\n' "$candidate" ;;
    *) die "Path escapes the repository root: $relative_path" ;;
  esac
}

[[ -f "$ADAPTER" ]] || die "Slither adapter not found: $ADAPTER"
command -v python3 >/dev/null 2>&1 || die "python3 is unavailable"

# The output directory's parent must already exist. Do not create directories
# before the adapter's write behavior and authorization have been established.
RESOLVED_TARGET="$(resolve_repo_path "$TARGET")"
RESOLVED_OUTPUT="$(resolve_repo_path "$OUTPUT_DIR")"

[[ -d "$RESOLVED_TARGET" ]] ||
  die "Target directory does not exist: $RESOLVED_TARGET"

# Prevent output from being placed inside the source tree being analyzed.
case "$RESOLVED_OUTPUT/" in
  "$RESOLVED_TARGET/"*)
    die "Output directory must not be inside the target directory"
    ;;
esac

# Explicit dry-run always takes precedence over --confirm.
MODE="--dry-run"
if [[ "$CONFIRM" == true && "$DRY_RUN" == false ]]; then
  MODE="--confirm"
fi

log "Workflow: Slither static analysis"
log "Repository: $REPO_ROOT"
log "Target: $RESOLVED_TARGET"
log "Output: $RESOLVED_OUTPUT"
log "Mode: $MODE"

ARGS=(
  --target "$RESOLVED_TARGET"
  --output-dir "$RESOLVED_OUTPUT"
  "$MODE"
)

# Preserve the adapter's exit status. Do not convert failures into success.
exec python3 "$ADAPTER" "${ARGS[@]}"
