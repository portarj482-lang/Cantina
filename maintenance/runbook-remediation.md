# Monorepo Remediation Runbook

**Audience:** DevOps Engineers, Monorepo Maintainers, Release Engineers  
**Target Root:** `/home/nova/projects/cantina`  
**Execution Posture:** Non-destructive by default. Always dry-run before confirm.

---

## 1. Safety & Non-Destructive Principles

1. **Mandatory Backups:** Every script creates an isolated backup under `maintenance/backups/<timestamp>/` prior to any modification.
2. **Idempotence:** Scripts support `--dry-run` (default) and `--confirm`.
3. **No Unapproved Force:** Never force-delete unversioned code; use `git rm --cached` or archive `.git` metadata.
4. **Zero Remote Push:** All operations stage changes locally for PR review.

---

## 2. Core Execution Procedures

### A. Submodule Conversion (Targets > 50 MB)
Converts loose, large nested repositories into tracked Git submodules while backing up `.git` metadata:

```bash
# Dry run verification
./scripts/convert-to-submodule.sh --dry-run bounties/base/spend-permissions

# Execute conversion and local commit
./scripts/convert-to-submodule.sh --confirm bounties/base/spend-permissions
```

### B. Monorepo Absorption (First-party targets < 5 MB)
Archives nested `.git` metadata into `maintenance/backups/` and stages source code directly:

```bash
# Dry run verification
./scripts/absorb-nested.sh --dry-run base-account-privy

# Execute absorption and local commit
./scripts/absorb-nested.sh --confirm base-account-privy
```

### C. Workspace Cache Purge
Cleans non-tracked transient Python, test, and log artifacts:

```bash
# Dry run check
./scripts/clean-local.sh --dry-run

# Execute purge
./scripts/clean-local.sh --confirm
```

---

## 3. Rollback & Recovery Procedures

### Rollback Submodule Conversion
If a submodule addition needs to be rolled back:
```bash
git submodule deinit -f <path>
git rm -f <path>
rm -rf .git/modules/<name>
git restore --staged .gitmodules
```

### Rollback Monorepo Absorption
To restore the independent `.git` repository from backup:
```bash
LATEST_BACKUP=$(ls -td maintenance/backups/*/ | head -n1)
cp -r "${LATEST_BACKUP}/<name>.git" "<path>/.git"
git restore --staged "<path>"
```

---

## 4. Owner & Contact Directory

| Area | Primary Owner | Escalation / Reviewer |
|---|---|---|
| Submodule Lifecycle & CI Workflows | DevOps Lead | Release Manager |
| Monorepo Absorption & Packaging | Monorepo Maintainer | Architecture Analyst |
| Bounty Scopes & Evidence Verification | Security Auditor | Playbook Admin Oracle |
| Local Tooling & Caches | Build Engineer | DevOps Lead |
