---
name: triage-group
type: reasoning
description: "Groups candidates that share a root cause, so each root cause is reported once."
tools: [view_file, write_to_file]
hidden: true
inheritCustomizations: false
inheritMcp: false
---

- First step: Read `global/agents/CONTRACT.md`, read `MEMORY.md` for the active slug, and read the `analysis` block of the manifest. Stop if any are missing.
- Group candidates sharing a common root cause into `groups.json`.
