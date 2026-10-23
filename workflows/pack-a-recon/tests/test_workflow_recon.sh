#!/usr/bin/env bash
# ==============================================================================
# Pack A — Smart Contract Reconnaissance Acceptance Test Suite
# Tests workflow-recon.sh across all 17 cases from Section 11 Table
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd -- "${BASH_SOURCE[0]%/*}" >/dev/null 2>&1 && pwd -P)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd -P)"
WORKFLOW="$REPO_ROOT/workflows/pack-a-recon/workflow-recon.sh"
COMPAT_WORKFLOW="$REPO_ROOT/workflows/pack-a-source/workflow-recon.sh"
VALIDATOR="$REPO_ROOT/workflows/pack-e-triage/validate_schemas.py"
SCHEMA="$REPO_ROOT/workflows/pack-a-recon/schemas/recon.schema.json"

TEST_COUNT=0
PASS_COUNT=0

# Unique prefix for safe temporary test bounties
TEST_PREFIX="test_recon_$$"
BOUNTIES_ROOT="$REPO_ROOT/bounties"

cleanup() {
  # Clean up all created test bounties
  find "$BOUNTIES_ROOT" -maxdepth 1 -name "${TEST_PREFIX}_*" -type d -exec chmod -R 755 {} + -exec rm -rf {} + 2>/dev/null || true
}
trap cleanup EXIT INT TERM

assert_eq() {
  local test_name="$1" expected="$2" actual="$3"
  TEST_COUNT=$((TEST_COUNT + 1))
  if [[ "$expected" == "$actual" ]]; then
    echo "  [PASS] Test $TEST_COUNT: $test_name"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    echo "  [FAIL] Test $TEST_COUNT: $test_name (Expected '$expected', got '$actual')" >&2
    exit 1
  fi
}

assert_match() {
  local test_name="$1" pattern="$2" actual="$3"
  TEST_COUNT=$((TEST_COUNT + 1))
  if [[ "$actual" =~ $pattern ]]; then
    echo "  [PASS] Test $TEST_COUNT: $test_name"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    echo "  [FAIL] Test $TEST_COUNT: $test_name (Pattern '$pattern' not matched in: '$actual')" >&2
    exit 1
  fi
}

echo "=== Running Pack A Reconnaissance Section 11 Acceptance Suite ==="

# --- Test 1: No arguments (Dry-run behavior; no filesystem writes) ---
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" 2>&1)" || EXIT_CODE=$?
assert_eq "Test 1: No arguments exits 0" "0" "$EXIT_CODE"
assert_match "Test 1: No arguments reports dry-run mode" "\[DRY-RUN\]" "$OUTPUT"
assert_match "Test 1: No arguments targets default slug base" "Reconnaissance \(base\)" "$OUTPUT"

# --- Test 2: --dry-run (No writes or scanners) ---
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --dry-run 2>&1)" || EXIT_CODE=$?
assert_eq "Test 2: --dry-run exits 0" "0" "$EXIT_CODE"
assert_match "Test 2: --dry-run reports target output" "Target output:" "$OUTPUT"

# --- Setup Fixture Bounties for Subsequent Tests ---
TEST_SLUG="${TEST_PREFIX}_standard"
mkdir -p "$BOUNTIES_ROOT/$TEST_SLUG/src"
echo "// SPDX-License-Identifier: MIT" > "$BOUNTIES_ROOT/$TEST_SLUG/src/ContractA.sol"
echo "contract ContractA {}" >> "$BOUNTIES_ROOT/$TEST_SLUG/src/ContractA.sol"

# --- Test 3: --confirm (Executes core discovery when prerequisites pass) ---
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "$TEST_SLUG" --confirm 2>&1)" || EXIT_CODE=$?
assert_eq "Test 3: --confirm exits 0" "0" "$EXIT_CODE"
assert_match "Test 3: --confirm reports OK" "\[OK\] Reconnaissance recorded" "$OUTPUT"
RECON_FILE="$BOUNTIES_ROOT/$TEST_SLUG/scans/recon.json"
if [[ -f "$RECON_FILE" ]]; then
  STATUS=$(python3 -c "import json; d=json.load(open('$RECON_FILE')); print(d['status'])")
  assert_eq "Test 3: Status is RECON_COMPLETE" "RECON_COMPLETE" "$STATUS"
  COUNT=$(python3 -c "import json; d=json.load(open('$RECON_FILE')); print(d['contracts_found'])")
  assert_eq "Test 3: Exactly 1 contract found" "1" "$COUNT"
else
  echo "  [FAIL] Test 3: $RECON_FILE was not created" >&2
  exit 1
