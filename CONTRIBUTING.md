# Contributing to Cantina Monorepo

Welcome to the Cantina workspace. Follow these guidelines to maintain repository reproducibility, CI hygiene, and consistent architecture boundaries.

---

## 1. Quickstart Development Setup

```bash
# 0. Initialize and sync all submodules
git submodule update --init --recursive

# 1. Create a clean virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies & editable engine package
make dev-install

# 3. Verify unit tests
make test
```

---

## 2. Hygiene & Code Quality Gates

Before committing any changes:

- **Audit Tracked Files:** Run `make audit` to ensure zero runtime artifacts (`.env`, `node_modules`, `__pycache__`, `*.so`) are staged.
- **Local Cleanup:** Use `./scripts/clean-local.sh --dry-run` or `./scripts/clean-local.sh --confirm` to safely clear transient caches.
- **Pre-commit Hooks:** Install pre-commit hooks via `pre-commit install`.

---

## 3. Working with Nested Repositories & Submodules

Nested repositories are governed by [maintenance/nested-repos-policy.md](maintenance/nested-repos-policy.md).

- **Cloning & Syncing:** When cloning or switching branches, initialize and recursively fetch all registered submodules:
  ```bash
  git submodule update --init --recursive
  ```
- **Never create loose untracked `.git` repositories in the workspace.**
- To add a dependency larger than 50MB, register it as a submodule via `./scripts/convert-to-submodule.sh`.
- To absorb a first-party package under 5MB, use `./scripts/absorb-nested.sh`.

---

## 4. Submitting Pull Requests

1. Verify all unit tests pass (`make test`).
2. Verify zero secrets or runtime logs are present (`make audit`).
3. Fill out all sections in the [Pull Request Template](.github/PULL_REQUEST_TEMPLATE.md).
