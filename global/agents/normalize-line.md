---
name: normalize-line
type: executor
description: "Checks each finding's line range against the file length and resolves the enclosing contract and function from the compiler's AST."
tools: [run_command, view_file]
hidden: true
inheritCustomizations: false
inheritMcp: false
---

- First step: Read `global/agents/CONTRACT.md`, read `MEMORY.md` for the active slug, and read the `analysis` block of the manifest. Stop if any are missing.
- Validate line numbers against file length. Resolve contract/function from AST.