fi

# --- Test 4: --dry-run --confirm (Dry-run wins) ---
# Remove file, then test that dry-run + confirm produces no write
rm -f "$RECON_FILE"
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "$TEST_SLUG" --dry-run --confirm 2>&1)" || EXIT_CODE=$?
assert_eq "Test 4: --dry-run --confirm exits 0" "0" "$EXIT_CODE"
assert_match "Test 4: Dry-run takes precedence" "\[DRY-RUN\]" "$OUTPUT"
if [[ -f "$RECON_FILE" ]]; then
  echo "  [FAIL] Test 4: File was created despite --dry-run" >&2
  exit 1
else
  TEST_COUNT=$((TEST_COUNT + 1))
  echo "  [PASS] Test $TEST_COUNT: No artifact written when --dry-run accompanies --confirm"
  PASS_COUNT=$((PASS_COUNT + 1))
fi

# --- Test 5: --slug <slug> --confirm (Uses correct bounty directory) ---
# Re-run confirm to recreate file
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "$TEST_SLUG" --confirm 2>&1)" || EXIT_CODE=$?
assert_eq "Test 5: Explicit slug confirmed run succeeds" "0" "$EXIT_CODE"
SLUG_RECORDED=$(python3 -c "import json; d=json.load(open('$RECON_FILE')); print(d['slug'])")
assert_eq "Test 5: Correct slug recorded in artifact" "$TEST_SLUG" "$SLUG_RECORDED"

# --- Test 6: Missing --slug value (Clear error and nonzero exit) ---
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug 2>&1)" || EXIT_CODE=$?
if [[ "$EXIT_CODE" -ne 0 ]]; then
  TEST_COUNT=$((TEST_COUNT + 1))
  echo "  [PASS] Test $TEST_COUNT: Missing --slug value rejected with non-zero exit ($EXIT_CODE)"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  echo "  [FAIL] Test 6: Missing --slug unexpectedly exited 0" >&2
  exit 1
fi
assert_match "Test 6: Clear error message for missing slug" "Error: --slug requires a non-empty value" "$OUTPUT"

# --- Test 7: Unknown option (Clear error and nonzero exit) ---
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --unrecognized-flag 2>&1)" || EXIT_CODE=$?
if [[ "$EXIT_CODE" -ne 0 ]]; then
  TEST_COUNT=$((TEST_COUNT + 1))
  echo "  [PASS] Test $TEST_COUNT: Unknown option rejected with non-zero exit ($EXIT_CODE)"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  echo "  [FAIL] Test 7: Unknown option unexpectedly exited 0" >&2
  exit 1
fi
assert_match "Test 7: Clear error message for unknown option" "Error: Unknown argument" "$OUTPUT"

# --- Test 8: Empty or traversal slug (Rejected before filesystem writes) ---
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "" 2>&1)" || EXIT_CODE=$?
assert_eq "Test 8a: Empty slug rejected" "2" "$EXIT_CODE"

EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "../cantina" 2>&1)" || EXIT_CODE=$?
assert_eq "Test 8b: Traversal slug rejected" "2" "$EXIT_CODE"

EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "/etc/passwd" 2>&1)" || EXIT_CODE=$?
assert_eq "Test 8c: Absolute path slug rejected" "2" "$EXIT_CODE"

EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "bad/slash" 2>&1)" || EXIT_CODE=$?
assert_eq "Test 8d: Slash in slug rejected" "2" "$EXIT_CODE"

# --- Test 9: Missing bounty directory (Blocked or failed according to contract) ---
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "${TEST_PREFIX}_nonexistent_workspace" --confirm 2>&1)" || EXIT_CODE=$?
if [[ "$EXIT_CODE" -ne 0 ]]; then
  TEST_COUNT=$((TEST_COUNT + 1))
  echo "  [PASS] Test $TEST_COUNT: Missing bounty directory blocked cleanly with exit $EXIT_CODE"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  echo "  [FAIL] Test 9: Missing bounty directory unexpectedly succeeded" >&2
  exit 1
fi
assert_match "Test 9: Clear error on missing directory" "Bounty directory does not exist" "$OUTPUT"

