# Cantina Maintenance & Remediation Framework

This directory contains canonical audit reports, governance policies, and runbooks established by the Repository Steward.

## Directory Structure
```
maintenance/
├── README.md                 # This guide & execution sequence
├── nested-repos-policy.md    # Submodule vs Absorb rules and thresholds
├── runbook-remediation.md    # Operational runbook and rollback steps
├── backups/                  # Timestamped isolated .git and artifact backups
└── reports/
    ├── action_plan.csv       # Prioritized 38-item plan with owners and commands
    ├── nested_repo_decisions.csv # Full classification of all 31 nested repos
    └── top200_untracked.csv  # Byte-accurate top-200 untracked entries
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

### Step 3: Run High-Priority Submodule Conversions (Dry-Run -> Confirm)
```bash
# 1. Preview
./scripts/convert-to-submodule.sh --dry-run bounties/base/spend-permissions
./scripts/convert-to-submodule.sh --dry-run onchainsummer.xyz

# 2. Confirm & Commit
./scripts/convert-to-submodule.sh --confirm bounties/base/spend-permissions
./scripts/convert-to-submodule.sh --confirm onchainsummer.xyz
```

### Step 4: Run First-Party Package Absorptions
```bash
# 1. Preview
./scripts/absorb-nested.sh --dry-run base-account-privy

# 2. Confirm & Commit
./scripts/absorb-nested.sh --confirm base-account-privy
```

### Step 5: Verify Full Test Suite & Manifest
```bash
make test
```
*Expected output: `Ran 193 tests in ~18.7s — OK`.*
