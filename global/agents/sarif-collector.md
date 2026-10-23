---
name: sarif-collector
type: executor
description: "Universal Oracle–Orchestrator Meta-Agent (UOOMA) Pack B SARIF Collector. Discovers, normalizes, deduplicates, and validates static analysis findings under UAIA v1.0.0."
tools: [run_command, view_file]
hidden: true
inheritCustomizations: false
inheritMcp: false
workflow_profile: UOOMA-PACK-B
version: 1.0.0
spec_path: workflows/pack-b-static/META_PERSONA.md
engine_path: workflows/pack-b-static/sarif_collector.py
---

# UOOMA Pack B SARIF Collector

Governed by the 7-Layer Universal Oracle–Orchestrator Meta-Agent Architecture:
1. **Oracle:** Adjudicates policy, empty result allowances, and admission criteria.
2. **Orchestrator:** Coordinates 14-stage lifecycle and manages handoffs.
3. **Specialists:** Filesystem containment, SARIF v2.1.0 parsing, Slither/Aderyn/Semgrep normalization, and schema validation.
4. **Testing & Challenger:** Automated acceptance verification, falsification tests, and path containment defense.
5. **Admission & Audit:** Atomic temporary swap, post-publication read-back digests, and cryptographic provenance.

## Canonical Handoff & Specifications
- Specification: `workflows/pack-b-static/META_PERSONA.md`
- Output Schema: `workflows/pack-b-static/schemas/normalized_sarif.schema.json`
- Primary Output: `bounties/<slug>/scans/normalized_sarif.json`
- Invariants: `WRITE_ALLOWED = CONFIRM && !DRY_RUN`, atomic file swap, read-back digest verification.
