#!/usr/bin/env bash
# ==============================================================================
# Integration Test Suite for Pack C workflow-echidna.sh Execution Wrapper
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd -- "${BASH_SOURCE[0]%/*}" >/dev/null 2>&1 && pwd -P)"
WORKFLOW_DIR="$(cd "$SCRIPT_DIR/.." && pwd -P)"
REPO_ROOT="$(cd "$WORKFLOW_DIR/../.." && pwd -P)"
WRAPPER="$WORKFLOW_DIR/workflow-echidna.sh"

TESTS_PASSED=0
TESTS_FAILED=0

assert_exit() {
  local desc="$1"
  local expected="$2"
  shift 2
  echo -n "[TEST] $desc ... "
  set +e
  "$@" >/dev/null 2>&1
  local actual=$?
  set -e

  if [[ "$actual" -eq "$expected" ]]; then
    echo "PASS (exit $actual)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
  else
    echo "FAIL (expected $expected, got $actual)"
    TESTS_FAILED=$((TESTS_FAILED + 1))
  fi
}

assert_output_contains() {
  local desc="$1"
  local match="$2"
  shift 2
  echo -n "[TEST] $desc ... "
  set +e
  local output
  output="$("$@" 2>&1)"
  local actual=$?
  set -e

  if [[ "$output" == *"$match"* ]]; then
    echo "PASS"
    TESTS_PASSED=$((TESTS_PASSED + 1))
  else
    echo "FAIL (pattern '$match' not found in output)"
    echo "Actual output:"
    echo "$output"
    TESTS_FAILED=$((TESTS_FAILED + 1))
  fi
}

echo "=== Running Integration Tests for workflow-echidna.sh ==="

# 1. Help flag
assert_exit "--help returns exit code 0" 0 "$WRAPPER" --help

# 2. Missing value for options
assert_exit "--slug without value fails with exit code 2" 2 "$WRAPPER" --slug
assert_exit "--target without value fails with exit code 2" 2 "$WRAPPER" --target
assert_exit "--seed without value fails with exit code 2" 2 "$WRAPPER" --seed

# 3. Invalid parameter values
assert_exit "--seed negative number fails with exit code 2" 2 "$WRAPPER" --seed -1
assert_exit "--seed non-numeric fails with exit code 2" 2 "$WRAPPER" --seed abc
assert_exit "--timeout zero fails with exit code 2" 2 "$WRAPPER" --timeout 0
assert_exit "--timeout negative fails with exit code 2" 2 "$WRAPPER" --timeout -10

# 4. Slug traversal
assert_exit "--slug ../escape fails with exit code 2" 2 "$WRAPPER" --slug "../escape"
assert_exit "--slug slash fails with exit code 2" 2 "$WRAPPER" --slug "a/b"

# 5. Path containment escape
assert_exit "--target /etc fails with exit code 2" 2 "$WRAPPER" --target "/etc"

# 6. Target non-existent
assert_exit "Non-existent target fails with exit code 3" 3 "$WRAPPER" --target "bounties/non_existent_path_xyz123"

# 7. Preflight Dry-run against fixture
FIXTURE_DIR="$SCRIPT_DIR/fixtures"
TMP_OUT="$WORKFLOW_DIR/.tmp_test_$$"
mkdir -p "$TMP_OUT"
trap 'rm -rf "$TMP_OUT"' EXIT

assert_exit "Dry-run against fixture returns 0" 0 \
  "$WRAPPER" --target "$FIXTURE_DIR" --output-dir "$TMP_OUT/dry_run" --dry-run

assert_output_contains "Dry-run output contains PREFLIGHT_PASSED" "PREFLIGHT_PASSED" \
  "$WRAPPER" --target "$FIXTURE_DIR" --output-dir "$TMP_OUT/dry_run" --dry-run

# Ensure dry-run created no output files
if [[ -d "$TMP_OUT/dry_run" ]]; then
  echo "[FAIL] Dry-run created directory $TMP_OUT/dry_run"
  TESTS_FAILED=$((TESTS_FAILED + 1))
else
  echo "[TEST] Dry-run zero mutation verified ... PASS"
  TESTS_PASSED=$((TESTS_PASSED + 1))
fi

# 8. Clean simulation
assert_exit "--clean-sim with --confirm returns 0" 0 \
  "$WRAPPER" --target "$FIXTURE_DIR" --output-dir "$TMP_OUT/clean_sim" --confirm --clean-sim

if [[ -f "$TMP_OUT/clean_sim/campaign_manifest.json" && -f "$TMP_OUT/clean_sim/receipt.json" ]]; then
  echo "[TEST] Clean simulation artifacts created ... PASS"
  TESTS_PASSED=$((TESTS_PASSED + 1))
else
  echo "[FAIL] Clean simulation artifacts missing"
  TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# 9. Falsify simulation
assert_exit "--falsify-sim with --confirm returns 0" 0 \
  "$WRAPPER" --target "$FIXTURE_DIR" --output-dir "$TMP_OUT/falsify_sim" --confirm --falsify-sim

if [[ -f "$TMP_OUT/falsify_sim/findings.json" ]]; then
  echo "[TEST] Falsify simulation findings created ... PASS"
  TESTS_PASSED=$((TESTS_PASSED + 1))
else
  echo "[FAIL] Falsify simulation findings missing"
  TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# 10. Fail simulation
assert_exit "--fail-sim with --confirm returns exit code 1" 1 \
  "$WRAPPER" --target "$FIXTURE_DIR" --output-dir "$TMP_OUT/fail_sim" --confirm --fail-sim

echo "=========================================================="
echo "Summary: $TESTS_PASSED passed, $TESTS_FAILED failed"
echo "=========================================================="

if [[ "$TESTS_FAILED" -gt 0 ]]; then
  exit 1
fi
exit 0
