#!/usr/bin/env bash
# test_workflow_pathway_scout.sh — Pack A Pathway Scout Acceptance Test Suite
# Tests the workflow-pathway-scout.sh orchestrator for PACK-A-PATHWAY-SCOUT-001
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKFLOW="$SCRIPT_DIR/../workflow-pathway-scout.sh"
REPO_ROOT="/home/nova/projects/cantina"
VALIDATOR="$REPO_ROOT/workflows/pack-e-triage/validate_schemas.py"
META_PERSONA="$SCRIPT_DIR/../META_PERSONA.md"
INDEX="$REPO_ROOT/global/agents/index.md"
SCHEMA="$SCRIPT_DIR/../schemas/pathways.schema.json"

PASS=0
FAIL=0
TOTAL=0

# Test bounty slugs for isolated testing
TEST_SLUG="test-pack-a-$$"
SYMLINK_SLUG="test-pack-a-sym-$$"
TEST_BOUNTY="$REPO_ROOT/bounties/$TEST_SLUG"
TEST_BOUNTY_SYM="$REPO_ROOT/bounties/$SYMLINK_SLUG"

# Cleanup on exit
cleanup() {
  rm -rf "$TEST_BOUNTY" 2>/dev/null || true
  rm -f "$TEST_BOUNTY_SYM" 2>/dev/null || true
}
trap cleanup EXIT

pass() {
  PASS=$((PASS + 1))
  TOTAL=$((TOTAL + 1))
  echo "  [PASS] $1"
}

fail() {
  FAIL=$((FAIL + 1))
  TOTAL=$((TOTAL + 1))
  echo "  [FAIL] $1"
  echo "         => $2"
}

run_test() {
  TOTAL=$((TOTAL + 1))
  local desc="$1"; shift
  local expected_exit="${1:-0}"; shift
  local actual_exit=0
  local out
  out="$("$@" 2>&1)" || actual_exit=$?
  if [[ "$actual_exit" -eq "$expected_exit" ]]; then
    PASS=$((PASS + 1))
    echo "  [PASS] $desc (exit=$actual_exit)"
  else
    FAIL=$((FAIL + 1))
    echo "  [FAIL] $desc (expected exit=$expected_exit, got exit=$actual_exit)"
    echo "         output: ${out:0:200}"
  fi
}

echo "============================================================"
echo "  Pack A Pathway Scout — Acceptance Test Suite"
echo "  PACK-A-PATHWAY-SCOUT-001"
echo "============================================================"
echo ""

# --- CRITERION 1: Canonical identity checks ---
echo "--- [1] Canonical Identity ---"
if [[ -f "$META_PERSONA" ]] && grep -q "PACK-A-PATHWAY-SCOUT-001" "$META_PERSONA"; then
  pass "META_PERSONA.md exists and contains PACK-A-PATHWAY-SCOUT-001"
else
  fail "META_PERSONA.md" "Missing file or PACK-A-PATHWAY-SCOUT-001 not found in $META_PERSONA"
fi

if [[ -f "$INDEX" ]] && grep -q "pathway-scout-oracle" "$INDEX"; then
  pass "global/agents/index.md contains pathway-scout-oracle"
else
  fail "index.md registration" "pathway-scout-oracle not found in $INDEX"
fi

if [[ -f "$REPO_ROOT/global/agents/pathway-scout-oracle.md" ]]; then
  pass "global/agents/pathway-scout-oracle.md exists"
else
  fail "pathway-scout-oracle.md" "File missing: $REPO_ROOT/global/agents/pathway-scout-oracle.md"
fi

if [[ -f "$REPO_ROOT/.agents/skills/pathway-scout-oracle/SKILL.md" ]]; then
  pass ".agents/skills/pathway-scout-oracle/SKILL.md exists"
else
  fail "SKILL.md" "File missing: $REPO_ROOT/.agents/skills/pathway-scout-oracle/SKILL.md"
fi

if [[ -f "$SCHEMA" ]]; then
  pass "pathways.schema.json exists"
else
  fail "pathways.schema.json" "Schema missing at $SCHEMA"
