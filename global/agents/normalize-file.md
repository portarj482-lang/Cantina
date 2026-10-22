---
name: normalize-file
type: executor
description: "Converts each finding's file reference to a repo-relative path and confirms the file exists in the build copy at the pinned commit. Drops any path outside the repository or under an excluded path."
tools: [run_command, view_file]
hidden: true
inheritCustomizations: false
inheritMcp: false
---

- First step: Read `global/agents/CONTRACT.md`, read `MEMORY.md` for the active slug, and read the `analysis` block of the manifest. Stop if any are missing.
- Convert URIs to repo-relative paths. Drop excluded paths.
- Write drops to `dropped.json`.
