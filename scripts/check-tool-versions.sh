#!/usr/bin/env bash
# scripts/check-tool-versions.sh
# Deterministic version check for tools referenced in Section 7.1 and global/tooling.md.
# Supports --out <json_file> and --dry-run.

set -euo pipefail

OUT_FILE=""
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --out)
            OUT_FILE="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo "Unknown argument: $1" >&2
            echo "Usage: $0 [--out <file.json>] [--dry-run]" >&2
            exit 1
            ;;
    esac
done

# Expand PATH to include user-installed toolchains if present
export PATH="$HOME/.foundry/bin:$HOME/.cargo/bin:$HOME/.local/bin:$PATH"

TOOLS=(
    "forge:Foundry build & test:forge --version:scanner"
    "cast:Foundry chain interactions:cast --version:chain"
    "anvil:Foundry local fork node:anvil --version:chain"
    "chisel:Foundry Solidity REPL:chisel --version:chain"
    "cargo:Rust package manager:cargo --version:runtime"
    "rustc:Rust compiler:rustc --version:runtime"
    "anchor:Anchor framework CLI:anchor --version:scanner"
    "solana:Solana CLI:solana --version:chain"
    "solana-test-validator:Solana test cluster:solana-test-validator --version:chain"
    "python3:Python runtime:python3 --version:runtime"
    "git:Git revision control:git --version:runtime"
    "node:NodeJS runtime:node --version:runtime"
    "npm:Node package manager:npm --version:runtime"
    "tsx:TypeScript executor:tsx --version:runtime"
    "slither:Static analysis:slither --version:scanner"
    "aderyn:Rust-based Solidity scanner:aderyn --version:scanner"
    "semgrep:Semantic code pattern scanner:semgrep --version:scanner"
    "solc:Solidity compiler:solc --version:runtime"
    "halmos:Symbolic Foundry tester:halmos --version:scanner"
    "myth:Symbolic execution:myth version:scanner"
    "echidna:Property fuzzer:echidna --version:scanner"
    "medusa:Parallel fuzzer:medusa --version:scanner"
    "solhint:Solidity linter:solhint --version:scanner"
    "certoraRun:Certora Prover CLI:certoraRun --version:scanner"
    "kontrol:Kontrol verification:kontrol --version:scanner"
    "heimdall:EVM bytecode decompiler:heimdall --version:scanner"
)

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

if [ "$DRY_RUN" = true ]; then
    echo "[DRY-RUN] Will inspect ${#TOOLS[@]} tools and write JSON report to: ${OUT_FILE:-stdout}"
    exit 0
fi

JSON_ENTRIES=()

echo "================================================================================"
echo " Cantina Monorepo Tooling Census — $TIMESTAMP"
echo "================================================================================"
printf "%-22s %-10s %-25s %-20s\n" "TOOL" "STATUS" "VERSION" "PATH"
echo "--------------------------------------------------------------------------------"

for item in "${TOOLS[@]}"; do
    IFS=":" read -r name desc cmd type <<< "$item"
    cmd_bin=$(echo "$cmd" | awk '{print $1}')
    
    bin_path=$(which "$cmd_bin" 2>/dev/null || true)
    
    if [ -n "$bin_path" ]; then
        ver_output=$($cmd 2>&1 | head -n 1 | tr -d '\r\n' || true)
        # Determine status
        if [ "$type" = "scanner" ]; then
            status="OK"
        else
            status="PRESENT"
        fi
    else
        bin_path="NOT_FOUND"
        ver_output="—"
        status="MISSING"
    fi
    
    printf "%-22s %-10s %-25s %-20s\n" "$name" "$status" "${ver_output:0:24}" "${bin_path:0:20}"
    
    # Escape quotes for json
    escaped_ver=$(echo "$ver_output" | sed 's/"/\\"/g')
    escaped_path=$(echo "$bin_path" | sed 's/"/\\"/g')
    
    JSON_ENTRIES+=("{\"tool\":\"$name\",\"description\":\"$desc\",\"command\":\"$cmd\",\"status\":\"$status\",\"version\":\"$escaped_ver\",\"path\":\"$escaped_path\",\"type\":\"$type\"}")
done

echo "================================================================================"

JSON_OUTPUT="{\"timestamp\":\"$TIMESTAMP\",\"tools_count\":${#TOOLS[@]},\"tools\":[$(IFS=,; echo "${JSON_ENTRIES[*]}") ]}"

if [ -n "$OUT_FILE" ]; then
    mkdir -p "$(dirname "$OUT_FILE")"
    echo "$JSON_OUTPUT" > "$OUT_FILE"
    echo "Saved JSON report to $OUT_FILE"
fi
