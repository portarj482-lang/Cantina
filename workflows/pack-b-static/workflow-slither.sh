#!/usr/bin/env bash
# ==============================================================================
# Pack B — Oracle Agentic Mesh (OAM) Slither Static Analysis Workflow
# Version: 1.0.0
# Capability: SAMA (Security Analysis Meta-Agent)
# Architecture: Refractor Mesh / OAM
# Mission: Execute bounded static analysis with Slither, strictly enforce
#          authorization and path containment, independently validate reports,
#          and publish standard evidence envelopes under policy governance.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd -- "${BASH_SOURCE[0]%/*}" >/dev/null 2>&1 && pwd -P)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd -P)"

DRY_RUN=false
CONFIRM=false
SLUG="base"
TARGET=""
OUTPUT_DIR=""
TIMEOUT=300

# Simulation / Negative Control Flags
SCANNER_FAIL_SIM=false
FAIL_RECEIPT_SIM=false
TIMEOUT_SIM=false
CORRUPT_REPORT_SIM=false
DIGEST_MISMATCH_SIM=false
ATTRIBUTION_MISMATCH_SIM=false
EMPTY_REPORT_SIM=false
VERSION_DRIFT_SIM=false
CLEAN_SIM=false

usage() {
  cat >&2 <<EOF
Usage: $(basename "$0") [--dry-run] [--confirm] [--slug SLUG] [--target TARGET] [--output-dir DIR] [options]

Pack B — SAMA Slither Static Analysis Workflow under Refractor Mesh / OAM

Options:
  --dry-run                    Preview scan plan without execution (default if --confirm omitted)
  --confirm                    Authorize verified Slither execution and evidence persistence
  --slug SLUG                  Target bounty workspace under bounties/ (default: base)
  --target TARGET              Explicit target source directory (defaults to bounties/<slug>/contracts)
  --output-dir DIR             Explicit scan output directory (defaults to bounties/<slug>/scans/slither)
  --timeout SECONDS            Execution timeout in seconds (default: 300)
  --scanner-fail-sim           Simulate scanner nonzero exit code (for adversarial testing)
  --fail-receipt-sim           Simulate receipt serialization failure
  --timeout-sim                Simulate execution timeout
  --corrupt-report-sim         Simulate corrupted report JSON/SARIF
  --digest-mismatch-sim        Simulate receipt SHA-256 digest mismatch
  --attribution-mismatch-sim   Simulate findings attributed to external scope
  --empty-report-sim           Simulate missing report file when scanner exits 0
  --version-drift-sim          Simulate unverified scanner version drift
  --clean-sim                  Simulate clean report (zero findings detected)
  -h, --help                   Show this help message and exit 0

Exit codes:
  0  Success (including verified dry-run preview, clean completion, findings completion)
  1  Execution failure, schema failure, or independent validation failure
  2  Invalid command-line arguments, path traversal, or symlink scope escape
  3  Missing bounty directory, missing adapter, or unresolvable scope
EOF
  exit "${1:-0}"
}

# --- Check realpath -m availability ---
if ! command -v realpath >/dev/null 2>&1 || ! realpath -m . >/dev/null 2>&1; then
  echo "Error: 'realpath -m' utility is required but not installed or functional." >&2
  exit 3
fi

# Path containment helper: ensures path is strictly within root, preventing prefix substring escapes
is_contained() {
  local p="$1"
  local root="$2"
  [[ "$p" == "$root" || "$p" == "$root/"* ]]
}

# --- Strict Option Parsing ---
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
    --target)
      if [[ $# -lt 2 || -z "${2:-}" || "${2:-}" == --* ]]; then
        echo "Error: --target requires a non-empty value" >&2
        usage 2
      fi
      TARGET="$2"
      shift 2
      ;;
    --output-dir)
      if [[ $# -lt 2 || -z "${2:-}" || "${2:-}" == --* ]]; then
        echo "Error: --output-dir requires a non-empty value" >&2
        usage 2
      fi
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --timeout)
      if [[ $# -lt 2 || -z "${2:-}" || "${2:-}" == --* || ! "${2:-}" =~ ^[0-9]+$ || "${2:-}" -le 0 ]]; then
        echo "Error: --timeout requires a positive numeric value" >&2
        usage 2
      fi
      TIMEOUT="$2"
      shift 2
      ;;
    --scanner-fail-sim)
      SCANNER_FAIL_SIM=true
      shift
      ;;
    --fail-receipt-sim)
      FAIL_RECEIPT_SIM=true
      shift
      ;;
    --timeout-sim)
      TIMEOUT_SIM=true
      shift
      ;;
    --corrupt-report-sim)
      CORRUPT_REPORT_SIM=true
      shift
      ;;
    --digest-mismatch-sim)
      DIGEST_MISMATCH_SIM=true
      shift
      ;;
    --attribution-mismatch-sim)
      ATTRIBUTION_MISMATCH_SIM=true
      shift
      ;;
    --empty-report-sim)
      EMPTY_REPORT_SIM=true
      shift
      ;;
    --version-drift-sim)
      VERSION_DRIFT_SIM=true
      shift
      ;;
    --clean-sim)
      CLEAN_SIM=true
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

# --- Default Target & Output Resolution ---
if [[ -z "$TARGET" ]]; then
  if [[ -d "$BOUNTY_DIR/contracts" ]]; then
    TARGET="$BOUNTY_DIR/contracts"
  else
    TARGET="$BOUNTY_DIR"
  fi
