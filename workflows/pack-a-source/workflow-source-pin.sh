#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=false
CONFIRM=false
SLUG="base"

while [[ $# -gt 0 ]]; do
  case $1 in
    --dry-run) DRY_RUN=true; shift ;;
    --confirm) CONFIRM=true; shift ;;
    --slug) SLUG="$2"; shift 2 ;;
    *) shift ;;
  esac
done

REPO_ROOT="/home/nova/projects/cantina"
BOUNTY_DIR="$REPO_ROOT/bounties/$SLUG"
SCOPE_FILE="$BOUNTY_DIR/scope.md"
SNAPSHOT_FILE="$BOUNTY_DIR/snapshots/scope.sha256"

echo "=== [Pack A] Workflow: Source Pin ($SLUG) ==="

if [[ ! -f "$SCOPE_FILE" ]]; then
  echo "[FAIL] Scope file missing: $SCOPE_FILE"
  exit 1
fi

if [[ ! -f "$SNAPSHOT_FILE" ]]; then
  echo "[FAIL] Scope snapshot missing: $SNAPSHOT_FILE"
  exit 1
fi

ACTUAL_HASH=$(sha256sum "$SCOPE_FILE" | awk '{print $1}')
EXPECTED_HASH=$(awk '{print $1}' "$SNAPSHOT_FILE")

echo "[VERIFY] Checking scope hash..."
if [[ "$ACTUAL_HASH" != "$EXPECTED_HASH" ]]; then
  echo "[FAIL] Scope hash mismatch! Expected: $EXPECTED_HASH, Actual: $ACTUAL_HASH"
  exit 1
fi
echo "[OK] Scope hash verified: $ACTUAL_HASH"

PIN_JSON="$BOUNTY_DIR/scans/pin.json"
mkdir -p "$BOUNTY_DIR/scans"

if [[ "$DRY_RUN" == true || "$CONFIRM" == false ]]; then
  echo "[DRY-RUN] Source pin verified. Target output: $PIN_JSON"
  exit 0
fi

cat <<EOF > "$PIN_JSON"
{
  "slug": "$SLUG",
  "scope_file": "$SCOPE_FILE",
  "scope_sha256": "$ACTUAL_HASH",
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "status": "PIN_VERIFIED"
}
EOF

echo "[OK] Pin recorded in $PIN_JSON"
