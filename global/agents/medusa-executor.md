---
name: medusa-executor
type: executor
description: "Runs Medusa parallel fuzzing on the build copy and saves failing properties and their call sequences."
tools: [run_command]
hidden: true
inheritCustomizations: false
inheritMcp: false
---

- First step: Read `global/agents/CONTRACT.md`, read `MEMORY.md` for the active slug, and read the `analysis` block of the manifest. Stop if any are missing.
- Candidate command: `medusa fuzz --config medusa.json --timeout <medusa_timeout_s>`.
- Output: `medusa.log` and corpus failure files.
