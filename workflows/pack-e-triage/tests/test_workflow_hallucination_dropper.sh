#!/usr/bin/env bash
# Test Suite for workflow-hallucination-dropper.sh
# Asserts all security, operational, invariant, and edge-case requirements.
set -euo pipefail

TEST_ROOT="$(mktemp -d -t cantina-test-XXXXXX)"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
WORKFLOW_DIR="$(cd "$SCRIPT_DIR/.." && pwd -P)"
WORKFLOW_SCRIPT="$WORKFLOW_DIR/workflow-hallucination-dropper.sh"
VALIDATOR_SCRIPT="$WORKFLOW_DIR/validate_schemas.py"
ADAPTER_SCRIPT="$WORKFLOW_DIR/adapters/example_adapter.py"
export PYTHONPATH="$WORKFLOW_DIR:${PYTHONPATH:-}"

cleanup() {
  rm -rf "$TEST_ROOT"
}
trap cleanup EXIT INT TERM

echo "=== Running Hallucination Dropper Automated Test Suite ==="
echo "Test working directory: $TEST_ROOT"

# Setup isolated git repository
REPO_DIR="$TEST_ROOT/repo"
mkdir -p "$REPO_DIR"
cd "$REPO_DIR"
git init -q
git config user.email "ci@cantina.local"
git config user.name "CI Runner"

# Create initial commits
mkdir -p src docs
cat <<'EOF' > src/auth.py
# Authentication Module
def login(username, password):
    if not username:
        return False
    if password == "secret":
        return True
    return False

def logout():
    return True
EOF

cat <<'EOF' > "docs/white space file.txt"
Line 1
Line 2
Line 3
Line 4
Line 5
EOF

touch empty.txt
printf "\x00\x01\x02\x03\x04\xff\xfe\x00" > binary.bin

# Create a small submodule to test submodule target handling
SUB_DIR="$TEST_ROOT/external_sub"
mkdir -p "$SUB_DIR"
(
  cd "$SUB_DIR"
  git init -q
  git config user.email "ci@cantina.local"
  git config user.name "CI Runner"
  echo "def helper(): pass" > helper.py
  git add helper.py
  git commit -q -m "initial sub commit"
)

git -c protocol.file.allow=always submodule add -q "$SUB_DIR" submod 2>/dev/null || true

git add src/auth.py "docs/white space file.txt" empty.txt binary.bin
git commit -q -m "feat: initial commit with varied blobs"
PINNED_COMMIT="$(git rev-parse HEAD)"

# Copy adapter inside test repo for adapter testing
mkdir -p adapters
cp "$ADAPTER_SCRIPT" adapters/example_adapter.py

PASS_COUNT=0

assert_eq() {
  local test_num="$1"
  local desc="$2"
  local expected="$3"
  local actual="$4"
  if [[ "$expected" == "$actual" ]]; then
    echo "  [PASS] Test $test_num: $desc"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    echo "  [FAIL] Test $test_num: $desc (Expected '$expected', got '$actual')"
    exit 1
  fi
}

assert_contains() {
  local test_num="$1"
  local desc="$2"
  local haystack="$3"
  local needle="$4"
  if [[ "$haystack" == *"$needle"* ]]; then
    echo "  [PASS] Test $test_num: $desc"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    echo "  [FAIL] Test $test_num: $desc (Expected output to contain '$needle')"
    echo "Actual output:"
    echo "$haystack"
    exit 1
  fi
}

assert_not_contains() {
  local test_num="$1"
  local desc="$2"
  local haystack="$3"
  local needle="$4"
  if [[ "$haystack" != *"$needle"* ]]; then
    echo "  [PASS] Test $test_num: $desc"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    echo "  [FAIL] Test $test_num: $desc (Output unexpectedly contained '$needle')"
    exit 1
  fi
}

# -------------------------------------------------------------
# Test 1: Missing --slug returns 4 and prints usage
# -------------------------------------------------------------
set +e
OUT1="$("$WORKFLOW_SCRIPT" 2>&1)"
CODE1=$?
set -e
assert_eq "1" "Missing --slug flag returns exit code 4" "4" "$CODE1"

# -------------------------------------------------------------
# Test 2: Unknown flags return 4
# -------------------------------------------------------------
set +e
OUT2="$("$WORKFLOW_SCRIPT" --slug valid-slug --unknown-opt 2>&1)"
CODE2=$?
set -e
assert_eq "2" "Unknown flag returns exit code 4" "4" "$CODE2"

