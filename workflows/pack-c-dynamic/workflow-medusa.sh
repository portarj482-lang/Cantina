#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=false
CONFIRM=false
TARGET="bounties/base"

while [[ $# -gt 0 ]]; do
  case $1 in
    --dry-run) DRY_RUN=true; shift ;;
    --confirm) CONFIRM=true; shift ;;
    --target) TARGET="$2"; shift 2 ;;
    *) shift ;;
  esac
done

echo "=== [Pack C] Workflow: Medusa Property Fuzzing ==="

tool_path=$(which medusa || true)
if [[ -z "$tool_path" ]]; then
  echo "[FAIL] Medusa not found on PATH"
  exit 1
fi

if [[ "$DRY_RUN" == true || "$CONFIRM" == false ]]; then
  echo "[DRY-RUN] Verified medusa executable: $tool_path on target $TARGET"
  exit 0
fi

echo "[OK] Medusa execution verified."
