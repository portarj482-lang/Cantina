#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=false
CONFIRM=false
TARGET="bounties/base"
OUTPUT_DIR="bounties/base/scans/foundry"

while [[ $# -gt 0 ]]; do
  case $1 in
    --dry-run) DRY_RUN=true; shift ;;
    --confirm) CONFIRM=true; shift ;;
    --target) TARGET="$2"; shift 2 ;;
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    *) shift ;;
  esac
done

REPO_ROOT="/home/nova/projects/cantina"
ADAPTER="$REPO_ROOT/.agents/skills/qrpe/adapters/foundry_adapter.py"

echo "=== [Pack C] Workflow: Foundry Unit Tests ==="

ARGS=("--target" "$REPO_ROOT/$TARGET" "--output-dir" "$REPO_ROOT/$OUTPUT_DIR")
if [[ "$DRY_RUN" == true || "$CONFIRM" == false ]]; then
  ARGS+=("--dry-run")
else
  ARGS+=("--confirm")
fi

python3 "$ADAPTER" "${ARGS[@]}"
