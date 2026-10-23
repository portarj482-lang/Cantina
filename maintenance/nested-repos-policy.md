# Nested Repositories & Submodule Governance Policy

## 1. Purpose & Scope
This policy governs how independent repositories, external library dependencies, and nested Git packages are handled inside the Cantina Monorepo workspace (`/home/nova/projects/cantina`).

---

## 2. Decision Rules & Criteria

| Repository Type | Criteria | Action | Procedure |
|---|---|---|---|
| **Large External / First-Party** | Footprint **> 50 MB** with upstream remote | **Submodule** | Register via `scripts/convert-to-submodule.sh`. Pin commit in `.gitmodules`. |
| **Small First-Party Package** | Footprint **< 5 MB** maintained by base/cantina | **Absorb** | Archive `.git` to `maintenance/backups/<timestamp>`, commit tree directly. |
| **Transient Build Outputs** | Output under `bounties/*/build/`, `target/`, etc. | **Remove & Ignore** | Run `scripts/clean-local.sh --confirm`. Verify rules in `.gitignore`. |
| **Shared Tool / Framework** | Foundry, OpenZeppelin, etc. | **Submodule** | Maintain as a reproducible Git submodule or foundry `lib/`. |
| **Public Documentation** | Pure markdown/specs (< 5MB) | **Absorb** | Absorb and version directly in documentation tree. |

---

## 3. Submodule Lifecycle & Commands

### Adding a Submodule
Always use the safe automation script or exact git commands:
```bash
./scripts/convert-to-submodule.sh --dry-run <path>
./scripts/convert-to-submodule.sh --confirm <path>
```

### Cloning with Submodules
Ensure all developers and CI clones initialize submodules recursively:
```bash
git clone --recurse-submodules <repo_url>
# Or in an existing working copy:
git submodule update --init --recursive
```

### Pinning Submodule Commits
Submodules must always point to an explicit, verified commit SHA, never a floating branch:
```bash
cd <path/to/submodule>
git checkout <pinned_sha_or_tag>
cd ../..
git add <path/to/submodule>
git commit -m "chore(deps): pin <submodule> to <commit_sha>"
```

---

## 4. Backup & Rollback Protocol
Before removing any nested Git metadata (`.git` directory), an exact copy is preserved under `maintenance/backups/<timestamp>/`.

### Rollback Procedure
If a nested repo was absorbed in error:
```bash
# Example restoring .git metadata
cp -r "maintenance/backups/<timestamp>/<name>.git" "<path>/.git"
git restore --staged "<path>"
```
