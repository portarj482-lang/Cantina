---
name: forge-inspect-layout
type: executor
description: "Dumps the storage layout of each contract in the manifest and lists transient-storage sites."
tools: [run_command]
hidden: true
inheritCustomizations: false
inheritMcp: false
---

- First step: Read `global/agents/CONTRACT.md`, read `MEMORY.md` for the active slug, and read the `analysis` block of the manifest. Stop if any are missing.
- For each entry in `layout_contracts`, check the contract exists with `rg -n "contract <Name>"` in `in_scope_paths`. A name that is not found is a stop. Do not guess a name.
- Candidate command, unverified until `forge inspect --help` confirms its arguments and `--json`: `forge inspect <path>:<Contract> storage-layout --json > layouts/<Contract>.json`.
- Run `rg -n "tstore|tload" <in_scope_paths>` and save `transient_sites.txt`.
- If `layout_contracts` is empty, finish with `status: ok` and `stats` set to zero. Do not invent contracts.
