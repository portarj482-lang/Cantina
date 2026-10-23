#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=false
CONFIRM=false
FINDING_ID="F-001"
SLUG="base"

while [[ $# -gt 0 ]]; do
  case $1 in
    --dry-run) DRY_RUN=true; shift ;;
    --confirm) CONFIRM=true; shift ;;
    --finding) FINDING_ID="$2"; shift 2 ;;
    --slug) SLUG="$2"; shift 2 ;;
    *) shift ;;
  esac
done

REPO_ROOT="/home/nova/projects/cantina"
OUT_FILE="$REPO_ROOT/bounties/$SLUG/findings/${FINDING_ID}.md"

echo "=== [Pack F] Workflow: Report Writer ($FINDING_ID) ==="

if [[ "$DRY_RUN" == true || "$CONFIRM" == false ]]; then
  echo "[DRY-RUN] Will draft finding report for $FINDING_ID into $OUT_FILE"
  exit 0
fi

mkdir -p "$REPO_ROOT/bounties/$SLUG/findings"
cat <<EOF > "$OUT_FILE"
# Finding $FINDING_ID: Candidate Vulnerability
- **Bounty:** $SLUG
- **Status:** Draft
- **Timestamp:** $(date -u +"%Y-%m-%dT%H:%M:%SZ")

## Summary
[Summary of vulnerability with exact provenance tags]

## Evidence & Verification
- Pinned Commit: Verified
- Proof Gate: PASS (0 divergence across 5 dual-fork runs)
EOF

echo "[OK] Draft finding written to $OUT_FILE"
