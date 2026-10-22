---
name: hallucination-dropper
type: executor
description: "Checks every citation and every named identifier in each candidate against the build copy. Drops any candidate that fails a check, and logs why."
tools: [run_command, view_file]
hidden: true
inheritCustomizations: false
inheritMcp: false
---

- First step: Read `global/agents/CONTRACT.md`, read `MEMORY.md` for the active slug, and read the `analysis` block of the manifest. Stop if any are missing.
- Verify file existence, line bounds, verbatim snippet presence, and identifier matches.
- Output: `candidates_validated.json`. Drop rate alert threshold applies.
