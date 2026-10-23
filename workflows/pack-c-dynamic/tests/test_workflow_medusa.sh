#!/usr/bin/env bash
# ==============================================================================
# Integration Test Suite for Pack C workflow-medusa.sh Execution Wrapper
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd -- "${BASH_SOURCE[0]%/*}" >/dev/null 2>&1 && pwd -P)"
WORKFLOW_DIR="$(cd "$SCRIPT_DIR/.." && pwd -P)"
REPO_ROOT="$(cd "$WORKFLOW_DIR/../.." && pwd -P)"
WRAPPER="$WORKFLOW_DIR/workflow-medusa.sh"

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

echo "=== Running Integration Tests for workflow-medusa.sh ==="

# 1. Help flag
assert_exit "--help returns exit code 0" 0 "$WRAPPER" --help
assert_exit "-h returns exit code 0" 0 "$WRAPPER" -h

# 2. Missing value for options
assert_exit "--slug without value fails with exit code 2" 2 "$WRAPPER" --slug
assert_exit "--target without value fails with exit code 2" 2 "$WRAPPER" --target
assert_exit "--timeout without value fails with exit code 2" 2 "$WRAPPER" --timeout
assert_exit "--seed without value fails with exit code 2" 2 "$WRAPPER" --seed
assert_exit "--workers without value fails with exit code 2" 2 "$WRAPPER" --workers
assert_exit "--test-limit without value fails with exit code 2" 2 "$WRAPPER" --test-limit
assert_exit "--report-dir without value fails with exit code 2" 2 "$WRAPPER" --report-dir

# 3. Unknown flag fails with exit code 2
assert_exit "--invalid-flag fails with exit code 2" 2 "$WRAPPER" --invalid-flag

# 4. Invalid parameter values
assert_exit "--seed negative number fails with exit code 2" 2 "$WRAPPER" --seed -1
assert_exit "--seed non-numeric fails with exit code 2" 2 "$WRAPPER" --seed abc
assert_exit "--timeout zero fails with exit code 2" 2 "$WRAPPER" --timeout 0
assert_exit "--timeout negative fails with exit code 2" 2 "$WRAPPER" --timeout -10
assert_exit "--workers zero fails with exit code 2" 2 "$WRAPPER" --workers 0
assert_exit "--test-limit negative fails with exit code 2" 2 "$WRAPPER" --test-limit -5

# 5. Slug traversal
assert_exit "--slug ../escape fails with exit code 2" 2 "$WRAPPER" --slug "../escape"
assert_exit "--slug slash fails with exit code 2" 2 "$WRAPPER" --slug "a/b"

# 6. Path containment escape
assert_exit "--target /etc fails with exit code 2" 2 "$WRAPPER" --target "/etc"
assert_exit "--target containing traversal fails with exit code 2" 2 "$WRAPPER" --target "workflows/../escaped"

# 7. Target non-existent
assert_exit "Non-existent target fails with exit code 3" 3 "$WRAPPER" --target "bounties/non_existent_path_xyz123"

# 8. Preflight Dry-run against fixture
FIXTURE_DIR="$SCRIPT_DIR/fixtures"
TMP_OUT="$WORKFLOW_DIR/.tmp_medusa_test_$$"
mkdir -p "$TMP_OUT"
cleanup() {
  rm -rf "$TMP_OUT"
}
trap cleanup EXIT

assert_exit "Dry-run against fixture returns 0" 0 \
  "$WRAPPER" --target "$FIXTURE_DIR" --output-dir "$TMP_OUT/dry_run" --dry-run

assert_output_contains "Dry-run output contains PREFLIGHT_PASSED" "PREFLIGHT_PASSED" \
  "$WRAPPER" --target "$FIXTURE_DIR" --output-dir "$TMP_OUT/dry_run" --dry-run

# Ensure dry-run created no output files (zero mutation)
if [[ -d "$TMP_OUT/dry_run" ]]; then
  echo "[FAIL] Dry-run created directory $TMP_OUT/dry_run"
  TESTS_FAILED=$((TESTS_FAILED + 1))
else
  echo "[TEST] Dry-run zero mutation verified ... PASS"
  TESTS_PASSED=$((TESTS_PASSED + 1))
fi

# 9. Dry-run precedence over confirm
assert_exit "--confirm with --dry-run still executes in dry-run mode" 0 \
  "$WRAPPER" --target "$FIXTURE_DIR" --output-dir "$TMP_OUT/dry_run_precedence" --confirm --dry-run

if [[ -d "$TMP_OUT/dry_run_precedence" ]]; then
  echo "[FAIL] Dry-run precedence created directory $TMP_OUT/dry_run_precedence"
  TESTS_FAILED=$((TESTS_FAILED + 1))
else
  echo "[TEST] Dry-run precedence zero mutation verified ... PASS"
  TESTS_PASSED=$((TESTS_PASSED + 1))
fi

# 10. Clean simulation
assert_exit "--clean-sim with --confirm returns 0" 0 \
  "$WRAPPER" --target "$FIXTURE_DIR" --output-dir "$TMP_OUT/clean_sim" --confirm --clean-sim

