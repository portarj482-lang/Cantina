#!/usr/bin/env bash
# Behavioral Test Suite for Pack E Overlap & Known-Issue Annotation (workflow-overlap.sh)
set -euo pipefail

TEST_ROOT="$(mktemp -d -t cantina-overlap-test-XXXXXX)"
SCRIPT_DIR="$(cd -- "${BASH_SOURCE[0]%/*}" >/dev/null 2>&1 && pwd -P)"
WORKFLOW_DIR="$(cd "$SCRIPT_DIR/.." && pwd -P)"
WORKFLOW_SCRIPT="$WORKFLOW_DIR/workflow-overlap.sh"
VALIDATOR_SCRIPT="$WORKFLOW_DIR/validate_schemas.py"
REPO_ROOT="/home/nova/projects/cantina"

cleanup() {
  rm -rf "$TEST_ROOT"
}
trap cleanup EXIT INT TERM

TEST_COUNT=0
PASS_COUNT=0

assert_eq() {
  local num="$1" desc="$2" expected="$3" actual="$4"
  TEST_COUNT=$((TEST_COUNT + 1))
  if [[ "$expected" == "$actual" ]]; then
    echo "  [PASS] Test $num: $desc"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    echo "  [FAIL] Test $num: $desc (Expected '$expected', got '$actual')" >&2
    exit 1
  fi
}

assert_match() {
  local num="$1" desc="$2" pattern="$3" actual="$4"
  TEST_COUNT=$((TEST_COUNT + 1))
  if [[ "$actual" =~ $pattern ]]; then
    echo "  [PASS] Test $num: $desc"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    echo "  [FAIL] Test $num: $desc (Pattern '$pattern' not found in '$actual')" >&2
    exit 1
  fi
}

echo "=== Running Overlap & Known-Issue Annotation Automated Test Suite ==="
echo "Test root: $TEST_ROOT"

# Setup isolated test repo workspace
TEST_REPO="$TEST_ROOT/repo"
mkdir -p "$TEST_REPO/bounties"
(
  cd "$TEST_REPO"
  git init -q
  git config user.email "test@cantina.local"
  git config user.name "Test Runner"
  mkdir -p global
  cat <<'EOF' > global/refutations.md
# Global Refutations
- Refuted hypothesis: reentrancy in read-only methods is non-exploitable
EOF
  git add .
  git commit -q -m "init test repo"
)

# -------------------------------------------------------------
# Test 1: Missing --slug value returns exit code 4
# -------------------------------------------------------------
set +e
OUT1="$("$WORKFLOW_SCRIPT" --slug 2>&1)"
CODE1=$?
set -e
assert_eq "1" "Missing --slug value returns exit code 4" "4" "$CODE1"
assert_match "1 (msg)" "Missing --slug reports error" "Missing value for --slug" "$OUT1"

# -------------------------------------------------------------
# Test 2: Unknown flag returns exit code 4
# -------------------------------------------------------------
set +e
OUT2="$("$WORKFLOW_SCRIPT" --unknown-flag 2>&1)"
CODE2=$?
set -e
assert_eq "2" "Unknown flag returns exit code 4" "4" "$CODE2"
assert_match "2 (msg)" "Unknown flag reports error" "Unknown flag" "$OUT2"

# -------------------------------------------------------------
# Test 3: Slug path traversal returns exit code 4
# -------------------------------------------------------------
set +e
OUT3="$("$WORKFLOW_SCRIPT" --slug "../escape" 2>&1)"
CODE3=$?
set -e
assert_eq "3" "Slug path traversal returns exit code 4" "4" "$CODE3"

# -------------------------------------------------------------
# Test 4: Invalid slug characters return exit code 4
# -------------------------------------------------------------
set +e
OUT4="$("$WORKFLOW_SCRIPT" --slug "bad@slug!" 2>&1)"
CODE4=$?
set -e
assert_eq "4" "Invalid characters in slug returns exit code 4" "4" "$CODE4"

# -------------------------------------------------------------
# Test 5: Conflicting duplicate --slug options return exit code 4
# -------------------------------------------------------------
set +e
OUT5="$("$WORKFLOW_SCRIPT" --slug slug-a --slug slug-b 2>&1)"
CODE5=$?
set -e
assert_eq "5" "Conflicting duplicate --slug returns exit code 4" "4" "$CODE5"

# -------------------------------------------------------------
# Test 6: Missing bounty directory returns exit code 2
# -------------------------------------------------------------
set +e
REPO_ROOT="$TEST_REPO" "$WORKFLOW_SCRIPT" --slug non-existent-bounty >/dev/null 2>&1
CODE6=$?
set -e
assert_eq "6" "Missing bounty directory returns exit code 2" "2" "$CODE6"

# -------------------------------------------------------------
# Test 7: Preview mode with --dry-run returns 0 and writes NO files
# -------------------------------------------------------------
mkdir -p "$TEST_REPO/bounties/bounty-preview/scans"
set +e
OUT7=$(REPO_ROOT="$TEST_REPO" "$WORKFLOW_SCRIPT" --slug bounty-preview --dry-run 2>&1)
CODE7=$?
set -e
assert_eq "7" "Preview mode with --dry-run returns exit code 0" "0" "$CODE7"
assert_match "7 (msg)" "Preview mode indicates dry-run" "\[DRY-RUN\] Will annotate overlaps into" "$OUT7"
if [[ ! -f "$TEST_REPO/bounties/bounty-preview/scans/overlap_analysis.json" ]]; then
  echo "  [PASS] Test 7 (no-write): No file written in preview mode"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  echo "  [FAIL] Test 7 (no-write): File written unexpectedly in preview mode" >&2
  exit 1
fi
TEST_COUNT=$((TEST_COUNT + 1))

# -------------------------------------------------------------
# Test 8: Default invocation (no --confirm) returns 0 and writes NO files
# -------------------------------------------------------------
set +e
OUT8=$(REPO_ROOT="$TEST_REPO" "$WORKFLOW_SCRIPT" --slug bounty-preview 2>&1)
CODE8=$?
set -e
assert_eq "8" "Default invocation (no --confirm) returns exit code 0" "0" "$CODE8"
if [[ ! -f "$TEST_REPO/bounties/bounty-preview/scans/overlap_analysis.json" ]]; then
  echo "  [PASS] Test 8 (no-write): No file written without --confirm"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  echo "  [FAIL] Test 8 (no-write): File written unexpectedly without --confirm" >&2
  exit 1
fi
TEST_COUNT=$((TEST_COUNT + 1))

# -------------------------------------------------------------
# Test 9: --dry-run with --confirm still preserves preview (writes NO files)
# -------------------------------------------------------------
set +e
OUT9=$(REPO_ROOT="$TEST_REPO" "$WORKFLOW_SCRIPT" --slug bounty-preview --dry-run --confirm 2>&1)
CODE9=$?
set -e
assert_eq "9" "--dry-run with --confirm returns exit code 0" "0" "$CODE9"
if [[ ! -f "$TEST_REPO/bounties/bounty-preview/scans/overlap_analysis.json" ]]; then
  echo "  [PASS] Test 9 (no-write): No file written when --dry-run is supplied"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  echo "  [FAIL] Test 9 (no-write): File written unexpectedly when --dry-run is supplied" >&2
  exit 1
fi
TEST_COUNT=$((TEST_COUNT + 1))

# -------------------------------------------------------------
# Test 10: Symlinked scans directory is refused (exit code 2)
# -------------------------------------------------------------
mkdir -p "$TEST_REPO/bounties/bounty-symlink-scans"
TARGET_SCANS="$TEST_ROOT/external_scans"
mkdir -p "$TARGET_SCANS"
ln -s "$TARGET_SCANS" "$TEST_REPO/bounties/bounty-symlink-scans/scans"

set +e
REPO_ROOT="$TEST_REPO" "$WORKFLOW_SCRIPT" --slug bounty-symlink-scans --confirm >/dev/null 2>&1
CODE10=$?
set -e
assert_eq "10" "Symlinked scans directory is refused with exit code 2" "2" "$CODE10"

# -------------------------------------------------------------
# Test 11: Symlinked bounty directory is refused (exit code 2)
# -------------------------------------------------------------
TARGET_BOUNTY="$TEST_ROOT/external_bounty"
mkdir -p "$TARGET_BOUNTY"
ln -s "$TARGET_BOUNTY" "$TEST_REPO/bounties/bounty-symlink-dir"

set +e
REPO_ROOT="$TEST_REPO" "$WORKFLOW_SCRIPT" --slug bounty-symlink-dir --confirm >/dev/null 2>&1
CODE11=$?
set -e
assert_eq "11" "Symlinked bounty directory is refused with exit code 2" "2" "$CODE11"

# -------------------------------------------------------------
# Test 12: Confirmed run with valid candidates & known issues writes JSON artifact
# -------------------------------------------------------------
VALID_BOUNTY="$TEST_REPO/bounties/bounty-confirmed"
mkdir -p "$VALID_BOUNTY/scans" "$VALID_BOUNTY/findings"

cat <<'EOF' > "$VALID_BOUNTY/MEMORY.md"
# Known Issues & Accepted Risks
- Vault fee calculation rounding error is accepted risk
- Unprotected initialization on implementation contract is known
EOF

cat <<'EOF' > "$VALID_BOUNTY/findings/finding1.md"
# Vault Fee Rounding Allows Truncation
Affected: Vault.sol
Root Cause: Fee calculation truncates downward to zero when amount is small.
Impact: Loss of fees.
EOF

cat <<'EOF' > "$VALID_BOUNTY/findings/finding2.md"
# Flashloan Callback Missing Validation
Affected: FlashMinter.sol
Root Cause: Arbitrary recipient executes flashloan without balance assertion.
Impact: Unauthorized minting.
EOF

set +e
OUT12=$(REPO_ROOT="$TEST_REPO" "$WORKFLOW_SCRIPT" --slug bounty-confirmed --confirm 2>&1)
CODE12=$?
set -e
assert_eq "12" "Confirmed run returns exit code 0" "0" "$CODE12"
assert_match "12 (saved)" "Confirmed run reports saved file" "\[OK\] Overlap analysis saved to" "$OUT12"

OUT_ARTIFACT="$VALID_BOUNTY/scans/overlap_analysis.json"
if [[ -f "$OUT_ARTIFACT" ]]; then
  echo "  [PASS] Test 12 (artifact-exists): Output artifact was created"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  echo "  [FAIL] Test 12 (artifact-exists): Output artifact not found at $OUT_ARTIFACT" >&2
  exit 1
fi
TEST_COUNT=$((TEST_COUNT + 1))

# -------------------------------------------------------------
# Test 13: Output JSON conforms to schema via validate_schemas.py
# -------------------------------------------------------------
set +e
VAL_OUT=$(python3 "$VALIDATOR_SCRIPT" --overlap "$OUT_ARTIFACT" 2>&1)
VAL_CODE=$?
set -e
assert_eq "13" "Output artifact validates against overlap schema" "0" "$VAL_CODE"

# -------------------------------------------------------------
# Test 14: Output artifact has strict 0600 permissions
# -------------------------------------------------------------
PERMS=$(stat -c "%a" "$OUT_ARTIFACT" 2>/dev/null || stat -f "%Lp" "$OUT_ARTIFACT" 2>/dev/null)
assert_eq "14" "Output artifact has 0600 permissions" "600" "$PERMS"

# -------------------------------------------------------------
# Test 15: Confirmed run properly detects overlap relationships
# -------------------------------------------------------------
CHECK_ANALYSIS=$(python3 -c "
import json
with open('$OUT_ARTIFACT') as f:
    d = json.load(f)
assert d['schema_version'] == '1.0'
assert d['slug'] == 'bounty-confirmed'
assert d['known_issues_checked'] is True
assert d['status'] == 'OVERLAP_CHECK_COMPLETE'
assert d['analysis']['candidate_count'] == 2
assert d['analysis']['known_issue_count'] >= 2
assert d['analysis']['confirmed_overlap_count'] + d['analysis']['probable_overlap_count'] >= 1
assert d['write']['authorized'] is True
assert d['write']['written'] is True
assert d['write']['validated_after_write'] is True
print('ANALYSIS_OK')
")
assert_eq "15" "Analysis payload contains verified overlap relationships" "ANALYSIS_OK" "$CHECK_ANALYSIS"

# -------------------------------------------------------------
# Test 16: No temporary files leaked in scans directory
# -------------------------------------------------------------
LEAKED_TMP=$(ls -a "$VALID_BOUNTY/scans" | grep -E '\.overlap_analysis\.tmp' || true)
assert_eq "16" "Zero temporary files leaked after write" "" "$LEAKED_TMP"

# -------------------------------------------------------------
# Test 17: Empty known-issue corpus sets known_issues_checked=false and status=OVERLAP_CHECK_PARTIAL
# -------------------------------------------------------------
NO_KNOWN_BOUNTY="$TEST_REPO/bounties/bounty-no-known"
mkdir -p "$NO_KNOWN_BOUNTY/scans" "$NO_KNOWN_BOUNTY/findings"

cat <<'EOF' > "$NO_KNOWN_BOUNTY/findings/cand.md"
# Candidate Finding Without Prior Knowledge
Affected: Dummy.sol
EOF

set +e
REPO_ROOT="$TEST_REPO" "$WORKFLOW_SCRIPT" --slug bounty-no-known --confirm >/dev/null 2>&1
CODE17=$?
set -e
assert_eq "17" "Confirmed run without known issues returns exit code 0" "0" "$CODE17"

NO_KNOWN_ARTIFACT="$NO_KNOWN_BOUNTY/scans/overlap_analysis.json"
CHECK_NO_KNOWN=$(python3 -c "
import json
with open('$NO_KNOWN_ARTIFACT') as f:
    d = json.load(f)
assert d['known_issues_checked'] is False, 'known_issues_checked must be false when corpus is empty'
assert d['status'] == 'OVERLAP_CHECK_PARTIAL', f'status must be PARTIAL, got {d[\"status\"]}'
assert len(d['limitations']) >= 1, 'limitation must be recorded'
print('EMPTY_CORPUS_OK')
")
assert_eq "17 (check)" "Empty corpus sets known_issues_checked: false and OVERLAP_CHECK_PARTIAL" "EMPTY_CORPUS_OK" "$CHECK_NO_KNOWN"

# -------------------------------------------------------------
# Test 18: Missing dependency returns exit code 3
# -------------------------------------------------------------
MOCK_BIN="$TEST_ROOT/mock_bin_no_git"
mkdir -p "$MOCK_BIN"
ln -s "$(command -v bash)" "$MOCK_BIN/bash"
ln -s "$(command -v python3)" "$MOCK_BIN/python3"
ln -s "$(command -v pwd)" "$MOCK_BIN/pwd"
ln -s "$(command -v date)" "$MOCK_BIN/date"
# git is omitted intentionally

set +e
PATH="$MOCK_BIN" "$WORKFLOW_SCRIPT" --slug base >/dev/null 2>&1
CODE18=$?
set -e
assert_eq "18" "Missing dependency returns exit code 3" "3" "$CODE18"

# -------------------------------------------------------------
# Test 19: Write failure on read-only scans dir exits code 2
# -------------------------------------------------------------
RO_BOUNTY="$TEST_REPO/bounties/bounty-ro"
mkdir -p "$RO_BOUNTY/scans"
chmod 555 "$RO_BOUNTY/scans"

set +e
REPO_ROOT="$TEST_REPO" "$WORKFLOW_SCRIPT" --slug bounty-ro --confirm >/dev/null 2>&1
CODE19=$?
set -e
chmod 755 "$RO_BOUNTY/scans" || true
assert_eq "19" "Write failure on read-only directory exits code 2" "2" "$CODE19"

# -------------------------------------------------------------
# Test 20: Stderr outputs valid JSON Lines event log
# -------------------------------------------------------------
STDERR_OUT=$(REPO_ROOT="$TEST_REPO" "$WORKFLOW_SCRIPT" --slug bounty-confirmed --dry-run 2>&1 >/dev/null)
JSON_CHECK=$(python3 -c "
import json, sys
lines = '''$STDERR_OUT'''.strip().splitlines()
found_preview = False
for l in lines:
    try:
        obj = json.loads(l)
        if obj.get('event') == 'PREVIEW_COMPLETE':
            found_preview = True
    except Exception:
        pass
print('JSON_EVENT_OK' if found_preview else 'NO_EVENT')
")
assert_eq "20" "Stderr outputs structured JSON Lines event" "JSON_EVENT_OK" "$JSON_CHECK"

# -------------------------------------------------------------
# Test 21: Symlinked destination output file is refused with exit code 2
# -------------------------------------------------------------
SYMLINK_FILE_BOUNTY="$TEST_REPO/bounties/bounty-symlink-file"
mkdir -p "$SYMLINK_FILE_BOUNTY/scans"
TARGET_EVIL_FILE="$TEST_ROOT/external_evil.json"
echo '{"evil": true}' > "$TARGET_EVIL_FILE"
ln -s "$TARGET_EVIL_FILE" "$SYMLINK_FILE_BOUNTY/scans/overlap_analysis.json"

set +e
REPO_ROOT="$TEST_REPO" "$WORKFLOW_SCRIPT" --slug bounty-symlink-file --confirm >/dev/null 2>&1
CODE21=$?
set -e
assert_eq "21" "Symlinked destination output file is refused with exit code 2" "2" "$CODE21"

# -------------------------------------------------------------
# Test 22: Ingest findings_normalized.json with nested target/location dicts
# -------------------------------------------------------------
NORM_BOUNTY="$TEST_REPO/bounties/bounty-norm"
mkdir -p "$NORM_BOUNTY/scans"
cat <<'EOF' > "$NORM_BOUNTY/scans/findings_normalized.json"
{
  "slug": "bounty-norm",
  "status": "NORMALIZATION_COMPLETE",
  "timestamp": "2026-10-23T00:00:00Z",
  "normalized_findings": [
    {
      "id": "NORM-001",
      "title": "Rounding bug in TokenVault fee calculation",
      "severity": "HIGH",
      "classification": "CONFIRMED",
      "description": "Fee rounding down to zero in TokenVault allows drain",
      "target": {
        "repository": "bounty-norm",
        "slug": "bounty-norm"
      },
      "location": {
        "file": "contracts/TokenVault.sol",
        "contract_or_program": "TokenVault"
      },
      "provenance": []
    }
  ]
}
EOF

cat <<'EOF' > "$NORM_BOUNTY/MEMORY.md"
# Known Issues
- Fee rounding down in TokenVault is accepted risk
EOF

set +e
OUT22=$(REPO_ROOT="$TEST_REPO" "$WORKFLOW_SCRIPT" --slug bounty-norm --confirm 2>&1)
CODE22=$?
set -e
assert_eq "22" "Confirmed run ingesting findings_normalized.json returns 0" "0" "$CODE22"

CHECK_NORM=$(python3 -c "
import json
with open('$NORM_BOUNTY/scans/overlap_analysis.json') as f:
    d = json.load(f)
assert d['analysis']['candidate_count'] == 1
assert d['analysis']['confirmed_overlap_count'] + d['analysis']['probable_overlap_count'] == 1
print('NORM_INGEST_OK')
")
assert_eq "22 (check)" "findings_normalized.json candidate correctly parsed and correlated" "NORM_INGEST_OK" "$CHECK_NORM"

# -------------------------------------------------------------
# Test 23: Ingest triage_summary.json with list components and dict impact
# -------------------------------------------------------------
TRIAGE_BOUNTY="$TEST_REPO/bounties/bounty-triage"
mkdir -p "$TRIAGE_BOUNTY/scans"
cat <<'EOF' > "$TRIAGE_BOUNTY/scans/triage_summary.json"
{
  "schema_version": "1.0",
  "slug": "bounty-triage",
  "status": "TRIAGE_COMPLETE",
  "timestamp": "2026-10-23T00:00:00Z",
  "summary": {
    "total_candidates": 1,
    "validated": 1,
    "likely_valid": 0,
    "needs_investigation": 0,
    "false_positive": 0,
    "duplicates": 0,
    "out_of_scope": 0,
    "informational": 0
  },
  "environment": {
    "repository_root": "/tmp",
    "source_revision": "abc123",
    "tool_registry_baseline": "2026-10-23",
    "tools_executed": [],
    "tools_skipped": [],
    "limitations": []
  },
  "candidates": [
    {
      "id": "TRIAGE-001",
      "title": "Flash loan minting without balance check",
      "disposition": "VALIDATED",
      "severity": "CRITICAL",
      "confidence": "HIGH",
      "root_cause": "Arbitrary recipient executes flashloan without balance assertion",
      "affected_components": ["FlashMinter", "contracts/FlashMinter.sol"],
      "evidence": [],
      "exploitability": {
        "prerequisites": ["unauthorized caller"],
        "attacker_capabilities": ["flashloan execution"],
        "reproduction_status": "REPRODUCED"
      },
      "impact": {
        "description": "Unauthorized minting and collateral drainage",
        "demonstrated": true
      },
      "duplicate_of": null,
      "scope_status": "IN_SCOPE",
      "remediation": "Add balance assertion",
      "limitations": []
    }
  ],
  "errors": [],
  "provenance": {
    "input_artifacts": [],
    "output_artifact": "triage_summary.json"
  }
}
EOF

cat <<'EOF' > "$TRIAGE_BOUNTY/MEMORY.md"
# Known Issues
- FlashMinter flashloan lacks balance assertion
EOF

set +e
OUT23=$(REPO_ROOT="$TEST_REPO" "$WORKFLOW_SCRIPT" --slug bounty-triage --confirm 2>&1)
CODE23=$?
set -e
assert_eq "23" "Confirmed run ingesting triage_summary.json returns 0" "0" "$CODE23"

CHECK_TRIAGE=$(python3 -c "
import json
with open('$TRIAGE_BOUNTY/scans/overlap_analysis.json') as f:
    d = json.load(f)
assert d['analysis']['candidate_count'] == 1
assert d['analysis']['confirmed_overlap_count'] + d['analysis']['probable_overlap_count'] == 1
print('TRIAGE_INGEST_OK')
")
assert_eq "23 (check)" "triage_summary.json candidate correctly parsed and correlated" "TRIAGE_INGEST_OK" "$CHECK_TRIAGE"

# -------------------------------------------------------------
# Test 24: Candidate with empty / insufficient evidence results in UNABLE_TO_DETERMINE
# -------------------------------------------------------------
INDET_BOUNTY="$TEST_REPO/bounties/bounty-indet"
mkdir -p "$INDET_BOUNTY/scans" "$INDET_BOUNTY/findings"
cat <<'EOF' > "$INDET_BOUNTY/MEMORY.md"
# Known Issues
- Some documented issue
EOF
# Create empty candidate finding
touch "$INDET_BOUNTY/findings/empty_cand.md"

set +e
OUT24=$(REPO_ROOT="$TEST_REPO" "$WORKFLOW_SCRIPT" --slug bounty-indet --confirm 2>&1)
CODE24=$?
set -e
assert_eq "24" "Confirmed run with empty candidate evidence returns 0" "0" "$CODE24"

CHECK_INDET=$(python3 -c "
import json
with open('$INDET_BOUNTY/scans/overlap_analysis.json') as f:
    d = json.load(f)
assert d['analysis']['indeterminate_count'] >= 1
assert d['status'] == 'OVERLAP_CHECK_PARTIAL'
rel = d['analysis']['relationships'][0]
assert rel['classification'] == 'UNABLE_TO_DETERMINE'
print('INDET_CHECK_OK')
")
assert_eq "24 (check)" "Empty candidate yields UNABLE_TO_DETERMINE and OVERLAP_CHECK_PARTIAL" "INDET_CHECK_OK" "$CHECK_INDET"

# -------------------------------------------------------------
# Test 25: Schema validation failure on write returns exit code 1
# -------------------------------------------------------------
MOCK_SCHEMAS_DIR="$TEST_ROOT/bad_schemas"
mkdir -p "$MOCK_SCHEMAS_DIR"
cat <<'EOF' > "$MOCK_SCHEMAS_DIR/overlap_analysis.schema.json"
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["impossible_non_existent_key_12345"]
}
EOF

set +e
python3 "$WORKFLOW_DIR/overlap_analyzer.py" --repo-root "$TEST_REPO" --slug bounty-confirmed --confirm --schemas-dir "$MOCK_SCHEMAS_DIR" >/dev/null 2>&1
CODE25=$?
set -e
assert_eq "25" "Schema validation failure during write returns exit code 1" "1" "$CODE25"

echo "=========================================================="
echo "TEST SUITE COMPLETE: $PASS_COUNT / $TEST_COUNT assertions passed successfully."
echo "=========================================================="
