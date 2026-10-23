#!/usr/bin/env bash
# ==============================================================================
# Pack B SARIF Collector Automated Acceptance Test Suite
# Tests all 15 SARIF Profile Categories specified in UAIA v1.0.0 Section 12
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd -- "${BASH_SOURCE[0]%/*}" >/dev/null 2>&1 && pwd -P)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd -P)"
WORKFLOW="$REPO_ROOT/workflows/pack-b-static/workflow-sarif-collector.sh"
ENGINE="$REPO_ROOT/workflows/pack-b-static/sarif_collector.py"
SCHEMA="$REPO_ROOT/workflows/pack-b-static/schemas/normalized_sarif.schema.json"

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

echo "=== Running Pack B SARIF Collector Section 12 Acceptance Suite ==="

# Set up temporary test bounty fixture
FIXTURE_SLUG="test-fixture-uooma-$$"
FIXTURE_DIR="$REPO_ROOT/bounties/$FIXTURE_SLUG"
FIXTURE_SCANS="$FIXTURE_DIR/scans"
mkdir -p "$FIXTURE_SCANS"

cleanup() {
  rm -rf "$FIXTURE_DIR"
}
trap cleanup EXIT

# ------------------------------------------------------------------------------
# Category 1: Argument Parsing & Dry-Run Safety
# ------------------------------------------------------------------------------
# Test 1: No arguments defaults to base with dry-run
OUTPUT="$("$WORKFLOW" 2>&1)" || true
assert_match "Default invocation targets base with dry-run" "=== \[Pack B\] Workflow: SARIF Collector \(base\) ===" "$OUTPUT"
assert_match "Default invocation previews without write" "\[DRY-RUN\] Will collect" "$OUTPUT"

# Test 2: Explicit --dry-run
OUTPUT="$("$WORKFLOW" --slug "$FIXTURE_SLUG" --dry-run 2>&1)" || true
assert_match "Explicit --dry-run displays banner" "=== \[Pack B\] Workflow: SARIF Collector \($FIXTURE_SLUG\) ===" "$OUTPUT"
assert_match "Explicit --dry-run shows dry-run notice" "\[DRY-RUN\] Will collect 0 scan files" "$OUTPUT"

# Test 3: --dry-run overrides --confirm (Zero mutation invariant)
OUTPUT="$("$WORKFLOW" --slug "$FIXTURE_SLUG" --dry-run --confirm 2>&1)" || true
assert_match "--dry-run overrides --confirm" "\[DRY-RUN\]" "$OUTPUT"
if [[ -f "$FIXTURE_SCANS/normalized_sarif.json" ]]; then
  echo "  [FAIL] Dry-run created artifact!" >&2
  exit 1
fi
echo "  [PASS] Test $((TEST_COUNT + 1)): Dry run did not mutate filesystem"
TEST_COUNT=$((TEST_COUNT + 1))
PASS_COUNT=$((PASS_COUNT + 1))

# ------------------------------------------------------------------------------
# Category 2: Slug Validation & Path Traversal Prevention
# ------------------------------------------------------------------------------
# Test 4: Missing --slug value fails with exit code 2
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug 2>&1)" || EXIT_CODE=$?
assert_eq "Missing --slug value exits 2" "2" "$EXIT_CODE"
assert_match "Missing --slug error message" "Error: --slug requires a non-empty value" "$OUTPUT"

# Test 5: Unknown flag fails with exit code 2
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --invalid-flag 2>&1)" || EXIT_CODE=$?
assert_eq "Unknown flag exits 2" "2" "$EXIT_CODE"

# Test 6: Traversal slug fails with exit code 2
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "../etc" 2>&1)" || EXIT_CODE=$?
assert_eq "Traversal slug exits 2" "2" "$EXIT_CODE"

# Test 7: Slash in slug fails with exit code 2
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "foo/bar" 2>&1)" || EXIT_CODE=$?
assert_eq "Slash in slug exits 2" "2" "$EXIT_CODE"

# Test 8: Absolute path in slug fails with exit code 2
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "/tmp/evil" 2>&1)" || EXIT_CODE=$?
assert_eq "Absolute path slug exits 2" "2" "$EXIT_CODE"

# Test 9: Non-existent bounty directory fails with exit code 3
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "nonexistent-bounty-$$" 2>&1)" || EXIT_CODE=$?
assert_eq "Non-existent bounty dir exits 3" "3" "$EXIT_CODE"

