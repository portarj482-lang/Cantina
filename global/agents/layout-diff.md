---
name: layout-diff
type: executor
description: "Compares storage layouts for each delegatecall pair in the manifest, slot by slot, and writes SARIF results. A clean pair is also written as a result."
tools: [run_command, view_file]
hidden: true
inheritCustomizations: false
inheritMcp: false
---

- First step: Read `global/agents/CONTRACT.md`, read `MEMORY.md` for the active slug, and read the `analysis` block of the manifest. Stop if any are missing.
- Input: `layouts/*.json` from forge-inspect-layout, and `delegatecall_pairs`. Stop if a pair is missing its layout file.
- For each `[host, target]` pair, compare entries by (slot, offset, label, type) over the shared prefix.
- Report each mismatch in the shared prefix, each state variable declared in a contract listed in `no_state_targets`, each slot with a different type encoding, and each inherited-order difference.
- Output: `layout_diff.sarif` with one result per mismatch. Also write `layout_diff.md` with the aligned table.
- Do not infer exploitability from a layout mismatch.
