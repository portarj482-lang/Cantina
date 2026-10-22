---
name: forge-invariant-runner
type: executor
description: "Runs the invariant tests with explicit runs, depth, and seed. Confirms each invariant can fail, using the broken variant in the test directories."
tools: [run_command]
hidden: true
inheritCustomizations: false
inheritMcp: false
---

- First step: Read `global/agents/CONTRACT.md`, read `MEMORY.md` for the active slug, and read the `analysis` block of the manifest. Stop if any are missing.
- Candidate command: `FOUNDRY_INVARIANT_RUNS=<invariant_runs> FOUNDRY_INVARIANT_DEPTH=<invariant_depth> forge test --match-test "invariant_" --fuzz-seed <fuzz_seed> --json`.
- Before any PASS is reported, run the broken variant from `test_dirs` to confirm sensitivity.
- On failure, capture the call sequence.
- Output: `forge_invariant.json` with handler statistics.
