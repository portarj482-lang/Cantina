#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=false
CONFIRM=false
TARGET="bounties/base"
OUTPUT_DIR="bounties/base/scans/halmos"

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
ADAPTER="$REPO_ROOT/.agents/skills/qrpe/adapters/halmos_adapter.py"

echo "=== [Pack D] Workflow: Halmos Symbolic Proof ==="

ARGS=("--target" "$REPO_ROOT/$TARGET" "--output-dir" "$REPO_ROOT/$OUTPUT_DIR")
if [[ "$DRY_RUN" == true || "$CONFIRM" == false ]]; then
  ARGS+=("--dry-run")
else
  ARGS+=("--confirm")
fi

python3 "$ADAPTER" "${ARGS[@]}"