fi

# --- CRITERION 2: Bash syntax check ---
echo ""
echo "--- [2] Bash Syntax Check ---"
if bash -n "$WORKFLOW" 2>/dev/null; then
  pass "bash -n passes on workflow-pathway-scout.sh"
else
  fail "bash -n" "Syntax error in $WORKFLOW"
fi

# --- CRITERION 3: Unknown arguments rejected ---
echo ""
echo "--- [3] Unknown Arguments ---"
exit_code=0
"$WORKFLOW" --unknown-arg 2>/dev/null || exit_code=$?
if [[ "$exit_code" -eq 2 ]]; then
  pass "Unknown argument --unknown-arg → exit 2"
else
  fail "Unknown argument" "Expected exit 2, got $exit_code"
fi

exit_code=0
"$WORKFLOW" unexpected-positional 2>/dev/null || exit_code=$?
if [[ "$exit_code" -eq 2 ]]; then
  pass "Positional argument rejected → exit 2"
else
  fail "Positional argument" "Expected exit 2, got $exit_code"
fi

# --- CRITERION 4: Missing --slug value rejected ---
echo ""
echo "--- [4] Missing --slug Value ---"
exit_code=0
"$WORKFLOW" --slug 2>/dev/null || exit_code=$?
if [[ "$exit_code" -eq 2 ]]; then
  pass "--slug with no value → exit 2"
else
  fail "--slug missing value" "Expected exit 2, got $exit_code"
fi

# --- CRITERION 5: Path traversal rejected ---
echo ""
echo "--- [5] Path Traversal Rejection ---"
exit_code=0
"$WORKFLOW" --slug "../etc" 2>/dev/null || exit_code=$?
if [[ "$exit_code" -eq 2 ]]; then
  pass "Slug ../etc → exit 2"
else
  fail "Path traversal ../etc" "Expected exit 2, got $exit_code"
fi

exit_code=0
"$WORKFLOW" --slug "../../root" 2>/dev/null || exit_code=$?
if [[ "$exit_code" -eq 2 ]]; then
  pass "Slug ../../root → exit 2"
else
  fail "Path traversal ../../root" "Expected exit 2, got $exit_code"
fi

# --- CRITERION 6: Slug with slashes rejected ---
echo ""
echo "--- [6] Slug With Slashes ---"
exit_code=0
"$WORKFLOW" --slug "foo/bar" 2>/dev/null || exit_code=$?
if [[ "$exit_code" -eq 2 ]]; then
  pass "Slug foo/bar → exit 2"
else
  fail "Slug with slash" "Expected exit 2, got $exit_code"
fi

# --- CRITERION 7: Invalid slug characters rejected ---
echo ""
echo "--- [7] Invalid Slug Characters ---"
exit_code=0
"$WORKFLOW" --slug "bad slug!" 2>/dev/null || exit_code=$?
if [[ "$exit_code" -eq 2 ]]; then
  pass "Slug 'bad slug!' → exit 2"
else
  fail "Invalid slug chars" "Expected exit 2, got $exit_code"
fi

exit_code=0
"$WORKFLOW" --slug "/absolute" 2>/dev/null || exit_code=$?
if [[ "$exit_code" -eq 2 ]]; then
  pass "Absolute path slug → exit 2"
else
  fail "Absolute path slug" "Expected exit 2, got $exit_code"
fi

# --- CRITERION 8: Default invocation performs dry-run, no write ---
echo ""
echo "--- [8] Default Invocation Is Dry-Run ---"
exit_code=0
out=$("$WORKFLOW" --slug "$TEST_SLUG" 2>&1) || exit_code=$?
if [[ "$exit_code" -eq 0 ]]; then
  pass "Default invocation exits 0"
else
  fail "Default invocation" "Expected exit 0, got $exit_code"
fi
if [[ ! -f "$TEST_BOUNTY/scans/pathways.json" ]]; then
  pass "Default invocation did not write pathways.json"
else
  fail "Default no-write" "pathways.json was unexpectedly created by default invocation"
