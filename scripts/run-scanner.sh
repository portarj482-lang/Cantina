#!/usr/bin/env bash
# scripts/run-scanner.sh
# Automated scanner runner supporting --dry-run and --confirm per Section 7.2 of INSTRUCTIONS.md.

set -euo pipefail

TOOL=""
TARGET="."
OUT_FILE=""
CONFIRM=false
DRY_RUN=false
EXTRA_ARGS=""

usage() {
    echo "Usage: $0 --tool <tool_name> [--target <path>] [--out <output_path>] [--dry-run] [--confirm] [--extra-args '<args>']" >&2
    echo "Tools supported: forge, slither, aderyn, semgrep, solhint, halmos, echidna, medusa, anchor" >&2
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --tool)
            TOOL="$2"
            shift 2
            ;;
        --target)
            TARGET="$2"
            shift 2
            ;;
        --out)
            OUT_FILE="$2"
            shift 2
            ;;
        --confirm)
            CONFIRM=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --extra-args)
            EXTRA_ARGS="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage
            ;;
    esac
done

if [ -z "$TOOL" ]; then
    echo "Error: --tool is required." >&2
    usage
fi

# Expand PATH to include user-installed toolchains
export PATH="$HOME/.foundry/bin:$HOME/.cargo/bin:$HOME/.local/bin:$PATH"

# Default to dry-run unless --confirm is explicitly passed
if [ "$CONFIRM" = false ]; then
    DRY_RUN=true
fi

# Construct candidate scanner commands
CMD=""
case "$TOOL" in
    forge)
        CMD="forge test --root $TARGET $EXTRA_ARGS"
        ;;
    slither)
        CMD="slither $TARGET $EXTRA_ARGS"
        ;;
    aderyn)
        CMD="aderyn $TARGET $EXTRA_ARGS"
        ;;
    semgrep)
        CMD="semgrep scan --config auto $TARGET $EXTRA_ARGS"
        ;;
    solhint)
        CMD="solhint '$TARGET/**/*.sol' $EXTRA_ARGS"
        ;;
    halmos)
        CMD="halmos --root $TARGET $EXTRA_ARGS"
        ;;
    echidna)
        CMD="echidna $TARGET $EXTRA_ARGS"
        ;;
    medusa)
        CMD="medusa fuzz $EXTRA_ARGS"
        ;;
    anchor)
        CMD="anchor test --working-directory $TARGET $EXTRA_ARGS"
        ;;
    *)
        CMD="$TOOL $TARGET $EXTRA_ARGS"
        ;;
esac

CMD_BIN=$(echo "$CMD" | awk '{print $1}')
TOOL_PATH=$(which "$CMD_BIN" 2>/dev/null || true)

TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
DATE_DAY=$(date -u +"%Y-%m-%d")

if [ -z "$OUT_FILE" ]; then
    OUT_FILE="scans/${DATE_DAY}-${TOOL}.log"
fi

if [ "$DRY_RUN" = true ]; then
    echo "================================================================================"
    echo " [DRY-RUN] Scanner Dispatch Plan"
    echo "================================================================================"
    echo " Tool:         $TOOL"
    echo " Binary Path:  ${TOOL_PATH:-NOT FOUND (Tool is MISSING)}"
    echo " Target:       $TARGET"
    echo " Command:      $CMD"
    echo " Output File:  $OUT_FILE"
    echo " Mode:         DRY-RUN (Pass --confirm to execute)"
    echo "================================================================================"
    exit 0
fi

# --confirm execution mode
if [ -z "$TOOL_PATH" ]; then
    echo "ERROR: Tool '$TOOL' ($CMD_BIN) is NOT installed or not found on PATH." >&2
    echo "Install instructions are documented in global/tooling.md." >&2
    exit 1
fi

mkdir -p "$(dirname "$OUT_FILE")"

echo "================================================================================"
echo " Executing Scanner: $TOOL"
echo " Timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo " Target:    $TARGET"
echo " Command:   $CMD"
echo " Output:    $OUT_FILE"
echo "================================================================================"

{
    echo "# Scanner Execution Log"
    echo "# Tool: $TOOL"
    echo "# Command: $CMD"
    echo "# Timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    echo "# Target: $TARGET"
    echo "--------------------------------------------------------------------------------"
} > "$OUT_FILE"

# Execute command and capture exit code
set +e
eval "$CMD" 2>&1 | tee -a "$OUT_FILE"
EXIT_CODE="${PIPESTATUS[0]}"
set -e

echo "--------------------------------------------------------------------------------" >> "$OUT_FILE"
echo "# Process completed with exit code: $EXIT_CODE" >> "$OUT_FILE"

echo "Scan finished with exit code $EXIT_CODE. Results saved to $OUT_FILE."
exit "$EXIT_CODE"
