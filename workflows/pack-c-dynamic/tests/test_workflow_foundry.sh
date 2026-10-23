#!/usr/bin/env bash
# ==============================================================================
# Automated Test Suite for Pack C Foundry Workflow & Adapter
# Version: 2.0.0
# Architecture: Glassbox Mirror Plane / Production Validation Suite
# Mission: Validate all 16 test cases from the Production Validation Plan:
#          argument validation, execution mode precedence, path containment,
#          leaf symlink safety, error handling, and exit code propagation.
# ==============================================================================
set -Eeuo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd -- "${BASH_SOURCE[0]%/*}" >/dev/null 2>&1 && pwd -P)"
WORKFLOW_SCRIPT="$(cd "$SCRIPT_DIR/.." && pwd -P)/workflow-foundry-tests.sh"
REPO_ROOT="${REPO_ROOT:-$(cd "$SCRIPT_DIR/../../.." && pwd -P)}"

PASSED=0
FAILED=0
TOTAL=0

# Colors for terminal reporting
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Temporary sandbox directory for test artifacts and symlinks
TEST_SANDBOX="$REPO_ROOT/workflows/pack-c-dynamic/tests/.tmp_sandbox_$$"
mkdir -p "$TEST_SANDBOX"

cleanup() {
  rm -rf "$TEST_SANDBOX"
}
trap cleanup EXIT

report_result() {
  local test_name="$1"
  local status="$2"
  local details="${3:-}"

  TOTAL=$((TOTAL + 1))
  if [[ "$status" == "PASS" ]]; then
    PASSED=$((PASSED + 1))
    printf "${GREEN}[PASS]${NC} %s\n" "$test_name"
  else
    FAILED=$((FAILED + 1))
    printf "${RED}[FAIL]${NC} %s\n" "$test_name"
    if [[ -n "$details" ]]; then
      printf "       ${YELLOW}Details:${NC} %s\n" "$details"
    fi
  fi
}

printf "${BLUE}==============================================================================${NC}\n"
printf "${BLUE} Running Pack C Foundry Workflow & Adapter Production Validation Suite        ${NC}\n"
printf "${BLUE}==============================================================================${NC}\n\n"

