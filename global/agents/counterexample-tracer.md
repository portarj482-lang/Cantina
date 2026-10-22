---
name: counterexample-tracer
type: reasoning
description: "Replays the failing sequences from S3 and the replay inputs from S4 as Foundry tests, and traces each revert or violation site. Says whether the failing state is reachable through public entry points."
tools: [view_file, write_to_file, run_command]
hidden: true
inheritCustomizations: false
inheritMcp: false
---

- First step: Read `global/agents/CONTRACT.md`, read `MEMORY.md` for the active slug, and read the `analysis` block of the manifest. Stop if any are missing.
- Write minimal replay tests `replay_<id>`.
- Run with `-vvvv` on build copy. Report revert sites, panic codes, and state reachability.
