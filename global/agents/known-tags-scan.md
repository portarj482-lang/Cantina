---
name: known-tags-scan
type: executor
description: "Finds every known-issue tag pattern in the manifest and copies the known-issue list from scope.md verbatim."
tools: [run_command]
hidden: true
inheritCustomizations: false
inheritMcp: false
---

- First step: Read `global/agents/CONTRACT.md`, read `MEMORY.md` for the active slug, and read the `analysis` block of the manifest. Stop if any are missing.
- Scan for `known_tag_patterns` and output `tags.json` and `known_issues.json`.
