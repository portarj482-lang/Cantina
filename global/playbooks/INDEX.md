# Playbooks Master Index

**Domain:** `global/playbooks/`  
**Governing Oracle:** G2 — Playbook Administrator Oracle  
**Last updated:** 2026-10-21

---

## Registered Playbooks

| Playbook Identifier | File | Version | Oracle | Scope & Focus |
|---|---|---|---|---|
| `ubuntu-rpc-multi-agent` | [`ubuntu_rpc_playbook.md`](./ubuntu_rpc_playbook.md) | 1.0.0 | G3 / O3 | Linux RPC discovery, portmapper inspection, and Samba RPC interaction (10 sub-goals) |
| `ai-bug-bounty-research` | [`ai_bug_bounty_playbook.md`](./ai_bug_bounty_playbook.md) | 2.0.0 | G1 / G2 | Systematic AI bug bounty research methodology and multi-temporal falsification |
| `target-scan-rule` | [`target-scan-rule.md`](./target-scan-rule.md) | 1.0.0 | G1 / G2 | Multi-layer contract analysis and target-specific agent assignment |
| `tier0-fault-dispute-attestation` | [`tier0_fault_dispute_playbook.md`](./tier0_fault_dispute_playbook.md) | 2.0.0 | G4 / G5 / G6 | Tier 0 Fault Dispute System, DelayedWETH Solvency & Multiproof TEE Attestation under USAP & Glassbox 8-Stage Orchestration |

---

## Schema & Governance

All playbooks in this directory adhere to the standard frontmatter schema:
```yaml
---
playbook: <slug>
version: <semver>
oracle: <governing_oracle>
sub-agents: [<sub_agent_list>]
last-updated: <YYYY-MM-DD>
---
```
Every modification or new playbook must be authorized by the Playbook Administrator Oracle (G2).
