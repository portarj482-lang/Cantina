---
name: universal-adaptive-orchestrator
description: >-
  Execution harness and workflow coordinator for the Universal Adaptive Engineering Orchestrator.
  Manages the 14-stage lifecycle, TargetContext resolution, task ledgers, evidence stores,
  and independent challenger steps across heterogeneous smart-contract architectures under USAP.
---

# Universal Adaptive Orchestrator Skill (USAP Architecture)

## Overview
The Universal Adaptive Orchestrator coordinates engineering and security workflows across diverse target architectures (EVM, Solana, Move, CosmWasm, Rust). It enforces dynamic `TargetContext` resolution, executes the 14-stage lifecycle, logs audit trails, verifies acceptance criteria with independent evidence, and executes adversarial challenge steps under the 5-state result taxonomy (`PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`, `NOT_VERIFIED`).

---

## Quick Start CLI Operations

```bash
# 1. Discover target architecture and capabilities
python3 universal_adaptive_engine/cli.py discover --target-root bounties/base

# 2. Run domain operation pipelines against specific targets
python3 universal_adaptive_engine/cli.py operation --name dispute --target-root bounties/base
python3 universal_adaptive_engine/cli.py operation --name delayed-weth --target-root bounties/base
python3 universal_adaptive_engine/cli.py operation --name multiproof-tee --target-root bounties/base
python3 universal_adaptive_engine/cli.py operation --name rpc-governance --target-root bounties/base

# 3. Target discovery across heterogeneous architectures
python3 universal_adaptive_engine/cli.py operation --name dispute --bounty agglayer
```

---

## Lifecycle Stages & Execution Pipeline

```
INTAKE -> DISCOVERY -> BASELINE -> DECOMPOSITION -> PLAN 
-> AUTHORIZATION CHECK -> IMPLEMENTATION -> VERIFICATION 
-> INDEPENDENT REVIEW -> STAGING -> APPROVAL 
-> DEPLOYMENT (Skipped for Audits) -> POST-DEPLOYMENT VALIDATION -> COMPLETION REPORT
```

Every stage produces a validated `HandoffRecord` committed to the execution report.
Stage skips (e.g. `DEPLOYMENT` in audit-only domains) require documented architectural rationale.
If mandatory context is missing, the orchestrator immediately halts with `BLOCKED: MISSING_CONTEXT`.
