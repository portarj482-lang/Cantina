#!/usr/bin/env bash
# Pack E Triage: Hallucination & Citation Dropper
# Audits report citations against a pinned Git commit revision.
set -euo pipefail

SCRIPT_DIR="$(cd -- "${BASH_SOURCE[0]%/*}" >/dev/null 2>&1 && pwd -P)"
PYTHON_ENGINE="$SCRIPT_DIR/hallucination_dropper.py"

usage() {
  cat <<'EOF' >&2
Usage: workflow-hallucination-dropper.sh --slug SLUG [OPTIONS]

Options:
  --slug SLUG               Bounty slug (must match ^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$)
  --sources GLOB[,GLOB...]  Repository-relative glob patterns of report files (repeatable)
  --adapter PYTHON_MODULE   Pluggable python adapter for citation extraction
  --commit COMMIT_ID        Pinned Git commit to verify against (defaults to HEAD)
  --dry-run                 Preview audit without writing artifacts (default)
  --confirm                 Authorize atomic artifact creation and replacement
  -h, --help                Show this help message

Exit codes:
  0 - Verification succeeded, or preview completed without operational errors
  1 - One or more citations failed verification or no citations found
  2 - Output creation, synchronization, or replacement failed
  3 - Required dependency is missing or unavailable
  4 - Invalid arguments, invalid slug, or invalid option combination
EOF
}

log_bash_event() {
  local level="$1" event="$2" msg="$3" err="${4:-null}"
  local ts
  ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date +"%Y-%m-%dT%H:%M:%SZ")"
  if command -v python3 >/dev/null 2>&1; then
    python3 -c "import json, sys; print(json.dumps({'timestamp': sys.argv[1], 'level': sys.argv[2], 'event': sys.argv[3], 'component': 'workflow_bash', 'slug': sys.argv[4] if sys.argv[4] else None, 'pinned_commit': None, 'source': None, 'processed_count': 0, 'error_code': sys.argv[5] if sys.argv[5] != 'null' else None, 'message': sys.argv[6]}, ensure_ascii=False))" \
      "$ts" "$level" "$event" "${SLUG:-}" "$err" "$msg" >&2 || true
  else
    printf '{"timestamp":"%s","level":"%s","event":"%s","component":"workflow_bash","slug":%s,"pinned_commit":null,"source":null,"processed_count":0,"error_code":%s,"message":"%s"}\n' \
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
SLUG=""
SOURCES=""
ADAPTER=""
COMMIT=""
DRY_RUN=false
CONFIRM=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --slug)
      if [[ $# -lt 2 || "$2" == --* ]]; then
        log_bash_event "ERROR" "MISSING_ARG_VALUE" "Missing value for --slug" "INVALID_ARGUMENTS"
        echo "Error: Missing value for --slug" >&2
        usage
        exit 4
      fi
      if [[ -n "$SLUG" && "$SLUG" != "$2" ]]; then
        log_bash_event "ERROR" "CONFLICTING_OPTIONS" "Conflicting duplicate --slug options provided: '$SLUG' vs '$2'" "INVALID_ARGUMENTS"
        echo "Error: Conflicting duplicate --slug options provided." >&2
        usage
        exit 4
      fi
      SLUG="$2"
      shift 2
      ;;
    --sources)
      if [[ $# -lt 2 || "$2" == --* ]]; then
        log_bash_event "ERROR" "MISSING_ARG_VALUE" "Missing value for --sources" "INVALID_ARGUMENTS"
        echo "Error: Missing value for --sources" >&2
        usage
        exit 4
      fi
      if [[ -n "$SOURCES" ]]; then
        SOURCES="$SOURCES,$2"
      else
        SOURCES="$2"
      fi
      shift 2
      ;;
    --adapter)
      if [[ $# -lt 2 || "$2" == --* ]]; then
        log_bash_event "ERROR" "MISSING_ARG_VALUE" "Missing value for --adapter" "INVALID_ARGUMENTS"
        echo "Error: Missing value for --adapter" >&2
        usage
        exit 4
      fi
      if [[ -n "$ADAPTER" && "$ADAPTER" != "$2" ]]; then
        log_bash_event "ERROR" "CONFLICTING_OPTIONS" "Conflicting duplicate --adapter options provided: '$ADAPTER' vs '$2'" "INVALID_ARGUMENTS"
        echo "Error: Conflicting duplicate --adapter options provided." >&2
        usage
        exit 4
      fi
      ADAPTER="$2"
      shift 2
      ;;
    --commit)
      if [[ $# -lt 2 || "$2" == --* ]]; then
        log_bash_event "ERROR" "MISSING_ARG_VALUE" "Missing value for --commit" "INVALID_ARGUMENTS"
        echo "Error: Missing value for --commit" >&2
        usage
        exit 4
      fi
      if [[ -n "$COMMIT" && "$COMMIT" != "$2" ]]; then
        log_bash_event "ERROR" "CONFLICTING_OPTIONS" "Conflicting duplicate --commit options provided: '$COMMIT' vs '$2'" "INVALID_ARGUMENTS"
        echo "Error: Conflicting duplicate --commit options provided." >&2
        usage
        exit 4
      fi
      COMMIT="$2"
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
      log_bash_event "ERROR" "UNKNOWN_FLAG" "Unknown flag: $1" "INVALID_ARGUMENTS"
      echo "Error: Unknown flag: $1" >&2
      usage
      exit 4
      ;;
  esac
done

if [[ -z "$SLUG" ]]; then
  log_bash_event "ERROR" "MISSING_SLUG" "Required argument --slug is missing." "INVALID_ARGUMENTS"
  echo "Error: Required argument --slug is missing." >&2
  usage
  exit 4
fi

# Slug contract validation
if ! [[ "$SLUG" =~ ^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$ ]]; then
  log_bash_event "ERROR" "INVALID_SLUG" "Slug '$SLUG' violates contract ^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$" "INVALID_SLUG"
  echo "Error: Invalid slug '$SLUG'. Must match ^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$" >&2
  usage
  exit 4
fi

# Conflicting flags check
if [[ "$DRY_RUN" == true && "$CONFIRM" == true ]]; then
  log_bash_event "ERROR" "CONFLICTING_FLAGS" "Cannot specify both --dry-run and --confirm." "INVALID_ARGUMENTS"
  echo "Error: Cannot specify both --dry-run and --confirm." >&2
  usage
  exit 4
fi

# 3. Path & Filesystem Safety Checks
REPO_ROOT="${REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd -P)}"
OUT_DIR="$REPO_ROOT/bounties/$SLUG/scans"

# Validate --sources paths
if [[ -n "$SOURCES" ]]; then
  IFS=',' read -ra SRC_LIST <<< "$SOURCES"
  for s_pat in "${SRC_LIST[@]}"; do
    s_clean="$(echo "$s_pat" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
    if [[ -z "$s_clean" ]]; then
      log_bash_event "ERROR" "INVALID_SOURCE_PATH" "Empty source pattern specified in --sources" "INVALID_ARGUMENTS"
      echo "Error: Empty source pattern specified in --sources" >&2
      usage
      exit 4
    fi
    if [[ "$s_clean" == *".."* ]]; then
      log_bash_event "ERROR" "INVALID_SOURCE_PATH" "Traversal patterns rejected in --sources: '$s_clean'" "INVALID_ARGUMENTS"
      echo "Error: Path traversal is rejected in --sources: '$s_clean'" >&2
      usage
      exit 4
    fi
    if [[ "$s_clean" == /* || "$s_clean" == \\* ]]; then
      log_bash_event "ERROR" "INVALID_SOURCE_PATH" "Absolute paths rejected in --sources: '$s_clean'" "INVALID_ARGUMENTS"
      echo "Error: Absolute paths are rejected in --sources: '$s_clean'" >&2
      usage
      exit 4
    fi
  done
fi

# Validate --adapter path/module
if [[ -n "$ADAPTER" ]]; then
  if [[ "$ADAPTER" == *".."* ]]; then
    log_bash_event "ERROR" "INVALID_ADAPTER_PATH" "Traversal rejected in --adapter: '$ADAPTER'" "INVALID_ARGUMENTS"
    echo "Error: Traversal is rejected in --adapter: '$ADAPTER'" >&2
    usage
    exit 4
  fi
  if [[ "$ADAPTER" == /* || "$ADAPTER" == \\* ]]; then
    if [[ "$ADAPTER" == "$REPO_ROOT"/* ]]; then
      ADAPTER="${ADAPTER#$REPO_ROOT/}"
    else
      log_bash_event "ERROR" "INVALID_ADAPTER_PATH" "External absolute path rejected in --adapter: '$ADAPTER'" "INVALID_ARGUMENTS"
      echo "Error: External absolute path rejected in --adapter: '$ADAPTER'" >&2
      usage
      exit 4
    fi
  fi
fi

# Validate --commit ref format
if [[ -n "$COMMIT" ]]; then
  if ! [[ "$COMMIT" =~ ^[A-Za-z0-9_./@~^-]+$ ]]; then
    log_bash_event "ERROR" "INVALID_COMMIT_REF" "Invalid Git commit reference syntax: '$COMMIT'" "INVALID_ARGUMENTS"
    echo "Error: Invalid Git commit reference: '$COMMIT'" >&2
    usage
    exit 4
  fi
fi

# Symlink checks on output paths
if [[ -L "$OUT_DIR" ]]; then
  log_bash_event "ERROR" "SYMLINK_OUTPUT_DIR" "Output directory '$OUT_DIR' is a symlink. Refusing execution." "UNSAFE_OUTPUT_DIR"
  echo "Error: Output directory '$OUT_DIR' is a symlink. Refusing execution." >&2
  exit 2
fi

if [[ -L "$REPO_ROOT/bounties/$SLUG" ]]; then
  log_bash_event "ERROR" "SYMLINK_BOUNTY_DIR" "Bounty directory '$REPO_ROOT/bounties/$SLUG' is a symlink. Refusing execution." "UNSAFE_OUTPUT_DIR"
  echo "Error: Bounty directory '$REPO_ROOT/bounties/$SLUG' is a symlink. Refusing execution." >&2
  exit 2
fi

# Trap cleanup only after symlinks are verified safe
cleanup() {
  if [[ -d "$OUT_DIR" && ! -L "$OUT_DIR" && ! -L "$REPO_ROOT/bounties/$SLUG" ]]; then
    rm -f "$OUT_DIR"/.*.tmp-* 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

# 4. Invoke Core Python Verification Engine
PY_ARGS=(
  "--repo-root" "$REPO_ROOT"
  "--slug" "$SLUG"
)

if [[ -n "$SOURCES" ]]; then
  PY_ARGS+=("--sources" "$SOURCES")
fi

if [[ -n "$ADAPTER" ]]; then
  PY_ARGS+=("--adapter" "$ADAPTER")
fi

if [[ -n "$COMMIT" ]]; then
  PY_ARGS+=("--commit" "$COMMIT")
fi

if [[ "$CONFIRM" == true ]]; then
  PY_ARGS+=("--confirm")
fi

if [[ "$DRY_RUN" == true ]]; then
  PY_ARGS+=("--dry-run")
fi

PYTHONPATH="$SCRIPT_DIR:${PYTHONPATH:-}" python3 "$PYTHON_ENGINE" "${PY_ARGS[@]}"
