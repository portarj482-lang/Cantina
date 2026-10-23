## Description
<!-- Provide a concise summary of the change and its rationale. -->

## Changes Checklist
- [ ] Code follows monorepo layout and architectural boundaries (`scope.md` / `USAP`).
- [ ] No secrets, live API keys, or credentials committed (`.env.example` only).
- [ ] All unit tests pass locally (`make test` or `python3 -m unittest discover -s tests/universal_adaptive`).
- [ ] No tracked runtime artifacts (`.pyc`, `node_modules`, `build/`, `*.log`, `__pycache__`).
- [ ] Any database migration changes include fixtures and are tested against Postgres service container.

## Related Issues & Tasks
- Fixes #
