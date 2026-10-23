#!/usr/bin/env bash
# scripts/absorb-nested.sh
# Safely absorb a small first-party nested repository into the outer monorepo.
# Backs up .git metadata and stages content for commit.
# Supports --dry-run (default) and --confirm.

set -euo pipefail

DRY_RUN=1
TARGET_PATH=""

for arg in "$@"; do
    case "$arg" in
        --confirm)
            DRY_RUN=0
            ;;
        --dry-run)
            DRY_RUN=1
            ;;
        --help|-h)
            echo "Usage: $0 [--dry-run | --confirm] <path/to/nested/repo>"
            echo "  --dry-run   (Default) Show actions without modifying Git state."
            echo "  --confirm   Execute backup, git metadata removal, and commit."
            exit 0
            ;;
        *)
            if [ -z "$TARGET_PATH" ]; then
                TARGET_PATH="$arg"
            else
                echo "Unexpected extra argument: $arg"
                exit 1
            fi
            ;;
    esac
done

if [ -z "$TARGET_PATH" ]; then
    echo "Error: Target path required. Run with --help for usage."
    exit 1
fi

if [ ! -d "$TARGET_PATH/.git" ] && [ ! -f "$TARGET_PATH/.git" ]; then
    echo "Error: '$TARGET_PATH' is not a nested Git repository (no .git found)."
    exit 1
fi

NAME=$(basename "$TARGET_PATH")
TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
BACKUP_DIR="maintenance/backups/$TIMESTAMP"

echo "=== Monorepo Absorb Plan ==="
echo "Target:      $TARGET_PATH"
echo "Package:     $NAME"
echo "Backup Dest: $BACKUP_DIR/${NAME}.git"

if [ "$DRY_RUN" -eq 1 ]; then
    echo ""
    echo "[MODE] DRY RUN ONLY. No changes made."
    echo "Commands that will run with --confirm:"
    echo "  mkdir -p \"$BACKUP_DIR\""
    echo "  mv \"$TARGET_PATH/.git\" \"$BACKUP_DIR/${NAME}.git\""
    echo "  git add \"$TARGET_PATH\""
    echo "  git commit -m \"chore(monorepo): absorb $TARGET_PATH and archive nested .git metadata\""
    exit 0
fi

echo ""
echo "[MODE] Executing monorepo absorption..."
mkdir -p "$BACKUP_DIR"
mv "$TARGET_PATH/.git" "$BACKUP_DIR/${NAME}.git"

git add "$TARGET_PATH"
git commit -m "chore(monorepo): absorb $TARGET_PATH and archive nested .git metadata"

echo "Successfully absorbed $TARGET_PATH into outer repository."
