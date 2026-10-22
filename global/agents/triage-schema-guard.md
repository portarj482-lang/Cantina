---
name: triage-schema-guard
type: executor
description: "Checks each model output against the Candidate schema and rejects anything malformed. Logs each rejection."
tools: [run_command, view_file]
hidden: true
inheritCustomizations: false
inheritMcp: false
---

- First step: Read `global/agents/CONTRACT.md`, read `MEMORY.md` for the active slug, and read the `analysis` block of the manifest. Stop if any are missing.
- Validate candidate schema. Reject malformed responses.
