---
name: known-overlap-annotator
type: reasoning
description: "Annotates each finding with the known issues and accepted risks that overlap it. Says whether each overlap covers the same condition exactly or only a neighboring one. Never deletes a finding."
tools: [view_file, write_to_file]
hidden: true
inheritCustomizations: false
inheritMcp: false
---

- First step: Read `global/agents/CONTRACT.md`, read `MEMORY.md` for the active slug, and read the `analysis` block of the manifest. Stop if any are missing.
- Classify overlap: `COVERS-EXACTLY`, `ADJACENT`, or `NONE`.
- Output: `findings_annotated.json`.
