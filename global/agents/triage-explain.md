---
name: triage-explain
type: reasoning
description: "Writes a plain-language explanation of each ranked group and the single Foundry test that would prove or kill it."
tools: [view_file, write_to_file]
hidden: true
inheritCustomizations: false
inheritMcp: false
---

- First step: Read `global/agents/CONTRACT.md`, read `MEMORY.md` for the active slug, and read the `analysis` block of the manifest. Stop if any are missing.
- Produce `candidates.md` with plain-language explanation and Part B test specification.
