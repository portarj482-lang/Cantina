#!/usr/bin/env bash
# Usage: run_pipeline.sh <slug> <stage>
# Stages: verify | build | scan | fuzz | poc | gate
#
# Run from the isolated build copy at build/<pinned_commit>/, never from the checkout.
# Requires bash 4 or later.
# BOUNTY_ROOT and GLOBAL_DIR may be set to override paths inferred from this script.
# Stage-specific: FUZZ_SEED (fuzz); FINDING, PINNED_BLOCK, RPC_URL_A, RPC_URL_B (poc);
#                 SEMGREP_RULES (scan).
set -euo pipefail

readonly SLUG="${1:?usage: run_pipeline.sh <slug> <stage>}"
readonly STAGE="${2:?stage required: verify|build|scan|fuzz|poc|gate}"

case "$STAGE" in
    verify|build|scan|fuzz|poc|gate) ;;
    *) echo "unknown stage: ${STAGE}" >&2; exit 64 ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_GLOBAL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEFAULT_BOUNTY_ROOT="$(cd "${DEFAULT_GLOBAL_DIR}/../bounties/${SLUG}" 2>/dev/null && pwd || true)"

readonly GLOBAL_DIR="${GLOBAL_DIR:-$DEFAULT_GLOBAL_DIR}"
readonly ROOT="${BOUNTY_ROOT:-$DEFAULT_BOUNTY_ROOT}"
if [[ -z "${ROOT}" || ! -d "${ROOT}" ]]; then
    echo "ERROR: BOUNTY_ROOT is not set or not a valid directory: ${ROOT}" >&2
    exit 1
fi
readonly DAY="$(TZ=America/Los_Angeles date +%F)"
readonly RUN_DIR="${ROOT}/scans/${DAY}_${STAGE}"

mkdir -p "${ROOT}/logs"

# Ledger writers. Each line is one JSON object. Details must not contain double quotes or backslashes.
log_line() {
    # $1 = ledger file under logs/, $2 = event type, $3 = detail text
    printf '{"ts":"%s","bounty":"%s","stage":"%s","type":"%s","detail":"%s"}\n' \
        "$(TZ=America/Los_Angeles date -Is)" "$SLUG" "$STAGE" "$2" "$3" \
        >> "${ROOT}/logs/$1"
}
ledger()      { log_line "session_ledger_${DAY}.jsonl" "$1" "${2:-}"; }
ledger_scan() { log_line "scan_ledger_${DAY}.jsonl" "$1" "${2:-}"; }
ledger_poc()  { log_line "poc_ledger_${DAY}.jsonl" "$1" "${2:-}"; }
ledger_gate() { log_line "gate_ledger.jsonl" "$1" "${2:-}"; }

python_cmd() {
    if command -v python3 >/dev/null 2>&1; then
        python3 -I "$@"
    elif command -v py >/dev/null 2>&1; then
        py -3 -I "$@"
    elif command -v python >/dev/null 2>&1; then
        python -I "$@"
    else
        echo "No python found on PATH" >&2
        return 1
    fi
}

require_tool() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "MISSING: $1. Run the tool check first." >&2
        ledger "MISSING_TOOL_$1"
        exit 2
    fi
}

verify_scope() {
    local snap="${ROOT}/snapshots/scope.sha256"
    local scope="${ROOT}/scope.md"
    if [[ ! -s "$snap" ]]; then
        echo "NO SCOPE SNAPSHOT at ${snap}. Refusing to run stage '${STAGE}'." >&2
        ledger "SCOPE_SNAPSHOT_MISSING"
        exit 3
    fi
    if ! grep -q '<!-- SCOPE START -->' "$scope" || ! grep -q '<!-- SCOPE END -->' "$scope"; then
        echo "scope.md has no SCOPE START or SCOPE END marker. Refusing to run stage '${STAGE}'." >&2
        ledger "SCOPE_MARKERS_MISSING"
        exit 3
    fi
    local expected actual actual_strip
    expected="$(cat "$snap" | tr -d '\r\n ')"
    actual="$(sed -n '/<!-- SCOPE START -->/,/<!-- SCOPE END -->/p' "$scope" | tr -d '\r' | sha256sum | cut -d' ' -f1)"
    actual_strip="$(sed -n '/<!-- SCOPE START -->/,/<!-- SCOPE END -->/p' "$scope" | tr -d '\r' | head -c -1 | sha256sum | cut -d' ' -f1)"
    if [[ "$expected" != "$actual" && "$expected" != "$actual_strip" ]]; then
        echo "SCOPE CHANGED: refusing to run stage '${STAGE}'." >&2
        ledger "SCOPE_CHANGED"
        exit 3
    fi
    ledger "SCOPE_OK"
}

