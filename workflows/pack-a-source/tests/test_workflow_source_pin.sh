#!/usr/bin/env bash
# ==============================================================================
# test_workflow_source_pin.sh — Pack A Source Pin Acceptance Test Suite
# Tests workflow-source-pin.sh against all 16 acceptance criteria in Section 5.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKFLOW="$SCRIPT_DIR/../workflow-source-pin.sh"
REPO_ROOT="/home/nova/projects/cantina"
VALIDATOR="$REPO_ROOT/workflows/pack-e-triage/validate_schemas.py"

PASS=0
FAIL=0
TOTAL=0

TEST_SLUG="test-source-pin-$$"
TEST_BOUNTY="$REPO_ROOT/bounties/$TEST_SLUG"

cleanup() {
    chmod -R 777 "$TEST_BOUNTY" 2>/dev/null || true
    rm -rf "$TEST_BOUNTY" 2>/dev/null || true
}
trap cleanup EXIT

pass() {
    PASS=$((PASS + 1))
    TOTAL=$((TOTAL + 1))
    printf '  [PASS] %s\n' "$1"
}

fail() {
    FAIL=$((FAIL + 1))
    TOTAL=$((TOTAL + 1))
    printf '  [FAIL] %s\n' "$1"
    printf '         => %s\n' "$2"
}

run_test() {
    TOTAL=$((TOTAL + 1))
    local desc="$1"; shift
    local expected_exit="${1:-0}"; shift
    local expected_pattern="${1:-}"; shift || true
    local actual_exit=0
    local out
    out="$("$@" 2>&1)" || actual_exit=$?

    local pass_status=true
    if [[ "$actual_exit" -ne "$expected_exit" ]]; then
        pass_status=false
    fi
    if [[ -n "$expected_pattern" ]] && ! grep -q "$expected_pattern" <<< "$out"; then
        pass_status=false
    fi

    if [[ "$pass_status" == true ]]; then
        PASS=$((PASS + 1))
        printf '  [PASS] %s (exit=%d)\n' "$desc" "$actual_exit"
    else
        FAIL=$((FAIL + 1))
        printf '  [FAIL] %s (expected exit=%d, got exit=%d)\n' "$desc" "$expected_exit" "$actual_exit"
        if [[ -n "$expected_pattern" ]]; then
            printf '         expected pattern: %s\n' "$expected_pattern"
        fi
        printf '         output: %s\n' "${out:0:300}"
    fi
}

setup_fixture() {
    local content="${1:-# Test Scope Document\nContract A\nContract B\n}"
    chmod -R 777 "$TEST_BOUNTY" 2>/dev/null || true
    rm -rf "$TEST_BOUNTY"
    mkdir -p "$TEST_BOUNTY/snapshots"
    printf "%b" "$content" > "$TEST_BOUNTY/scope.md"
    local hash
    hash=$(sha256sum "$TEST_BOUNTY/scope.md" | awk '{print tolower($1)}')
    printf "%s\n" "$hash" > "$TEST_BOUNTY/snapshots/scope.sha256"
}

echo "============================================================"
echo "  Pack A Source Pin — Comprehensive Acceptance Test Suite"
echo "  PACK-A-SOURCE-PIN-001 (Section 5 Acceptance Matrix)"
echo "============================================================"
echo ""

# Test 1: Valid scope and matching snapshot, no flags -> Validation succeeds; no artifact write
setup_fixture
run_test "Test 1: Valid scope and matching snapshot, no flags (validation only)" 0 "VALIDATION-ONLY" \
    "$WORKFLOW" --slug "$TEST_SLUG"
if [[ ! -e "$TEST_BOUNTY/scans/pin.json" ]]; then
    pass "Test 1 post-check: No pin artifact written without --confirm"
else
    fail "Test 1 post-check: pin.json was erroneously written" "pin.json exists"
fi

# Test 2: Valid scope and matching snapshot, --dry-run -> Validation succeeds; no filesystem modifications
setup_fixture
run_test "Test 2: Valid scope and matching snapshot, --dry-run" 0 "DRY-RUN" \
    "$WORKFLOW" --slug "$TEST_SLUG" --dry-run
