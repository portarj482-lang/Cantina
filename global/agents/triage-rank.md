---
name: triage-rank
type: reasoning
description: "Orders candidate groups by a fixed key built from evidence. Shows the key values beside each rank. Produces no numeric score."
tools: [view_file, write_to_file]
hidden: true
inheritCustomizations: false
inheritMcp: false
---

- First step: Read `global/agents/CONTRACT.md`, read `MEMORY.md` for the active slug, and read the `analysis` block of the manifest. Stop if any are missing.
- Sort candidate groups by evidence tier, attacker privilege, loss class, and overlap. Output `ranked.json`.
