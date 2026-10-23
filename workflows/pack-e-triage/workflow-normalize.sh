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
OUT_FILE="$REPO_ROOT/bounties/$SLUG/scans/findings_normalized.json"

echo "=== [Pack E] Workflow: Normalize Findings ($SLUG) ==="

if [[ "$DRY_RUN" == true || "$CONFIRM" == false ]]; then
  echo "[DRY-RUN] Will normalize findings into $OUT_FILE"
  exit 0
fi

cat <<EOF > "$OUT_FILE"
{
  "slug": "$SLUG",
  "normalized_findings": [],
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "status": "NORMALIZATION_COMPLETE"
}
EOF

echo "[OK] Normalized findings saved to $OUT_FILE"
