#!/usr/bin/env bash
# ==============================================================================
# Pack C — Glassbox Mirror Plane Echidna Dynamic Fuzzing Workflow
# Version: 2.0.0
# Architecture: Universal Adaptive Security Verification / Glassbox Mirror Plane
# Role: Execution Wrapper & Hardened Entrypoint
# Mission: Safely validate arguments, inspect Echidna CLI compatibility, enforce
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
CONTRACT=""
TEST_MODE="property"
TEST_LIMIT=""
SEED=""
TIMEOUT=60
ARTIFACT_DIR=""

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
  workflow-echidna.sh [options]

Pack C — Glassbox Mirror Plane Echidna Dynamic Fuzzing Workflow

Options:
  --slug SLUG                  Target bounty workspace under bounties/ (default: base)
  --target PATH                Solidity target directory or source file (default: bounties/<slug>/contracts)
  --config PATH                Echidna configuration YAML/JSON file
  --contract CONTRACT          Specific contract name to analyze
  --test-mode MODE             Echidna test mode: property, assertion, overflow, exploration (default: property)
  --test-limit INTEGER         Maximum number of test sequences to execute
  --seed INTEGER               Deterministic random seed (non-negative integer)
  --timeout SECONDS            Campaign timeout in seconds (default: 60)
  --artifacts, --output-dir P  Directory for campaign output artifacts
  --dry-run                    Validate prerequisites and preview without running fuzzing
  --confirm                    Explicitly authorize live fuzzing execution
  --fail-sim                   Simulate execution failure (for adversarial testing)
  --timeout-sim                Simulate execution timeout (for deadline recovery testing)
  --corrupt-sim                Simulate corrupt artifact payload
  --clean-sim                  Simulate clean campaign with all properties passing
  --falsify-sim                Simulate campaign falsifying an invariant with counterexamples
  --digest-mismatch-sim        Simulate cryptographic digest mismatch
  -h, --help                   Display this help message and exit 0

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
    --contract)
      need_value "$@"
      CONTRACT="$2"
      shift 2
      ;;
    --test-mode)
      need_value "$@"
      TEST_MODE="$2"
      shift 2
      ;;
    --test-limit)
      need_value "$@"
      TEST_LIMIT="$2"
      shift 2
      ;;
    --seed)
      need_value "$@"
      SEED="$2"
      shift 2
      ;;
    --timeout)
      need_value "$@"
      TIMEOUT="$2"
      shift 2
      ;;
    --artifacts|--output-dir)
      need_value "$@"
      ARTIFACT_DIR="$2"
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

if [[ -z "$ARTIFACT_DIR" ]]; then
  ARTIFACT_DIR="$BOUNTY_DIR/scans/echidna"
else
  if [[ "$ARTIFACT_DIR" != /* ]]; then
    ARTIFACT_DIR="$CANONICAL_REPO/$ARTIFACT_DIR"
  fi
fi

CANONICAL_TARGET="$(realpath -m "$TARGET")"
CANONICAL_ARTIFACT_DIR="$(realpath -m "$ARTIFACT_DIR")"

# --- Strict Path Containment Checks ---
if ! is_contained "$CANONICAL_TARGET" "$CANONICAL_REPO"; then
  die_code 2 "Target path '$CANONICAL_TARGET' escapes workspace repository root '$CANONICAL_REPO'"
fi

if ! is_contained "$CANONICAL_ARTIFACT_DIR" "$CANONICAL_REPO"; then
  die_code 2 "Artifact directory '$CANONICAL_ARTIFACT_DIR' escapes workspace repository root '$CANONICAL_REPO'"
fi

# Prevent output directory from being inside target contracts directory
if [[ "$CANONICAL_TARGET" != "$BOUNTY_DIR" ]]; then
  case "$CANONICAL_ARTIFACT_DIR/" in
    "$CANONICAL_TARGET/"*)
      die_code 2 "Artifact directory '$CANONICAL_ARTIFACT_DIR' must not be inside target directory '$CANONICAL_TARGET'"
      ;;
  esac
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
ECHIDNA_BIN="$(command -v echidna || true)"
if [[ -z "$ECHIDNA_BIN" ]]; then
  if [[ -x "$HOME/.local/bin/echidna" ]]; then
    ECHIDNA_BIN="$HOME/.local/bin/echidna"
  elif [[ -x "/usr/local/bin/echidna" ]]; then
    ECHIDNA_BIN="/usr/local/bin/echidna"
  fi
fi

if [[ -z "$ECHIDNA_BIN" || ! -x "$ECHIDNA_BIN" ]]; then
  if [[ "$DRY_RUN" == true || "$CONFIRM" == false ]]; then
    ECHIDNA_BIN="echidna"
    ECHIDNA_VERSION="Echidna (dry-run simulation)"
  else
    die_code 3 "Echidna executable not found on PATH or in standard user locations"
  fi
else
  ECHIDNA_VERSION="$("$ECHIDNA_BIN" --version 2>&1 | head -n 1)" ||
    die_code 3 "Unable to obtain Echidna version from $ECHIDNA_BIN"
fi

log INFO "Workflow: Glassbox Echidna Dynamic Fuzzing Agent"
log INFO "Executable: $ECHIDNA_BIN"
log INFO "Version: $ECHIDNA_VERSION"
log INFO "Target: $CANONICAL_TARGET"
if [[ -n "$CONFIG" ]]; then
  log INFO "Configuration: $CONFIG"
fi

# Check Python environment
command -v python3 >/dev/null 2>&1 ||
  die_code 3 "Required runtime not found: python3"

ORCHESTRATOR="$SCRIPT_DIR/echidna_orchestrator.py"
[[ -f "$ORCHESTRATOR" ]] ||
  die_code 3 "Glassbox orchestrator engine not found at $ORCHESTRATOR"

# --- Build Orchestrator Arguments ---
ORCHESTRATOR_ARGS=(
  "--slug" "$SLUG"
  "--target" "$CANONICAL_TARGET"
  "--output-dir" "$CANONICAL_ARTIFACT_DIR"
  "--timeout" "$TIMEOUT"
  "--test-mode" "$TEST_MODE"
)

if [[ -n "$CONFIG" ]]; then
  ORCHESTRATOR_ARGS+=("--config" "$CONFIG")
fi

if [[ -n "$CONTRACT" ]]; then
  ORCHESTRATOR_ARGS+=("--contract" "$CONTRACT")
fi

if [[ -n "$TEST_LIMIT" ]]; then
  ORCHESTRATOR_ARGS+=("--test-limit" "$TEST_LIMIT")
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
EOF
