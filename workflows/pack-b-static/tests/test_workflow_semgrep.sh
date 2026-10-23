#!/usr/bin/env bash
# ==============================================================================
# Pack B UAIA / Glassbox Semgrep Static Analysis Acceptance Test Suite
# Tests all 18 Production Acceptance Scenarios
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd -- "${BASH_SOURCE[0]%/*}" >/dev/null 2>&1 && pwd -P)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd -P)"
WORKFLOW="$REPO_ROOT/workflows/pack-b-static/workflow-semgrep.sh"
ADAPTER="$REPO_ROOT/.agents/skills/qrpe/adapters/semgrep_adapter.py"
ORCHESTRATOR="$REPO_ROOT/workflows/pack-b-static/semgrep_orchestrator.py"
SCHEMA="$REPO_ROOT/workflows/pack-b-static/schemas/evidence_envelope.schema.json"

TEST_COUNT=0
PASS_COUNT=0

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
    echo "  [FAIL] Test $TEST_COUNT: $test_name (Pattern '$pattern' not found in '$actual')" >&2
    exit 1
  fi
}

assert_valid_envelope() {
  local test_name="$1" envelope_file="$2"
  TEST_COUNT=$((TEST_COUNT + 1))
  local val_res
  val_res=$(python3 -c "
import json, jsonschema, sys
try:
    env = json.load(open('$envelope_file'))
    schema = json.load(open('$SCHEMA'))
    jsonschema.validate(instance=env, schema=schema)
    print('VALID')
except Exception as e:
    print(f'INVALID: {e}')
    sys.exit(1)
" 2>&1)
  if [[ "$val_res" == "VALID" ]]; then
    echo "  [PASS] Test $TEST_COUNT: $test_name (Envelope schema valid)"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    echo "  [FAIL] Test $TEST_COUNT: $test_name ($val_res)" >&2
    exit 1
  fi
}

echo "=== Running UAIA / Glassbox Semgrep Static Analysis Acceptance Suite ==="

# Set up temporary test bounty fixture
FIXTURE_SLUG="test-fixture-semgrep-$$"
FIXTURE_DIR="$REPO_ROOT/bounties/$FIXTURE_SLUG"
FIXTURE_CONTRACTS="$FIXTURE_DIR/contracts"
FIXTURE_SCANS="$FIXTURE_DIR/scans/semgrep"

mkdir -p "$FIXTURE_CONTRACTS/src"
mkdir -p "$FIXTURE_SCANS"

cat <<'EOF' > "$FIXTURE_CONTRACTS/src/Vault.sol"
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract Vault {
    mapping(address => uint256) public balances;

    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }

    function withdraw() external {
        uint256 bal = balances[msg.sender];
        require(bal > 0);
        (bool s, ) = msg.sender.call{value: bal}("");
        require(s);
        balances[msg.sender] = 0;
    }
}
EOF

cleanup() {
  rm -rf "$FIXTURE_DIR"
}
trap cleanup EXIT

# ------------------------------------------------------------------------------
# Scenario 1: No arguments -> Dry-run (exit 0)
# ------------------------------------------------------------------------------
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" 2>&1)" || EXIT_CODE=$?
assert_eq "Scenario 1: Default invocation exits 0" "0" "$EXIT_CODE"
assert_match "Scenario 1: Displays Semgrep banner for base" "=== \[Pack B\] UAIA / Glassbox Workflow: Semgrep Static Analysis \(base\) ===" "$OUTPUT"
assert_match "Scenario 1: Previews dry-run" "\[DRY-RUN\]" "$OUTPUT"

# ------------------------------------------------------------------------------
# Scenario 2: Confirmation without dry-run -> Live execution
# ------------------------------------------------------------------------------
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "$FIXTURE_SLUG" --confirm --clean-sim 2>&1)" || EXIT_CODE=$?
assert_eq "Scenario 2: Confirmed invocation exits 0" "0" "$EXIT_CODE"
assert_match "Scenario 2: Successful scan message" "\[OK\] Semgrep OAM scan completed successfully" "$OUTPUT"
if [[ ! -f "$FIXTURE_SCANS/evidence_envelope.json" ]]; then
  echo "  [FAIL] Scenario 2: evidence_envelope.json not created!" >&2
  exit 1
