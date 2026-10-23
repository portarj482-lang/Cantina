#!/usr/bin/env bash
# ==============================================================================
# Pack A — Reconnaissance Test Runner Wrapper
# ==============================================================================
set -euo pipefail
SCRIPT_DIR="$(cd -- "${BASH_SOURCE[0]%/*}" >/dev/null 2>&1 && pwd -P)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"
exec "$REPO_ROOT/workflows/pack-a-recon/tests/test_workflow_recon.sh" "$@"
