---
name: slither-runner
type: executor
description: "Runs Slither on the build copy and saves its SARIF output and per-check counts."
tools: [run_command]
hidden: true
inheritCustomizations: false
inheritMcp: false
---

- First step: Read `global/agents/CONTRACT.md`, read `MEMORY.md` for the active slug, and read the `analysis` block of the manifest. Stop if any are missing.
- Candidate command, unverified until `slither --help` confirms each flag: `slither . --sarif slither.sarif --fail-none --filter-paths "<exclude_paths joined by |>"`.
- Run in the build copy, never in the checkout.
- If compilation fails, write the compiler error to `result.json`, set `status: fail`, and stop. Do not retry with other settings.
- Record the exact filter string in `command.txt`.
- Output: `slither.sarif`, and `stats` with a count per check ID.