record_versions() {
    mkdir -p "${RUN_DIR}"
    {
        command -v forge >/dev/null && forge --version || true
        command -v slither >/dev/null && slither --version || true
        command -v aderyn >/dev/null && aderyn --version || true
        command -v semgrep >/dev/null && semgrep --version || true
    } > "${RUN_DIR}/version.txt" 2>&1
}

run_build() {
    require_tool forge
    mkdir -p "${RUN_DIR}"
    record_versions
    local rc
    set +e
    forge build --sizes > "${RUN_DIR}/build.log" 2>&1
    rc=$?
    set -e
    if (( rc != 0 )); then
        ledger "BUILD_FAILED" "exit=${rc}; see build.log"
        exit 4
    fi
    ledger "BUILD_OK"
}

# Runs one scanner and fails closed when its output file is missing or empty.
# Scanners may exit non-zero when they report findings, so the exit code is logged, not trusted.
run_scanner() {
    # $1 = name, $2 = output file that must exist afterwards, rest = command
    local name="$1" out="$2"
    shift 2
    local rc
    rm -f "$out"
    set +e
    "$@" > "${RUN_DIR}/${name}.log" 2>&1
    rc=$?
    set -e
    if [[ ! -s "$out" ]]; then
        ledger_scan "${name^^}_FAILED" "exit=${rc}; no output; see ${name}.log"
        exit 4
    fi
    ledger_scan "${name^^}_DONE" "exit=${rc}; $(basename "$out")"
}

run_scan() {
    local semgrep_rules="${SEMGREP_RULES:?set SEMGREP_RULES to the ruleset path}"
    require_tool slither
    require_tool aderyn
    require_tool semgrep
    mkdir -p "${RUN_DIR}"
    record_versions
    run_scanner slither "${RUN_DIR}/slither.json" slither . --json "${RUN_DIR}/slither.json"
    run_scanner aderyn "${RUN_DIR}/aderyn.md" aderyn . -o "${RUN_DIR}/aderyn.md"
    run_scanner semgrep "${RUN_DIR}/semgrep.json" semgrep scan --config "$semgrep_rules" --json -o "${RUN_DIR}/semgrep.json"
}

run_fuzz() {
    local seed="${FUZZ_SEED:?set FUZZ_SEED to a recorded integer seed}"
    [[ "$seed" =~ ^[0-9]+$ ]] || { echo "FUZZ_SEED must be an integer" >&2; exit 64; }
    require_tool forge
    mkdir -p "${RUN_DIR}"
    record_versions

    local rc
    set +e
    forge test --match-test "invariant_|testFuzz_" --fuzz-seed "$seed" > "${RUN_DIR}/forge.log" 2>&1
    rc=$?
    set -e

    # Confirm this output line on the first run. Zero matched tests is not a pass.
    if ! grep -qE 'Ran [1-9][0-9]* test' "${RUN_DIR}/forge.log"; then
        ledger_scan "FUZZ_NO_TESTS" "seed=${seed} exit=${rc}; zero tests matched; not a pass"
        echo "Zero fuzz or invariant tests matched. Not a pass." >&2
        exit 7
    fi
    # A non-zero exit means a failing property (counterexample). Triage must read it.
    ledger_scan "FUZZ_EXIT_${rc}" "seed=${seed}"
}

# Prints the PASS and FAIL lines with gas counts removed. Gas differences between planes do not count.
result_lines() {
    grep -E '^\[(PASS|FAIL)' "$1" | sed -E 's/ \(gas: [0-9]+\)//' || true
}

python_cmd() {
    if python3 --version >/dev/null 2>&1; then
        python3 -I "$@"
    elif command -v py >/dev/null 2>&1; then
        py -3 -I "$@"
    else
        python -I "$@"
    fi
}