# -------------------------------------------------------------
# Test 3: Invalid slugs return 4 and create no artifacts
# -------------------------------------------------------------
set +e
OUT3="$("$WORKFLOW_SCRIPT" --slug "../escape" --confirm 2>&1)"
CODE3=$?
set -e
assert_eq "3" "Slug path traversal returns exit code 4" "4" "$CODE3"
if [[ -d "$REPO_DIR/bounties/../escape" ]]; then
  echo "FAIL: Artifact directory created for invalid slug"
  exit 1
fi

# -------------------------------------------------------------
# Test 4: Preview mode creates no artifacts and returns 0
# -------------------------------------------------------------
mkdir -p "$REPO_DIR/bounties/preview-bounty/reports"
cat <<'EOF' > "$REPO_DIR/bounties/preview-bounty/reports/rep.md"
CITE: src/auth.py:2-5
EOF
set +e
OUT4="$("$WORKFLOW_SCRIPT" --slug preview-bounty --dry-run 2>&1)"
CODE4=$?
set -e
assert_eq "4" "Explicit preview mode returns exit code 0" "0" "$CODE4"
if [[ -f "$REPO_DIR/bounties/preview-bounty/scans/hallucination_audit.json" ]]; then
  echo "FAIL: Preview mode created audit artifact"
  exit 1
fi

# -------------------------------------------------------------
# Test 5: Omitting --confirm creates no artifacts and returns 0
# -------------------------------------------------------------
set +e
OUT5="$("$WORKFLOW_SCRIPT" --slug preview-bounty 2>&1)"
CODE5=$?
set -e
assert_eq "5" "Default preview (no --confirm) returns exit code 0" "0" "$CODE5"
if [[ -f "$REPO_DIR/bounties/preview-bounty/scans/hallucination_audit.json" ]]; then
  echo "FAIL: Default preview mode created audit artifact"
  exit 1
fi

# -------------------------------------------------------------
# Test 6: A symlinked scans directory is refused with nonzero result
# -------------------------------------------------------------
mkdir -p "$REPO_DIR/bounties/symlink-scans" "$TEST_ROOT/external_scans"
ln -s "$TEST_ROOT/external_scans" "$REPO_DIR/bounties/symlink-scans/scans"
set +e
OUT6="$("$WORKFLOW_SCRIPT" --slug symlink-scans --confirm 2>&1)"
CODE6=$?
set -e
if [[ "$CODE6" -ne 0 ]]; then
  echo "  [PASS] Test 6: Symlinked scans directory refused (exit code $CODE6)"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  echo "  [FAIL] Test 6: Symlinked scans directory unexpectedly permitted"
  exit 1
fi

# -------------------------------------------------------------
# Test 7: A symlinked output directory is refused
# -------------------------------------------------------------
mkdir -p "$TEST_ROOT/external_bounty"
ln -s "$TEST_ROOT/external_bounty" "$REPO_DIR/bounties/symlink-bounty"
set +e
OUT7="$("$WORKFLOW_SCRIPT" --slug symlink-bounty --confirm 2>&1)"
CODE7=$?
set -e
if [[ "$CODE7" -ne 0 ]]; then
  echo "  [PASS] Test 7: Symlinked bounty directory refused (exit code $CODE7)"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  echo "  [FAIL] Test 7: Symlinked bounty directory unexpectedly permitted"
  exit 1
fi

# -------------------------------------------------------------
# Test 8: Cross-device output is refused where separate device is available
# -------------------------------------------------------------
REPO_DEV="$(stat -c %d "$REPO_DIR")"
SHM_DEV=""
if [[ -d "/dev/shm" ]]; then
  SHM_DEV="$(stat -c %d /dev/shm 2>/dev/null || true)"
fi

if [[ -n "$SHM_DEV" && "$REPO_DEV" != "$SHM_DEV" ]]; then
  mkdir -p /dev/shm/cantina-test-crossdev-$$
  set +e
  python3 -c "
import sys, pathlib
from hallucination_dropper import validate_filesystem_safety
repo = pathlib.Path('$REPO_DIR')
out = pathlib.Path('/dev/shm/cantina-test-crossdev-$$')
validate_filesystem_safety(repo, out)
" 2>/dev/null
  CODE8=$?
  set -e
  rm -rf /dev/shm/cantina-test-crossdev-$$
  assert_eq "8" "Cross-device output directory refused with exit code 2" "2" "$CODE8"
else
  set +e
  python3 -c "
import sys, pathlib
from unittest.mock import patch, MagicMock
from hallucination_dropper import validate_filesystem_safety
repo = pathlib.Path('$REPO_DIR')
out = repo / 'bounties' / 'test' / 'scans'

stat_repo = MagicMock(st_dev=100)
stat_out = MagicMock(st_dev=200)

