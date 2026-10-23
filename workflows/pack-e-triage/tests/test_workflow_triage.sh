#!/usr/bin/env bash
# Test suite for Pack E Vulnerability Triage Workflow (workflow-triage.sh)
# Persona: CANTINA-SEC-TRIAGE-001
# Validates the 12-item Deployment Acceptance Checklist
set -euo pipefail

SCRIPT_DIR="$(cd -- "${BASH_SOURCE[0]%/*}" >/dev/null 2>&1 && pwd -P)"
WORKFLOW="$SCRIPT_DIR/../workflow-triage.sh"
REPO_ROOT="/home/nova/projects/cantina"
VALIDATOR="$SCRIPT_DIR/../validate_schemas.py"

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

echo "=== Running Pack E Vulnerability Triage 12-Item Acceptance Suite ==="

# Criterion 1: Existing agent identified and replacement decision documented
TEST_COUNT=$((TEST_COUNT + 1))
if grep -q "CANTINA-SEC-TRIAGE-001" "$SCRIPT_DIR/../META_PERSONA.md" && \
   grep -q "vulnerability-triage-oracle" "$REPO_ROOT/global/agents/index.md"; then
  echo "  [PASS] Test $TEST_COUNT: Criterion 1 - Canonical agent identified and registered"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  echo "  [FAIL] Test $TEST_COUNT: Criterion 1 - Canonical agent not registered" >&2
  exit 1
fi

# Criterion 2: Bash syntax valid
EXIT_CODE=0
bash -n "$WORKFLOW" || EXIT_CODE=$?
assert_eq "Criterion 2 - Bash syntax valid via bash -n" "0" "$EXIT_CODE"

# Criterion 3: Unknown arguments rejected
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --invalid-flag 2>&1)" || EXIT_CODE=$?
assert_eq "Criterion 3 - Unknown arguments rejected with exit 1" "1" "$EXIT_CODE"
assert_match "Criterion 3 - Unknown arguments error message" "\[ERROR\] init: Malformed or unsupported option" "$OUTPUT"

# Criterion 4: Missing slug value rejected
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug 2>&1)" || EXIT_CODE=$?
assert_eq "Criterion 4 - Missing slug value exits 1" "1" "$EXIT_CODE"
assert_match "Criterion 4 - Missing slug error message" "\[ERROR\] init: Missing value for --slug" "$OUTPUT"

# Criterion 5: Path traversal rejected
EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "../etc" 2>&1)" || EXIT_CODE=$?
assert_eq "Criterion 5 - Path traversal (..) rejected with exit 1" "1" "$EXIT_CODE"
assert_match "Criterion 5 - Path traversal error message" "\[ERROR\] init: Invalid slug format" "$OUTPUT"

EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "foo/bar" 2>&1)" || EXIT_CODE=$?
assert_eq "Criterion 5 - Path separators (/) rejected with exit 1" "1" "$EXIT_CODE"

EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "bad#slug!" 2>&1)" || EXIT_CODE=$?
assert_eq "Criterion 5 - Invalid special characters rejected with exit 1" "1" "$EXIT_CODE"

# Criterion 6: Dry run performs no final write
TEST_SLUG="test-triage-chk-$(date +%s)"
TEST_BOUNTY="$REPO_ROOT/bounties/$TEST_SLUG"
TEST_OUT="$TEST_BOUNTY/scans/triage_summary.json"
trap 'rm -rf "$TEST_BOUNTY"' EXIT

OUTPUT="$("$WORKFLOW" --slug "$TEST_SLUG" --dry-run 2>&1)" || true
assert_match "Criterion 6 - Dry run prints destination preview" "\[DRY-RUN\] Will triage candidate findings into" "$OUTPUT"
TEST_COUNT=$((TEST_COUNT + 1))
if [[ ! -f "$TEST_OUT" ]]; then
  echo "  [PASS] Test $TEST_COUNT: Criterion 6 - Dry run wrote no file"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  echo "  [FAIL] Test $TEST_COUNT: Criterion 6 - Dry run unexpectedly wrote file" >&2
  exit 1
fi

# Criterion 7: Confirmation gate enforced
OUTPUT="$("$WORKFLOW" --slug "$TEST_SLUG" 2>&1)" || true
assert_match "Criterion 7 - Unconfirmed run defaults to preview" "\[DRY-RUN\]" "$OUTPUT"
OUTPUT="$("$WORKFLOW" --slug "$TEST_SLUG" --dry-run --confirm 2>&1)" || true
assert_match "Criterion 7 - --dry-run overrides --confirm" "\[DRY-RUN\]" "$OUTPUT"

# Criterion 8: Malformed scanner input reported
mkdir -p "$TEST_BOUNTY/scans"
echo "{ malformed json corrupt content" > "$TEST_BOUNTY/scans/findings_normalized.json"

EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "$TEST_SLUG" --confirm 2>&1)" || EXIT_CODE=$?
assert_eq "Criterion 8 - Workflow handles malformed scanner input safely" "0" "$EXIT_CODE"

CORRUPT_CHECK="$(python3 -c "
import json
with open('$TEST_OUT') as f:
    d = json.load(f)
assert len(d['errors']) > 0, 'No errors captured for corrupt json'
assert any('Failed to parse' in e for e in d['errors']), 'Parse error missing from errors'
assert any('Failed to parse' in lim for lim in d['environment']['limitations']), 'Parse error missing from limitations'
assert d['status'] == 'TRIAGE_INCOMPLETE', f'expected TRIAGE_INCOMPLETE, got {d[\"status\"]}'
print('CORRUPT_INPUT_SAFELY_HANDLED')
")"
assert_eq "Criterion 8 - Corrupt scanner input safely recorded in errors & limitations" "CORRUPT_INPUT_SAFELY_HANDLED" "$CORRUPT_CHECK"

# Criterion 9: JSON output validated against schema
VALIDATION_OUT="$(python3 "$VALIDATOR" --triage "$TEST_OUT" 2>&1)"
assert_match "Criterion 9 - JSON output passes schema validation" "SCHEMA_VALIDATION_PASSED" "$VALIDATION_OUT"

# Criterion 10: Summary counts reconcile
cat <<'MOCK_NORM' > "$TEST_BOUNTY/scans/findings_normalized.json"
{
  "slug": "mock",
  "normalized_findings": [
    {
      "id": "SEC-001",
      "title": "Unchecked transfer return",
      "disposition": "NEEDS_INVESTIGATION",
      "severity": "HIGH",
      "confidence": "LOW",
      "root_cause": "Missing require on ERC20 transfer call",
      "affected_components": ["Vault.sol"],
      "evidence": ["Vault.sol#L42"]
    },
    {
      "id": "SEC-002",
      "title": "Reentrancy in withdraw",
      "disposition": "VALIDATED",
      "severity": "CRITICAL",
      "confidence": "HIGH",
      "root_cause": "State update after external call",
      "affected_components": ["Pool.sol"],
      "evidence": ["Pool.sol#L99"]
    },
    {
      "id": "SEC-003",
      "title": "Unverified external call",
      "disposition": "UNVERIFIED",
      "severity": "LOW",
      "confidence": "UNVERIFIED",
      "root_cause": "Call to unverified address",
      "affected_components": ["Router.sol"],
      "evidence": ["Router.sol#L12"]
    }
  ]
}
MOCK_NORM

EXIT_CODE=0
OUTPUT="$("$WORKFLOW" --slug "$TEST_SLUG" --confirm 2>&1)" || EXIT_CODE=$?
assert_eq "Confirmed run with mock findings exits 0" "0" "$EXIT_CODE"

RECONCILE_CHECK="$(python3 -c "
import json
with open('$TEST_OUT') as f:
    d = json.load(f)
s = d['summary']
c = d['candidates']
assert s['total_candidates'] == 3, f'total mismatch: {s[\"total_candidates\"]}'
assert s['validated'] == 1, 'validated count mismatch'
assert s['needs_investigation'] == 1, 'needs_investigation count mismatch'
assert s['unverified'] == 1, 'unverified count mismatch'
assert s['false_positive'] == 0
assert s['duplicates'] == 0
assert s['out_of_scope'] == 0
assert s['informational'] == 0
assert sum(s[k] for k in ['validated', 'likely_valid', 'needs_investigation', 'false_positive', 'duplicates', 'out_of_scope', 'informational', 'unverified']) == s['total_candidates']
print('SUMMARY_COUNTS_RECONCILED')
")"
assert_eq "Criterion 10 - Summary counts reconcile with candidate records" "SUMMARY_COUNTS_RECONCILED" "$RECONCILE_CHECK"

# Criterion 11: Existing evidence preserved
TEST_COUNT=$((TEST_COUNT + 1))
if [[ -f "$TEST_BOUNTY/scans/findings_normalized.json" ]]; then
  echo "  [PASS] Test $TEST_COUNT: Criterion 11 - Source scan artifacts preserved"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  echo "  [FAIL] Test $TEST_COUNT: Criterion 11 - Source scan artifact unexpectedly deleted" >&2
  exit 1
fi

# Criterion 12: Final status reflects actual work
STATUS_CHECK="$(python3 -c "
import json
with open('$TEST_OUT') as f:
    d = json.load(f)
assert d['status'] == 'TRIAGE_COMPLETE_WITH_LIMITATIONS', f'expected TRIAGE_COMPLETE_WITH_LIMITATIONS, got {d[\"status\"]}'
print('FINAL_STATUS_ACCURATE')
")"
assert_eq "Criterion 12 - Final status reflects actual work with limitations" "FINAL_STATUS_ACCURATE" "$STATUS_CHECK"

echo "=========================================================="
echo "ACCEPTANCE CHECKLIST: All 12 deployment criteria verified ($PASS_COUNT / $TEST_COUNT passed)."
echo "=========================================================="