# Replaces a secret RPC URL in a log file with a placeholder. The URL is passed through the environment.
redact_url() {
    RPC_SECRET="$2" python_cmd -c '
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
secret = os.environ["RPC_SECRET"]
text = path.read_text(encoding="utf-8", errors="replace")
path.write_text(text.replace(secret, "<redacted-rpc-url>"), encoding="utf-8")
' "$1"
}

run_poc() {
    local finding="${FINDING:?set FINDING to F-### (for example F-001)}"
    [[ "$finding" =~ ^F-[0-9]{3}$ ]] || { echo "FINDING must match F-### (for example F-001)" >&2; exit 64; }
    local block="${PINNED_BLOCK:?set PINNED_BLOCK to the pinned block number}"
    [[ "$block" =~ ^[0-9]+$ ]] || { echo "PINNED_BLOCK must be a number, never latest" >&2; exit 64; }
    local url_a="${RPC_URL_A:?set RPC_URL_A to the first provider endpoint}"
    local url_b="${RPC_URL_B:?set RPC_URL_B to the second provider endpoint}"
    require_tool forge
    mkdir -p "${RUN_DIR}"
    record_versions

    local provider url log rc
    local -A rc_of
    for provider in A B; do
        if [[ "$provider" == A ]]; then url="$url_a"; else url="$url_b"; fi
        log="${RUN_DIR}/${finding}_provider-${provider}.log"
        set +e
        forge test --match-path "poc/${finding}_*.t.sol" \
            --fork-url "$url" --fork-block-number "$block" -vvvv > "$log" 2>&1
        rc=$?
        set -e
        rc_of[$provider]=$rc
        redact_url "$log" "$url"
        ledger_poc "PROVIDER_${provider}" "${finding} rc=${rc} block=${block}"
    done

    local ra rb
    ra="$(result_lines "${RUN_DIR}/${finding}_provider-A.log")"
    rb="$(result_lines "${RUN_DIR}/${finding}_provider-B.log")"

    # An empty result set on either plane is a failure, not a match.
    if [[ -z "$ra" || -z "$rb" ]]; then
        ledger_poc "NO_TEST_RESULTS" "${finding}: no PASS or FAIL lines on one or both planes"
        echo "No test results for ${finding}. Check the poc/ path glob and the forge output." >&2
        exit 5
    fi
    if [[ "${rc_of[A]}" != "${rc_of[B]}" || "$ra" != "$rb" ]]; then
        ledger_poc "DIVERGENCE_NONZERO" "${finding}: planes differ"
        echo "Planes disagree for ${finding}. Finding stays Unconfirmed." >&2
        exit 5
    fi
    ledger_poc "DIVERGENCE_0" "${finding}: planes match"

    if grep -q '^\[FAIL' <<< "$ra"; then
        ledger_poc "RESULT_FAIL" "${finding}: fails on both planes; not a pass"
        echo "PoC for ${finding} fails on both planes. Not a pass." >&2
        exit 6
    fi
    ledger_poc "RESULT_PASS" "${finding}: passes on both planes at block ${block}"
}

run_gate() {
    mkdir -p "${RUN_DIR}"
    local out="${RUN_DIR}/gate_audit.json"
    if python_cmd "${GLOBAL_DIR}/tools/provenance_audit.py" "${ROOT}/findings" > "$out"; then
        ledger_gate "PROVENANCE_CLEAN" "audit=${out}"
    else
        ledger_gate "PROVENANCE_FLAGS" "audit=${out}; exit 1 means flags, exit 2 means usage or no files"
        echo "Provenance audit did not pass. See ${out}." >&2
        exit 1
    fi
}

verify_scope

if [[ "$STAGE" != verify ]]; then
    mkdir -p "${RUN_DIR}"
    printf 'run_pipeline.sh %s %s\n' "$SLUG" "$STAGE" > "${RUN_DIR}/command.txt"
fi

case "$STAGE" in
    verify) echo "Scope verified." ;;
    build)  run_build ;;
    scan)   run_scan ;;
    fuzz)   run_fuzz ;;
    poc)    run_poc ;;
    gate)   run_gate ;;
esac