if [[ -f "$TMP_OUT/clean_sim/campaign_manifest.json" && -f "$TMP_OUT/clean_sim/receipt.json" && -f "$TMP_OUT/clean_sim/envelope.json" ]]; then
  echo "[TEST] Clean simulation artifacts created ... PASS"
  TESTS_PASSED=$((TESTS_PASSED + 1))
else
  echo "[FAIL] Clean simulation artifacts missing"
  TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# 11. Falsify simulation
assert_exit "--falsify-sim with --confirm returns 0" 0 \
  "$WRAPPER" --target "$FIXTURE_DIR" --output-dir "$TMP_OUT/falsify_sim" --confirm --falsify-sim

if [[ -f "$TMP_OUT/falsify_sim/findings.json" && -f "$TMP_OUT/falsify_sim/campaign_manifest.json" ]]; then
  echo "[TEST] Falsify simulation findings created ... PASS"
  TESTS_PASSED=$((TESTS_PASSED + 1))
else
  echo "[FAIL] Falsify simulation findings missing"
  TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# 12. Fail simulation
assert_exit "--fail-sim with --confirm returns exit code 1" 1 \
  "$WRAPPER" --target "$FIXTURE_DIR" --output-dir "$TMP_OUT/fail_sim" --confirm --fail-sim

# 13. Operator-reviewed MEDUSA_COMMAND tests
# Relative MEDUSA_COMMAND rejected
assert_exit "Relative MEDUSA_COMMAND fails with exit code 2" 2 \
  env MEDUSA_COMMAND="relative/cmd" "$WRAPPER" --target "$FIXTURE_DIR" --output-dir "$TMP_OUT/rel_cmd"

# Non-executable MEDUSA_COMMAND rejected
NON_EXEC="$TMP_OUT/non_exec.sh"
touch "$NON_EXEC"
assert_exit "Non-executable MEDUSA_COMMAND fails with exit code 2" 2 \
  env MEDUSA_COMMAND="$NON_EXEC" "$WRAPPER" --target "$FIXTURE_DIR" --output-dir "$TMP_OUT/non_exec"

# Valid reviewed MEDUSA_COMMAND dry-run
MOCK_MEDUSA="$TMP_OUT/mock_medusa.sh"
cat <<'EOF_MOCK' > "$MOCK_MEDUSA"
#!/usr/bin/env bash
echo "All properties passed"
exit 0
EOF_MOCK
chmod +x "$MOCK_MEDUSA"

assert_exit "Reviewed MEDUSA_COMMAND in dry-run returns 0" 0 \
  env MEDUSA_COMMAND="$MOCK_MEDUSA" "$WRAPPER" --target "$FIXTURE_DIR" --output-dir "$TMP_OUT/mock_dry" --dry-run

assert_exit "Reviewed MEDUSA_COMMAND with --confirm runs successfully" 0 \
  env MEDUSA_COMMAND="$MOCK_MEDUSA" "$WRAPPER" --target "$FIXTURE_DIR" --report-dir "$TMP_OUT/mock_run" --confirm

if ls "$TMP_OUT/mock_run"/medusa-*.log >/dev/null 2>&1; then
  echo "[TEST] MEDUSA_COMMAND log created ... PASS"
  TESTS_PASSED=$((TESTS_PASSED + 1))
else
  echo "[FAIL] MEDUSA_COMMAND log missing"
  TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# Ensure MEDUSA_COMMAND with --confirm generates full Glassbox artifacts
if [[ -f "$TMP_OUT/mock_run/campaign_manifest.json" && -f "$TMP_OUT/mock_run/receipt.json" && -f "$TMP_OUT/mock_run/envelope.json" ]]; then
  echo "[TEST] MEDUSA_COMMAND Glassbox Mirror Plane artifacts generated ... PASS"
  TESTS_PASSED=$((TESTS_PASSED + 1))
else
  echo "[FAIL] MEDUSA_COMMAND Glassbox Mirror Plane artifacts missing"
  TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# 14. Bounty workspace root target containment
assert_exit "Targeting bounty workspace root in dry-run returns 0" 0 \
  "$WRAPPER" --target "bounties/base" --dry-run

# 15. medusa_adapter.py independent path containment verification
MEDUSA_ADAPTER="$REPO_ROOT/.agents/skills/qrpe/adapters/medusa_adapter.py"
if [[ -f "$MEDUSA_ADAPTER" ]]; then
  assert_exit "medusa_adapter.py rejects escaped target with exit 1" 1 \
    python3 "$MEDUSA_ADAPTER" --target "/tmp" --output-dir "$REPO_ROOT/bounties/base/scans/medusa" --dry-run
  assert_exit "medusa_adapter.py rejects escaped output-dir with exit 1" 1 \
    python3 "$MEDUSA_ADAPTER" --target "$REPO_ROOT/bounties/base/contracts" --output-dir "/tmp/test" --dry-run
fi

echo "=========================================================="
echo "Summary: $TESTS_PASSED passed, $TESTS_FAILED failed"
echo "=========================================================="

if [[ "$TESTS_FAILED" -gt 0 ]]; then
  exit 1
fi
exit 0
