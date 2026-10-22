---
name: aderyn-runner
type: executor
description: "Runs Aderyn on the build copy and saves its SARIF output and per-detector counts."
tools: [run_command]
hidden: true
inheritCustomizations: false
inheritMcp: false
---

- First step: Read `global/agents/CONTRACT.md`, read `MEMORY.md` for the active slug, and read the `analysis` block of the manifest. Stop if any are missing.
- Confirm with `aderyn --help` how SARIF output is requested and how paths are excluded.
- Exclude `exclude_paths`, using the exclusion flag confirmed in the help output.
- Output: `aderyn.sarif`, `stats` with a count per detector, and the version in `version.txt`.
