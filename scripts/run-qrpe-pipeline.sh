#!/usr/bin/env bash
# ==============================================================================
# Quantum Recursive Pipeline Engineer (QRPE) — Unified Pipeline Runner
# Version: 1.0.0
# Canonical Path: /home/nova/projects/cantina/scripts/run-qrpe-pipeline.sh
# ==============================================================================
set -euo pipefail

export PATH="/home/nova/.local/bin:/home/nova/.cargo/bin:/home/nova/.foundry/bin:$PATH"

REPO_ROOT="/home/nova/projects/cantina"
REPORT_DIR="$REPO_ROOT/maintenance/reports"
LOG_FILE="$REPORT_DIR/qrpe-pipeline-run.log"

PACK="all"
DRY_RUN=false
CONFIRM=false

usage() {
  cat <<EOF
Usage: $0 [OPTIONS]

Options:
  --pack <name>    Select workflow pack to execute:
                   pack-a-source, pack-b-static, pack-c-dynamic,
                   pack-d-symbolic, pack-e-triage, pack-f-review,
                   pack-g-solana, all (default)
  --dry-run        Simulate workflow executions without mutating state
  --confirm        Authorize verified mutations and receipt generation
  -h, --help       Show this help message
EOF
  exit 1
}

while [[ $# -gt 0 ]]; do
  case $1 in
    --pack) PACK="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    --confirm) CONFIRM=true; shift ;;
    -h|--help) usage ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
done

mkdir -p "$REPORT_DIR"

MODE_STR="CONFIRM (MUTATING)"
FLAG="--confirm"
if [[ "$DRY_RUN" == true || "$CONFIRM" == false ]]; then
  MODE_STR="DRY-RUN (SIMULATION)"
  FLAG="--dry-run"
fi

echo "==========================================================" | tee -a "$LOG_FILE"
echo "QRPE Unified Pipeline Runner v1.0.0" | tee -a "$LOG_FILE"
echo "Timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")" | tee -a "$LOG_FILE"
echo "Target Pack: $PACK" | tee -a "$LOG_FILE"
echo "Mode: $MODE_STR" | tee -a "$LOG_FILE"
echo "==========================================================" | tee -a "$LOG_FILE"

run_pack_a() {
  echo -e "\n--- Executing Pack A: Source Layer ---" | tee -a "$LOG_FILE"
  "$REPO_ROOT/workflows/pack-a-source/workflow-source-pin.sh" "$FLAG" | tee -a "$LOG_FILE"
  "$REPO_ROOT/workflows/pack-a-recon/workflow-recon.sh" "$FLAG" | tee -a "$LOG_FILE"
  "$REPO_ROOT/workflows/pack-a-source/workflow-pathway-scout.sh" "$FLAG" | tee -a "$LOG_FILE"
}

run_pack_b() {
  echo -e "\n--- Executing Pack B: Static Analysis Layer ---" | tee -a "$LOG_FILE"
  "$REPO_ROOT/workflows/pack-b-static/workflow-slither.sh" "$FLAG" | tee -a "$LOG_FILE"
  "$REPO_ROOT/workflows/pack-b-static/workflow-aderyn.sh" "$FLAG" | tee -a "$LOG_FILE"
  "$REPO_ROOT/workflows/pack-b-static/workflow-semgrep.sh" "$FLAG" | tee -a "$LOG_FILE"
  "$REPO_ROOT/workflows/pack-b-static/workflow-sarif-collector.sh" "$FLAG" | tee -a "$LOG_FILE"
}

run_pack_c() {
  echo -e "\n--- Executing Pack C: Dynamic Testing Layer ---" | tee -a "$LOG_FILE"
  "$REPO_ROOT/workflows/pack-c-dynamic/workflow-foundry-tests.sh" "$FLAG" | tee -a "$LOG_FILE"
  "$REPO_ROOT/workflows/pack-c-dynamic/workflow-fuzz.sh" "$FLAG" | tee -a "$LOG_FILE"
  "$REPO_ROOT/workflows/pack-c-dynamic/workflow-echidna.sh" "$FLAG" | tee -a "$LOG_FILE"
  "$REPO_ROOT/workflows/pack-c-dynamic/workflow-medusa.sh" "$FLAG" | tee -a "$LOG_FILE"
}

run_pack_d() {
  echo -e "\n--- Executing Pack D: Symbolic Proof Layer ---" | tee -a "$LOG_FILE"
  "$REPO_ROOT/workflows/pack-d-symbolic/workflow-halmos.sh" "$FLAG" | tee -a "$LOG_FILE"
  "$REPO_ROOT/workflows/pack-d-symbolic/workflow-mythril.sh" "$FLAG" | tee -a "$LOG_FILE"
  "$REPO_ROOT/workflows/pack-d-symbolic/workflow-counterexample.sh" "$FLAG" | tee -a "$LOG_FILE"
}

run_pack_e() {
  echo -e "\n--- Executing Pack E: Evidence & Triage Layer ---" | tee -a "$LOG_FILE"
  "$REPO_ROOT/workflows/pack-e-triage/workflow-normalize.sh" "$FLAG" | tee -a "$LOG_FILE"
  "$REPO_ROOT/workflows/pack-e-triage/workflow-overlap.sh" "$FLAG" | tee -a "$LOG_FILE"
  "$REPO_ROOT/workflows/pack-e-triage/workflow-triage.sh" "$FLAG" | tee -a "$LOG_FILE"
  "$REPO_ROOT/workflows/pack-e-triage/workflow-hallucination-dropper.sh" --slug base "$FLAG" | tee -a "$LOG_FILE"
}

run_pack_f() {
  echo -e "\n--- Executing Pack F: Review & Reporting Layer ---" | tee -a "$LOG_FILE"
  "$REPO_ROOT/workflows/pack-f-review/workflow-proof-gate.sh" "$FLAG" | tee -a "$LOG_FILE"
  "$REPO_ROOT/workflows/pack-f-review/workflow-review.sh" "$FLAG" | tee -a "$LOG_FILE"
  "$REPO_ROOT/workflows/pack-f-review/workflow-report.sh" "$FLAG" | tee -a "$LOG_FILE"
}

run_pack_g() {
  echo -e "\n--- Executing Pack G: Solana Layer ---" | tee -a "$LOG_FILE"
  "$REPO_ROOT/workflows/pack-g-solana/workflow-anchor-idl.sh" "$FLAG" | tee -a "$LOG_FILE"
  "$REPO_ROOT/workflows/pack-g-solana/workflow-solana-validator.sh" "$FLAG" | tee -a "$LOG_FILE"
  "$REPO_ROOT/workflows/pack-g-solana/workflow-solana-poc.sh" "$FLAG" | tee -a "$LOG_FILE"
}

case $PACK in
  pack-a-source) run_pack_a ;;
  pack-b-static) run_pack_b ;;
  pack-c-dynamic) run_pack_c ;;
  pack-d-symbolic) run_pack_d ;;
  pack-e-triage) run_pack_e ;;
  pack-f-review) run_pack_f ;;
  pack-g-solana) run_pack_g ;;
  all)
    run_pack_a
    run_pack_b
    run_pack_c
    run_pack_d
    run_pack_e
    run_pack_f
    run_pack_g
    ;;
  *)
    echo "[FAIL] Unknown pack: $PACK"
    exit 1
    ;;
esac

echo -e "\n[SUCCESS] QRPE Pipeline execution finished cleanly." | tee -a "$LOG_FILE"