with patch.object(pathlib.Path, 'stat', side_effect=[stat_repo, stat_out]):
    validate_filesystem_safety(repo, out)
" 2>/dev/null
  CODE8=$?
  set -e
  assert_eq "8" "Cross-device check correctly returns exit code 2 on device divergence" "2" "$CODE8"
fi

# -------------------------------------------------------------
# Test 9: Successful confirmed run writes both JSON artifacts and returns 0
# -------------------------------------------------------------
mkdir -p "$REPO_DIR/bounties/bounty-valid/reports"
cat <<'EOF' > "$REPO_DIR/bounties/bounty-valid/reports/finding.md"
# Vulnerability Report
CITE: src/auth.py:2-6
EOF

set +e
OUT9="$("$WORKFLOW_SCRIPT" --slug bounty-valid --confirm 2>&1)"
CODE9=$?
set -e
assert_eq "9" "Valid confirmed run returns exit code 0" "0" "$CODE9"
if [[ -f "$REPO_DIR/bounties/bounty-valid/scans/hallucination_audit.json" && \
      -f "$REPO_DIR/bounties/bounty-valid/scans/hallucination_audit.provenance.json" ]]; then
  echo "  [PASS] Test 9 (artifacts): Both JSON artifacts written successfully"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  echo "FAIL: Expected output artifacts missing"
  exit 1
fi

# -------------------------------------------------------------
# Test 10: Partial verification writes required artifacts and returns 1
# -------------------------------------------------------------
mkdir -p "$REPO_DIR/bounties/bounty-fail/reports"
cat <<'EOF' > "$REPO_DIR/bounties/bounty-fail/reports/hallucinated.md"
CITE: src/auth.py:2-6
CITE: src/auth.py:100-110
EOF

set +e
OUT10="$("$WORKFLOW_SCRIPT" --slug bounty-fail --confirm 2>&1)"
CODE10=$?
set -e
assert_eq "10" "Partial verification run returns exit code 1" "1" "$CODE10"
if [[ -f "$REPO_DIR/bounties/bounty-fail/scans/hallucination_audit.json" && \
      -f "$REPO_DIR/bounties/bounty-fail/scans/hallucination_audit.provenance.json" ]]; then
  echo "  [PASS] Test 10 (artifacts): Partial verification wrote required artifacts"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  echo "FAIL: Expected partial verification output artifacts missing"
  exit 1
fi

# -------------------------------------------------------------
# Test 11: Missing dependencies return 3
# -------------------------------------------------------------
MOCK_BIN="$TEST_ROOT/mock_bin_no_git"
mkdir -p "$MOCK_BIN"
ln -s "$(command -v bash)" "$MOCK_BIN/bash"
ln -s "$(command -v python3)" "$MOCK_BIN/python3"
ln -s "$(command -v pwd)" "$MOCK_BIN/pwd"
ln -s "$(command -v date)" "$MOCK_BIN/date"
set +e
CODE11=$(PATH="$MOCK_BIN" "$WORKFLOW_SCRIPT" --slug test-slug 2>/dev/null || echo $?)
set -e
assert_eq "11" "Missing dependency returns exit code 3" "3" "$CODE11"

# -------------------------------------------------------------
# Test 12: Write failures return 2
# -------------------------------------------------------------
mkdir -p "$REPO_DIR/bounties/bounty-ro/scans"
chmod 555 "$REPO_DIR/bounties/bounty-ro/scans"
set +e
OUT12="$("$WORKFLOW_SCRIPT" --slug bounty-ro --confirm 2>&1)"
CODE12=$?
set -e
chmod 755 "$REPO_DIR/bounties/bounty-ro/scans"
assert_eq "12" "Write failure on read-only directory returns exit code 2" "2" "$CODE12"

# -------------------------------------------------------------
# Test 13: Git filenames containing whitespace are handled correctly
# -------------------------------------------------------------
mkdir -p "$REPO_DIR/bounties/bounty-space/reports"
cat <<'EOF' > "$REPO_DIR/bounties/bounty-space/reports/space_cite.md"
CITE: docs/white space file.txt:1-3
EOF

set +e
OUT13="$("$WORKFLOW_SCRIPT" --slug bounty-space --confirm 2>&1)"
CODE13=$?
set -e
assert_eq "13" "Filename with whitespace verified with exit code 0" "0" "$CODE13"

# -------------------------------------------------------------
# Test 14: Empty and binary blobs do not crash the workflow
# -------------------------------------------------------------
mkdir -p "$REPO_DIR/bounties/bounty-blobs/reports"
cat <<'EOF' > "$REPO_DIR/bounties/bounty-blobs/reports/blobs.md"
CITE: empty.txt:1-2
CITE: binary.bin:1-1
EOF

