#!/usr/bin/env bash
# scripts/clean-local.sh
# Safely clean temporary runtime caches, untracked build artifacts, and test logs.
# Includes --dry-run (default) and --confirm execution flags.

set -euo pipefail

DRY_RUN=1

for arg in "$@"; do
    case "$arg" in
        --confirm)
            DRY_RUN=0
            ;;
        --dry-run)
            DRY_RUN=1
            ;;
        --help|-h)
            echo "Usage: $0 [--dry-run | --confirm]"
            echo "  --dry-run   (Default) Report files that would be removed without deleting."
            echo "  --confirm   Execute deletion of transient cache and build artifacts."
            exit 0
            ;;
        *)
            echo "Unknown argument: $arg"
            echo "Run with --help for usage."
            exit 1
            ;;
    esac
done

TARGET_DIRS=(
    "__pycache__"
    ".pytest_cache"
    ".mypy_cache"
    ".ruff_cache"
    "*.egg-info"
)

TARGET_FILES=(
    "*.pyc"
    "*.pyo"
    "*.pyd"
    ".coverage"
    "*.log"
    "*.tmp"
    "*.swp"
)

echo "=== Repository Local Cleanup Utility ==="
if [ "$DRY_RUN" -eq 1 ]; then
    echo "[MODE] DRY RUN ONLY. No files will be removed. Pass --confirm to execute."
else
    echo "[MODE] CONFIRM. Transient artifacts will be purged."
fi

for dir_pat in "${TARGET_DIRS[@]}"; do
    while IFS= read -r -d '' d; do
        if [ "$DRY_RUN" -eq 1 ]; then
            echo "[DRY-RUN] Directory would be removed: $d"
        else
            echo "[REMOVING] Directory: $d"
            rm -rf "$d"
        fi
    done < <(find . -type d -name "$dir_pat" -not -path "./.git/*" -not -path "./maintenance/*" -print0 2>/dev/null)
done

for file_pat in "${TARGET_FILES[@]}"; do
    while IFS= read -r -d '' f; do
        if [ "$DRY_RUN" -eq 1 ]; then
            echo "[DRY-RUN] File would be removed: $f"
        else
            echo "[REMOVING] File: $f"
            rm -f "$f"
        fi
    done < <(find . -type f -name "$file_pat" -not -path "./.git/*" -not -path "./maintenance/*" -print0 2>/dev/null)
done

echo "Cleanup scan complete."
