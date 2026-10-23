# Executive Summary: Monorepo Hygiene Remediation (Phase Two)

**To:** DevOps Lead & Release Engineering Team  
**From:** Phase Two Remediator  
**Date:** October 2026  
**Repository:** `/home/nova/projects/cantina`  
**Base Commit Synced:** `2af7ac6` ➔ `b00deda`  
**Execution Posture:** Non-destructive; local branch `master`; **zero remote push**; isolated backups in `maintenance/backups/<timestamp>/`.

---

## 1. Context & Remediation Objectives

An exhaustive forensic audit identified **31 nested Git repositories** and **8.7+ GB of untracked assets** across `/home/nova/projects/cantina`. Untracked sub-ecosystems, transient build outputs, and loose `.git` directories compromise build reproducibility, inflate clone times, and risk accidental data leakage in CI.

Phase Two establishes automated, idempotent governance tools, updates exclusion rules, enforces root PEP 621 Python packaging, and validates all remediation steps with `--dry-run` logs and automated test suites.

---

## 2. Top 5 High-Risk Targets & Immediate Remediation Strategy

| Target Path | Footprint | Upstream Remote | Action | Rationale |
|---|---:|---|---|---|
| `bounties/base/spend-permissions` | **1.44 GB** | `https://github.com/coinbase/spend-permissions.git` | **Submodule** | Third-party upstream; massive Git history and build cache. |
| `onchainsummer.xyz` | **808 MB** | `https://github.com/base/onchainsummer.xyz.git` | **Submodule** | Independent Next.js / onchain web app; separate release cycle. |
| `bounties/base/eip-7702-proxy` | **488 MB** | `https://github.com/base/eip-7702-proxy.git` | **Submodule** | Deeply nested Foundry library tree with upstream sync requirements. |
| `bounties/base/smart-wallet` | **472 MB** | `https://github.com/coinbase/smart-wallet.git` | **Submodule** | Official Coinbase smart wallet repository; canonical upstream remote. |
| `docs` / `bounties/base/docs` | **927 MB** (combined) | `https://github.com/base/docs.git` | **Submodule** | Heavy documentation clones; should reference upstream commit pins. |

---

## 3. Governance Decision Thresholds

- **Submodule Rule (> 50 MB):** Any nested repository with an active upstream remote and footprint > 50 MB is registered via `./scripts/convert-to-submodule.sh --confirm`. Original `.git` metadata is preserved in `maintenance/backups/<timestamp>/`.
- **Absorb Rule (< 5 MB):** First-party packages under 5 MB (`base-account-privy`, `contract-address-checker`, `transaction-latency`, etc.) are absorbed directly into the root monorepo tree via `./scripts/absorb-nested.sh --confirm`.
- **Transient Purge Rule:** Ephemeral compiler outputs (`bounties/*/build/`, `target/`, `node_modules/`, `runs/`) are excluded via hardened `.gitignore` and safely purged with `./scripts/clean-local.sh --confirm`.
- **Reproducible Manifest:** Root PEP 621 `pyproject.toml` and pinned `requirements.txt` guarantee clean, repeatable installs.

---

## 4. Verification & Evidence Status

- **Automated Test Suite:** `python3 -m unittest discover -s tests/universal_adaptive` ➔ **193 tests passed in 16.286s (100% pass rate)**.
- **Hygiene Gate:** `make audit` ➔ **Audit OK: Zero tracked secrets or runtime artifacts**.
- **CI Workflows:** `.github/workflows/ci.yml` (hygiene gate + untracked audit upload + Python matrix) and `security-mesh-ci.yml` (Postgres container integration) lint clean and valid.
- **Dry-Run Logs:** 16 verified logs generated under [maintenance/reports/dryrun-logs/](file:///home/nova/projects/cantina/maintenance/reports/dryrun-logs/).
- **Canonical Action Plan:** [maintenance/reports/action_plan_phase2.csv](file:///home/nova/projects/cantina/maintenance/reports/action_plan_phase2.csv) maps top 30 items with assigned owners, ETAs, and exact commands.

---

## 5. Rollback & Safety Guarantee

Every destructive action is strictly prohibited. Submodule and absorb operations archive `.git` metadata into `maintenance/backups/<timestamp>/` before executing. Submodules can be reversed via `git submodule deinit`, and absorbed packages can be restored by returning the archived `.git` directory. No remote pushes or history rewrites will occur without explicit human approval.

---

## 6. Recommended Execution Order Upon Maintainer Signoff

```bash
# Batch 1: Absorb First-Party Packages (< 5MB)
./scripts/absorb-nested.sh --confirm base-account-privy
./scripts/absorb-nested.sh --confirm contract-address-checker
./scripts/absorb-nested.sh --confirm transaction-latency

# Batch 2: Register Heavy Upstream Submodules (> 50MB)
./scripts/convert-to-submodule.sh --confirm bounties/base/spend-permissions
./scripts/convert-to-submodule.sh --confirm onchainsummer.xyz

# Batch 3: Local Cache Purge
./scripts/clean-local.sh --confirm

# Batch 4: Re-verify Gate
make audit && make test
```