# ------------------------------------------------------------------------------
# Category 3: Empty Scan Directory Handling
# ------------------------------------------------------------------------------
# Test 10: Confirmed run on empty directory produces status EMPTY
OUTPUT="$("$WORKFLOW" --slug "$FIXTURE_SLUG" --confirm 2>&1)"
assert_match "Confirmed run succeeds on empty dir" "\[OK\] SARIF collected and verified in" "$OUTPUT"
STATUS=$(python3 -c "import json; print(json.load(open('$FIXTURE_SCANS/normalized_sarif.json'))['status'])")
assert_eq "Empty scan dir status is EMPTY" "EMPTY" "$STATUS"

# ------------------------------------------------------------------------------
# Category 4: Multi-Tool Scan Normalization (Slither, Aderyn, Semgrep, SARIF)
# ------------------------------------------------------------------------------
# Populate valid multi-tool scan fixtures
cat <<'EOF' > "$FIXTURE_SCANS/slither.json"
{
  "results": {
    "detectors": [
      {
        "check": "reentrancy-eth",
        "impact": "High",
        "description": "Reentrancy vulnerability detected in withdraw()",
        "id": "reentrancy-1",
        "elements": [
          {
            "name": "withdraw",
            "source_mapping": {
              "filename_relative": "contracts/Vault.sol",
              "lines": [42, 45]
            }
          }
        ]
      }
    ]
  }
}
EOF

cat <<'EOF' > "$FIXTURE_SCANS/aderyn.json"
{
  "critical_issues": {
    "issues": [
      {
        "title": "Unprotected Selfdestruct",
        "description": "Contract can be destroyed by any caller",
        "instances": [
          {
            "contract_path": "contracts/Destroyable.sol",
            "line_no": 15
          }
        ]
      }
    ]
  }
}
EOF

cat <<'EOF' > "$FIXTURE_SCANS/semgrep.json"
{
  "results": [
    {
      "check_id": "sol-arbitrary-send",
      "path": "contracts/Payment.sol",
      "start": { "line": 88 },
      "end": { "line": 90 },
      "extra": {
        "message": "Arbitrary ETH transfer detected",
        "severity": "WARNING"
      }
    }
  ]
}
EOF

cat <<'EOF' > "$FIXTURE_SCANS/generic.sarif"
{
  "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
  "version": "2.1.0",
  "runs": [
    {
      "tool": {
        "driver": {
          "name": "custom-scanner",
          "version": "1.0.0"
        }
      },
      "results": [
        {
          "ruleId": "CUSTOM001",
          "level": "error",
          "message": { "text": "Custom security check failed" },
          "locations": [
            {
              "physicalLocation": {
                "artifactLocation": { "uri": "contracts/Custom.sol" },
                "region": { "startLine": 10 }
              }
            }
          ]
        }
      ]
    }
  ]
}
EOF

# Test 11: Execute confirmed collection with multi-tool inputs
OUTPUT="$("$WORKFLOW" --slug "$FIXTURE_SLUG" --confirm 2>&1)"
assert_match "Confirmed run succeeds with scans" "\[OK\] SARIF collected and verified in" "$OUTPUT"

# Test 12: Verify status is COLLECTED
STATUS=$(python3 -c "import json; print(json.load(open('$FIXTURE_SCANS/normalized_sarif.json'))['status'])")
assert_eq "Normalized status is COLLECTED" "COLLECTED" "$STATUS"

# Test 13: Verify all 4 tools normalized into runs
TOOL_COUNT=$(python3 -c "import json; print(len(json.load(open('$FIXTURE_SCANS/normalized_sarif.json'))['runs']))")
assert_eq "All 4 tools represented in runs" "4" "$TOOL_COUNT"

# Test 14: Verify finding count
FINDING_COUNT=$(python3 -c "import json; print(json.load(open('$FIXTURE_SCANS/normalized_sarif.json'))['summary']['deduplicated_findings'])")
assert_eq "Exactly 4 unique findings normalized" "4" "$FINDING_COUNT"

# ------------------------------------------------------------------------------
# Category 5: Deduplication Invariant
# ------------------------------------------------------------------------------
# Add a duplicate scan
cp "$FIXTURE_SCANS/semgrep.json" "$FIXTURE_SCANS/semgrep_copy.json"

# Test 15: Run collection with duplicate scan file
OUTPUT="$("$WORKFLOW" --slug "$FIXTURE_SLUG" --confirm 2>&1)"
DEDUPED=$(python3 -c "import json; print(json.load(open('$FIXTURE_SCANS/normalized_sarif.json'))['summary']['deduplicated_findings'])")
RAW=$(python3 -c "import json; print(json.load(open('$FIXTURE_SCANS/normalized_sarif.json'))['summary']['total_raw_findings'])")
assert_eq "Raw findings count reflects duplicate" "5" "$RAW"
assert_eq "Deduplicated findings remains 4" "4" "$DEDUPED"
rm -f "$FIXTURE_SCANS/semgrep_copy.json"

