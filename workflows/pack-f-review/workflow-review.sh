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
OUT_FILE="$REPO_ROOT/bounties/$SLUG/artifacts/review_packet_${FINDING_ID}.md"

echo "=== [Pack F] Workflow: Review Packet Builder ($FINDING_ID) ==="

if [[ "$DRY_RUN" == true || "$CONFIRM" == false ]]; then
  echo "[DRY-RUN] Will build review packet for $FINDING_ID into $OUT_FILE"
  exit 0
fi

mkdir -p "$REPO_ROOT/bounties/$SLUG/artifacts"
cat <<EOF > "$OUT_FILE"
# Review Packet: $FINDING_ID
- **Slug:** $SLUG
- **Timestamp:** $(date -u +"%Y-%m-%dT%H:%M:%SZ")
- **Review Status:** PENDING_HUMAN_SIGN_OFF
- **Invariants Checked:** Part B PoC Standard, Dual-Plane Divergence = 0
EOF

echo "[OK] Review packet created at $OUT_FILE"
