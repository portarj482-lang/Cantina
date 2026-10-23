---
name: sarif-collector
description: Bounded security workflow for discovering, normalizing, deduplicating, and validating static analysis SARIF and JSON scan outputs (Pack B) under UOOMA.
---

# Pack B SARIF Collector Skill

## Overview
This skill implements the Pack B SARIF Collector workflow under the Universal Oracle–Orchestrator Meta-Agent (UOOMA) architecture. It collects raw scan outputs from tools registered in `global/tooling.md` (Slither, Aderyn, Semgrep, and generic SARIF v2.1.0), normalizes them to canonical SARIF, deduplicates findings, validates against JSON Schema, and publishes atomically.

## Governing Invariants
- `WRITE_ALLOWED = CONFIRM && !DRY_RUN`: `--dry-run` always takes precedence over `--confirm`.
- Atomic publication via `.tmp.<pid>` swap to ensure existing valid outputs remain intact on failure.
- Fail-closed path traversal validation on target slugs (`^[A-Za-z0-9][A-Za-z0-9_-]*$`).
- Full provenance preservation for both accepted findings and rejected inputs.

## Key Files
- Orchestrator Wrapper: `workflows/pack-b-static/workflow-sarif-collector.sh`
- Execution Engine: `workflows/pack-b-static/sarif_collector.py`
- Schema: `workflows/pack-b-static/schemas/normalized_sarif.schema.json`
- Output Destination: `bounties/<slug>/scans/normalized_sarif.json`