fi

# --- CRITERION 9: --dry-run performs no write ---
echo ""
echo "--- [9] --dry-run Performs No Write ---"
exit_code=0
"$WORKFLOW" --dry-run --slug "$TEST_SLUG" 2>&1 || exit_code=$?
if [[ "$exit_code" -eq 0 ]]; then
  pass "--dry-run exits 0"
else
  fail "--dry-run" "Expected exit 0, got $exit_code"
fi
if [[ ! -f "$TEST_BOUNTY/scans/pathways.json" ]]; then
  pass "--dry-run did not write pathways.json"
else
  fail "--dry-run no-write" "pathways.json was unexpectedly written with --dry-run"
fi

# --- CRITERION 10: --dry-run --confirm still dry-runs (dry-run takes precedence) ---
echo ""
echo "--- [10] --dry-run Overrides --confirm ---"
exit_code=0
"$WORKFLOW" --dry-run --confirm --slug "$TEST_SLUG" 2>&1 || exit_code=$?
if [[ "$exit_code" -eq 0 ]]; then
  pass "--dry-run --confirm exits 0"
else
  fail "--dry-run --confirm" "Expected exit 0, got $exit_code"
fi
if [[ ! -f "$TEST_BOUNTY/scans/pathways.json" ]]; then
  pass "--dry-run --confirm did not write pathways.json"
else
  fail "--dry-run overrides --confirm" "pathways.json was unexpectedly written with --dry-run --confirm"
fi

# --- CRITERION 11: Confirmed write ---
echo ""
echo "--- [11] Confirmed Write ---"
mkdir -p "$TEST_BOUNTY"
exit_code=0
"$WORKFLOW" --confirm --slug "$TEST_SLUG" 2>&1 || exit_code=$?

# Accept exit 0 (PARTIAL with source) or exit 3 (BLOCKED, no source) — both are honest
if [[ "$exit_code" -eq 0 || "$exit_code" -eq 3 || "$exit_code" -eq 4 ]]; then
  pass "--confirm exits 0, 3, or 4 (exit=$exit_code)"
else
  fail "--confirm exit code" "Expected 0, 3, or 4 — got $exit_code"
fi

PATHWAY_FILE="$TEST_BOUNTY/scans/pathways.json"
if [[ -f "$PATHWAY_FILE" ]]; then
  pass "pathways.json was created"

  # Validate JSON is parseable
  if python3 -c "import json,sys; json.load(open('$PATHWAY_FILE'))" 2>/dev/null; then
    pass "pathways.json is valid JSON"
  else
    fail "pathways.json JSON validity" "File is not valid JSON"
  fi

  # Validate against schema
  validate_exit=0
  python3 "$VALIDATOR" --pathways "$PATHWAY_FILE" >/dev/null 2>&1 || validate_exit=$?
  if [[ "$validate_exit" -eq 0 ]]; then
    pass "pathways.json passes --pathways schema validation"
  else
    fail "pathways.json schema validation" "validate_schemas.py --pathways returned exit $validate_exit"
  fi

  # Check that entrypoints_mapped is NOT true by default (no source analysis done)
  mapped=$(python3 -c "import json; d=json.load(open('$PATHWAY_FILE')); print(d['completion']['entrypoints_mapped'])" 2>/dev/null || echo "ERROR")
  if [[ "$mapped" == "False" ]]; then
    pass "completion.entrypoints_mapped is false (truthful default)"
  else
    fail "entrypoints_mapped truthfulness" "Expected False, got '$mapped'"
  fi

  # Check complete is false when not fully scouted
  complete=$(python3 -c "import json; d=json.load(open('$PATHWAY_FILE')); print(d['completion']['complete'])" 2>/dev/null || echo "ERROR")
  if [[ "$complete" == "False" ]]; then
    pass "completion.complete is false (truthful default)"
  else
    fail "completion.complete truthfulness" "Expected False, got '$complete'"
  fi

  # Verify status is BLOCKED or PARTIAL (not PATHWAYS_SCOUTED without real evidence)
  status=$(python3 -c "import json; d=json.load(open('$PATHWAY_FILE')); print(d['status'])" 2>/dev/null || echo "ERROR")
  if [[ "$status" == "BLOCKED" || "$status" == "PARTIAL" || "$status" == "DRY_RUN" ]]; then
    pass "status is honest: $status"
  elif [[ "$status" == "PATHWAYS_SCOUTED" ]]; then
    # Verify this is backed by actual evidence
    entrypoints_total=$(python3 -c "import json; d=json.load(open('$PATHWAY_FILE')); print(d['analysis']['coverage']['entrypoints_total'])" 2>/dev/null || echo "0")
    if [[ "$entrypoints_total" -gt 0 ]]; then
      pass "status PATHWAYS_SCOUTED backed by $entrypoints_total entrypoints"
    else
      fail "status honesty" "PATHWAYS_SCOUTED claimed with zero entrypoints — stub behavior detected"
    fi
  else
    fail "status value" "Unexpected status: '$status'"
  fi