fi
echo "  [PASS] Test $((TEST_COUNT + 1)): Scenario 2: Evidence envelope created"
TEST_COUNT=$((TEST_COUNT + 1))
PASS_COUNT=$((PASS_COUNT + 1))
assert_valid_envelope "Scenario 2: Evidence envelope schema compliance" "$FIXTURE_SCANS/evidence_envelope.json"

# ------------------------------------------------------------------------------
# Scenario 3: Both dry-run and confirmation -> No live scan (zero mutation)
# ------------------------------------------------------------------------------
rm -rf "$FIXTURE_SCANS"/*
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "$FIXTURE_SLUG" --dry-run --confirm 2>&1)" || EXIT_CODE=$?
assert_eq "Scenario 3: Dry-run with confirm exits 0" "0" "$EXIT_CODE"
assert_match "Scenario 3: Dry-run overrides confirm" "\[DRY-RUN\]" "$OUTPUT"
if [[ -f "$FIXTURE_SCANS/semgrep.json" || -f "$FIXTURE_SCANS/evidence_envelope.json" ]]; then
  echo "  [FAIL] Scenario 3: File written during dry run!" >&2
  exit 1
fi
echo "  [PASS] Test $((TEST_COUNT + 1)): Scenario 3: Zero filesystem writes during dry run"
TEST_COUNT=$((TEST_COUNT + 1))
PASS_COUNT=$((PASS_COUNT + 1))

# ------------------------------------------------------------------------------
# Scenario 4: Unknown option or missing value -> Reject before adapter (exit 2)
# ------------------------------------------------------------------------------
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug 2>&1)" || EXIT_CODE=$?
assert_eq "Scenario 4: Missing slug value exits 2" "2" "$EXIT_CODE"
assert_match "Scenario 4: Missing value message" "Error: --slug requires a non-empty value" "$OUTPUT"

EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --unrecognized-flag 2>&1)" || EXIT_CODE=$?
assert_eq "Scenario 4: Unknown option exits 2" "2" "$EXIT_CODE"
assert_match "Scenario 4: Unknown argument message" "Error: Unknown argument: --unrecognized-flag" "$OUTPUT"

EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --timeout abc 2>&1)" || EXIT_CODE=$?
assert_eq "Scenario 4: Non-numeric timeout exits 2" "2" "$EXIT_CODE"
assert_match "Scenario 4: Timeout validation message" "Error: --timeout requires a positive numeric value" "$OUTPUT"

# ------------------------------------------------------------------------------
# Scenario 5: Target or output escapes approved scope -> Block execution (exit 2)
# ------------------------------------------------------------------------------
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "$FIXTURE_SLUG" --target "/etc/passwd" 2>&1)" || EXIT_CODE=$?
assert_eq "Scenario 5: Target outside repo exits 2" "2" "$EXIT_CODE"
assert_match "Scenario 5: Path containment message" "escapes repository root" "$OUTPUT"

EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "$FIXTURE_SLUG" --target "${REPO_ROOT}_attacker" 2>&1)" || EXIT_CODE=$?
assert_eq "Scenario 5: Target prefix match attack exits 2" "2" "$EXIT_CODE"
assert_match "Scenario 5: Prefix attack containment message" "escapes repository root" "$OUTPUT"

EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "$FIXTURE_SLUG" --output-dir "/var/log" 2>&1)" || EXIT_CODE=$?
assert_eq "Scenario 5: Output outside repo exits 2" "2" "$EXIT_CODE"
assert_match "Scenario 5: Output path containment message" "escapes repository root" "$OUTPUT"

# Output inside target directory check
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "$FIXTURE_SLUG" --target "$FIXTURE_CONTRACTS" --output-dir "$FIXTURE_CONTRACTS/scans" 2>&1)" || EXIT_CODE=$?
assert_eq "Scenario 5: Output inside target directory exits 2" "2" "$EXIT_CODE"
assert_match "Scenario 5: Output inside target message" "must not be inside target directory" "$OUTPUT"

# ------------------------------------------------------------------------------
# Scenario 6: Missing adapter, interpreter, or scanner -> Fail preflight (exit 3)
# ------------------------------------------------------------------------------
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "nonexistent-bounty-$$" 2>&1)" || EXIT_CODE=$?
assert_eq "Scenario 6: Missing bounty directory exits 3" "3" "$EXIT_CODE"
assert_match "Scenario 6: Missing directory message" "Target bounty directory does not exist" "$OUTPUT"

# ------------------------------------------------------------------------------
# Scenario 7: Scanner exits nonzero -> Preserve underlying failure (exit 1)
# ------------------------------------------------------------------------------
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "$FIXTURE_SLUG" --confirm --scanner-fail-sim 2>&1)" || EXIT_CODE=$?
assert_eq "Scenario 7: Scanner failure exits 1" "1" "$EXIT_CODE"
STATUS=$(python3 -c "import json; print(json.load(open('$FIXTURE_SCANS/evidence_envelope.json'))['terminal_status'])")
assert_eq "Scenario 7: Terminal status is EXECUTION_FAILED" "EXECUTION_FAILED" "$STATUS"
ERR_CODE=$(python3 -c "import json; print(json.load(open('$FIXTURE_SCANS/evidence_envelope.json'))['error_code'])")
assert_eq "Scenario 7: Error code is EXECUTION_FAILED" "EXECUTION_FAILED" "$ERR_CODE"
assert_valid_envelope "Scenario 7: Envelope validates against schema on failure" "$FIXTURE_SCANS/evidence_envelope.json"

# ------------------------------------------------------------------------------
# Scenario 8: Scanner exits zero but report is missing -> Validation fails (exit 1)
# ------------------------------------------------------------------------------
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "$FIXTURE_SLUG" --confirm --empty-report-sim 2>&1)" || EXIT_CODE=$?
assert_eq "Scenario 8: Missing report exits 1" "1" "$EXIT_CODE"
STATUS=$(python3 -c "import json; print(json.load(open('$FIXTURE_SCANS/evidence_envelope.json'))['terminal_status'])")
assert_eq "Scenario 8: Terminal status is VALIDATION_FAILED" "VALIDATION_FAILED" "$STATUS"
assert_valid_envelope "Scenario 8: Envelope validates against schema on missing report" "$FIXTURE_SCANS/evidence_envelope.json"

# ------------------------------------------------------------------------------
# Scenario 9: Scanner output is corrupted JSON -> Independent check fails (exit 1)
# ------------------------------------------------------------------------------
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "$FIXTURE_SLUG" --confirm --corrupt-report-sim 2>&1)" || EXIT_CODE=$?
assert_eq "Scenario 9: Corrupt JSON exits 1" "1" "$EXIT_CODE"
STATUS=$(python3 -c "import json; print(json.load(open('$FIXTURE_SCANS/evidence_envelope.json'))['terminal_status'])")
assert_eq "Scenario 9: Terminal status is VALIDATION_FAILED" "VALIDATION_FAILED" "$STATUS"
assert_valid_envelope "Scenario 9: Envelope validates against schema on corrupt report" "$FIXTURE_SCANS/evidence_envelope.json"

# ------------------------------------------------------------------------------
# Scenario 10: Scanner output SHA-256 digest does not match receipt -> Fail (exit 1)
# ------------------------------------------------------------------------------
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "$FIXTURE_SLUG" --confirm --digest-mismatch-sim 2>&1)" || EXIT_CODE=$?
assert_eq "Scenario 10: Digest mismatch exits 1" "1" "$EXIT_CODE"
STATUS=$(python3 -c "import json; print(json.load(open('$FIXTURE_SCANS/evidence_envelope.json'))['terminal_status'])")
assert_eq "Scenario 10: Terminal status is VALIDATION_FAILED" "VALIDATION_FAILED" "$STATUS"
assert_valid_envelope "Scenario 10: Envelope validates against schema on digest mismatch" "$FIXTURE_SCANS/evidence_envelope.json"

# ------------------------------------------------------------------------------
# Scenario 11: Finding attributes outside target directory -> Scope violation (exit 1)
# ------------------------------------------------------------------------------
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "$FIXTURE_SLUG" --confirm --attribution-mismatch-sim 2>&1)" || EXIT_CODE=$?
assert_eq "Scenario 11: Attribution mismatch exits 1" "1" "$EXIT_CODE"
STATUS=$(python3 -c "import json; print(json.load(open('$FIXTURE_SCANS/evidence_envelope.json'))['terminal_status'])")
assert_eq "Scenario 11: Terminal status is VALIDATION_FAILED" "VALIDATION_FAILED" "$STATUS"
assert_valid_envelope "Scenario 11: Envelope validates against schema on attribution mismatch" "$FIXTURE_SCANS/evidence_envelope.json"

# ------------------------------------------------------------------------------
# Scenario 12: Clean scan -> COMPLETED_CLEAN (exit 0)
# ------------------------------------------------------------------------------
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "$FIXTURE_SLUG" --confirm --clean-sim 2>&1)" || EXIT_CODE=$?
assert_eq "Scenario 12: Clean scan exits 0" "0" "$EXIT_CODE"
STATUS=$(python3 -c "import json; print(json.load(open('$FIXTURE_SCANS/evidence_envelope.json'))['terminal_status'])")
assert_eq "Scenario 12: Clean report yields COMPLETED_CLEAN" "COMPLETED_CLEAN" "$STATUS"
FINDINGS_TOTAL=$(python3 -c "import json; print(json.load(open('$FIXTURE_SCANS/evidence_envelope.json'))['findings_summary']['total_findings'])")
assert_eq "Scenario 12: Zero findings recorded" "0" "$FINDINGS_TOTAL"
assert_valid_envelope "Scenario 12: Envelope validates against schema for clean scan" "$FIXTURE_SCANS/evidence_envelope.json"

# ------------------------------------------------------------------------------
# Scenario 13: Timeout -> Terminate execution safely (exit 1)
# ------------------------------------------------------------------------------
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "$FIXTURE_SLUG" --confirm --timeout-sim 2>&1)" || EXIT_CODE=$?
assert_eq "Scenario 13: Timeout exits 1" "1" "$EXIT_CODE"
STATUS=$(python3 -c "import json; print(json.load(open('$FIXTURE_SCANS/evidence_envelope.json'))['terminal_status'])")
assert_eq "Scenario 13: Terminal status is EXECUTION_FAILED" "EXECUTION_FAILED" "$STATUS"
assert_valid_envelope "Scenario 13: Envelope validates against schema on timeout" "$FIXTURE_SCANS/evidence_envelope.json"

# ------------------------------------------------------------------------------
# Scenario 14: Symlink escape in target -> Rejection (exit 2)
# ------------------------------------------------------------------------------
SYMLINK_TARGET="$FIXTURE_DIR/symlink_outside"
ln -s "/tmp" "$SYMLINK_TARGET"
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "$FIXTURE_SLUG" --target "$SYMLINK_TARGET" 2>&1)" || EXIT_CODE=$?
assert_eq "Scenario 14: Symlink escape exits 2" "2" "$EXIT_CODE"
assert_match "Scenario 14: Symlink error message" "escapes repository root" "$OUTPUT"
rm -f "$SYMLINK_TARGET"

# ------------------------------------------------------------------------------
# Scenario 15: Receipt writing failure simulation -> Failure (exit 1)
# ------------------------------------------------------------------------------
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "$FIXTURE_SLUG" --confirm --fail-receipt-sim 2>&1)" || EXIT_CODE=$?
assert_eq "Scenario 15: Receipt writing failure exits 1" "1" "$EXIT_CODE"

# ------------------------------------------------------------------------------
# Scenario 16: Version drift simulation -> Captured accurately
# ------------------------------------------------------------------------------
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "$FIXTURE_SLUG" --confirm --clean-sim --version-drift-sim 2>&1)" || EXIT_CODE=$?
assert_eq "Scenario 16: Version drift run exits 0" "0" "$EXIT_CODE"
DRIFT_VER=$(python3 -c "import json; print(json.load(open('$FIXTURE_SCANS/evidence_envelope.json'))['process_execution']['tool_version'])")
assert_eq "Scenario 16: Drifted version recorded" "9.9.9-unverified" "$DRIFT_VER"
assert_valid_envelope "Scenario 16: Envelope validates against schema with version drift" "$FIXTURE_SCANS/evidence_envelope.json"

# ------------------------------------------------------------------------------
# Scenario 17: Prompt injection resilience in slug -> Blocked at intake (exit 2)
# ------------------------------------------------------------------------------
INJECTION_SLUG="base;rm -rf /;echo injected"
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "$INJECTION_SLUG" 2>&1)" || EXIT_CODE=$?
assert_eq "Scenario 17: Injection in slug exits 2" "2" "$EXIT_CODE"
assert_match "Scenario 17: Path separators or invalid characters error" "(Path separators or traversal components prohibited|contains invalid characters)" "$OUTPUT"

# ------------------------------------------------------------------------------
# Scenario 18: Glassbox 8-Stage Run Artifacts Verification
# ------------------------------------------------------------------------------
# Perform a clean confirmed scan
EXIT_CODE=0
"$WORKFLOW" --slug "$FIXTURE_SLUG" --confirm --clean-sim >/dev/null 2>&1 || EXIT_CODE=$?
assert_eq "Scenario 18: Clean scan exits 0" "0" "$EXIT_CODE"

LATEST_RUN_PATH=$(cat "$FIXTURE_SCANS/latest_run")
if [[ ! -d "$LATEST_RUN_PATH" ]]; then
  echo "  [FAIL] Scenario 18: latest_run directory does not exist: $LATEST_RUN_PATH" >&2
  exit 1
fi
echo "  [PASS] Test $((TEST_COUNT + 1)): Scenario 18: latest_run pointer is valid directory"
TEST_COUNT=$((TEST_COUNT + 1))
PASS_COUNT=$((PASS_COUNT + 1))

# Verify all 8 Glassbox stage artifacts and subdirectories
for required_art in \
  "request.normalized.json" \
  "inputs.inventory.json" \
  "execution.plan.json" \
  "provenance.manifest.json" \
  "verification.report.json" \
  "reconciliation.report.json" \
  "admission.decision.json" \
  "manifest.json" \
  "raw/stdout.log" \
  "raw/stderr.log" \
  "raw/semgrep.json" \
  "raw/receipt.json" \
  "validation/coverage-report.json" \
  "validation/verification-report.json" \
  "governance/admission.decision.json"
do
  if [[ ! -f "$LATEST_RUN_PATH/$required_art" ]]; then
    echo "  [FAIL] Scenario 18: Required artifact missing: $LATEST_RUN_PATH/$required_art" >&2
    exit 1
  fi
done
echo "  [PASS] Test $((TEST_COUNT + 1)): Scenario 18: All 8 Glassbox stage artifacts verified in run directory"
TEST_COUNT=$((TEST_COUNT + 1))
PASS_COUNT=$((PASS_COUNT + 1))

# Verify all 8 Gates (G1-G8) evaluated in admission decision
GATES_EVALUATED=$(python3 -c "
import json
adm = json.load(open('$LATEST_RUN_PATH/admission.decision.json'))
gate_ids = [g['gate_id'] for g in adm['gate_decisions']]
expected = {'G1', 'G2', 'G3', 'G4', 'G5', 'G6', 'G7', 'G8'}
if expected.issubset(set(gate_ids)):
    print('ALL_GATES_EVALUATED')
else:
    print(f'MISSING_GATES: {expected - set(gate_ids)}')
")
assert_eq "Scenario 18: All 8 gates G1-G8 evaluated in admission.decision.json" "ALL_GATES_EVALUATED" "$GATES_EVALUATED"

echo "=============================================================================="
echo "All Acceptance Scenarios PASSED successfully ($PASS_COUNT / $TEST_COUNT assertions passed)."
echo "=============================================================================="