set +e
OUT14="$("$WORKFLOW_SCRIPT" --slug bounty-blobs --confirm 2>&1)"
CODE14=$?
set -e
assert_eq "14" "Empty and binary blobs safely unverified (exit code 1)" "1" "$CODE14"

# -------------------------------------------------------------
# Test 15: Adapter output validation rejects malformed records and traversal
# -------------------------------------------------------------
cat <<'EOF' > "$REPO_DIR/custom_malicious_adapter.py"
def extract_citations(report_path):
    return [
        {"target": "../../etc/passwd", "start_line": 1, "end_line": 2, "reported_in": report_path},
        {"target": "src/auth.py", "start_line": True, "end_line": 5, "reported_in": report_path},
        {"target": "src/auth.py", "start_line": 10, "end_line": 5, "reported_in": report_path}
    ]
EOF

set +e
OUT15="$("$WORKFLOW_SCRIPT" --slug bounty-valid --adapter "$REPO_DIR/custom_malicious_adapter.py" --confirm 2>&1)"
CODE15=$?
set -e
assert_eq "15" "Malformed / traversal adapter records rejected (exit code 1)" "1" "$CODE15"

# -------------------------------------------------------------
# Test 16: Success sentinel logic
# -------------------------------------------------------------
# 16a: Check successful run has sentinel
STDOUT9="$("$WORKFLOW_SCRIPT" --slug bounty-valid --confirm 2>/dev/null)"
assert_contains "16a" "Success sentinel present on verified run" "$STDOUT9" "ALL_CITATIONS_VERIFIED"

# 16b: Check unverified run does NOT have sentinel
STDOUT10="$("$WORKFLOW_SCRIPT" --slug bounty-fail --confirm 2>/dev/null || true)"
assert_not_contains "16b" "Success sentinel absent on partial verification" "$STDOUT10" "ALL_CITATIONS_VERIFIED"

# 16c: Check preview mode does NOT have sentinel
STDOUT4="$("$WORKFLOW_SCRIPT" --slug bounty-valid --dry-run 2>/dev/null || true)"
assert_not_contains "16c" "Success sentinel absent in preview mode" "$STDOUT4" "ALL_CITATIONS_VERIFIED"

# 16d: Check sentinel ABSENT when zero citations exist
mkdir -p "$REPO_DIR/bounties/bounty-nocite/reports"
cat <<'EOF' > "$REPO_DIR/bounties/bounty-nocite/reports/report_without_cites.md"
# General Notes
No citations here.
EOF
set +e
STDOUT16d="$("$WORKFLOW_SCRIPT" --slug bounty-nocite --confirm 2>/dev/null || true)"
CODE16d=$?
set -e
assert_not_contains "16d" "Success sentinel absent when ZERO citations exist" "$STDOUT16d" "ALL_CITATIONS_VERIFIED"

# -------------------------------------------------------------
# Test 17: Temporary files are cleaned up after injected failures
# -------------------------------------------------------------
mkdir -p "$REPO_DIR/bounties/bounty-tmpclean/scans"
chmod 555 "$REPO_DIR/bounties/bounty-tmpclean/scans"
set +e
"$WORKFLOW_SCRIPT" --slug bounty-tmpclean --confirm >/dev/null 2>&1 || true
set -e
chmod 755 "$REPO_DIR/bounties/bounty-tmpclean/scans"
TMP_COUNT="$(find "$REPO_DIR/bounties/bounty-tmpclean/scans" -name ".*.tmp*" | wc -l)"
assert_eq "17" "Temporary files cleaned up after write failure" "0" "$TMP_COUNT"

# -------------------------------------------------------------
# Test 18: Both output files pass JSON parsing and schema validation
# -------------------------------------------------------------
set +e
VALID_OUT="$(python3 "$VALIDATOR_SCRIPT" --dir "$REPO_DIR/bounties/bounty-valid/scans" 2>&1)"
VALID_CODE=$?
set -e
assert_eq "18" "Both artifacts conform to JSON schemas" "0" "$VALID_CODE"

# -------------------------------------------------------------
# Test 19: Absolute paths in --sources return exit code 4
# -------------------------------------------------------------
set +e
OUT19="$("$WORKFLOW_SCRIPT" --slug bounty-valid --sources "/etc/passwd" 2>&1)"
CODE19=$?
set -e
assert_eq "19" "Absolute path in --sources returns exit code 4" "4" "$CODE19"