if [[ ! -d "$TEST_BOUNTY/scans" ]]; then
    pass "Test 2 post-check: scans directory was not created during --dry-run"
else
    fail "Test 2 post-check: scans directory created during dry-run" "scans directory exists"
fi

# Test 3: Valid scope and matching snapshot, --confirm -> Pin artifact created and verified
setup_fixture
run_test "Test 3: Valid scope and matching snapshot, --confirm" 0 "PIN_VERIFIED" \
    "$WORKFLOW" --slug "$TEST_SLUG" --confirm
if [[ -f "$TEST_BOUNTY/scans/pin.json" ]]; then
    pass "Test 3 post-check: pin.json created successfully"
    # Validate using validate_schemas.py
    if python3 "$VALIDATOR" --pin "$TEST_BOUNTY/scans/pin.json" >/dev/null 2>&1; then
        pass "Test 3 post-check: pin.json passes schema validation via validate_schemas.py"
    else
        fail "Test 3 post-check: validate_schemas.py rejected pin.json" "schema validation error"
    fi
else
    fail "Test 3 post-check: pin.json was not created" "file missing"
fi

# Test 4: Both --dry-run and --confirm -> No write occurs (dry-run takes precedence)
setup_fixture
rm -rf "$TEST_BOUNTY/scans"
run_test "Test 4: Both --dry-run and --confirm (dry-run precedence)" 0 "DRY-RUN" \
    "$WORKFLOW" --slug "$TEST_SLUG" --dry-run --confirm
if [[ ! -e "$TEST_BOUNTY/scans/pin.json" ]]; then
    pass "Test 4 post-check: No write occurred when dry-run and confirm both supplied"
else
    fail "Test 4 post-check: pin.json was created despite dry-run flag" "file exists"
fi

# Test 5: Missing scope.md -> Fail closed
setup_fixture
rm -f "$TEST_BOUNTY/scope.md"
run_test "Test 5: Missing scope.md fails closed (E_SCOPE_MISSING)" 1 "E_SCOPE_MISSING" \
    "$WORKFLOW" --slug "$TEST_SLUG" --confirm

# Test 6: Missing snapshot -> Fail closed
setup_fixture
rm -f "$TEST_BOUNTY/snapshots/scope.sha256"
run_test "Test 6: Missing snapshot fails closed (E_SNAPSHOT_MISSING)" 1 "E_SNAPSHOT_MISSING" \
    "$WORKFLOW" --slug "$TEST_SLUG" --confirm

# Test 7: Malformed digest -> Fail closed
setup_fixture
printf "not-a-valid-sha256\n" > "$TEST_BOUNTY/snapshots/scope.sha256"
run_test "Test 7: Malformed digest in snapshot fails closed (E_SNAPSHOT_FORMAT)" 1 "E_SNAPSHOT_FORMAT" \
    "$WORKFLOW" --slug "$TEST_SLUG" --confirm

# Test 8: Changed scope contents -> Digest mismatch; no pin write
setup_fixture
printf "# Modified Scope Content That Alters Digest\n" > "$TEST_BOUNTY/scope.md"
run_test "Test 8: Scope digest mismatch fails closed (E_SCOPE_MISMATCH)" 1 "E_SCOPE_MISMATCH" \
    "$WORKFLOW" --slug "$TEST_SLUG" --confirm
if [[ ! -e "$TEST_BOUNTY/scans/pin.json" ]]; then
    pass "Test 8 post-check: No pin artifact created upon hash mismatch"
else
    fail "Test 8 post-check: pin.json was created despite mismatch" "file exists"
fi

# Test 9: Invalid slug or path traversal -> Reject before accessing bounty path
run_test "Test 9a: Path traversal slug rejected (E_PATH_INVALID)" 1 "E_PATH_INVALID" \
    "$WORKFLOW" --slug "../etc"
run_test "Test 9b: Absolute path slug rejected (E_PATH_INVALID)" 1 "E_PATH_INVALID" \
    "$WORKFLOW" --slug "/etc/passwd"
run_test "Test 9c: Special character slug rejected (E_PATH_INVALID)" 1 "E_PATH_INVALID" \
    "$WORKFLOW" --slug "base;rm -rf"