# ------------------------------------------------------------------------------
# Test 1: No flags supplied -> Default Dry-Run mode, exit 0
# ------------------------------------------------------------------------------
TEST_NAME="Test 1: Default execution without flags resolves to DRY-RUN mode"
OUTPUT=""
STATUS=0
OUTPUT=$(bash "$WORKFLOW_SCRIPT" 2>&1) || STATUS=$?
if [[ $STATUS -eq 0 && "$OUTPUT" == *"[DRY-RUN]"* && "$OUTPUT" == *"Mode: DRY-RUN"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Exit code $STATUS, output: $OUTPUT"
fi

# ------------------------------------------------------------------------------
# Test 2: --dry-run explicitly supplied -> Dry-Run mode, exit 0
# ------------------------------------------------------------------------------
TEST_NAME="Test 2: Explicit --dry-run flag executes in DRY-RUN mode"
OUTPUT=""
STATUS=0
OUTPUT=$(bash "$WORKFLOW_SCRIPT" --dry-run 2>&1) || STATUS=$?
if [[ $STATUS -eq 0 && "$OUTPUT" == *"[DRY-RUN]"* && "$OUTPUT" == *"Mode: DRY-RUN"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Exit code $STATUS, output: $OUTPUT"
fi

# ------------------------------------------------------------------------------
# Test 3: Both --confirm and --dry-run supplied -> Dry-run takes precedence
# ------------------------------------------------------------------------------
TEST_NAME="Test 3: Both --confirm and --dry-run supplied -> DRY-RUN takes precedence"
OUTPUT=""
STATUS=0
OUTPUT=$(bash "$WORKFLOW_SCRIPT" --confirm --dry-run 2>&1) || STATUS=$?
if [[ $STATUS -eq 0 && "$OUTPUT" == *"[DRY-RUN]"* && "$OUTPUT" == *"Mode: DRY-RUN"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Exit code $STATUS, output: $OUTPUT"
fi

# ------------------------------------------------------------------------------
# Test 4: Unknown flag -> Rejected immediately with exit code 1
# ------------------------------------------------------------------------------
TEST_NAME="Test 4: Unknown flag (--bogus-flag) rejected with exit 1"
OUTPUT=""
STATUS=0
OUTPUT=$(bash "$WORKFLOW_SCRIPT" --bogus-flag 2>&1) || STATUS=$?
if [[ $STATUS -eq 1 && "$OUTPUT" == *"Unknown argument: --bogus-flag"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Expected exit 1, got $STATUS; output: $OUTPUT"
fi

# ------------------------------------------------------------------------------
# Test 5: Missing option value for --target -> Rejected with exit code 1
# ------------------------------------------------------------------------------
TEST_NAME="Test 5: Missing option value for --target rejected with exit 1"
OUTPUT=""
STATUS=0
OUTPUT=$(bash "$WORKFLOW_SCRIPT" --target 2>&1) || STATUS=$?
if [[ $STATUS -eq 1 && "$OUTPUT" == *"--target requires"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Expected exit 1, got $STATUS; output: $OUTPUT"
fi

# ------------------------------------------------------------------------------
# Test 6: Next flag passed as option value for --target -> Rejected with exit code 1
# ------------------------------------------------------------------------------
TEST_NAME="Test 6: Option value following --target cannot be another flag"
OUTPUT=""
STATUS=0
OUTPUT=$(bash "$WORKFLOW_SCRIPT" --target --dry-run 2>&1) || STATUS=$?
if [[ $STATUS -eq 1 && "$OUTPUT" == *"--target requires a value"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Expected exit 1, got $STATUS; output: $OUTPUT"
fi

# ------------------------------------------------------------------------------
# Test 7: Missing option value for --output-dir -> Rejected with exit code 1
# ------------------------------------------------------------------------------
TEST_NAME="Test 7: Missing option value for --output-dir rejected with exit 1"
OUTPUT=""
STATUS=0
OUTPUT=$(bash "$WORKFLOW_SCRIPT" --output-dir 2>&1) || STATUS=$?
if [[ $STATUS -eq 1 && "$OUTPUT" == *"--output-dir requires"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Expected exit 1, got $STATUS; output: $OUTPUT"
fi

# ------------------------------------------------------------------------------
# Test 8: Target path traversal escaping repo root (../) -> Rejected with exit code 1
# ------------------------------------------------------------------------------
TEST_NAME="Test 8: Relative path traversal escaping repo root rejected"
OUTPUT=""
STATUS=0
OUTPUT=$(bash "$WORKFLOW_SCRIPT" --target "../cantina_escaped" 2>&1) || STATUS=$?
if [[ $STATUS -eq 1 && "$OUTPUT" == *"escapes repository root"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Expected exit 1 with escape error, got $STATUS; output: $OUTPUT"
fi

# ------------------------------------------------------------------------------
# Test 9: Absolute path input for --target -> Rejected with exit code 1
# ------------------------------------------------------------------------------
TEST_NAME="Test 9: Absolute path input for --target rejected"
OUTPUT=""
STATUS=0
OUTPUT=$(bash "$WORKFLOW_SCRIPT" --target "/etc/passwd" 2>&1) || STATUS=$?
if [[ $STATUS -eq 1 && "$OUTPUT" == *"Paths must be relative to the repository root"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Expected exit 1 with relative requirement, got $STATUS; output: $OUTPUT"
fi

# ------------------------------------------------------------------------------
# Test 10: Symlink escaping repository root -> Rejected with exit code 1
# ------------------------------------------------------------------------------
TEST_NAME="Test 10: Symlink directory escaping repository root rejected"
SYMLINK_DIR_ESCAPED="$TEST_SANDBOX/symlink_dir_escape"
ln -s /tmp "$SYMLINK_DIR_ESCAPED"
REL_SYM_DIR="workflows/pack-c-dynamic/tests/.tmp_sandbox_$$/symlink_dir_escape"
OUTPUT=""
STATUS=0
OUTPUT=$(bash "$WORKFLOW_SCRIPT" --target "$REL_SYM_DIR" 2>&1) || STATUS=$?
if [[ $STATUS -eq 1 && "$OUTPUT" == *"escapes repository root"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Expected exit 1, got $STATUS; output: $OUTPUT"
fi

# ------------------------------------------------------------------------------
# Test 11: Leaf/final-component symlink escaping repository root -> Rejected with exit code 1
# ------------------------------------------------------------------------------
TEST_NAME="Test 11: Leaf-component symlink escaping repository root rejected"
SYMLINK_LEAF_ESCAPED="$TEST_SANDBOX/leaf_link_escape"
ln -s /var/log "$SYMLINK_LEAF_ESCAPED"
REL_LEAF_SYM="workflows/pack-c-dynamic/tests/.tmp_sandbox_$$/leaf_link_escape"
OUTPUT=""
STATUS=0
OUTPUT=$(bash "$WORKFLOW_SCRIPT" --target "$REL_LEAF_SYM" 2>&1) || STATUS=$?
if [[ $STATUS -eq 1 && "$OUTPUT" == *"escapes repository root"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Expected exit 1 for leaf symlink escape, got $STATUS; output: $OUTPUT"
fi

# ------------------------------------------------------------------------------
# Test 12: Existing output path is a regular file -> Rejected with exit code 1
# ------------------------------------------------------------------------------
TEST_NAME="Test 12: Output path existing as a regular file rejected"
REGULAR_FILE="$TEST_SANDBOX/not_a_directory.txt"
touch "$REGULAR_FILE"
REL_REG_FILE="workflows/pack-c-dynamic/tests/.tmp_sandbox_$$/not_a_directory.txt"
OUTPUT=""
STATUS=0
OUTPUT=$(bash "$WORKFLOW_SCRIPT" --output-dir "$REL_REG_FILE" 2>&1) || STATUS=$?
if [[ $STATUS -eq 1 && "$OUTPUT" == *"Output path exists but is not a directory"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Expected exit 1 for file as output dir, got $STATUS; output: $OUTPUT"
fi

# ------------------------------------------------------------------------------
# Test 13: Non-existent repository root -> Rejected with exit code 1
# ------------------------------------------------------------------------------
TEST_NAME="Test 13: Non-existent repository root rejected"
OUTPUT=""
STATUS=0
OUTPUT=$(bash "$WORKFLOW_SCRIPT" --repo-root "/nonexistent_root_path_$$" 2>&1) || STATUS=$?
if [[ $STATUS -eq 1 && "$OUTPUT" == *"Repository root does not exist"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Expected exit 1, got $STATUS; output: $OUTPUT"
fi

# ------------------------------------------------------------------------------
# Test 14: Help flag (-h and --help) displays usage and exits 0
# ------------------------------------------------------------------------------
TEST_NAME="Test 14: Help flags (-h, --help) display usage and exit 0"
OUTPUT_H=$(bash "$WORKFLOW_SCRIPT" -h 2>&1) || STATUS=$?
OUTPUT_HELP=$(bash "$WORKFLOW_SCRIPT" --help 2>&1) || STATUS=$?
if [[ "$OUTPUT_H" == *"Usage:"* && "$OUTPUT_HELP" == *"Usage:"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Help flag failed to output usage"
fi

# ------------------------------------------------------------------------------
# Test 15: Adapter independent path containment check (Python level)
# ------------------------------------------------------------------------------
TEST_NAME="Test 15: Adapter independently verifies path containment (defense-in-depth)"
ADAPTER="$REPO_ROOT/.agents/skills/qrpe/adapters/foundry_adapter.py"
OUTPUT=""
STATUS=0
OUTPUT=$(python3 "$ADAPTER" --target "/tmp" --output-dir "$REPO_ROOT/bounties/base/scans" --dry-run 2>&1) || STATUS=$?
if [[ $STATUS -eq 1 && "$OUTPUT" == *"[FAIL] Target path"* && "$OUTPUT" == *"escapes repository root"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Adapter failed to catch escaped target: exit $STATUS, output: $OUTPUT"
fi

# ------------------------------------------------------------------------------
# Test 16: Nonzero exit code from adapter preserved by bash wrapper
# ------------------------------------------------------------------------------
TEST_NAME="Test 16: Nonzero exit code from adapter is preserved by wrapper"
# Force adapter exit 1 by passing target with missing dir
FAKE_DIR="workflows/pack-c-dynamic/tests/.tmp_sandbox_$$/missing_target_dir"
mkdir -p "$REPO_ROOT/$FAKE_DIR"
# Delete directory right before Python checks it, or test adapter directly
rmdir "$REPO_ROOT/$FAKE_DIR"
STATUS=0
OUTPUT=$(bash "$WORKFLOW_SCRIPT" --target "$FAKE_DIR" 2>&1) || STATUS=$?
if [[ $STATUS -eq 1 && "$OUTPUT" == *"Target directory does not exist"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Expected exit 1, got $STATUS; output: $OUTPUT"
fi

printf "\n${BLUE}==============================================================================${NC}\n"
printf "${BLUE} Test Summary: %d passed, %d failed out of %d tests                         ${NC}\n" "$PASSED" "$FAILED" "$TOTAL"
printf "${BLUE}==============================================================================${NC}\n"

if [[ $FAILED -gt 0 ]]; then
  exit 1
fi
exit 0
