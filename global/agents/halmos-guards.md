---
name: halmos-guards
type: executor
description: "Runs Halmos on guard and access-control check functions that exist in the test directories."
tools: [run_command]
hidden: true
inheritCustomizations: false
inheritMcp: false
---

- First step: Read `global/agents/CONTRACT.md`, read `MEMORY.md` for the active slug, and read the `analysis` block of the manifest. Stop if any are missing.
- Find `check_guard_*` functions in `test_dirs`.
- Run Halmos with loop bound and assertion timeout. Output: `halmos_guards.json`.
