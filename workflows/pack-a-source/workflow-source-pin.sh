#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

REPO_ROOT="${REPO_ROOT:-/home/nova/projects/cantina}"

DRY_RUN=false
CONFIRM=false
SLUG="base"

usage() {
    cat <<'USAGE'
Usage: source-pin.sh [--dry-run] [--confirm] [--slug IDENTIFIER]

Options:
  --dry-run   Validate inputs and report intended output without writing.
  --confirm   Authorize creation or replacement of pin.json.
  --slug ID   Select a bounty slug (default: base).
  -h, --help  Show this help message.

Without --confirm, the workflow validates but does not write.
If --dry-run and --confirm are both supplied, no write occurs.
USAGE
}

fail() {
    local category="E_INTERNAL"
    if [[ $# -ge 2 ]]; then
        category="$1"
        shift
    fi
    printf '[FAIL] [%s] %s\n' "$category" "$*" >&2
    exit 1
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
        --slug)
            (($# >= 2)) || fail "E_ARGUMENT" "--slug requires an identifier"
            SLUG="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            fail "E_ARGUMENT" "Unknown argument: $1"
            ;;
    esac
done

[[ "$SLUG" =~ ^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$ ]] || fail "E_PATH_INVALID" "Invalid slug: $SLUG"

[[ -d "$REPO_ROOT" ]] || fail "E_PATH_INVALID" "Repository root does not exist: $REPO_ROOT"

REPO_ROOT=$(cd -- "$REPO_ROOT" && pwd -P)
readonly REPO_ROOT

BOUNTY_DIR="$REPO_ROOT/bounties/$SLUG"
SCOPE_FILE="$BOUNTY_DIR/scope.md"
SNAPSHOT_FILE="$BOUNTY_DIR/snapshots/scope.sha256"
SCANS_DIR="$BOUNTY_DIR/scans"
PIN_JSON="$SCANS_DIR/pin.json"
SCHEMA_FILE="$REPO_ROOT/workflows/pack-a-source/schemas/pin.schema.json"

printf '=== [Pack A] Workflow: Source Pin v1.0.0 (%s) ===\n' "$SLUG"
printf '  Repository Root: %s\n' "$REPO_ROOT"
printf '  Bounty Slug:     %s\n' "$SLUG"
printf '  Scope Path:      %s\n' "$SCOPE_FILE"
printf '  Snapshot Path:   %s\n' "$SNAPSHOT_FILE"

[[ -d "$BOUNTY_DIR" && ! -L "$BOUNTY_DIR" ]] || fail "E_PATH_INVALID" "Bounty directory missing or is a symlink: $BOUNTY_DIR"

[[ -f "$SCOPE_FILE" && ! -L "$SCOPE_FILE" && -r "$SCOPE_FILE" ]] || fail "E_SCOPE_MISSING" "Scope file missing, unreadable, or a symlink: $SCOPE_FILE"

[[ -f "$SNAPSHOT_FILE" && ! -L "$SNAPSHOT_FILE" && -r "$SNAPSHOT_FILE" ]] || fail "E_SNAPSHOT_MISSING" "Scope snapshot missing, unreadable, or a symlink: $SNAPSHOT_FILE"

# Require exactly one SHA-256 digest, optionally followed by a filename.
# Reject extra records, malformed digests, and unexpected filenames.
SNAPSHOT_LINE=$(<"$SNAPSHOT_FILE") || fail "E_SNAPSHOT_FORMAT" "Cannot read scope snapshot"

[[ "$SNAPSHOT_LINE" =~ ^([[:xdigit:]]{64})([[:space:]]+\*?scope\.md)?$ ]] || fail "E_SNAPSHOT_FORMAT" "Malformed scope snapshot"

EXPECTED_HASH="${BASH_REMATCH[1],,}"

calculate_hash() {
    sha256sum -- "$SCOPE_FILE" | awk '{print tolower($1)}'
}

ACTUAL_HASH=$(calculate_hash) || fail "E_INTERNAL" "Unable to calculate scope SHA-256"

printf '[VERIFY] Checking scope hash...\n'

[[ "$ACTUAL_HASH" == "$EXPECTED_HASH" ]] || fail "E_SCOPE_MISMATCH" "Scope hash mismatch. Expected: $EXPECTED_HASH, Actual: $ACTUAL_HASH"

printf '[OK] Scope hash verified: %s (matches snapshot)\n' "$ACTUAL_HASH"

if [[ "$DRY_RUN" == true || "$CONFIRM" == false ]]; then
    if [[ "$DRY_RUN" == true ]]; then
        printf '[DRY-RUN] Mode: DRY_RUN. Source pin verified. No files written.\n'
    else
        printf '[VALIDATION-ONLY] Mode: VALIDATION_ONLY. Source pin verified. Confirmation required to write.\n'
    fi
    printf '[INFO] Target output: %s\n' "$PIN_JSON"
    exit 0
fi

# Reject symlinked output directories and files.
if [[ -L "$SCANS_DIR" ]]; then
    fail "E_PATH_INVALID" "Output directory must not be a symlink: $SCANS_DIR"
fi

if [[ -e "$SCANS_DIR" && ! -d "$SCANS_DIR" ]]; then
    fail "E_PATH_INVALID" "Output path exists but is not a directory: $SCANS_DIR"
fi

if [[ -L "$PIN_JSON" ]]; then
    fail "E_PATH_INVALID" "Output file must not be a symlink: $PIN_JSON"
fi

# Test simulation hook for TOCTOU verification
if [[ "${TEST_SIMULATE_PREWRITE_CHANGE:-false}" == true ]]; then
    printf '\n# Concurrently appended untrusted byte\n' >> "$SCOPE_FILE"
fi

# Recheck immediately before writing to reduce stale-verification risk.
PREWRITE_HASH=$(calculate_hash) || fail "E_INTERNAL" "Unable to recheck scope SHA-256"

[[ "$PREWRITE_HASH" == "$EXPECTED_HASH" && "$PREWRITE_HASH" == "$ACTUAL_HASH" ]] || fail "E_SCOPE_MISMATCH" "Scope changed after initial verification"

# A trusted JSON serializer is required. Python is listed as PRESENT in
# the supplied registry; verify availability before relying on it.
command -v python3 >/dev/null 2>&1 || fail "E_TOOL_UNAVAILABLE" "python3 is required for safe JSON serialization"

mkdir -p -- "$SCANS_DIR" || fail "E_OUTPUT_WRITE" "Unable to create scans directory"

[[ -d "$SCANS_DIR" && ! -L "$SCANS_DIR" ]] || fail "E_OUTPUT_WRITE" "Output directory failed validation"

# Keep the temporary file on the same filesystem as the final artifact.
TMP_FILE=$(mktemp "$SCANS_DIR/.pin.json.XXXXXXXX") || fail "E_OUTPUT_WRITE" "Unable to create temporary artifact"

cleanup() {
    if [[ -n "${TMP_FILE:-}" && -f "$TMP_FILE" ]]; then
        rm -f -- "$TMP_FILE"
    fi
}
trap cleanup EXIT

export PIN_SLUG="$SLUG"
export PIN_SCOPE_FILE="bounties/$SLUG/scope.md"
export PIN_SCOPE_HASH="$ACTUAL_HASH"
export PIN_TIMESTAMP
PIN_TIMESTAMP=$(date -u '+%Y-%m-%dT%H:%M:%SZ') || fail "E_INTERNAL" "Unable to obtain UTC timestamp"
export PIN_TIMESTAMP

python3 - "$TMP_FILE" <<'PY' || fail "E_OUTPUT_WRITE" "Failed to serialize JSON record"
import json
import os
import sys

record = {
    "slug": os.environ["PIN_SLUG"],
    "scope_file": os.environ["PIN_SCOPE_FILE"],
    "scope_sha256": os.environ["PIN_SCOPE_HASH"],
    "timestamp": os.environ["PIN_TIMESTAMP"],
    "status": "PIN_VERIFIED",
}

with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump(record, f, indent=2, sort_keys=True)
    f.write("\n")
    f.flush()
    os.fsync(f.fileno())
PY

# Test simulation hook for corrupt JSON
if [[ "${TEST_SIMULATE_CORRUPT_JSON:-false}" == true ]]; then
    printf '{corrupt json' > "$TMP_FILE"
fi

python3 - "$TMP_FILE" "$SLUG" "$ACTUAL_HASH" "bounties/$SLUG/scope.md" "$SCHEMA_FILE" <<'PY' || fail "E_OUTPUT_WRITE" "Temporary artifact failed schema/value validation"
import json
import os
import sys
from datetime import datetime

path, expected_slug, expected_hash, expected_scope_file, schema_file = sys.argv[1:6]

with open(path, encoding="utf-8") as f:
    record = json.load(f)

assert record.get("slug") == expected_slug, f"Slug mismatch: {record.get('slug')} != {expected_slug}"
assert record.get("scope_sha256") == expected_hash, f"Hash mismatch: {record.get('scope_sha256')} != {expected_hash}"
assert record.get("status") == "PIN_VERIFIED", f"Status mismatch: {record.get('status')}"
assert record.get("scope_file") == expected_scope_file, f"Scope file mismatch: {record.get('scope_file')} != {expected_scope_file}"
ts = record.get("timestamp")
assert isinstance(ts, str), "Timestamp is not a string"
datetime.fromisoformat(ts.replace("Z", "+00:00"))

if os.path.isfile(schema_file):
    try:
        import jsonschema
        with open(schema_file, encoding="utf-8") as sf:
            schema = json.load(sf)
        jsonschema.validate(instance=record, schema=schema)
    except ImportError:
        pass
PY

# Test simulation hook for pre-commit change
if [[ "${TEST_SIMULATE_PRECOMMIT_CHANGE:-false}" == true ]]; then
    printf '\n# Concurrently appended byte before commit\n' >> "$SCOPE_FILE"
fi

# Final provenance check before atomic replacement.
FINAL_HASH=$(calculate_hash) || fail "E_INTERNAL" "Unable to perform final scope verification"

[[ "$FINAL_HASH" == "$EXPECTED_HASH" ]] || fail "E_SCOPE_MISMATCH" "Scope changed before artifact commit"

# GNU mv -T prevents treating an existing destination directory as a target.
mv -fT -- "$TMP_FILE" "$PIN_JSON" || fail "E_OUTPUT_WRITE" "Unable to commit pin artifact"

TMP_FILE=""

# Verify the committed artifact.
python3 - "$PIN_JSON" "$SLUG" "$ACTUAL_HASH" "bounties/$SLUG/scope.md" "$SCHEMA_FILE" <<'PY' || fail "E_OUTPUT_VERIFY" "Committed artifact failed post-write verification"
import json
import os
import sys
from datetime import datetime

path, expected_slug, expected_hash, expected_scope_file, schema_file = sys.argv[1:6]

with open(path, encoding="utf-8") as f:
    record = json.load(f)

assert record.get("slug") == expected_slug, f"Slug mismatch: {record.get('slug')} != {expected_slug}"
assert record.get("scope_sha256") == expected_hash, f"Hash mismatch: {record.get('scope_sha256')} != {expected_hash}"
assert record.get("status") == "PIN_VERIFIED", f"Status mismatch: {record.get('status')}"
assert record.get("scope_file") == expected_scope_file, f"Scope file mismatch: {record.get('scope_file')} != {expected_scope_file}"
ts = record.get("timestamp")
assert isinstance(ts, str), "Timestamp is not a string"
datetime.fromisoformat(ts.replace("Z", "+00:00"))

if os.path.isfile(schema_file):
    try:
        import jsonschema
        with open(schema_file, encoding="utf-8") as sf:
            schema = json.load(sf)
        jsonschema.validate(instance=record, schema=schema)
    except ImportError:
        pass
PY

printf '[OK] Mode: PIN_VERIFIED. Artifact committed: %s\n' "$PIN_JSON"
printf '[OK] Scope SHA-256: %s\n' "$ACTUAL_HASH"
printf '[OK] Post-write verification: PASSED (schema and context validated)\n'
printf '[OK] Status: PIN_VERIFIED\n'
