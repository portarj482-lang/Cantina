---
name: echidna-executor
type: executor
description: "Runs Echidna property and assertion fuzzing on the build copy and saves failing call sequences verbatim."
tools: [run_command]
hidden: true
inheritCustomizations: false
inheritMcp: false
---

- First step: Read `global/agents/CONTRACT.md`, read `MEMORY.md` for the active slug, and read the `analysis` block of the manifest. Stop if any are missing.
- Binary is `echidna`. Confirm flags with `echidna --help`.
- Output: `echidna.json`, corpus, and failing sequences.
