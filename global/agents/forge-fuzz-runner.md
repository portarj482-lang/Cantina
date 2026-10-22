---
name: forge-fuzz-runner
type: executor
description: "Runs the fuzz tests with a recorded seed, then a second pass with a different seed, and preserves any shrunk counterexample."
tools: [run_command]
hidden: true
inheritCustomizations: false
inheritMcp: false
---

- First step: Read `global/agents/CONTRACT.md`, read `MEMORY.md` for the active slug, and read the `analysis` block of the manifest. Stop if any are missing.
- Candidate command: `forge test --match-test "testFuzz_" --fuzz-runs <fuzz_runs> --fuzz-seed <fuzz_seed> --json`.
- Run a second pass with `fuzz_seed_alt`.
- On failure, copy the shrunk counterexample from output into the run folder.
- Record the seed and run count in `command.txt` and in every ledger line.
- Output: `forge_fuzz.json` and the failure files.
