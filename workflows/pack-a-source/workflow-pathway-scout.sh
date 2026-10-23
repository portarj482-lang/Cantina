#!/usr/bin/env bash
# ==============================================================================
# Pack A — Pathway Scout Workflow (Compatibility Wrapper)
# Delegates to canonical implementation at workflows/pack-a-pathway-scout/workflow-pathway-scout.sh
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd -- "${BASH_SOURCE[0]%/*}" >/dev/null 2>&1 && pwd -P)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd -P)"

exec "$REPO_ROOT/workflows/pack-a-pathway-scout/workflow-pathway-scout.sh" "$@"
