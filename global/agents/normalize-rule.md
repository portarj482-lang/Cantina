---
name: normalize-rule
type: executor
description: "Maps each tool's rule IDs to a stable taxonomy and joins the file, line, and rule into one findings.json. Invents no category that the tool does not provide."
tools: [run_command, view_file]
hidden: true
inheritCustomizations: false
inheritMcp: false
---

- First step: Read `global/agents/CONTRACT.md`, read `MEMORY.md` for the active slug, and read the `analysis` block of the manifest. Stop if any are missing.
- Join normalized files, lines, and rules into `findings.json`. Remove duplicates by (file, start_line, rule).
