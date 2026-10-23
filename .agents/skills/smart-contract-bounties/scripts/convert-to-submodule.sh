#!/usr/bin/env bash
# scripts/convert-to-submodule.sh
# Safely convert a nested Git repository into a tracked Git submodule.
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
            echo "  --confirm   Execute backup, submodule registration, and commit."
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
REMOTE_URL=$(git -C "$TARGET_PATH" remote get-url origin 2>/dev/null || echo "")

if [ -z "$REMOTE_URL" ]; then
    echo "Error: No remote 'origin' found for '$TARGET_PATH'. Cannot register as submodule."
    exit 1
fi

TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
BACKUP_DIR="maintenance/backups/$TIMESTAMP"

echo "=== Submodule Conversion Plan ==="
echo "Target:      $TARGET_PATH"
echo "Submodule:   $NAME"
echo "Remote URL:  $REMOTE_URL"
echo "Backup Dest: $BACKUP_DIR/${NAME}.git.bak"

if [ "$DRY_RUN" -eq 1 ]; then
    echo ""
    echo "[MODE] DRY RUN ONLY. No changes made."
    echo "Commands that will run with --confirm:"
    echo "  mkdir -p \"$BACKUP_DIR\""
    echo "  cp -r \"$TARGET_PATH/.git\" \"$BACKUP_DIR/${NAME}.git.bak\""
    echo "  git submodule add --name \"$NAME\" \"$REMOTE_URL\" \"$TARGET_PATH\""
    echo "  git submodule absorbgitdirs \"$TARGET_PATH\""
    echo "  git commit -m \"chore(submodules): register $TARGET_PATH as git submodule\""
    exit 0
fi

echo ""
echo "[MODE] Executing submodule conversion..."
mkdir -p "$BACKUP_DIR"
cp -r "$TARGET_PATH/.git" "$BACKUP_DIR/${NAME}.git.bak"

git submodule add --name "$NAME" "$REMOTE_URL" "$TARGET_PATH"
git submodule absorbgitdirs "$TARGET_PATH"
git add .gitmodules "$TARGET_PATH"
git commit -m "chore(submodules): register $TARGET_PATH as git submodule"

echo "Successfully converted $TARGET_PATH to submodule."
