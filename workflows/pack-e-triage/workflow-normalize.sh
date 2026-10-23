#!/usr/bin/env bash
# Pack E Workflow: Normalize Findings
# Meta Persona: Cantina Security Findings Normalization Orchestrator
set -euo pipefail

SCRIPT_DIR="$(cd -- "${BASH_SOURCE[0]%/*}" >/dev/null 2>&1 && pwd -P)"
REPO_ROOT="${CANTINA_REPO_ROOT:-/home/nova/projects/cantina}"

DRY_RUN=false
CONFIRM=false
SLUG="base"

usage() {
  cat <<'EOF' >&2
Usage: workflow-normalize.sh [--slug SLUG] [--dry-run] [--confirm] [-h|--help]

Options:
  --slug SLUG    Target bounty slug (default: base, pattern: ^[A-Za-z0-9][A-Za-z0-9_-]*$)
  --dry-run      Preview normalization destination without writing (default behavior if unconfirmed)
  --confirm      Authorize normalization write and durable replacement
  -h, --help     Show this help message
EOF
}

# Phase A — Initialize & Parse arguments
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
        echo "[ERROR] init: Missing value for --slug" >&2
        usage
        exit 1
      fi
      SLUG="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[ERROR] init: Malformed or unsupported option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

# Argument validation: slug policy
SLUG_REGEX='^[A-Za-z0-9][A-Za-z0-9_-]*$'
if [[ ! "$SLUG" =~ $SLUG_REGEX ]]; then
  echo "[ERROR] init: Invalid slug format '$SLUG'. Must match $SLUG_REGEX without path traversal." >&2
  exit 1
fi

if [[ "$SLUG" == *"/"* || "$SLUG" == *"\\"* || "$SLUG" == *".."* ]]; then
  echo "[ERROR] init: Path separators or traversal components prohibited in slug." >&2
  exit 1
fi

BOUNTY_DIR="$REPO_ROOT/bounties/$SLUG"
SCANS_DIR="$BOUNTY_DIR/scans"
OUT_FILE="$SCANS_DIR/findings_normalized.json"

echo "=== [Pack E] Workflow: Normalize Findings ($SLUG) ==="

# Authorization Invariant:
# Write allowed only when DRY_RUN=false AND CONFIRM=true.
# If --dry-run is specified, it overrides --confirm.
if [[ "$DRY_RUN" == true || "$CONFIRM" == false ]]; then
  echo "[DRY-RUN] Will normalize findings into $OUT_FILE"
  exit 0
fi

# Trap to guarantee temporary file cleanup
trap 'rm -f "$SCANS_DIR"/findings_normalized.tmp.* 2>/dev/null || true' EXIT

# Phase B & F — Prepare destination & Atomic persist
if ! mkdir -p "$SCANS_DIR" 2>/dev/null; then
  echo "[ERROR] persist: Destination permission failure or cannot create scans directory: $SCANS_DIR" >&2
  exit 1
fi

# Destination containment check
RESOLVED_SCANS_DIR="$(cd "$SCANS_DIR" && pwd -P)"
RESOLVED_REPO_ROOT="$(cd "$REPO_ROOT" && pwd -P)"
if [[ "$RESOLVED_SCANS_DIR" != "$RESOLVED_REPO_ROOT"/bounties/* ]]; then
  echo "[ERROR] persist: Destination path escaped workspace boundary." >&2
  exit 1
fi

# Phase C, D, E & F — Execute dedicated Python normalization engine
if ! python3 "$SCRIPT_DIR/normalizer.py" --slug "$SLUG" --repo-root "$REPO_ROOT" --confirm >/dev/null 2>&1; then
  echo "[ERROR] normalize: Normalization engine execution failed." >&2
  exit 1
fi

# Phase G — Verify and report
if ! python3 "$SCRIPT_DIR/validate_schemas.py" --normalized "$OUT_FILE" >/dev/null 2>&1; then
  echo "[ERROR] verify: Post-write verification failed for generated JSON artifact." >&2
  exit 1
fi

echo "[OK] Normalized findings saved to $OUT_FILE"
