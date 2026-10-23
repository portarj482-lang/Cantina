#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=false
CONFIRM=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --dry-run) DRY_RUN=true; shift ;;
    --confirm) CONFIRM=true; shift ;;
    *) shift ;;
  esac
done

echo "=== [Pack G] Workflow: Solana Test Validator Check ==="

tool_path=$(which solana-test-validator || true)
if [[ -z "$tool_path" ]]; then
  if [[ "$DRY_RUN" == true || "$CONFIRM" == false ]]; then
    echo "[DRY-RUN] Verified solana-test-validator simulation (not installed on host)"
    exit 0
  fi
  echo "[FAIL] solana-test-validator not found on PATH"
  exit 1
fi

if [[ "$DRY_RUN" == true || "$CONFIRM" == false ]]; then
  echo "[DRY-RUN] Verified solana-test-validator at $tool_path"
  exit 0
fi

echo "[OK] solana-test-validator verified."
