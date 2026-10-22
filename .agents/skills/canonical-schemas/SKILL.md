---
name: canonical-schemas
description: >-
  Provides canonical schemas, models, and type definitions (TargetContext, TargetResultStatus,
  Task Records, Finding Records, Adaptation Records, Evidence Records, and Capability Records)
  for universal, architecture-aware smart-contract security under USAP.
---

# Canonical Schemas Skill (USAP Architecture)

## Overview
Canonical contracts provide shared semantic meaning across heterogeneous agent runtimes, blockchain architectures, and host environments. Schemas are defined in JSON Schema (Draft 2020-12), Python typed dataclasses, and TypeScript interface definitions.

---

## Universal Architecture Models
- **`TargetContext`** (`universal_adaptive_engine/models/target_context.py`): Normalized target specification capturing `target_root`, `architecture`, `languages`, `runtimes`, `source_roots`, `test_roots`, `manifests`, `scope_manifest`, `session_id`, and `capabilities`.
- **`TargetResultStatus`**: The 5-state result taxonomy required by USAP:
  - `PASS`: Property verified within declared assumptions with evidence.
  - `FAIL`: Violation demonstrated or attack reproduced.
  - `BLOCKED`: Missing context, manifest, or permissions.
  - `NOT_APPLICABLE`: Property irrelevant to detected architecture.
  - `NOT_VERIFIED`: Incomplete analysis or unavailable tooling.
- **`TargetFinding`**: Evidence-backed security finding recording target, architecture, property violated, affected artifact, and limitations.
- **`TargetContextResolver`**: Authoritative resolution engine with fail-closed semantics.

---

## Existing Canonical Schemas
- **`TaskRecord`** (`schemas/task_record.schema.json`): Tracks individual units of work in the task ledger.
- **`FindingRecord`** (`schemas/finding_record.schema.json`): Records security, architectural, and code findings with provenance tags.
- **`AdaptationRecord`** (`schemas/adaptation_record.schema.json`): Governs admission decisions for new tools, skills, agents, and patterns.
- **`CapabilityRecord`** (`schemas/capability_record.schema.json`): Documents host capabilities and their verification status.
- **`EvidenceRecord`** (`schemas/evidence_record.schema.json`): Cryptographically pins observations to physical artifacts on disk.
- **`HandoffRecord`**: Machine-validated stage handoffs across the 14-stage lifecycle.

---

## Python API Usage

```python
from universal_adaptive_engine.models import (
    TargetContext, TargetResultStatus, TargetFinding, TargetContextResolver,
    TaskRecord, TaskState, FindingRecord, EvidenceRecord, HandoffRecord
)

# Resolve and validate target context
target_ctx = TargetContextResolver.resolve(context={"bounty_slug": "base"})
assert target_ctx.is_valid, "Target context must be valid"
print(f"Architecture: {target_ctx.architecture}, Capabilities: {target_ctx.capabilities}")
```
