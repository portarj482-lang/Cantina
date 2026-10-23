---
name: recon
description: "Pack A — Smart Contract Reconnaissance Orchestrator (META-RECON-A). Refactors, validates, executes, and audits the reconnaissance workflow for authorized smart-contract security assessments under USAP."
---

# Pack A — Reconnaissance Orchestrator Skill

**Persona ID:** `META-RECON-A`  
**Workflow:** `workflows/pack-a-recon/workflow-recon.sh`  
**Primary Artifact:** `bounties/<slug>/scans/recon.json`  
**Schema:** `workflows/pack-a-recon/schemas/recon.schema.json`  
**Supervised by:** G1 (Global Admin Oracle)  
**Registry Baseline:** 2026-10-23  

---

## Activation

Load this skill when:
- Executing Pack A reconnaissance across authorized smart-contract targets.
- Discovering and cataloging in-scope Solidity source files without modifying target code.
- Verifying repository git provenance and dirty worktree states.
- Generating deterministic `recon.json` artifacts under fail-closed authorization.

---

## Operational Mandate

This agent transforms the minimal baseline reconnaissance shell script into an evidence-driven, fail-closed orchestrator:
- Preserves the baseline CLI interface (`--dry-run`, `--confirm`, `--slug <slug>`).
- Enforces strict path containment, allowlists, and traversal rejection.
- Traverses directories without following symlinks and excludes generated scan directories.
- Refuses to report false completion on missing target directories or permission errors.
- Validates JSON output against formal schema before atomic rename.

---

## Invocation

```bash
# Dry-run (default — safe, simulation only)
./workflows/pack-a-recon/workflow-recon.sh --slug <bounty-slug>

# Confirmed write
./workflows/pack-a-recon/workflow-recon.sh --slug <bounty-slug> --confirm
```

---

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success (including dry-run plan) |
| `1` | Execution, traversal, or artifact validation failure |
| `2` | Invalid command-line arguments or path traversal |
| `3` | Missing bounty directory or unresolvable scope |
