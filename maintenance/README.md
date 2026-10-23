# Cantina Maintenance & Remediation Framework

This directory contains canonical audit reports, governance policies, runbooks, and automation scripts established for the Cantina monorepo.

---

## Executive Summary for DevOps Lead

> **DevOps Lead Briefing:**  
> The Cantina repository contains 31 nested Git checkouts and over 8.7 GB of untracked assets across multiple sub-ecosystems. All 10 high-risk submodule conversions, 3 package absorptions, and local cleanup scans have been validated with zero exit code across all dry-runs.
>
> **Top 5 Risky Targets & Recommended Immediate Action:**
> 1. `bounties/base/spend-permissions` (1.44 GB, independent remote) -> Convert to Submodule via `./scripts/convert-to-submodule.sh --confirm bounties/base/spend-permissions`
> 2. `onchainsummer.xyz` (808 MB, large web application & git history) -> Convert to Submodule via `./scripts/convert-to-submodule.sh --confirm onchainsummer.xyz`
> 3. `bounties/base/eip-7702-proxy` (488 MB, nested foundry tree) -> Convert to Submodule via `./scripts/convert-to-submodule.sh --confirm bounties/base/eip-7702-proxy`
> 4. `bounties/base/smart-wallet` (472 MB, Coinbase smart wallet upstream) -> Convert to Submodule via `./scripts/convert-to-submodule.sh --confirm bounties/base/smart-wallet`
> 5. `docs` / `bounties/base/docs` (927 MB combined, redundant documentation clones) -> Convert to Submodule via `./scripts/convert-to-submodule.sh --confirm docs`
>
> All operations automatically back up nested `.git` metadata to `maintenance/backups/<timestamp>/` prior to modifying working tree state.

---

## Directory Structure
```
maintenance/
├── README.md                 # This executive summary & execution sequence
├── nested-repos-policy.md    # Submodule vs Absorb rules and thresholds
├── runbook-remediation.md    # Operational runbook and rollback steps
├── backups/                  # Timestamped isolated .git and artifact backups
└── reports/
    ├── action_plan_phase2.csv    # Top-30 item plan with owners, ETAs, and exact commands
    ├── action_plan.csv           # Full 38-item plan with owners and commands
    ├── nested_repo_decisions.csv # Full classification of all 31 nested repos
    ├── top200_untracked.csv      # Byte-accurate top-200 untracked entries
    ├── dryrun-logs/              # Validated dry-run logs for top 10 targets
    └── handoff_package/          # Unified diffs and handoff package manifest
```

---

## Exact Sequence of Commands to Apply and Verify

### Step 1: Verify Hygiene & Status
```bash
make audit
```
*Expected output: `Audit OK: Zero tracked transient runtime artifacts.`*

### Step 2: Dry-Run Cleanup
```bash
./scripts/clean-local.sh --dry-run
```
*Expected output: Lists transient `__pycache__` and `.log` files without removal.*

### Step 3: Run High-Priority Submodule Conversions
```bash
# 1. Preview dry-runs
./scripts/convert-to-submodule.sh --dry-run bounties/base/spend-permissions
./scripts/convert-to-submodule.sh --dry-run onchainsummer.xyz

# 2. Confirm & Commit (one at a time)
./scripts/convert-to-submodule.sh --confirm bounties/base/spend-permissions
./scripts/convert-to-submodule.sh --confirm onchainsummer.xyz
```

### Step 4: Run First-Party Package Absorptions
```bash
# 1. Preview dry-run
./scripts/absorb-nested.sh --dry-run base-account-privy

# 2. Confirm & Commit
./scripts/absorb-nested.sh --confirm base-account-privy
```

### Step 5: Verify Full Test Suite & Manifest
```bash
make test
```
*Expected output: `Ran 193 tests in ~20s — OK`.*
