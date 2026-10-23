#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

readonly SCRIPT_NAME="${0##*/}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly DEFAULT_REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd -P)"
REPO_ROOT="${REPO_ROOT:-$DEFAULT_REPO_ROOT}"
readonly REPO_ROOT
ADAPTER="${ADAPTER:-$REPO_ROOT/.agents/skills/qrpe/adapters/foundry_adapter.py}"
readonly ADAPTER

TARGET="bounties/base"
OUTPUT_DIR="bounties/base/scans/fuzz"
DRY_RUN_EXPLICIT=false
CONFIRM=false

usage() {
  cat <<EOF
Usage:
  ${SCRIPT_NAME} [OPTIONS]

Options:
  --target PATH       Target directory relative to the repository root
                      (default: bounties/base)
  --output-dir PATH   Output directory relative to the repository root
                      (default: bounties/base/scans/fuzz)
  --dry-run           Validate and preview without executing fuzz tests
  --confirm           Authorize execution, subject to runtime policy
  --help              Show this help

Execution is dry-run by default. --dry-run and --confirm are exclusive.
EOF
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 2
}

cleanup_cancel() {
  printf 'ERROR: Workflow cancelled. Incomplete state recorded.\n' >&2
  exit 130
}
trap cleanup_cancel INT TERM

while (($#)); do
  case "$1" in
    --target|--output-dir)
      option="$1"
      (($# >= 2)) || die "Missing value for $option"
      [[ -n "$2" && "$2" != --* ]] ||
        die "Invalid value for $option"

      case "$option" in
        --target) TARGET="$2" ;;
        --output-dir) OUTPUT_DIR="$2" ;;
      esac
      shift 2
      ;;
    --dry-run)
      [[ "$CONFIRM" == false ]] ||
        die "--dry-run and --confirm cannot be combined"
      DRY_RUN_EXPLICIT=true
      shift
      ;;
    --confirm)
      [[ "$DRY_RUN_EXPLICIT" == false ]] ||
        die "--dry-run and --confirm cannot be combined"
      CONFIRM=true
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      die "Unknown argument: $1"
      ;;
  esac
done

# Preserve dry-run as the default. Conflicting authorization flags are rejected.
[[ -d "$REPO_ROOT" ]] || die "Repository root not found"
[[ -f "$ADAPTER" ]] || die "Foundry adapter not found"
command -v python3 >/dev/null 2>&1 || die "python3 is required"

# Canonicalize paths and prevent escaping the authorized repository.
PATHS="$(
  python3 - "$REPO_ROOT" "$TARGET" "$OUTPUT_DIR" <<'PY'
import pathlib
import sys

root = pathlib.Path(sys.argv[1]).resolve(strict=True)

def contained_path(value, label):
    clean_val = value.strip()
    if not clean_val:
        sys.stderr.write(f"{label} cannot be empty\n")
        sys.exit(1)

    supplied = pathlib.Path(clean_val)
    if supplied.is_absolute():
        sys.stderr.write(f"{label} must be repository-relative\n")
        sys.exit(1)

    parent_path = (root / supplied.parent).resolve(strict=False)
    if not parent_path.is_relative_to(root):
        sys.stderr.write(f"{label} escapes the repository root\n")
        sys.exit(1)

    path = (root / supplied).resolve(strict=False)
    if not path.is_relative_to(root):
        sys.stderr.write(f"{label} escapes the repository root\n")
        sys.exit(1)

    if path == root:
        sys.stderr.write(f"{label} cannot be the repository root\n")
        sys.exit(1)

    direct_path = root / supplied
    if direct_path.is_symlink():
        target_dest = direct_path.resolve()
        if not target_dest.is_relative_to(root):
            sys.stderr.write(f"{label} escapes the repository root\n")
            sys.exit(1)

    return path

target = contained_path(sys.argv[2], "Target")
output = contained_path(sys.argv[3], "Output directory")

if not target.is_dir():
    sys.stderr.write(f"Target directory does not exist: {target}\n")
    sys.exit(1)

if output.exists() and not output.is_dir():
    sys.stderr.write(f"Output path exists but is not a directory: {output}\n")
    sys.exit(1)

print(target)
print(output)
PY
)" || die "Path validation failed"

mapfile -t RESOLVED_PATHS <<< "$PATHS"
((${#RESOLVED_PATHS[@]} == 2)) || die "Invalid validated paths"

RESOLVED_TARGET="${RESOLVED_PATHS[0]}"
RESOLVED_OUTPUT="${RESOLVED_PATHS[1]}"

ARGS=(
  --target "$RESOLVED_TARGET"
  --output-dir "$RESOLVED_OUTPUT"
  --match-test 'testFuzz_'
)

if [[ "$CONFIRM" == true ]]; then
  MODE="execute"
  ARGS+=(--confirm)
else
  MODE="dry-run"
  ARGS+=(--dry-run)
fi

printf '%s\n' "=== [Pack C] Bounded Forge Fuzz Runner ==="
printf 'Mode: %s\n' "$MODE"
printf 'Target: %s\n' "$RESOLVED_TARGET"
printf 'Output: %s\n' "$RESOLVED_OUTPUT"

ADAPTER_STATUS=0
python3 "$ADAPTER" "${ARGS[@]}" || ADAPTER_STATUS=$?

if [[ "$CONFIRM" == true ]]; then
  if [[ $ADAPTER_STATUS -eq 0 ]]; then
    # Invariant 2: No success by exit code alone.
    # Verify mandatory result artifacts exist and are valid JSON.
    RECEIPT_FILE="$RESOLVED_OUTPUT/receipt.json"
    if [[ ! -f "$RECEIPT_FILE" ]]; then
      printf 'ERROR: Missing result artifact: %s\n' "$RECEIPT_FILE" >&2
      exit 1
    fi
    if ! python3 -c 'import json, sys; json.load(open(sys.argv[1]))' "$RECEIPT_FILE" >/dev/null 2>&1; then
      printf 'ERROR: Invalid result artifact JSON: %s\n' "$RECEIPT_FILE" >&2
      exit 1
    fi
  elif [[ $ADAPTER_STATUS -eq 124 ]]; then
    printf 'ERROR: Execution timed out (exit code 124). Incomplete state recorded.\n' >&2
  fi
fi

exit "$ADAPTER_STATUS"
