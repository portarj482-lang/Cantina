#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=false
CONFIRM=false
TARGET="bounties/pump-fun"
OUTPUT_DIR="bounties/pump-fun/scans/idl"

while [[ $# -gt 0 ]]; do
  case $1 in
    --dry-run) DRY_RUN=true; shift ;;
    --confirm) CONFIRM=true; shift ;;
    --target) TARGET="$2"; shift 2 ;;
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    *) shift ;;
  esac
done

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="${REPO_ROOT:-$(cd -- "$SCRIPT_DIR/../.." && pwd -P)}"
ADAPTER="$REPO_ROOT/.agents/skills/qrpe/adapters/solana_adapter.py"

echo "=== [Pack G] Workflow: Anchor IDL Mapper ==="

ARGS=("--target" "$REPO_ROOT/$TARGET" "--output-dir" "$REPO_ROOT/$OUTPUT_DIR" "--action" "idl")
if [[ "$DRY_RUN" == true || "$CONFIRM" == false ]]; then
  ARGS+=("--dry-run")
else
  ARGS+=("--confirm")
fi

python3 "$ADAPTER" "${ARGS[@]}"
