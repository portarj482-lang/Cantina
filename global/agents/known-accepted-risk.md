---
name: known-accepted-risk
type: executor
description: "Extracts the accepted-risk NatSpec blocks and the documented trust-model statements from the in-scope source, quoted verbatim."
tools: [run_command, view_file]
hidden: true
inheritCustomizations: false
inheritMcp: false
---

- First step: Read `global/agents/CONTRACT.md`, read `MEMORY.md` for the active slug, and read the `analysis` block of the manifest. Stop if any are missing.
- Extract NatSpec tags and write `accepted_risks.json`.