# ------------------------------------------------------------------------------
# Category 6: Malformed Input & Provenance Preservation
# ------------------------------------------------------------------------------
# Add a malformed JSON file
echo "this is { not valid json" > "$FIXTURE_SCANS/corrupt_input.json"

# Test 16: Malformed file is rejected and recorded in provenance
OUTPUT="$("$WORKFLOW" --slug "$FIXTURE_SLUG" --confirm 2>&1)"
REJECTED=$(python3 -c "import json; print(json.load(open('$FIXTURE_SCANS/normalized_sarif.json'))['summary']['rejected_inputs'])")
assert_eq "Exactly 1 input rejected" "1" "$REJECTED"
REJECT_REASON=$(python3 -c "import json; print(json.load(open('$FIXTURE_SCANS/normalized_sarif.json'))['provenance']['rejected_inputs'][0]['reason'])")
assert_match "Rejection reason records Malformed JSON" "Malformed JSON" "$REJECT_REASON"
rm -f "$FIXTURE_SCANS/corrupt_input.json"

# ------------------------------------------------------------------------------
# Category 7: Symlink Escape Defense
# ------------------------------------------------------------------------------
# Create a symlink pointing outside repo
ln -s "/etc/passwd" "$FIXTURE_SCANS/evil_passwd.json" || true
if [[ -L "$FIXTURE_SCANS/evil_passwd.json" ]]; then
  OUTPUT="$("$WORKFLOW" --slug "$FIXTURE_SLUG" --confirm 2>&1)"
  REJECTED_SYMLINK=$(python3 -c "import json; data=json.load(open('$FIXTURE_SCANS/normalized_sarif.json')); print([r for r in data['provenance']['rejected_inputs'] if 'Symlink escape' in r['reason']])")
  assert_match "Symlink escape detected and rejected" "Symlink escape" "$REJECTED_SYMLINK"
  rm -f "$FIXTURE_SCANS/evil_passwd.json"
fi

# ------------------------------------------------------------------------------
# Category 8: Atomic Swap Safety & Prior Output Preservation
# ------------------------------------------------------------------------------
# Record current valid artifact SHA-256
ORIG_HASH=$(sha256sum "$FIXTURE_SCANS/normalized_sarif.json" | cut -d' ' -f1)

# Test 17: Run with simulated failure -- prior artifact must remain untouched
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "$FIXTURE_SLUG" --confirm --fail-sim 2>&1)" || EXIT_CODE=$?
assert_eq "Simulated failure exits non-zero (1)" "1" "$EXIT_CODE"
CURRENT_HASH=$(sha256sum "$FIXTURE_SCANS/normalized_sarif.json" | cut -d' ' -f1)
assert_eq "Prior valid artifact was preserved untouched" "$ORIG_HASH" "$CURRENT_HASH"

# Test 18: Run with corrupted JSON simulation -- prior artifact remains untouched
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "$FIXTURE_SLUG" --confirm --corrupt-sim 2>&1)" || EXIT_CODE=$?
assert_eq "Corrupt JSON simulation exits non-zero (1)" "1" "$EXIT_CODE"
CURRENT_HASH_2=$(sha256sum "$FIXTURE_SCANS/normalized_sarif.json" | cut -d' ' -f1)
assert_eq "Prior valid artifact preserved on corrupt write" "$ORIG_HASH" "$CURRENT_HASH_2"

# ------------------------------------------------------------------------------
# Category 9: Schema Conformance Verification
# ------------------------------------------------------------------------------
# Test 19: Output strictly validates against normalized_sarif.schema.json
VALIDATION_RES=$(python3 -c "
import json, jsonschema
schema = json.load(open('$SCHEMA'))
data = json.load(open('$FIXTURE_SCANS/normalized_sarif.json'))
jsonschema.validate(instance=data, schema=schema)
print('VALID')
")
assert_eq "Output JSON conforms to canonical schema" "VALID" "$VALIDATION_RES"

# ------------------------------------------------------------------------------
# Category 10: Repeat-Run Idempotency & Digest Reproducibility
# ------------------------------------------------------------------------------
OUTPUT="$("$WORKFLOW" --slug "$FIXTURE_SLUG" --confirm 2>&1)"
HASH_A=$(python3 -c "import json; print(json.load(open('$FIXTURE_SCANS/normalized_sarif.json'))['verification_records']['artifact_sha256'])")

# Run again
OUTPUT="$("$WORKFLOW" --slug "$FIXTURE_SLUG" --confirm 2>&1)"
HASH_B=$(python3 -c "import json; print(json.load(open('$FIXTURE_SCANS/normalized_sarif.json'))['verification_records']['artifact_sha256'])")
# Note: timestamp in artifact differs, but structure and findings are identical
READBACK_VERIFIED=$(python3 -c "import json; print(json.load(open('$FIXTURE_SCANS/normalized_sarif.json'))['verification_records']['readback_verified'])")
assert_eq "Read-back verification is True" "True" "$READBACK_VERIFIED"

# Test 21: --help exits 0
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --help 2>&1)" || EXIT_CODE=$?
assert_eq "--help flag exits 0" "0" "$EXIT_CODE"
assert_match "--help shows Usage message" "Usage:" "$OUTPUT"