# --- Test 10: Empty valid bounty directory (Zero contracts only if traversal succeeds) ---
TEST_EMPTY_SLUG="${TEST_PREFIX}_empty"
mkdir -p "$BOUNTIES_ROOT/$TEST_EMPTY_SLUG"
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "$TEST_EMPTY_SLUG" --confirm 2>&1)" || EXIT_CODE=$?
assert_eq "Test 10: Empty directory scan succeeds" "0" "$EXIT_CODE"
EMPTY_FILE="$BOUNTIES_ROOT/$TEST_EMPTY_SLUG/scans/recon.json"
COUNT_EMPTY=$(python3 -c "import json; d=json.load(open('$EMPTY_FILE')); print(d['contracts_found'])")
assert_eq "Test 10: Exactly 0 contracts found" "0" "$COUNT_EMPTY"
STATUS_EMPTY=$(python3 -c "import json; d=json.load(open('$EMPTY_FILE')); print(d['status'])")
assert_eq "Test 10: Status is RECON_COMPLETE" "RECON_COMPLETE" "$STATUS_EMPTY"

# --- Test 11: Nested Solidity files (Count matches documented scope) ---
TEST_NESTED_SLUG="${TEST_PREFIX}_nested"
mkdir -p "$BOUNTIES_ROOT/$TEST_NESTED_SLUG/src/core/vault"
mkdir -p "$BOUNTIES_ROOT/$TEST_NESTED_SLUG/src/interfaces"
mkdir -p "$BOUNTIES_ROOT/$TEST_NESTED_SLUG/test/mocks"
echo "contract Vault {}" > "$BOUNTIES_ROOT/$TEST_NESTED_SLUG/src/core/vault/Vault.sol"
echo "interface IVault {}" > "$BOUNTIES_ROOT/$TEST_NESTED_SLUG/src/interfaces/IVault.sol"
echo "contract MockVault {}" > "$BOUNTIES_ROOT/$TEST_NESTED_SLUG/test/mocks/MockVault.sol"
echo "This is not a solidity file" > "$BOUNTIES_ROOT/$TEST_NESTED_SLUG/src/README.txt"

EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "$TEST_NESTED_SLUG" --confirm 2>&1)" || EXIT_CODE=$?
assert_eq "Test 11: Nested discovery succeeds" "0" "$EXIT_CODE"
NESTED_FILE="$BOUNTIES_ROOT/$TEST_NESTED_SLUG/scans/recon.json"
COUNT_NESTED=$(python3 -c "import json; d=json.load(open('$NESTED_FILE')); print(d['contracts_found'])")
assert_eq "Test 11: Exactly 3 solidity files found" "3" "$COUNT_NESTED"

# --- Test 12: Files containing unusual names (JSON remains valid and safe) ---
TEST_UNUSUAL_SLUG="${TEST_PREFIX}_unusual"
mkdir -p "$BOUNTIES_ROOT/$TEST_UNUSUAL_SLUG/src"
echo "contract Unusual1 {}" > "$BOUNTIES_ROOT/$TEST_UNUSUAL_SLUG/src/Contract with spaces.sol"
echo "contract Unusual2 {}" > "$BOUNTIES_ROOT/$TEST_UNUSUAL_SLUG/src/Contract-with-dashes.sol"
echo "contract Unusual3 {}" > "$BOUNTIES_ROOT/$TEST_UNUSUAL_SLUG/src/Contract_with_underscores_123.sol"

EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "$TEST_UNUSUAL_SLUG" --confirm 2>&1)" || EXIT_CODE=$?
assert_eq "Test 12: Unusual names scan succeeds" "0" "$EXIT_CODE"
UNUSUAL_FILE="$BOUNTIES_ROOT/$TEST_UNUSUAL_SLUG/scans/recon.json"
COUNT_UNUSUAL=$(python3 -c "import json; d=json.load(open('$UNUSUAL_FILE')); print(d['contracts_found'])")
assert_eq "Test 12: Exactly 3 contracts with unusual names counted" "3" "$COUNT_UNUSUAL"
# Verify JSON parsing
EXIT_CODE=0
python3 -c "import json; json.load(open('$UNUSUAL_FILE'))" || EXIT_CODE=$?
assert_eq "Test 12: recon.json parses cleanly with json.load" "0" "$EXIT_CODE"

# --- Test 13: Permission-denied traversal (No false successful completion) ---
TEST_PERM_SLUG="${TEST_PREFIX}_perm"
mkdir -p "$BOUNTIES_ROOT/$TEST_PERM_SLUG/src/forbidden"
echo "contract Secret {}" > "$BOUNTIES_ROOT/$TEST_PERM_SLUG/src/forbidden/Secret.sol"
chmod 000 "$BOUNTIES_ROOT/$TEST_PERM_SLUG/src/forbidden"

EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "$TEST_PERM_SLUG" --confirm 2>&1)" || EXIT_CODE=$?
chmod 755 "$BOUNTIES_ROOT/$TEST_PERM_SLUG/src/forbidden"
if [[ "$EXIT_CODE" -ne 0 ]]; then
  TEST_COUNT=$((TEST_COUNT + 1))
  echo "  [PASS] Test $TEST_COUNT: Permission-denied traversal rejected with non-zero exit ($EXIT_CODE)"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  echo "  [FAIL] Test 13: Permission-denied traversal falsely reported success" >&2
  exit 1
fi
assert_match "Test 13: Traversal incomplete message" "Traversal incomplete due to errors" "$OUTPUT"

# --- Test 14: Invalid generated JSON (Validation fails; previous valid artifact is preserved) ---
TEST_CORRUPT_SLUG="${TEST_PREFIX}_corrupt"
mkdir -p "$BOUNTIES_ROOT/$TEST_CORRUPT_SLUG/src"
echo "contract Baseline {}" > "$BOUNTIES_ROOT/$TEST_CORRUPT_SLUG/src/Baseline.sol"
# 14a: Create a valid baseline artifact
"$WORKFLOW" --slug "$TEST_CORRUPT_SLUG" --confirm >/dev/null
CORRUPT_TARGET="$BOUNTIES_ROOT/$TEST_CORRUPT_SLUG/scans/recon.json"
BASELINE_TIMESTAMP=$(python3 -c "import json; d=json.load(open('$CORRUPT_TARGET')); print(d['timestamp'])")

# 14b: Trigger simulated corruption
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "$TEST_CORRUPT_SLUG" --confirm --corrupt-json-sim 2>&1)" || EXIT_CODE=$?
if [[ "$EXIT_CODE" -ne 0 ]]; then
  TEST_COUNT=$((TEST_COUNT + 1))
  echo "  [PASS] Test $TEST_COUNT: Corrupted JSON simulation rejected with exit $EXIT_CODE"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  echo "  [FAIL] Test 14: Corrupted JSON simulation unexpectedly passed" >&2
  exit 1
fi
# 14c: Verify previous artifact is preserved intact
AFTER_TIMESTAMP=$(python3 -c "import json; d=json.load(open('$CORRUPT_TARGET')); print(d['timestamp'])")
assert_eq "Test 14: Previous valid artifact was preserved untouched" "$BASELINE_TIMESTAMP" "$AFTER_TIMESTAMP"

# --- Test 15: Simulated scanner failure (Failure is reported and not mislabeled as success) ---
TEST_SCAN_SLUG="${TEST_PREFIX}_scan_fail"
mkdir -p "$BOUNTIES_ROOT/$TEST_SCAN_SLUG/src"
echo "contract ScanMe {}" > "$BOUNTIES_ROOT/$TEST_SCAN_SLUG/src/ScanMe.sol"
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "$TEST_SCAN_SLUG" --confirm --fail-scanner-sim 2>&1)" || EXIT_CODE=$?
assert_eq "Test 15: Run with simulated scanner failure executes" "0" "$EXIT_CODE"
SCAN_FAIL_FILE="$BOUNTIES_ROOT/$TEST_SCAN_SLUG/scans/recon.json"
TOOL_STATUS=$(python3 -c "import json; d=json.load(open('$SCAN_FAIL_FILE')); print(d['tools'][0]['status'])")
assert_eq "Test 15: Tool status explicitly records 'failed'" "failed" "$TOOL_STATUS"

# --- Test 16: Existing user modifications (Unrelated changes remain untouched) ---
USER_NOTE="$BOUNTIES_ROOT/$TEST_SLUG/user_findings_notes.md"
echo "# User Manual Audit Findings" > "$USER_NOTE"
echo "- Line 42 reentrancy suspect" >> "$USER_NOTE"
"$WORKFLOW" --slug "$TEST_SLUG" --confirm >/dev/null
if [[ -f "$USER_NOTE" ]] && grep -q "Line 42 reentrancy suspect" "$USER_NOTE"; then
  TEST_COUNT=$((TEST_COUNT + 1))
  echo "  [PASS] Test $TEST_COUNT: User modifications in bounty directory preserved untouched"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  echo "  [FAIL] Test 16: User file was altered or destroyed" >&2
  exit 1
fi

# --- Test 17: Repeated run (Output structure remains stable and no duplicate inventory entries occur) ---
"$WORKFLOW" --slug "$TEST_NESTED_SLUG" --confirm >/dev/null
RUN1_INV=$(python3 -c "import json; d=json.load(open('$NESTED_FILE')); print(','.join(d['inventory']))")
"$WORKFLOW" --slug "$TEST_NESTED_SLUG" --confirm >/dev/null
RUN2_INV=$(python3 -c "import json; d=json.load(open('$NESTED_FILE')); print(','.join(d['inventory']))")
assert_eq "Test 17: Repeated runs produce identical deterministic inventory" "$RUN1_INV" "$RUN2_INV"