else
  # If TARGET is relative, make it relative to REPO_ROOT
  if [[ "$TARGET" != /* ]]; then
    TARGET="$REPO_ROOT/$TARGET"
  fi
fi

if [[ -z "$OUTPUT_DIR" ]]; then
  OUTPUT_DIR="$BOUNTY_DIR/scans/slither"
else
  if [[ "$OUTPUT_DIR" != /* ]]; then
    OUTPUT_DIR="$REPO_ROOT/$OUTPUT_DIR"
  fi
fi

# --- Strict Canonical Path Containment Checks (realpath -m) ---
CANONICAL_TARGET="$(realpath -m "$TARGET")"
CANONICAL_OUTPUT="$(realpath -m "$OUTPUT_DIR")"
CANONICAL_REPO="$(realpath "$REPO_ROOT")"

# Check symlink escapes
if [[ -L "$TARGET" ]]; then
  RESOLVED_TARGET="$(realpath "$TARGET")"
  if ! is_contained "$RESOLVED_TARGET" "$CANONICAL_REPO"; then
    echo "Error: Symlink target '$RESOLVED_TARGET' escapes repository root '$CANONICAL_REPO'" >&2
    exit 2
  fi
fi

if [[ -L "$OUTPUT_DIR" ]]; then
  RESOLVED_OUTPUT="$(realpath "$OUTPUT_DIR")"
  if ! is_contained "$RESOLVED_OUTPUT" "$CANONICAL_REPO"; then
    echo "Error: Symlink output directory '$RESOLVED_OUTPUT' escapes repository root '$CANONICAL_REPO'" >&2
    exit 2
  fi
fi

# Also inspect parent directory of output if it exists as symlink
OUTPUT_PARENT="$(dirname "$CANONICAL_OUTPUT")"
if [[ -L "$OUTPUT_PARENT" ]]; then
  RESOLVED_PARENT="$(realpath "$OUTPUT_PARENT")"
  if ! is_contained "$RESOLVED_PARENT" "$CANONICAL_REPO"; then
    echo "Error: Output parent symlink '$RESOLVED_PARENT' escapes repository root '$CANONICAL_REPO'" >&2
    exit 2
  fi
fi

# Check canonical containment
if ! is_contained "$CANONICAL_TARGET" "$CANONICAL_REPO"; then
  echo "Error: Target directory '$CANONICAL_TARGET' escapes repository root '$CANONICAL_REPO'" >&2
  exit 2
fi

if ! is_contained "$CANONICAL_OUTPUT" "$CANONICAL_REPO"; then
  echo "Error: Output directory '$CANONICAL_OUTPUT' escapes repository root '$CANONICAL_REPO'" >&2
  exit 2
fi

echo "=== [Pack B] SAMA / OAM Workflow: Slither Static Analysis ($SLUG) ==="

# --- Preflight Directory & Environment Checks ---
if [[ ! -d "$BOUNTY_DIR" ]]; then
  echo "Error: Target bounty directory does not exist: $BOUNTY_DIR" >&2
  exit 3
fi

if [[ ! -d "$CANONICAL_TARGET" ]]; then
  echo "Error: Target directory does not exist: $CANONICAL_TARGET" >&2
  exit 3
fi

# Prevent output from being placed inside the source tree being analyzed
if [[ "$CANONICAL_TARGET" != "$BOUNTY_DIR" ]]; then
  case "$CANONICAL_OUTPUT/" in
    "$CANONICAL_TARGET/"*)
      echo "Error: Output directory '$CANONICAL_OUTPUT' must not be inside target directory '$CANONICAL_TARGET'" >&2
      exit 2
      ;;
  esac
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 is required on PATH" >&2
  exit 3
fi

ADAPTER="$REPO_ROOT/.agents/skills/qrpe/adapters/slither_adapter.py"
if [[ ! -f "$ADAPTER" ]]; then
  echo "Error: Slither adapter not found at $ADAPTER" >&2
  exit 3
fi

# Prepare arguments for Refractor Mesh Orchestrator
PYTHON_ARGS=(
  "--slug" "$SLUG"
  "--target" "$CANONICAL_TARGET"
  "--output-dir" "$CANONICAL_OUTPUT"
  "--timeout" "$TIMEOUT"
  "--adapter" "$ADAPTER"
)

if [[ "$DRY_RUN" == true || "$CONFIRM" == false ]]; then
  PYTHON_ARGS+=("--dry-run")
else
  PYTHON_ARGS+=("--confirm")
fi

if [[ "$SCANNER_FAIL_SIM" == true ]]; then
  PYTHON_ARGS+=("--scanner-fail-sim")
fi

if [[ "$FAIL_RECEIPT_SIM" == true ]]; then
  PYTHON_ARGS+=("--fail-receipt-sim")
fi

if [[ "$TIMEOUT_SIM" == true ]]; then
  PYTHON_ARGS+=("--timeout-sim")
fi

if [[ "$CORRUPT_REPORT_SIM" == true ]]; then
  PYTHON_ARGS+=("--corrupt-report-sim")
fi

if [[ "$DIGEST_MISMATCH_SIM" == true ]]; then
  PYTHON_ARGS+=("--digest-mismatch-sim")
fi

if [[ "$ATTRIBUTION_MISMATCH_SIM" == true ]]; then
  PYTHON_ARGS+=("--attribution-mismatch-sim")
fi

if [[ "$EMPTY_REPORT_SIM" == true ]]; then
  PYTHON_ARGS+=("--empty-report-sim")
fi

if [[ "$VERSION_DRIFT_SIM" == true ]]; then
  PYTHON_ARGS+=("--version-drift-sim")
fi

if [[ "$CLEAN_SIM" == true ]]; then
  PYTHON_ARGS+=("--clean-sim")
fi

# Execute Refractor Mesh Orchestrator
exec python3 "$SCRIPT_DIR/slither_orchestrator.py" "${PYTHON_ARGS[@]}"