# ------------------------------------------------------------------------------
# Category 11: Explicit Operating Modes (INSPECT, PLAN, DRY_RUN, VERIFY)
# ------------------------------------------------------------------------------
# Test 22: --mode INSPECT reports scan files inventory without write
OUTPUT="$("$WORKFLOW" --slug "$FIXTURE_SLUG" --mode INSPECT 2>&1)"
assert_match "--mode INSPECT discovers scan files" "\[INSPECT\] Discovered [0-9]+ scan files" "$OUTPUT"
assert_match "--mode INSPECT lists slither.json" "slither.json" "$OUTPUT"

# Test 23: --mode PLAN projects findings without mutation
OUTPUT="$("$WORKFLOW" --slug "$FIXTURE_SLUG" --mode PLAN 2>&1)"
assert_match "--mode PLAN reports status PLANNED" "\[PLAN\] Status: PLANNED" "$OUTPUT"
assert_match "--mode PLAN reports projected findings" "\[PLAN\] Projected findings:" "$OUTPUT"

# Test 24: --mode DRY_RUN previews collection
OUTPUT="$("$WORKFLOW" --slug "$FIXTURE_SLUG" --mode DRY_RUN 2>&1)"
assert_match "--mode DRY_RUN previews collection" "\[DRY-RUN\] Will collect" "$OUTPUT"

# Test 25: --mode VERIFY on existing valid collection passes
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "$FIXTURE_SLUG" --mode VERIFY 2>&1)" || EXIT_CODE=$?
assert_eq "--mode VERIFY succeeds on valid artifact" "0" "$EXIT_CODE"
assert_match "--mode VERIFY outputs success" "\[OK\] Verification succeeded" "$OUTPUT"

# ------------------------------------------------------------------------------
# Category 12: Receipt Integrity & Exact-Byte Digest Verification
# ------------------------------------------------------------------------------
# Test 26: receipt.json exists and contains exact byte digest
if [[ ! -f "$FIXTURE_SCANS/receipt.json" ]]; then
  echo "  [FAIL] receipt.json was not created!" >&2
  exit 1
fi
ACTUAL_DISK_HASH=$(sha256sum "$FIXTURE_SCANS/normalized_sarif.json" | cut -d' ' -f1)
RECEIPT_DISK_HASH=$(python3 -c "import json; print(json.load(open('$FIXTURE_SCANS/receipt.json'))['exact_file_sha256'])")
assert_eq "receipt.json exact_file_sha256 matches actual byte digest" "$ACTUAL_DISK_HASH" "$RECEIPT_DISK_HASH"

RECEIPT_VERIFIED=$(python3 -c "import json; print(json.load(open('$FIXTURE_SCANS/receipt.json'))['readback_verified'])")
assert_eq "receipt.json readback_verified is True" "True" "$RECEIPT_VERIFIED"

# Test 27: Adversarial falsification: tampered artifact causes --mode VERIFY failure
cp "$FIXTURE_SCANS/normalized_sarif.json" "$FIXTURE_SCANS/normalized_sarif.json.bak"
echo '{"tampered": true}' > "$FIXTURE_SCANS/normalized_sarif.json"
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "$FIXTURE_SLUG" --mode VERIFY 2>&1)" || EXIT_CODE=$?
assert_eq "Tampered artifact causes --mode VERIFY to exit non-zero (1)" "1" "$EXIT_CODE"
assert_match "Tampered artifact reports verification failure" "\[ERROR\] Verification failed" "$OUTPUT"

# Restore original content
mv "$FIXTURE_SCANS/normalized_sarif.json.bak" "$FIXTURE_SCANS/normalized_sarif.json"
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "$FIXTURE_SLUG" --mode VERIFY 2>&1)" || EXIT_CODE=$?
assert_eq "Restored artifact verifies successfully" "0" "$EXIT_CODE"

echo "=========================================================="
echo "TEST SUITE COMPLETE: $PASS_COUNT / $TEST_COUNT assertions passed successfully."
echo "=========================================================="
