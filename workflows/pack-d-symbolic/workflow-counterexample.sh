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

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="${REPO_ROOT:-$(cd -- "$SCRIPT_DIR/../.." && pwd -P)}"
OUT_FILE="$REPO_ROOT/bounties/$SLUG/scans/counterexamples.json"

echo "=== [Pack D] Workflow: Counterexample Tracer ($SLUG) ==="

if [[ "$DRY_RUN" == true || "$CONFIRM" == false ]]; then
  echo "[DRY-RUN] Tracer configured. Target output: $OUT_FILE"
  exit 0
fi

cat <<EOF > "$OUT_FILE"
{
  "slug": "$SLUG",
  "counterexamples": [],
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "status": "NO_COUNTEREXAMPLES_PENDING"
}
EOF

echo "[OK] Counterexample record saved to $OUT_FILE"
