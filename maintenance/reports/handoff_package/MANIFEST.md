# Cantina Remediation Handoff Package — Manifest

**Date:** 2026-10-22  
**Target:** `/home/nova/projects/cantina`  
**Author:** Phase Two Remediator & Release Coordinator  
**Execution Posture:** All changes staged locally and verified with dry-runs; zero remote push.

---

## Package Contents

### 1. Unified Diff Patch
- `maintenance/reports/handoff_package/unified_remediation.patch`: Comprehensive Git diff covering `.gitignore`, `pyproject.toml`, `requirements.in`, `requirements.txt`, `.github/workflows/ci.yml`, and `.github/workflows/security-mesh-ci.yml`.

### 2. Canonical Action Plans & Reports
- `maintenance/reports/action_plan_phase2.csv`: Top 30 remediation targets mapped to `path,size_bytes,recommended_action,owner,eta,commands`.
- `maintenance/reports/action_plan.csv`: Full 38-item prioritized execution ledger.
- `maintenance/reports/nested_repo_decisions.csv`: Complete inventory of all 31 nested repositories with remote origins and classifications.
- `maintenance/reports/top200_untracked.csv`: Byte-accurate ranking of top 200 untracked items derived from NUL-stream analysis.

### 3. Executable Automation Tooling (POSIX Shell)
- `scripts/convert-to-submodule.sh`: Idempotent conversion utility with `--dry-run`, `--confirm`, timestamped backup, and `.gitmodules` registration.
- `scripts/absorb-nested.sh`: Idempotent package absorption utility with `--dry-run`, `--confirm`, `.git` backup archival, and git staging.
- `scripts/clean-local.sh`: Workspace cache and transient compiler output purge tool.
- `Makefile`: Build, test, and audit entrypoints (`make audit`, `make test`, `make dev-install`, `make clean`).

### 4. Governance Policies & Runbooks
- `maintenance/README.md`: Maintenance directory overview and executive briefing for DevOps Lead.
- `maintenance/nested-repos-policy.md`: Governance thresholds (>50MB Submodule, <5MB Absorb), submodule lifecycle, and backup protocol.
- `maintenance/runbook-remediation.md`: Operational step-by-step apply and rollback guide with owner directory.
- `CONTRIBUTING.md`: Contributor guide for development setup, hygiene gates, and PR requirements.
- `.pre-commit-config.yaml`: Pre-commit hook definitions blocking secrets, private keys, merge conflicts, and files >50MB.

### 5. Dry-Run Verification Logs
Logs stored under `maintenance/reports/dryrun-logs/`:
- `spend-permissions.dryrun.log`
- `onchainsummer.dryrun.log`
- `eip-7702-proxy.dryrun.log`
- `smart-wallet.dryrun.log`
- `docs.dryrun.log`
- `base-docs.dryrun.log`
- `ulxly-contracts.dryrun.log`
- `uniswap-hooks.dryrun.log`
- `bold.dryrun.log`
- `ai-cookbook.dryrun.log`
- `base-account-privy.dryrun.log`
- `contract-address-checker.dryrun.log`
- `transaction-latency.dryrun.log`
- `base-snapshots-dashboard.dryrun.log`
- `base-skills.dryrun.log`
- `clean-local.dryrun.log`

---

## Maintainer Local Execution Guide

```bash
# 1. Audit repository cleanliness
make audit

# 2. Run unit tests
make test

# 3. Apply submodule conversion to high-priority targets
./scripts/convert-to-submodule.sh --confirm bounties/base/spend-permissions
./scripts/convert-to-submodule.sh --confirm onchainsummer.xyz
./scripts/convert-to-submodule.sh --confirm bounties/base/eip-7702-proxy
./scripts/convert-to-submodule.sh --confirm bounties/base/smart-wallet
./scripts/convert-to-submodule.sh --confirm docs

# 4. Absorb first-party packages
./scripts/absorb-nested.sh --confirm base-account-privy
./scripts/absorb-nested.sh --confirm contract-address-checker
./scripts/absorb-nested.sh --confirm transaction-latency

# 5. Clean transient cache artifacts
./scripts/clean-local.sh --confirm
```
