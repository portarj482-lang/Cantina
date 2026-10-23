#!/usr/bin/env bash
# ==============================================================================
# Pack C — Glassbox Mirror Plane Medusa Dynamic Property Fuzzing Workflow
# Version: 2.0.0
# Architecture: Universal Adaptive Security Verification / Glassbox Mirror Plane
# Role: Execution Wrapper & Hardened Entrypoint
# Mission: Safely validate arguments, inspect Medusa CLI compatibility, enforce
#          workspace containment and authorization gates, supervise execution,
#          and dispatch to the Glassbox Mirror Plane Orchestrator.
# ==============================================================================
set -Eeuo pipefail
IFS=$'\n\t'
umask 077

readonly SCRIPT_NAME="${0##*/}"
readonly SCRIPT_DIR="$(cd -- "${BASH_SOURCE[0]%/*}" >/dev/null 2>&1 && pwd -P)"
readonly REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd -P)"

# Default parameter values
DRY_RUN=false
CONFIRM=false
SLUG="base"
TARGET=""
CONFIG=""
TIMEOUT="${TIMEOUT_SECONDS:-60}"
TEST_LIMIT=""
WORKERS=""
SEED=""
OUTPUT_DIR="${REPORT_DIR:-}"

# Simulation / Negative Control Flags
FAIL_SIM=false
TIMEOUT_SIM=false
CORRUPT_SIM=false
CLEAN_SIM=false
FALSIFY_SIM=false
DIGEST_MISMATCH_SIM=false

usage() {
  cat <<'EOF'
Usage:
  workflow-medusa.sh [options]

Pack C — Glassbox Mirror Plane Medusa Dynamic Property Fuzzing Workflow

Options:
  --slug SLUG                  Target bounty workspace under bounties/ (default: base)
  --target PATH                Solidity target directory or source file (default: bounties/<slug>/contracts)
  --config PATH                Medusa configuration JSON file
  --timeout SECONDS            Campaign timeout in seconds (default: 60)
  --test-limit INTEGER         Maximum number of test transactions to execute
  --workers INTEGER            Number of parallel fuzzer workers
  --seed INTEGER               Deterministic random seed (non-negative integer)
  --report-dir, --output-dir,
  --artifacts PATH             Directory for campaign output artifacts
  --dry-run                    Validate configuration without running fuzzing
  --confirm                    Explicitly authorize live fuzzing execution
  --fail-sim                   Simulate execution failure (for adversarial testing)
  --timeout-sim                Simulate execution timeout (for deadline recovery testing)
  --corrupt-sim                Simulate corrupt artifact payload
  --clean-sim                  Simulate clean campaign with all properties passing
  --falsify-sim                Simulate campaign falsifying an invariant with counterexamples
  --digest-mismatch-sim        Simulate cryptographic digest mismatch
  -h, --help                   Display this help message and exit 0

Environment:
  MEDUSA_COMMAND               Optional reviewed absolute executable command for fuzzing

Exit codes:
  0  Success (including verified preflight dry-run and clean verified campaigns)
  1  Execution failure, invariant falsification, or schema validation failure
  2  Invalid command-line arguments, path traversal, or sandbox escape
  3  Missing target directory, missing tool, or unresolvable scope
EOF
  exit "${1:-0}"
}

die() {
  printf '[FAIL] %s\n' "$*" >&2
  exit 1
}

die_code() {
  local code="$1"
  shift
  printf '[FAIL] %s\n' "$*" >&2
  exit "$code"
}

log() {
  printf '[%s] %s\n' "$1" "$2"
}

need_value() {
  [[ $# -ge 2 && -n "$2" && "$2" != --* ]] ||
    die_code 2 "Option $1 requires a non-empty value"
}

# Cleanup and signal trap handlers
CLEANUP_REQUIRED=false
cleanup() {
  local exit_status=$?
  if [[ "$CLEANUP_REQUIRED" == true ]]; then
    log INFO "Performing campaign cleanup and releasing resources (exit code: $exit_status)..."
  fi
}
trap cleanup EXIT
trap 'die_code 130 "Workflow interrupted by SIGINT"' INT
trap 'die_code 143 "Workflow terminated by SIGTERM"' TERM

# --- Parse Command Line Options ---
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
    --slug)
      need_value "$@"
      SLUG="$2"
      shift 2
      ;;
    --target)
      need_value "$@"
      TARGET="$2"
      shift 2
      ;;
    --config)
      need_value "$@"
      CONFIG="$2"
      shift 2
      ;;
    --timeout)
      need_value "$@"
      TIMEOUT="$2"
      shift 2
      ;;
    --test-limit)
      need_value "$@"
      TEST_LIMIT="$2"
      shift 2
      ;;
    --workers)
      need_value "$@"
      WORKERS="$2"
      shift 2
      ;;
    --seed)
      need_value "$@"
      SEED="$2"
      shift 2
      ;;
    --report-dir|--output-dir|--artifacts)
      need_value "$@"
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --fail-sim)
      FAIL_SIM=true
      shift
      ;;
    --timeout-sim)
      TIMEOUT_SIM=true
      shift
      ;;
    --corrupt-sim)
      CORRUPT_SIM=true
      shift
      ;;
    --clean-sim)
      CLEAN_SIM=true
      shift
      ;;
    --falsify-sim)
      FALSIFY_SIM=true
      shift
      ;;
    --digest-mismatch-sim)
      DIGEST_MISMATCH_SIM=true
      shift
      ;;
    --help|-h)
      usage 0
      ;;
    --)
      shift
      break
      ;;
    *)
      die_code 2 "Unknown option: $1"
      ;;
  esac
done

# --- Validate Input Formats ---
readonly SLUG_REGEX='^[A-Za-z0-9][A-Za-z0-9_-]*$'
if [[ ! "$SLUG" =~ $SLUG_REGEX ]]; then
  die_code 2 "--slug '$SLUG' is invalid. Must match $SLUG_REGEX without traversal characters"
fi

if [[ -n "$SEED" && ! "$SEED" =~ ^[0-9]+$ ]]; then
  die_code 2 "--seed must be a non-negative integer: '$SEED'"
fi

if [[ ! "$TIMEOUT" =~ ^[0-9]+$ || "$TIMEOUT" -le 0 ]]; then
  die_code 2 "--timeout must be a positive integer: '$TIMEOUT'"
fi

if [[ -n "$TEST_LIMIT" && (! "$TEST_LIMIT" =~ ^[0-9]+$ || "$TEST_LIMIT" -le 0) ]]; then
  die_code 2 "--test-limit must be a positive integer: '$TEST_LIMIT'"
fi

if [[ -n "$WORKERS" && (! "$WORKERS" =~ ^[0-9]+$ || "$WORKERS" -le 0) ]]; then
  die_code 2 "--workers must be a positive integer: '$WORKERS'"
fi

# Ensure realpath utility is available
command -v realpath >/dev/null 2>&1 ||
  die_code 3 "Required utility not found: realpath"

is_contained() {
  local p="$1"
  local root="$2"
  [[ "$p" == "$root" || "$p" == "$root/"* ]]
}

CANONICAL_REPO="$(realpath "$REPO_ROOT")"
BOUNTY_DIR="$CANONICAL_REPO/bounties/$SLUG"

# --- Validate Target String for Non-Canonical Components ---
if [[ -n "$TARGET" ]]; then
  if [[ "$TARGET" == *"/../"* || "$TARGET" == *"/.." || "$TARGET" == "../"* || "$TARGET" == ".." || "$TARGET" == *"/./"* || "$TARGET" == *"//"* ]]; then
    die_code 2 "Target contains a non-canonical path component"
  fi
fi

# --- Resolve Target and Artifact Paths ---
if [[ -z "$TARGET" ]]; then
  if [[ -d "$BOUNTY_DIR/contracts" ]]; then
    TARGET="$BOUNTY_DIR/contracts"
  else
    TARGET="$BOUNTY_DIR"
  fi
else
  if [[ "$TARGET" != /* ]]; then
    TARGET="$CANONICAL_REPO/$TARGET"
  fi
fi

if [[ -z "$OUTPUT_DIR" ]]; then
  OUTPUT_DIR="$BOUNTY_DIR/scans/medusa"
else
  if [[ "$OUTPUT_DIR" != /* ]]; then
    OUTPUT_DIR="$CANONICAL_REPO/$OUTPUT_DIR"
  fi
fi

CANONICAL_TARGET="$(realpath -m "$TARGET")"
CANONICAL_OUTPUT_DIR="$(realpath -m "$OUTPUT_DIR")"

# --- Strict Path Containment Checks ---
if ! is_contained "$CANONICAL_TARGET" "$CANONICAL_REPO"; then
  die_code 2 "Target path '$CANONICAL_TARGET' escapes workspace repository root '$CANONICAL_REPO'"
fi

if ! is_contained "$CANONICAL_OUTPUT_DIR" "$CANONICAL_REPO"; then
  die_code 2 "Artifact directory '$CANONICAL_OUTPUT_DIR' escapes workspace repository root '$CANONICAL_REPO'"
fi

# Prevent leaf symlink escapes
if [[ -L "$CANONICAL_TARGET" ]]; then
  RESOLVED_LEAF="$(realpath -e "$CANONICAL_TARGET" 2>/dev/null || true)"
  if [[ -n "$RESOLVED_LEAF" ]] && ! is_contained "$RESOLVED_LEAF" "$CANONICAL_REPO"; then
    die_code 2 "Target leaf symlink escapes workspace repository root: $CANONICAL_TARGET -> $RESOLVED_LEAF"
  fi
fi

# Prevent output directory from being inside target contracts directory
if [[ "$CANONICAL_TARGET" != "$BOUNTY_DIR" ]]; then
  case "$CANONICAL_OUTPUT_DIR/" in
    "$CANONICAL_TARGET/"*)
      die_code 2 "Artifact directory '$CANONICAL_OUTPUT_DIR' must not be inside target directory '$CANONICAL_TARGET'"
      ;;
  esac
fi

# Existing output path must not be a regular file
if [[ -e "$CANONICAL_OUTPUT_DIR" && ! -d "$CANONICAL_OUTPUT_DIR" ]]; then
  die_code 2 "Output path exists but is not a directory: $CANONICAL_OUTPUT_DIR"
fi

# --- Target Validation ---
if [[ ! -e "$CANONICAL_TARGET" ]]; then
  die_code 3 "Target does not exist: $CANONICAL_TARGET"
fi

if [[ -n "$CONFIG" ]]; then
  if [[ "$CONFIG" != /* ]]; then
    CONFIG="$CANONICAL_REPO/$CONFIG"
  fi
  CONFIG="$(realpath -m "$CONFIG")"
  if [[ ! -f "$CONFIG" || ! -r "$CONFIG" ]]; then
    die_code 3 "Configuration file is not readable: $CONFIG"
  fi
fi

# --- Tool Resolution ---
MEDUSA_BIN="$(command -v medusa || true)"
if [[ -z "$MEDUSA_BIN" ]]; then
  if [[ -x "$HOME/.local/bin/medusa" ]]; then
    MEDUSA_BIN="$HOME/.local/bin/medusa"
  elif [[ -x "/usr/local/bin/medusa" ]]; then
    MEDUSA_BIN="/usr/local/bin/medusa"
  elif [[ -x "/usr/bin/medusa" ]]; then
    MEDUSA_BIN="/usr/bin/medusa"
  fi
fi

if [[ -z "$MEDUSA_BIN" || ! -x "$MEDUSA_BIN" ]]; then
  if [[ "$DRY_RUN" == true || "$CONFIRM" == false ]]; then
    MEDUSA_BIN="medusa"
    MEDUSA_VERSION="medusa (dry-run simulation)"
  else
    die_code 3 "Medusa executable not found on PATH or in standard user locations"
  fi
else
  MEDUSA_VERSION="$("$MEDUSA_BIN" --version 2>&1 | head -n 1)" ||
    die_code 3 "Unable to obtain Medusa version from $MEDUSA_BIN"
fi

log INFO "Workflow: Glassbox Medusa Dynamic Property Fuzzing Agent"
log INFO "Executable: $MEDUSA_BIN"
log INFO "Version: $MEDUSA_VERSION"
log INFO "Target: $CANONICAL_TARGET"
if [[ -n "$CONFIG" ]]; then
  log INFO "Configuration: $CONFIG"
fi

# Check Python environment
command -v python3 >/dev/null 2>&1 ||
  die_code 3 "Required runtime not found: python3"

ORCHESTRATOR="$SCRIPT_DIR/medusa_orchestrator.py"
[[ -f "$ORCHESTRATOR" ]] ||
  die_code 3 "Glassbox orchestrator engine not found at $ORCHESTRATOR"

# --- Check for Operator-Reviewed MEDUSA_COMMAND ---
if [[ -n "${MEDUSA_COMMAND:-}" ]]; then
  [[ "$MEDUSA_COMMAND" == /* ]] ||
    die_code 2 "MEDUSA_COMMAND must be an absolute executable path"
  [[ -x "$MEDUSA_COMMAND" ]] ||
    die_code 2 "Configured fuzzing command is not executable: $MEDUSA_COMMAND"

  log INFO "Operator-reviewed fuzzing command configured: $MEDUSA_COMMAND"
fi

# --- Build Orchestrator Arguments ---
ORCHESTRATOR_ARGS=(
  "--slug" "$SLUG"
  "--target" "$CANONICAL_TARGET"
  "--output-dir" "$CANONICAL_OUTPUT_DIR"
  "--timeout" "$TIMEOUT"
)

if [[ -n "${MEDUSA_COMMAND:-}" ]]; then
  ORCHESTRATOR_ARGS+=("--medusa-command" "$MEDUSA_COMMAND")
fi

if [[ -n "$CONFIG" ]]; then
  ORCHESTRATOR_ARGS+=("--config" "$CONFIG")
fi

if [[ -n "$TEST_LIMIT" ]]; then
  ORCHESTRATOR_ARGS+=("--test-limit" "$TEST_LIMIT")
fi

if [[ -n "$WORKERS" ]]; then
  ORCHESTRATOR_ARGS+=("--workers" "$WORKERS")
fi

if [[ -n "$SEED" ]]; then
  ORCHESTRATOR_ARGS+=("--seed" "$SEED")
fi

if [[ "$DRY_RUN" == true || "$CONFIRM" != true ]]; then
  ORCHESTRATOR_ARGS+=("--dry-run")
else
  ORCHESTRATOR_ARGS+=("--confirm")
fi

# Forward Simulation Flags
if [[ "$FAIL_SIM" == true ]]; then
  ORCHESTRATOR_ARGS+=("--fail-sim")
fi
if [[ "$TIMEOUT_SIM" == true ]]; then
  ORCHESTRATOR_ARGS+=("--timeout-sim")
fi
if [[ "$CORRUPT_SIM" == true ]]; then
  ORCHESTRATOR_ARGS+=("--corrupt-sim")
fi
if [[ "$CLEAN_SIM" == true ]]; then
  ORCHESTRATOR_ARGS+=("--clean-sim")
fi
if [[ "$FALSIFY_SIM" == true ]]; then
  ORCHESTRATOR_ARGS+=("--falsify-sim")
fi
if [[ "$DIGEST_MISMATCH_SIM" == true ]]; then
  ORCHESTRATOR_ARGS+=("--digest-mismatch-sim")
fi

# Execute Glassbox Mirror Plane Orchestrator
CLEANUP_REQUIRED=true
exec python3 "$ORCHESTRATOR" "${ORCHESTRATOR_ARGS[@]}"