# -------------------------------------------------------------
# Test 20: Path traversal in --sources returns exit code 4
# -------------------------------------------------------------
set +e
OUT20="$("$WORKFLOW_SCRIPT" --slug bounty-valid --sources "../escape" 2>&1)"
CODE20=$?
set -e
assert_eq "20" "Path traversal in --sources returns exit code 4" "4" "$CODE20"

# -------------------------------------------------------------
# Test 21: Conflicting duplicate options return exit code 4
# -------------------------------------------------------------
set +e
OUT21="$("$WORKFLOW_SCRIPT" --slug bounty-valid --slug different-slug 2>&1)"
CODE21=$?
set -e
assert_eq "21" "Conflicting duplicate --slug options return exit code 4" "4" "$CODE21"

# -------------------------------------------------------------
# Test 22: Git submodules explicitly handled as SUBMODULE_TARGET
# -------------------------------------------------------------
mkdir -p "$REPO_DIR/bounties/bounty-submod/reports"
cat <<'EOF' > "$REPO_DIR/bounties/bounty-submod/reports/submod_cite.md"
CITE: submod:1-2
EOF
set +e
OUT22="$("$WORKFLOW_SCRIPT" --slug bounty-submod --confirm 2>&1)"
CODE22=$?
set -e
assert_eq "22" "Submodule target citation flagged with exit code 1" "1" "$CODE22"
if [[ -f "$REPO_DIR/bounties/bounty-submod/scans/hallucination_audit.json" ]]; then
  AUDIT_SUBMOD="$(cat "$REPO_DIR/bounties/bounty-submod/scans/hallucination_audit.json")"
  assert_contains "22 (code)" "Audit artifact explicitly identifies SUBMODULE_TARGET" "$AUDIT_SUBMOD" "SUBMODULE_TARGET"
fi

# -------------------------------------------------------------
# Test 23: Large blobs (>10MB) bounded and flagged without memory crash
# -------------------------------------------------------------
# Write an 11MB file in git
head -c $((11 * 1024 * 1024)) </dev/zero | tr '\0' 'A' > "$REPO_DIR/large_blob.txt"
git add "$REPO_DIR/large_blob.txt"
git commit -q -m "feat: add 11MB blob"
PINNED_WITH_LARGE="$(git rev-parse HEAD)"

mkdir -p "$REPO_DIR/bounties/bounty-large/reports"
cat <<'EOF' > "$REPO_DIR/bounties/bounty-large/reports/large_cite.md"
CITE: large_blob.txt:1-5
EOF
set +e
OUT23="$("$WORKFLOW_SCRIPT" --slug bounty-large --commit "$PINNED_WITH_LARGE" --confirm 2>&1)"
CODE23=$?
set -e
assert_eq "23" "Large blob citation flagged safely with exit code 1" "1" "$CODE23"
if [[ -f "$REPO_DIR/bounties/bounty-large/scans/hallucination_audit.json" ]]; then
  AUDIT_LARGE="$(cat "$REPO_DIR/bounties/bounty-large/scans/hallucination_audit.json")"
  assert_contains "23 (code)" "Audit artifact flags BLOB_SIZE_EXCEEDED" "$AUDIT_LARGE" "BLOB_SIZE_EXCEEDED"
fi

# -------------------------------------------------------------
# Test 24: Unmatched --sources pattern recorded in provenance errors
# -------------------------------------------------------------
set +e
OUT24="$("$WORKFLOW_SCRIPT" --slug bounty-valid --sources "nonexistent_pattern_*.md" --confirm 2>&1)"
CODE24=$?
set -e
PROV_FILE="$REPO_DIR/bounties/bounty-valid/scans/hallucination_audit.provenance.json"
if [[ -f "$PROV_FILE" ]]; then
  PROV_CONTENT="$(cat "$PROV_FILE")"
  assert_contains "24" "Unmatched pattern recorded in provenance errors" "$PROV_CONTENT" "UNMATCHED_SOURCE_PATTERN"
else
  echo "FAIL: Provenance file missing for unmatched pattern test"
  exit 1
fi

# -------------------------------------------------------------
# Test 25: Bash operational errors emit valid JSON Lines to stderr
# -------------------------------------------------------------
set +e
STDERR25="$("$WORKFLOW_SCRIPT" --unknown-flag-test 2>&1 1>/dev/null)"
CODE25=$?
set -e
assert_eq "25 (code)" "Unknown flag exits with code 4" "4" "$CODE25"
assert_contains "25 (json)" "Stderr includes JSON Lines record with workflow_bash" "$STDERR25" '"component": "workflow_bash"'

echo "=========================================================="
echo "TEST SUITE COMPLETE: $PASS_COUNT test assertions evaluated successfully."
echo "=========================================================="
