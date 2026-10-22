---
name: halmos-arithmetic
type: executor
description: "Runs Halmos on arithmetic check functions (rounding, division by zero, truncation, decimal normalization) that exist in the test directories."
tools: [run_command]
hidden: true
inheritCustomizations: false
inheritMcp: false
---

- First step: Read `global/agents/CONTRACT.md`, read `MEMORY.md` for the active slug, and read the `analysis` block of the manifest. Stop if any are missing.
- Find `check_arith_*` functions with `rg -n "function check_arith_"`.
- Run Halmos with solver timeout and loop bounds. Output: `halmos_arith.json`.
