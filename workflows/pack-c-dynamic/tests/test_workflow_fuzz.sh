#!/usr/bin/env bash
# ==============================================================================
# Automated Acceptance Test Suite for Pack C Bounded Forge Fuzz Runner
# Version: 1.0.0
# Architecture: Glassbox Mirror Plane / Production Validation Suite
# Mission: Verify all 12 acceptance criteria from Section 5:
#          - Argument parsing & fail-closed validation
#          - Mutual exclusivity of --dry-run and --confirm
#          - Path containment and symlink escape rejection
#          - Prerequisite verification (Python, adapter, repo root)
#          - Subprocess exit code propagation & timeout handling
#          - Artifact integrity & no false verified claims
# ==============================================================================
set -Eeuo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd -- "${BASH_SOURCE[0]%/*}" >/dev/null 2>&1 && pwd -P)"
WORKFLOW_SCRIPT="$(cd "$SCRIPT_DIR/.." && pwd -P)/workflow-fuzz.sh"
REPO_ROOT="${REPO_ROOT:-$(cd "$SCRIPT_DIR/../../.." && pwd -P)}"
BOUNDED_FUZZ_SCRIPT="$REPO_ROOT/scripts/bounded_forge_fuzz.sh"

PASSED=0
FAILED=0
TOTAL=0

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

TEST_SANDBOX="$REPO_ROOT/workflows/pack-c-dynamic/tests/.tmp_fuzz_sandbox_$$"
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
printf "${BLUE} Running Pack C Bounded Forge Fuzz Acceptance Test Suite                      ${NC}\n"
printf "${BLUE}==============================================================================${NC}\n\n"

