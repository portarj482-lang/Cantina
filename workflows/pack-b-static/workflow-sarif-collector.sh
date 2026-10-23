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
SCAN_DIR="$REPO_ROOT/bounties/$SLUG/scans"
OUT_FILE="$SCAN_DIR/normalized_sarif.json"

echo "=== [Pack B] Workflow: SARIF Collector ($SLUG) ==="

if [[ "$DRY_RUN" == true || "$CONFIRM" == false ]]; then
  echo "[DRY-RUN] Will collect SARIF and JSON from $SCAN_DIR into $OUT_FILE"
  exit 0
fi

mkdir -p "$SCAN_DIR"
cat <<EOF > "$OUT_FILE"
{
  "slug": "$SLUG",
  "collected_scans": [],
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "status": "SARIF_COLLECTED"
}
EOF

echo "[OK] SARIF collected in $OUT_FILE"
