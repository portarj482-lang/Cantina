---
name: triage-gemini-runner
type: executor
description: "Sends one function's context to an external model with a schema-constrained request and no tools. Records the model, settings, prompt hash, and token counts. Runs only when the manifest and scope.md both allow it."
tools: [run_command]
hidden: true
inheritCustomizations: false
inheritMcp: false
---

- First step: Read `global/agents/CONTRACT.md`, read `MEMORY.md` for the active slug, and read the `analysis` block of the manifest. Stop if any are missing.
- Requires `allow_external_llm: true`.
- Send narrow function context. Enforce no secret exposure.