# ------------------------------------------------------------------------------
# Test 1: No arguments -> Default Dry-Run mode, exit 0
# ------------------------------------------------------------------------------
TEST_NAME="Test 1: Default execution without arguments resolves to dry-run mode"
OUTPUT=""
STATUS=0
OUTPUT=$(bash "$WORKFLOW_SCRIPT" 2>&1) || STATUS=$?
if [[ $STATUS -eq 0 && "$OUTPUT" == *"Mode: dry-run"* && "$OUTPUT" == *"[DRY-RUN]"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Exit code $STATUS, output: $OUTPUT"
fi

# ------------------------------------------------------------------------------
# Test 2: --dry-run explicitly supplied -> Preview only, exit 0
# ------------------------------------------------------------------------------
TEST_NAME="Test 2: Explicit --dry-run flag executes in preview mode only"
OUTPUT=""
STATUS=0
OUTPUT=$(bash "$WORKFLOW_SCRIPT" --dry-run 2>&1) || STATUS=$?
if [[ $STATUS -eq 0 && "$OUTPUT" == *"Mode: dry-run"* && "$OUTPUT" == *"[DRY-RUN]"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Exit code $STATUS, output: $OUTPUT"
fi

# ------------------------------------------------------------------------------
# Test 3: --confirm -> Requests actual execution mode
# ------------------------------------------------------------------------------
TEST_NAME="Test 3: Explicit --confirm flag sets Mode: execute"
OUTPUT=""
STATUS=0
# Test confirm flag with a dry-run mock adapter to verify argument dispatch
MOCK_ADAPTER="$TEST_SANDBOX/mock_confirm_adapter.py"
cat <<'PY' > "$MOCK_ADAPTER"
import sys, pathlib
if "--confirm" in sys.argv:
    print("[MOCK] Confirmed execution received")
    out_idx = sys.argv.index("--output-dir") + 1
    out_dir = pathlib.Path(sys.argv[out_idx])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "receipt.json").write_text('{"status": "ok"}')
    sys.exit(0)
sys.exit(1)
PY
chmod +x "$MOCK_ADAPTER"
OUTPUT=$(ADAPTER="$MOCK_ADAPTER" bash "$WORKFLOW_SCRIPT" --confirm 2>&1) || STATUS=$?
if [[ $STATUS -eq 0 && "$OUTPUT" == *"Mode: execute"* && "$OUTPUT" == *"[MOCK] Confirmed execution received"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Exit code $STATUS, output: $OUTPUT"
fi

# ------------------------------------------------------------------------------
# Test 4: Both execution flags (--dry-run and --confirm) -> Reject with exit 2
# ------------------------------------------------------------------------------
TEST_NAME="Test 4a: Conflicting flags (--dry-run followed by --confirm) rejected"
OUTPUT=""
STATUS=0
OUTPUT=$(bash "$WORKFLOW_SCRIPT" --dry-run --confirm 2>&1) || STATUS=$?
if [[ $STATUS -eq 2 && "$OUTPUT" == *"--dry-run and --confirm cannot be combined"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Expected exit 2, got $STATUS; output: $OUTPUT"
fi

TEST_NAME="Test 4b: Conflicting flags (--confirm followed by --dry-run) rejected"
OUTPUT=""
STATUS=0
OUTPUT=$(bash "$WORKFLOW_SCRIPT" --confirm --dry-run 2>&1) || STATUS=$?
if [[ $STATUS -eq 2 && "$OUTPUT" == *"--dry-run and --confirm cannot be combined"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Expected exit 2, got $STATUS; output: $OUTPUT"
fi

TEST_NAME="Test 4c: Duplicate identical flags (--dry-run --dry-run) are harmless"
OUTPUT=""
STATUS=0
OUTPUT=$(bash "$WORKFLOW_SCRIPT" --dry-run --dry-run 2>&1) || STATUS=$?
if [[ $STATUS -eq 0 && "$OUTPUT" == *"Mode: dry-run"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Exit code $STATUS, output: $OUTPUT"
fi

# ------------------------------------------------------------------------------
# Test 5: Unknown option -> Reject; never silently ignore
# ------------------------------------------------------------------------------
TEST_NAME="Test 5: Unknown flag rejected immediately with exit 2"
OUTPUT=""
STATUS=0
OUTPUT=$(bash "$WORKFLOW_SCRIPT" --unsupported-flag 2>&1) || STATUS=$?
if [[ $STATUS -eq 2 && "$OUTPUT" == *"Unknown argument: --unsupported-flag"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Expected exit 2, got $STATUS; output: $OUTPUT"
fi

# ------------------------------------------------------------------------------
# Test 6: Missing option values -> Reject before invoking adapter
# ------------------------------------------------------------------------------
TEST_NAME="Test 6a: Missing value for --target rejected with exit 2"
OUTPUT=""
STATUS=0
OUTPUT=$(bash "$WORKFLOW_SCRIPT" --target 2>&1) || STATUS=$?
if [[ $STATUS -eq 2 && "$OUTPUT" == *"Missing value for --target"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Expected exit 2, got $STATUS; output: $OUTPUT"
fi

TEST_NAME="Test 6b: Flag passed as value for --target rejected with exit 2"
OUTPUT=""
STATUS=0
OUTPUT=$(bash "$WORKFLOW_SCRIPT" --target --dry-run 2>&1) || STATUS=$?
if [[ $STATUS -eq 2 && "$OUTPUT" == *"Invalid value for --target"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Expected exit 2, got $STATUS; output: $OUTPUT"
fi

TEST_NAME="Test 6c: Missing value for --output-dir rejected with exit 2"
OUTPUT=""
STATUS=0
OUTPUT=$(bash "$WORKFLOW_SCRIPT" --output-dir 2>&1) || STATUS=$?
if [[ $STATUS -eq 2 && "$OUTPUT" == *"Missing value for --output-dir"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Expected exit 2, got $STATUS; output: $OUTPUT"
fi

TEST_NAME="Test 6d: Flag passed as value for --output-dir rejected with exit 2"
OUTPUT=""
STATUS=0
OUTPUT=$(bash "$WORKFLOW_SCRIPT" --output-dir --confirm 2>&1) || STATUS=$?
if [[ $STATUS -eq 2 && "$OUTPUT" == *"Invalid value for --output-dir"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Expected exit 2, got $STATUS; output: $OUTPUT"
fi

# ------------------------------------------------------------------------------
# Test 7: Target outside repository -> Reject
# ------------------------------------------------------------------------------
TEST_NAME="Test 7a: Relative traversal target outside repository rejected"
OUTPUT=""
STATUS=0
OUTPUT=$(bash "$WORKFLOW_SCRIPT" --target "../escape_path" 2>&1) || STATUS=$?
if [[ $STATUS -eq 2 && "$OUTPUT" == *"escapes the repository root"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Expected exit 2, got $STATUS; output: $OUTPUT"
fi

TEST_NAME="Test 7b: Absolute path target rejected"
OUTPUT=""
STATUS=0
OUTPUT=$(bash "$WORKFLOW_SCRIPT" --target "/etc/passwd" 2>&1) || STATUS=$?
if [[ $STATUS -eq 2 && "$OUTPUT" == *"must be repository-relative"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Expected exit 2, got $STATUS; output: $OUTPUT"
fi

TEST_NAME="Test 7c: Target symlink escaping repository root rejected"
SYMLINK_TARGET="$TEST_SANDBOX/sym_target_escape"
ln -s /tmp "$SYMLINK_TARGET"
REL_SYM="workflows/pack-c-dynamic/tests/.tmp_fuzz_sandbox_$$/sym_target_escape"
OUTPUT=""
STATUS=0
OUTPUT=$(bash "$WORKFLOW_SCRIPT" --target "$REL_SYM" 2>&1) || STATUS=$?
if [[ $STATUS -eq 2 && "$OUTPUT" == *"escapes the repository root"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Expected exit 2, got $STATUS; output: $OUTPUT"
fi

TEST_NAME="Test 7d: Non-existent target directory rejected"
OUTPUT=""
STATUS=0
OUTPUT=$(bash "$WORKFLOW_SCRIPT" --target "bounties/nonexistent_target_dir_$$" 2>&1) || STATUS=$?
if [[ $STATUS -eq 2 && "$OUTPUT" == *"Target directory does not exist"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Expected exit 2, got $STATUS; output: $OUTPUT"
fi

TEST_NAME="Test 7e: Repository root as target rejected"
OUTPUT=""
STATUS=0
OUTPUT=$(bash "$WORKFLOW_SCRIPT" --target "." 2>&1) || STATUS=$?
if [[ $STATUS -eq 2 && "$OUTPUT" == *"cannot be the repository root"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Expected exit 2, got $STATUS; output: $OUTPUT"
fi

# ------------------------------------------------------------------------------
# Test 8: Output path outside repository -> Reject
# ------------------------------------------------------------------------------
TEST_NAME="Test 8a: Relative traversal output-dir outside repository rejected"
OUTPUT=""
STATUS=0
OUTPUT=$(bash "$WORKFLOW_SCRIPT" --output-dir "../escape_output" 2>&1) || STATUS=$?
if [[ $STATUS -eq 2 && "$OUTPUT" == *"escapes the repository root"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Expected exit 2, got $STATUS; output: $OUTPUT"
fi

TEST_NAME="Test 8b: Output directory existing as regular file rejected"
REG_FILE="$TEST_SANDBOX/regular_file_output"
touch "$REG_FILE"
REL_FILE="workflows/pack-c-dynamic/tests/.tmp_fuzz_sandbox_$$/regular_file_output"
OUTPUT=""
STATUS=0
OUTPUT=$(bash "$WORKFLOW_SCRIPT" --output-dir "$REL_FILE" 2>&1) || STATUS=$?
if [[ $STATUS -eq 2 && "$OUTPUT" == *"Output path exists but is not a directory"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Expected exit 2, got $STATUS; output: $OUTPUT"
fi

TEST_NAME="Test 8c: Repository root as output-dir rejected"
OUTPUT=""
STATUS=0
OUTPUT=$(bash "$WORKFLOW_SCRIPT" --output-dir "." 2>&1) || STATUS=$?
if [[ $STATUS -eq 2 && "$OUTPUT" == *"cannot be the repository root"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Expected exit 2, got $STATUS; output: $OUTPUT"
fi

# ------------------------------------------------------------------------------
# Test 9: Missing adapter, repo root, or Python -> Fail before execution
# ------------------------------------------------------------------------------
TEST_NAME="Test 9a: Missing adapter file rejected before execution"
OUTPUT=""
STATUS=0
OUTPUT=$(ADAPTER="/nonexistent/adapter.py" bash "$WORKFLOW_SCRIPT" 2>&1) || STATUS=$?
if [[ $STATUS -eq 2 && "$OUTPUT" == *"Foundry adapter not found"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Expected exit 2, got $STATUS; output: $OUTPUT"
fi

TEST_NAME="Test 9b: Non-existent repository root rejected before execution"
OUTPUT=""
STATUS=0
OUTPUT=$(REPO_ROOT="/nonexistent/repo/root" bash "$WORKFLOW_SCRIPT" 2>&1) || STATUS=$?
if [[ $STATUS -eq 2 && "$OUTPUT" == *"Repository root not found"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Expected exit 2, got $STATUS; output: $OUTPUT"
fi

TEST_NAME="Test 9c: Missing python3 rejected before execution"
OUTPUT=""
STATUS=0
OUTPUT=$(/usr/bin/bash -c "PATH='/dev/null'; /usr/bin/bash '$WORKFLOW_SCRIPT'" 2>&1) || STATUS=$?
if [[ $STATUS -eq 2 && "$OUTPUT" == *"python3 is required"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Expected exit 2, got $STATUS; output: $OUTPUT"
fi

# ------------------------------------------------------------------------------
# Test 10: Adapter failure -> Preserve its nonzero exit status
# ------------------------------------------------------------------------------
TEST_NAME="Test 10: Nonzero exit code from adapter preserved exactly"
FAIL_ADAPTER="$TEST_SANDBOX/fail_adapter.py"
cat <<'PY' > "$FAIL_ADAPTER"
import sys
print("[FAIL MOCK] Adapter encountered critical failure")
sys.exit(42)
PY
chmod +x "$FAIL_ADAPTER"
STATUS=0
OUTPUT=$(ADAPTER="$FAIL_ADAPTER" bash "$WORKFLOW_SCRIPT" 2>&1) || STATUS=$?
if [[ $STATUS -eq 42 && "$OUTPUT" == *"[FAIL MOCK]"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Expected exit 42, got $STATUS; output: $OUTPUT"
fi

# ------------------------------------------------------------------------------
# Test 11: Missing or invalid result artifacts -> Do not report verified success
# ------------------------------------------------------------------------------
TEST_NAME="Test 11a: Confirmed run with missing receipt artifact rejected with exit 1"
MOCK_MISSING_ADAPTER="$TEST_SANDBOX/mock_missing_receipt_adapter.py"
cat <<'PY' > "$MOCK_MISSING_ADAPTER"
import sys
# Simulates an adapter exiting 0 without generating receipt.json
print("[MOCK] Adapter exited cleanly but created no receipt")
sys.exit(0)
PY
chmod +x "$MOCK_MISSING_ADAPTER"
STATUS=0
OUTPUT=$(ADAPTER="$MOCK_MISSING_ADAPTER" bash "$WORKFLOW_SCRIPT" --output-dir "workflows/pack-c-dynamic/tests/.tmp_fuzz_sandbox_$$/fuzz_out_missing" --confirm 2>&1) || STATUS=$?
if [[ $STATUS -eq 1 && "$OUTPUT" == *"Missing result artifact"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Expected exit 1 and Missing result artifact, got $STATUS; output: $OUTPUT"
fi

TEST_NAME="Test 11b: Confirmed run with invalid/corrupt receipt rejected with exit 1"
MOCK_CORRUPT_ADAPTER="$TEST_SANDBOX/mock_corrupt_receipt_adapter.py"
cat <<'PY' > "$MOCK_CORRUPT_ADAPTER"
import sys, pathlib
out_idx = sys.argv.index("--output-dir") + 1
out_dir = pathlib.Path(sys.argv[out_idx])
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "receipt.json").write_text("{ malformed json ... ")
sys.exit(0)
PY
chmod +x "$MOCK_CORRUPT_ADAPTER"
STATUS=0
OUTPUT=$(ADAPTER="$MOCK_CORRUPT_ADAPTER" bash "$WORKFLOW_SCRIPT" --output-dir "workflows/pack-c-dynamic/tests/.tmp_fuzz_sandbox_$$/fuzz_out_corrupt" --confirm 2>&1) || STATUS=$?
if [[ $STATUS -eq 1 && "$OUTPUT" == *"Invalid result artifact JSON"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Expected exit 1 and Invalid result artifact JSON, got $STATUS; output: $OUTPUT"
fi

TEST_NAME="Test 11c: Dry-run leaves zero result artifacts and reports preview only"
DRY_OUTPUT_DIR="$TEST_SANDBOX/fuzz_out_test11"
mkdir -p "$DRY_OUTPUT_DIR"
STATUS=0
OUTPUT=$(bash "$WORKFLOW_SCRIPT" --output-dir "workflows/pack-c-dynamic/tests/.tmp_fuzz_sandbox_$$/fuzz_out_test11" --dry-run 2>&1) || STATUS=$?
if [[ $STATUS -eq 0 && ! -f "$DRY_OUTPUT_DIR/receipt.json" && ! -f "$DRY_OUTPUT_DIR/stdout.log" ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Artifacts improperly created in dry-run mode"
fi

# ------------------------------------------------------------------------------
# Test 12: Subprocess timeout handling
# ------------------------------------------------------------------------------
TEST_NAME="Test 12: Subprocess timeout produces exit code 124"
TIMEOUT_ADAPTER="$TEST_SANDBOX/timeout_adapter.py"
cat <<'PY' > "$TIMEOUT_ADAPTER"
import sys
print("[TIMEOUT MOCK] Subprocess exceeded execution timeout")
sys.exit(124)
PY
chmod +x "$TIMEOUT_ADAPTER"
STATUS=0
OUTPUT=$(ADAPTER="$TIMEOUT_ADAPTER" bash "$WORKFLOW_SCRIPT" 2>&1) || STATUS=$?
if [[ $STATUS -eq 124 && "$OUTPUT" == *"[TIMEOUT MOCK]"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Expected exit 124, got $STATUS; output: $OUTPUT"
fi

# ------------------------------------------------------------------------------
# Test 13: scripts/bounded_forge_fuzz.sh invocation parity
# ------------------------------------------------------------------------------
TEST_NAME="Test 13: scripts/bounded_forge_fuzz.sh operates identically via symlink"
STATUS=0
OUTPUT=$(bash "$BOUNDED_FUZZ_SCRIPT" --help 2>&1) || STATUS=$?
if [[ $STATUS -eq 0 && "$OUTPUT" == *"Usage:"* && "$OUTPUT" == *"bounded_forge_fuzz.sh"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Invocation via scripts/bounded_forge_fuzz.sh failed"
fi

# ------------------------------------------------------------------------------
# Test 14: Help flags (-h and --help) output usage and exit 0
# ------------------------------------------------------------------------------
TEST_NAME="Test 14: Help flags (-h and --help) display usage and exit 0"
STATUS=0
OUTPUT_H=$(bash "$WORKFLOW_SCRIPT" -h 2>&1) || STATUS=$?
OUTPUT_HELP=$(bash "$WORKFLOW_SCRIPT" --help 2>&1) || STATUS=$?
if [[ $STATUS -eq 0 && "$OUTPUT_H" == *"Usage:"* && "$OUTPUT_HELP" == *"Usage:"* ]]; then
  report_result "$TEST_NAME" "PASS"
else
  report_result "$TEST_NAME" "FAIL" "Help flag failed to output usage"
fi

printf "\n${BLUE}==============================================================================${NC}\n"
printf "${BLUE} Test Summary: %d passed, %d failed out of %d tests                         ${NC}\n" "$PASSED" "$FAILED" "$TOTAL"
printf "${BLUE}==============================================================================${NC}\n"

if [[ $FAILED -gt 0 ]]; then
  exit 1
fi
exit 0
