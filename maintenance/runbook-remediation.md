# Monorepo Remediation Runbook — Phase Three Execution

**Audience:** DevOps Engineers, Monorepo Maintainers, Release Engineers  
**Target Root:** `/home/nova/projects/cantina`  
**Execution Posture:** Non-destructive by default. Always dry-run before confirm. Zero remote push without human approval.

---

## 1. Safety & Non-Destructive Principles

1. **Mandatory Backups:** Every script creates an isolated backup under `maintenance/backups/<timestamp>/` prior to any modification.
2. **Idempotence:** Scripts support `--dry-run` (default) and `--confirm`.
3. **Audit Trail:** All confirmed executions write signed execution logs to `maintenance/reports/confirm-logs/<target>.confirm.log`.
4. **Zero Remote Push:** All operations stage changes locally on `master` for maintainer review.

---

## 2. Batched Execution Roadmap

Execution is split into 3 distinct batches to minimize risk and allow incremental verification:

### Batch 1: High-Priority Submodules (>450MB) & First-Party Absorption (<5MB)
- **Submodules:**
  - `bounties/base/spend-permissions` (1.44 GB)
  - `onchainsummer.xyz` (808 MB)
  - `bounties/base/eip-7702-proxy` (488 MB)
  - `bounties/base/smart-wallet` (472 MB)
  - `docs` (472 MB)
- **Absorptions:**
  - `base-account-privy` (1.8 MB)
  - `contract-address-checker` (2.1 MB)
  - `transaction-latency` (1.5 MB)

### Batch 2: Secondary Submodules (100MB - 450MB)
- `bounties/base/docs` (455 MB)
- `bounties/agglayer/ulxly-contracts` (440 MB)
- `bounties/Revert v4lend Competition/lib/uniswap-hooks` (353 MB)
- `bounties/liquity/bold` (272 MB)
- `ai-cookbook` (207 MB)
- `bounties/base/contracts` (190 MB)
- `foundry` (132 MB)
- `bounties/base/foundry` (104 MB)
- `base-snapshots-dashboard` (absorb, 2.5 MB)
- `bounties/base/skills` (absorb, 1.2 MB)

### Batch 3: Long-Tail & Evaluation
- Remaining dependencies and compiler cache purges (`./scripts/clean-local.sh --confirm`).

---

## 3. Core Execution Procedures

### A. Submodule Conversion (Targets > 50 MB)
Converts loose, large nested repositories into tracked Git submodules while backing up `.git` metadata:

```bash
# 1. Dry run verification
./scripts/convert-to-submodule.sh --dry-run "bounties/base/spend-permissions"

# 2. Execute conversion and log confirm output
./scripts/convert-to-submodule.sh --confirm "bounties/base/spend-permissions" 2>&1 | tee maintenance/reports/confirm-logs/spend-permissions.confirm.log
```

### B. Monorepo Absorption (First-party targets < 5 MB)
Archives nested `.git` metadata into `maintenance/backups/` and stages source code directly:

```bash
# 1. Dry run verification
./scripts/absorb-nested.sh --dry-run "base-account-privy"

# 2. Execute absorption and log confirm output
./scripts/absorb-nested.sh --confirm "base-account-privy" 2>&1 | tee maintenance/reports/confirm-logs/base-account-privy.confirm.log
```

### C. Workspace Cache Purge
Cleans non-tracked transient Python, test, and log artifacts:

```bash
# 1. Dry run check
./scripts/clean-local.sh --dry-run

# 2. Execute purge
./scripts/clean-local.sh --confirm 2>&1 | tee maintenance/reports/confirm-logs/clean-local.confirm.log
```

---

## 4. Post-Action Verification Protocol

Immediately after running any `--confirm` command, execute the 4-step verification gate:

```bash
# 1. Check working tree cleanliness
git status --porcelain -uall

# 2. Verify hygiene gate (zero tracked runtime artifacts)
make audit

# 3. Verify Python dependencies & unit test pass rate
make test

# 4. Confirm backup existence
ls -la $(ls -td maintenance/backups/*/ | head -n1)
```

---

## 5. Rollback & Recovery Procedures

### Rollback Submodule Conversion
If a submodule addition needs to be rolled back:
```bash
TARGET="<path/to/submodule>"
NAME=$(basename "$TARGET")

git submodule deinit -f "$TARGET"
git rm -f "$TARGET"
rm -rf ".git/modules/$NAME"
git restore --staged .gitmodules

# Restore .git metadata from backup if reverting working copy:
LATEST_BACKUP=$(ls -td maintenance/backups/*/ | head -n1)
cp -r "${LATEST_BACKUP}/${NAME}.git.bak" "${TARGET}/.git"
```

### Rollback Monorepo Absorption
To restore the independent `.git` repository from backup:
```bash
TARGET="<path/to/absorbed/package>"
NAME=$(basename "$TARGET")

git restore --staged "$TARGET"
LATEST_BACKUP=$(ls -td maintenance/backups/*/ | head -n1)
mv "${LATEST_BACKUP}/${NAME}.git" "${TARGET}/.git"
```

---

## 6. Owner & Contact Directory

| Area | Primary Owner | Escalation / Reviewer |
|---|---|---|
| Submodule Lifecycle & CI Workflows | DevOps Lead | Release Manager |
| Monorepo Absorption & Packaging | Monorepo Maintainer | Architecture Analyst |
| Bounty Scopes & Evidence Verification | Security Auditor | Playbook Admin Oracle |
| Local Tooling & Caches | Build Engineer | DevOps Lead |

---

## 7. Operating Manual Tooling & Scope Verification Procedures

### A. Scope Verification & Hashing
To lock and verify the LF-normalized scope snapshot:
```bash
# Verify scope hash matches stored snapshot
./scripts/lock-scope.py --check --scope bounties/<slug>/scope.md --snapshot bounties/<slug>/snapshots/scope.sha256

# Write recomputed scope hash to snapshot
./scripts/lock-scope.py --write --scope bounties/<slug>/scope.md --snapshot bounties/<slug>/snapshots/scope.sha256
```

### B. Tooling Census & Version Verification
To run an automated audit of all 26 tools referenced in Section 7.1:
```bash
# Output JSON report and print verification table
./scripts/check-tool-versions.sh --out maintenance/reports/tool-versions.json
```

### C. Automated Scanner Dispatch
To execute static and dynamic scanners with dry-run protection:
```bash
# Dry run verification (default)
./scripts/run-scanner.sh --tool slither --dry-run --target bounties/<slug>/contracts

# Confirmed execution saving raw output to scans/
./scripts/run-scanner.sh --tool slither --confirm --target bounties/<slug>/contracts --out bounties/<slug>/scans/$(date +%Y-%m-%d)-slither.log
```
