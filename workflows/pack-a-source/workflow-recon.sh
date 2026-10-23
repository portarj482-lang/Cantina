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
RECON_OUT="$BOUNTY_DIR/scans/recon.json"

echo "=== [Pack A] Workflow: Reconnaissance ($SLUG) ==="

if [[ "$DRY_RUN" == true || "$CONFIRM" == false ]]; then
  echo "[DRY-RUN] Target output: $RECON_OUT"
  exit 0
fi

mkdir -p "$BOUNTY_DIR/scans"
CONTRACT_COUNT=$(find "$BOUNTY_DIR" -name "*.sol" 2>/dev/null | wc -l || echo 0)

cat <<EOF > "$RECON_OUT"
{
  "slug": "$SLUG",
  "contracts_found": $CONTRACT_COUNT,
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "status": "RECON_COMPLETE"
}
EOF

echo "[OK] Reconnaissance recorded in $RECON_OUT"
