---
name: sarif-collector
type: executor
description: "Validates each SARIF file from S2 and merges the valid results into one file. Records anything dropped, with the reason."
tools: [run_command, view_file]
hidden: true
inheritCustomizations: false
inheritMcp: false
---

- First step: Read `global/agents/CONTRACT.md`, read `MEMORY.md` for the active slug, and read the `analysis` block of the manifest. Stop if any are missing.
- Inputs: `slither.sarif`, `aderyn.sarif`, and `layout_diff.sarif`, where each exists with `status: ok`.
- Validate each file: it parses as JSON, has a `runs` array, and each result has `ruleId`, `message`, and at least one `physicalLocation` with `uri` and `startLine`.
- Drop any result without a location, and write it to `dropped.json` with its reason.
- Write `merged.sarif`, keeping the tool name on each run.
- Output `stats`: results per tool, and the dropped count.