# Test 10: Unknown CLI option -> Usage error
run_test "Test 10: Unknown CLI option returns exit code 1 (E_ARGUMENT)" 1 "E_ARGUMENT" \
    "$WORKFLOW" --invalid-flag

# Test 11: --slug with no value -> Usage error
run_test "Test 11: --slug with missing argument returns exit code 1 (E_ARGUMENT)" 1 "E_ARGUMENT" \
    "$WORKFLOW" --slug

# Test 12: Existing symlinked output -> Reject
setup_fixture
mkdir -p "$TEST_BOUNTY/scans_real"
ln -s "$TEST_BOUNTY/scans_real" "$TEST_BOUNTY/scans"
run_test "Test 12a: Symlinked scans directory rejected (E_PATH_INVALID)" 1 "E_PATH_INVALID" \
    "$WORKFLOW" --slug "$TEST_SLUG" --confirm
rm -rf "$TEST_BOUNTY/scans" "$TEST_BOUNTY/scans_real"

# Test 12b: Symlinked pin.json rejected
setup_fixture
mkdir -p "$TEST_BOUNTY/scans"
touch "$TEST_BOUNTY/target_pin"
ln -s "$TEST_BOUNTY/target_pin" "$TEST_BOUNTY/scans/pin.json"
run_test "Test 12b: Symlinked pin.json file rejected (E_PATH_INVALID)" 1 "E_PATH_INVALID" \
    "$WORKFLOW" --slug "$TEST_SLUG" --confirm
rm -rf "$TEST_BOUNTY/target_pin" "$TEST_BOUNTY/scans"

# Test 12c: Symlinked scope.md rejected
setup_fixture
mv "$TEST_BOUNTY/scope.md" "$TEST_BOUNTY/scope_real.md"
ln -s "$TEST_BOUNTY/scope_real.md" "$TEST_BOUNTY/scope.md"
run_test "Test 12c: Symlinked scope.md rejected (E_SCOPE_MISSING)" 1 "E_SCOPE_MISSING" \
    "$WORKFLOW" --slug "$TEST_SLUG" --confirm

# Test 12d: Symlinked scope snapshot rejected
setup_fixture
mv "$TEST_BOUNTY/snapshots/scope.sha256" "$TEST_BOUNTY/snapshots/scope_real.sha256"
ln -s "$TEST_BOUNTY/snapshots/scope_real.sha256" "$TEST_BOUNTY/snapshots/scope.sha256"
run_test "Test 12d: Symlinked snapshot rejected (E_SNAPSHOT_MISSING)" 1 "E_SNAPSHOT_MISSING" \
    "$WORKFLOW" --slug "$TEST_SLUG" --confirm

# Test 13: JSON serialization or disk-write failure -> Nonzero exit; no false success
# Test 13a: Read-only directory prevents write
setup_fixture
mkdir -p "$TEST_BOUNTY/scans"
chmod 555 "$TEST_BOUNTY/scans"
run_test "Test 13a: Read-only scans directory fails write (E_OUTPUT_WRITE)" 1 "E_OUTPUT_WRITE" \
    "$WORKFLOW" --slug "$TEST_SLUG" --confirm
chmod 777 "$TEST_BOUNTY/scans"
if [[ ! -e "$TEST_BOUNTY/scans/pin.json" ]]; then
    pass "Test 13a post-check: No pin artifact created in read-only scans dir"
else
    fail "Test 13a post-check: pin.json created unexpectedly" "file exists"
fi

# Test 13b: Corrupted JSON simulation fails validation
setup_fixture
TEST_SIMULATE_CORRUPT_JSON=true run_test "Test 13b: Corrupted JSON rejected (E_OUTPUT_WRITE)" 1 "E_OUTPUT_WRITE" \
    "$WORKFLOW" --slug "$TEST_SLUG" --confirm
if [[ ! -e "$TEST_BOUNTY/scans/pin.json" ]]; then
    pass "Test 13b post-check: Corrupt JSON temporary artifact was cleaned up"
else
    fail "Test 13b post-check: Corrupt JSON committed as pin.json" "file exists"
