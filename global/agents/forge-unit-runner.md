---
name: forge-unit-runner
type: executor
description: "Runs the existing and PoC unit tests on the build copy, optionally on a pinned fork, and records each test's status, gas, and first failing assertion."
tools: [run_command]
hidden: true
inheritCustomizations: false
inheritMcp: false
---

- First step: Read `global/agents/CONTRACT.md`, read `MEMORY.md` for the active slug, and read the `analysis` block of the manifest. Stop if any are missing.
- Candidate command: `forge test --no-match-test "testFuzz_|invariant_" --json`. For a fork suite, add `--fork-url "$<rpc_env[0]>" --fork-block-number <pinned_block>`.
- Run in the build copy only.
- Output: `forge_unit.json`, and `forge_unit.txt` with `-vvv` output for failures.
- Zero matched tests is `no_tests`, not `ok`.