else
  # No artifact written — only acceptable if blocked (exit 3)
  if [[ "$exit_code" -eq 3 ]]; then
    pass "No artifact written on BLOCKED exit (exit=3 is valid)"
  else
    fail "artifact creation" "pathways.json not created and exit code was $exit_code (not 3)"
  fi
fi

# --- CRITERION 12: Source artifacts preserved ---
echo ""
echo "--- [12] Source Scan Artifacts Preserved ---"
if [[ -d "$TEST_BOUNTY" ]]; then
  pass "Test bounty directory exists after run"
else
  fail "Bounty dir preserved" "Test bounty directory was unexpectedly removed"
fi

# --- CRITERION 13: Symlink at bounty dir rejected ---
echo ""
echo "--- [13] Symlink Rejection ---"
# Create a symlink target pointing somewhere safe
SYMLINK_TARGET="$(mktemp -d)"
ln -s "$SYMLINK_TARGET" "$TEST_BOUNTY_SYM"
exit_code=0
"$WORKFLOW" --confirm --slug "$SYMLINK_SLUG" 2>/dev/null || exit_code=$?
rm -rf "$SYMLINK_TARGET"
if [[ "$exit_code" -eq 1 ]]; then
  pass "Symlink at bounty dir rejected → exit 1"
else
  fail "Symlink rejection" "Expected exit 1, got $exit_code"
fi

# --- CRITERION 14: Existing artifact refuses overwrite ---
echo ""
echo "--- [14] Refuse Overwrite of Existing Artifact ---"
EXISTING_SLUG="test-pack-a-exist-$$"
EXISTING_BOUNTY="$REPO_ROOT/bounties/$EXISTING_SLUG"
mkdir -p "$EXISTING_BOUNTY/scans"
echo '{"placeholder": true}' > "$EXISTING_BOUNTY/scans/pathways.json"
exit_code=0
"$WORKFLOW" --confirm --slug "$EXISTING_SLUG" 2>/dev/null || exit_code=$?
rm -rf "$EXISTING_BOUNTY"
if [[ "$exit_code" -eq 1 ]]; then
  pass "Existing pathways.json → refuse overwrite, exit 1"
else
  fail "Overwrite refusal" "Expected exit 1, got $exit_code"
fi

# --- CRITERION 15: --help exits 0 ---
echo ""
echo "--- [15] --help Flag ---"
exit_code=0
out=$("$WORKFLOW" --help 2>&1) || exit_code=$?
if [[ "$exit_code" -eq 0 ]]; then
  pass "--help exits 0"
else
  fail "--help" "Expected exit 0, got $exit_code"
fi
if echo "$out" | grep -qi "usage\|--slug\|--confirm"; then
  pass "--help output contains usage information"
else
  fail "--help output" "Usage/options not found in help output"
fi

# --- Final summary ---
echo ""
echo "============================================================"
echo "  Results: $PASS PASSED / $FAIL FAILED / $TOTAL TOTAL"
echo "============================================================"

if [[ "$FAIL" -gt 0 ]]; then
  exit 1
fi
exit 0
