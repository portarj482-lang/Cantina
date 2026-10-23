#!/usr/bin/env bash
# Test suite for Pack E Findings Normalization Workflow (workflow-normalize.sh)
set -euo pipefail

SCRIPT_DIR="$(cd -- "${BASH_SOURCE[0]%/*}" >/dev/null 2>&1 && pwd -P)"
WORKFLOW="$SCRIPT_DIR/../workflow-normalize.sh"
REPO_ROOT="/home/nova/projects/cantina"

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

echo "=== Running Findings Normalization Automated Test Suite ==="

# Test 1: No arguments defaults to base and dry-run preview
OUTPUT="$("$WORKFLOW" 2>&1)" || true
assert_match "Default invocation shows base banner" "=== \[Pack E\] Workflow: Normalize Findings \(base\) ===" "$OUTPUT"
assert_match "Default invocation previews destination" "\[DRY-RUN\] Will normalize findings into .*bounties/base/scans/findings_normalized\.json" "$OUTPUT"

# Test 2: Explicit --dry-run
OUTPUT="$("$WORKFLOW" --dry-run 2>&1)" || true
assert_match "Explicit --dry-run previews destination" "\[DRY-RUN\] Will normalize findings into .*bounties/base/scans/findings_normalized\.json" "$OUTPUT"

# Test 3: --dry-run overrides --confirm
OUTPUT="$("$WORKFLOW" --dry-run --confirm 2>&1)" || true
assert_match "--dry-run overrides --confirm" "\[DRY-RUN\] Will normalize findings into .*bounties/base/scans/findings_normalized\.json" "$OUTPUT"

# Test 4: Missing --slug value fails
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug 2>&1)" || EXIT_CODE=$?
assert_eq "Missing --slug value exits non-zero" "1" "$EXIT_CODE"
assert_match "Missing --slug reports error" "\[ERROR\] init: Missing value for --slug" "$OUTPUT"

# Test 5: Unknown flag fails
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --invalid-flag 2>&1)" || EXIT_CODE=$?
assert_eq "Unknown flag exits non-zero" "1" "$EXIT_CODE"
assert_match "Unknown flag reports error" "\[ERROR\] init: Malformed or unsupported option: --invalid-flag" "$OUTPUT"

# Test 6: Slug with path traversal rejected
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "../etc" 2>&1)" || EXIT_CODE=$?
assert_eq "Traversal slug exits non-zero" "1" "$EXIT_CODE"
assert_match "Traversal slug reports error" "\[ERROR\] init: Invalid slug format" "$OUTPUT"

# Test 7: Slug with invalid chars rejected
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "bad@slug!" 2>&1)" || EXIT_CODE=$?
assert_eq "Invalid characters in slug exits non-zero" "1" "$EXIT_CODE"
assert_match "Invalid characters report error" "\[ERROR\] init: Invalid slug format" "$OUTPUT"

# Test 8: Help flags succeed with usage info
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --help 2>&1)" || EXIT_CODE=$?
assert_eq "--help flag exits 0" "0" "$EXIT_CODE"
assert_match "--help shows Usage message" "Usage: workflow-normalize.sh" "$OUTPUT"

EXIT_CODE=0
OUTPUT="$("$WORKFLOW" -h 2>&1)" || EXIT_CODE=$?
assert_eq "-h flag exits 0" "0" "$EXIT_CODE"
assert_match "-h shows Usage message" "Usage: workflow-normalize.sh" "$OUTPUT"

# Test 9: Confirmed run with valid custom slug (empty baseline findings)
TEST_SLUG="test-norm-$(date +%s)"
TEST_OUT="$REPO_ROOT/bounties/$TEST_SLUG/scans/findings_normalized.json"

CLEANUP_SLUGS=("$TEST_SLUG")
cleanup_all() {
  for s in "${CLEANUP_SLUGS[@]}"; do
    rm -rf "$REPO_ROOT/bounties/$s" 2>/dev/null || true
  done
}
trap cleanup_all EXIT

EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "$TEST_SLUG" --confirm 2>&1)" || EXIT_CODE=$?
assert_eq "Confirmed run exits 0" "0" "$EXIT_CODE"
assert_match "Confirmed run reports saved file" "\[OK\] Normalized findings saved to $TEST_OUT" "$OUTPUT"

# Test 10: Verify generated file exists and is valid JSON
TEST_COUNT=$((TEST_COUNT + 1))
if [[ -f "$TEST_OUT" ]]; then
  echo "  [PASS] Test $TEST_COUNT: Output artifact exists"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  echo "  [FAIL] Test $TEST_COUNT: Output artifact does not exist at $TEST_OUT" >&2
  exit 1
fi

# Test 11: Validate artifact schema fields (empty baseline)
VALIDATION="$(python3 "$SCRIPT_DIR/../validate_schemas.py" --normalized "$TEST_OUT" 2>&1)"
assert_match "Output JSON conforms to canonical schema" "SCHEMA_VALIDATION_PASSED" "$VALIDATION"

# Test 12: Ingestion and Normalization of synthetic scanner report fixtures
FIXTURE_SLUG="test-fixtures-$(date +%s)"
CLEANUP_SLUGS+=("$FIXTURE_SLUG")
FIXTURE_SCANS="$REPO_ROOT/bounties/$FIXTURE_SLUG/scans"
mkdir -p "$FIXTURE_SCANS"

# Seed a synthetic Slither report fixture
cat <<'EOF' > "$FIXTURE_SCANS/slither.json"
{
  "results": {
    "detectors": [
      {
        "check": "reentrancy-eth",
        "impact": "High",
        "confidence": "Medium",
        "description": "Reentrancy in Contract.withdraw() (src/Vault.sol#42-50)",
        "elements": [
          {
            "type": "function",
            "name": "withdraw",
            "source_mapping": {
              "filename_relative": "src/Vault.sol",
              "lines": [42, 50]
            }
          }
        ]
      }
    ]
  }
}
EOF

# Seed a synthetic Semgrep report fixture
cat <<'EOF' > "$FIXTURE_SCANS/semgrep.json"
{
  "results": [
    {
      "check_id": "rules.solidity.security.tx-origin",
      "path": "src/Auth.sol",
      "start": { "line": 15 },
      "end": { "line": 15 },
      "extra": {
        "severity": "WARNING",
        "message": "Use of tx.origin for authorization"
      }
    }
  ]
}
EOF

# Dry run with fixtures present does NOT write findings_normalized.json
FIXTURE_OUT="$FIXTURE_SCANS/findings_normalized.json"
DRY_OUTPUT="$("$WORKFLOW" --slug "$FIXTURE_SLUG" --dry-run 2>&1)" || true
assert_match "Fixture dry-run previews destination" "\[DRY-RUN\] Will normalize findings into $FIXTURE_OUT" "$DRY_OUTPUT"
TEST_COUNT=$((TEST_COUNT + 1))
if [[ ! -f "$FIXTURE_OUT" ]]; then
  echo "  [PASS] Test $TEST_COUNT: Dry run did not create artifact"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  echo "  [FAIL] Test $TEST_COUNT: Dry run created file unexpectedly" >&2
  exit 1
fi

# Confirmed run ingests and normalizes the fixtures
CONFIRM_OUTPUT="$("$WORKFLOW" --slug "$FIXTURE_SLUG" --confirm 2>&1)"
assert_match "Fixture confirmed run reports saved artifact" "\[OK\] Normalized findings saved to $FIXTURE_OUT" "$CONFIRM_OUTPUT"

# Validate ingested findings schema and contents
FIXTURE_VAL="$(python3 "$SCRIPT_DIR/../validate_schemas.py" --normalized "$FIXTURE_OUT" 2>&1)"
assert_match "Fixture output conforms to schema" "SCHEMA_VALIDATION_PASSED" "$FIXTURE_VAL"

FIXTURE_CONTENT_CHECK="$(python3 -c "
import json
with open('$FIXTURE_OUT') as f:
    d = json.load(f)
assert d['slug'] == '$FIXTURE_SLUG'
assert d['status'] == 'NORMALIZATION_COMPLETE'
findings = d['normalized_findings']
assert len(findings) == 2, f'Expected 2 findings, got {len(findings)}'

slither_finding = next((f for f in findings if 'slither' in f['id']), None)
assert slither_finding is not None, 'Slither finding missing'
assert slither_finding['classification'] == 'STATIC_ANALYSIS'
assert slither_finding['severity'] == 'HIGH'
assert slither_finding['location']['file'] == 'src/Vault.sol'
assert slither_finding['location']['line_start'] == 42
assert slither_finding['provenance'][0]['tool'] == 'slither'

semgrep_finding = next((f for f in findings if 'semgrep' in f['id']), None)
assert semgrep_finding is not None, 'Semgrep finding missing'
assert semgrep_finding['classification'] == 'STATIC_ANALYSIS'
assert semgrep_finding['location']['file'] == 'src/Auth.sol'
assert semgrep_finding['provenance'][0]['tool'] == 'semgrep'

print('FIXTURE_VERIFIED')
")"
assert_eq "Fixture findings accurately preserved metadata and provenance" "FIXTURE_VERIFIED" "$FIXTURE_CONTENT_CHECK"

echo "=========================================================="
echo "TEST SUITE COMPLETE: $PASS_COUNT / $TEST_COUNT assertions passed successfully."
echo "=========================================================="