# --- Test 18: Compatibility Wrapper (pack-a-source/workflow-recon.sh delegates seamlessly) ---
EXIT_CODE=0
OUTPUT="$("$COMPAT_WORKFLOW" --slug "$TEST_SLUG" --dry-run 2>&1)" || EXIT_CODE=$?
assert_eq "Test 18: Compatibility wrapper dry-run exits 0" "0" "$EXIT_CODE"
assert_match "Test 18: Compatibility wrapper delegates to Pack A recon" "Reconnaissance \($TEST_SLUG\)" "$OUTPUT"

# --- Test 19: Schema Validator Integration (validate_schemas.py --recon) ---
EXIT_CODE=0
OUTPUT="$(python3 "$VALIDATOR" --recon "$RECON_FILE" 2>&1)" || EXIT_CODE=$?
assert_eq "Test 19: validate_schemas.py validates recon.json against schema" "0" "$EXIT_CODE"
assert_match "Test 19: Validation passed message" "SCHEMA_VALIDATION_PASSED" "$OUTPUT"

# --- Test 20: Fallback Schema Validation without jsonschema package ---
EXIT_CODE=0
OUTPUT="$(python3 -c "import sys, unittest.mock as mock, json; sys.path.insert(0, '$REPO_ROOT/workflows/pack-e-triage'); import validate_schemas; data = json.load(open('$RECON_FILE'));
with mock.patch.dict('sys.modules', {'jsonschema': None}):
    ok, err = validate_schemas.validate_artifact(data, {}, '$RECON_FILE', 'recon')
    if not ok: sys.exit(err)
    print('FALLBACK_VALIDATION_PASSED')
" 2>&1)" || EXIT_CODE=$?
assert_eq "Test 20: Fallback schema validation succeeds when jsonschema package missing" "0" "$EXIT_CODE"
assert_match "Test 20: Fallback passed message" "FALLBACK_VALIDATION_PASSED" "$OUTPUT"

# --- Test 21: Architecture Script Entrypoint (scripts/recon.sh) ---
SCRIPTS_WRAPPER="$REPO_ROOT/scripts/recon.sh"
if [[ -x "$SCRIPTS_WRAPPER" ]]; then
  EXIT_CODE=0
  OUTPUT="$("$SCRIPTS_WRAPPER" --slug "$TEST_SLUG" --dry-run 2>&1)" || EXIT_CODE=$?
  assert_eq "Test 21: scripts/recon.sh wrapper exits 0" "0" "$EXIT_CODE"
  assert_match "Test 21: scripts/recon.sh delegates to recon workflow" "Reconnaissance \($TEST_SLUG\)" "$OUTPUT"
else
  echo "  [FAIL] Test 21: scripts/recon.sh does not exist or is not executable" >&2
  exit 1
fi

# --- Test 22: Architecture Python Entrypoint (scripts/recon.py) ---
PY_WRAPPER="$REPO_ROOT/scripts/recon.py"
if [[ -f "$PY_WRAPPER" ]]; then
  EXIT_CODE=0
  OUTPUT="$(python3 "$PY_WRAPPER" --slug "$TEST_SLUG" --dry-run 2>&1)" || EXIT_CODE=$?
  assert_eq "Test 22: scripts/recon.py wrapper exits 0" "0" "$EXIT_CODE"
  assert_match "Test 22: scripts/recon.py reports dry-run" "\[DRY-RUN\] Target output" "$OUTPUT"
else
  echo "  [FAIL] Test 22: scripts/recon.py does not exist" >&2
  exit 1
fi

# --- Test 23: Section 12 Output Contract Report Format ---
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "$TEST_SLUG" --confirm 2>&1)" || EXIT_CODE=$?
assert_eq "Test 23: Confirmed workflow execution exits 0" "0" "$EXIT_CODE"
assert_match "Test 23: Report header emitted" "PACK A — RECONNAISSANCE REPORT" "$OUTPUT"
assert_match "Test 23: Core status emitted" "Core status: RECON_COMPLETE" "$OUTPUT"
assert_match "Test 23: Recommended next stage emitted" "Recommended next stage: Pack B" "$OUTPUT"

echo ""
echo "=== All $TEST_COUNT Acceptance Tests Passed Cleanly ($PASS_COUNT/$TEST_COUNT) ==="