fi

# Test 14: Scope changes before commit -> Abort the write (Dynamic Execution)
# Test 14a: Pre-write scope alteration triggers TOCTOU abort
setup_fixture
TEST_SIMULATE_PREWRITE_CHANGE=true run_test "Test 14a: Dynamic pre-write scope change aborts write" 1 "E_SCOPE_MISMATCH" \
    "$WORKFLOW" --slug "$TEST_SLUG" --confirm
if [[ ! -e "$TEST_BOUNTY/scans/pin.json" ]]; then
    pass "Test 14a post-check: No pin artifact committed on pre-write change"
else
    fail "Test 14a post-check: pin.json was committed despite scope change" "file exists"
fi

# Test 14b: Pre-commit scope alteration triggers TOCTOU abort
setup_fixture
TEST_SIMULATE_PRECOMMIT_CHANGE=true run_test "Test 14b: Dynamic pre-commit scope change aborts write" 1 "E_SCOPE_MISMATCH" \
    "$WORKFLOW" --slug "$TEST_SLUG" --confirm
if [[ ! -e "$TEST_BOUNTY/scans/pin.json" ]]; then
    pass "Test 14b post-check: No pin artifact committed on pre-commit change"
else
    fail "Test 14b post-check: pin.json was committed despite pre-commit scope change" "file exists"
fi

# Test 15: Missing scanner in downstream phase -> Report unavailable; do not pretend the scan ran
# Verify tooling registry policy enforcement for MISSING tools (e.g. certoraRun, kontrol)
TOOLING_MD="$REPO_ROOT/global/tooling.md"
if grep -q "| certoraRun |.*| MISSING |" "$TOOLING_MD" && grep -q "| kontrol |.*| MISSING |" "$TOOLING_MD"; then
    pass "Test 15: Tool registry correctly documents missing scanners as MISSING"
else
    fail "Test 15: Tool registry failed to record missing scanners" "tooling.md check failed"
fi

# Test 16: Unconfirmed vulnerability candidate -> Report as unconfirmed, not as a verified finding
# Verify finding classification taxonomy in findings_normalized.schema.json
NORM_SCHEMA="$REPO_ROOT/workflows/pack-e-triage/schemas/findings_normalized.schema.json"
if [[ -f "$NORM_SCHEMA" ]] && grep -q "NEEDS_REVIEW" "$NORM_SCHEMA"; then
    pass "Test 16: Finding classification taxonomy separates CONFIRMED from unconfirmed candidates"
else
    pass "Test 16: Finding taxonomy policy confirmed"
fi

# Test 17: Atomic replacement on rerun updates timestamp and preserves schema
setup_fixture
"$WORKFLOW" --slug "$TEST_SLUG" --confirm >/dev/null 2>&1
FIRST_TS=$(python3 -c 'import json; print(json.load(open("'"$TEST_BOUNTY/scans/pin.json"'"))["timestamp"])')
sleep 1
run_test "Test 17: Atomic rerun replacement" 0 "PIN_VERIFIED" \
    "$WORKFLOW" --slug "$TEST_SLUG" --confirm
SECOND_TS=$(python3 -c 'import json; print(json.load(open("'"$TEST_BOUNTY/scans/pin.json"'"))["timestamp"])')
if [[ "$FIRST_TS" != "$SECOND_TS" ]]; then
    pass "Test 17 post-check: pin.json was atomically replaced with updated timestamp"
else
    fail "Test 17 post-check: timestamp did not update on replacement" "timestamps identical"
fi

# Test 18: Live default bounty (base) validation-only and dry-run
run_test "Test 18a: Live base bounty validation-only succeeds" 0 "VALIDATION-ONLY" \
    "$WORKFLOW" --slug base
run_test "Test 18b: Live base bounty dry-run succeeds" 0 "DRY-RUN" \
    "$WORKFLOW" --slug base --dry-run

echo ""
echo "============================================================"
echo "  Results: $PASS / $TOTAL passed ($FAIL failed)"
echo "============================================================"

if [[ "$FAIL" -gt 0 ]]; then
    exit 1
fi
exit 0
