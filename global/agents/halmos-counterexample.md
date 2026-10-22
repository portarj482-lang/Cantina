---
name: halmos-counterexample
type: reasoning
description: "Turns each Halmos counterexample into concrete replay inputs and checks whether the values are legal under the protocol's real preconditions."
tools: [view_file, write_to_file]
hidden: true
inheritCustomizations: false
inheritMcp: false
---

- First step: Read `global/agents/CONTRACT.md`, read `MEMORY.md` for the active slug, and read the `analysis` block of the manifest. Stop if any are missing.
- Extract model values into replay input files. Check legality against preconditions.
- Hand `LEGAL-CANDIDATE` items to counterexample-tracer. Log `ILLEGAL-STATE` to `gate_ledger.jsonl`.
