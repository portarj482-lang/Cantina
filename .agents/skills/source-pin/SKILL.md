---
name: source-pin
description: "Pack A Source Pin executor and scope verifier. Enforces scope SHA-256 snapshot matching and delegates to PACK-A-SOURCE-PIN-001 (source-pin-oracle) for deterministic tool governance and pin.json artifact creation."
---

# Pack A — Source Pin Skill

**Persona ID:** `PACK-A-SOURCE-PIN-001`  
**Supervising Oracle:** `source-pin-oracle` (`global/agents/source-pin-oracle.md`)  
**Workflow:** `workflows/pack-a-source/workflow-source-pin.sh`  
**Primary Artifact:** `bounties/<slug>/scans/pin.json`  

---

## Overview

This skill provides the execution and verification primitive for Pack A Source Pin.
Full governance, tool policy, downstream assessment protocols, and state machine specifications are defined in `source-pin-oracle`.

## Quick Invocation

```bash
# Validation only (safe, no filesystem writes)
./workflows/pack-a-source/workflow-source-pin.sh --slug <bounty-slug>

# Confirmed atomic pin write
./workflows/pack-a-source/workflow-source-pin.sh --slug <bounty-slug> --confirm
```
