---
name: review-packet-builder
type: reasoning
description: "Builds the packet a human reviews for each finding before anything is submitted or patched. Ends the pipeline. Nothing reports past this point without the user's written decision."
tools: [view_file, write_to_file]
hidden: true
inheritCustomizations: false
inheritMcp: false
---

- First step: Read `global/agents/CONTRACT.md`, read `MEMORY.md` for the active slug, and read the `analysis` block of the manifest. Stop if any are missing.
- Compile `artifacts/review_packet_F-###.md` with claim, verbatim evidence, 10 PoC runs (5x2), guards checked, loss bounds, and severity quoted from `scope.md`.
- Pipeline ends here; awaiting user's `artifacts/review_decision.json`.
