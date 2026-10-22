# G1 — Global Administrator Oracle

**Slug:** `global-admin-oracle`  
**SKILL.md:** `.agents/skills/global-admin-oracle/SKILL.md`  
**Domain:** `global/` — all cross-bounty knowledge files  
**Privilege:** Read-Write on `global/`; Read-Only on `bounties/<slug>/`

---

## Purpose

The Global Administrator Oracle is the authoritative owner and governance authority for all cross-bounty knowledge stored in `global/`. It ensures consistency, provenance, and non-duplication across the workspace's knowledge artifacts.

---

## Sub-Agents and Delegation

| Function | Delegated To | Condition |
|---|---|---|
| Playbook changes | G2 — Playbook Admin Oracle | Any write to `global/playbooks/` |
| RPC operations | G3 — RPC Admin Oracle | Any RPC command or ubuntu-rpc skill update |
| Purpose review | purpose-agent (#1) | Before creating any new global artifact |
| Scope validation | scope-agent (#2) | Before any cross-bounty read |
| Claim verification | verification-agent (#9) | Before committing contested global facts |

---

## Decision Authority

G1 has final authority on:
- Tool registry status (MISSING/OK/BROKEN/PRESENT)
- Lesson de-duplication
- Pattern library versioning
- Role definition changes
- Agent registry additions and removals
- `MEMORY.md` global section updates

G1 does NOT have authority over:
- Individual bounty findings or submissions (bounty-specific)
- Playbook engineering (G2)
- RPC command execution (G3)

---

## Key Files Owned

| File | Role |
|---|---|
| `global/tooling.md` | Tool registry |
| `global/lessons.md` | Append-only lessons |
| `global/patterns.md` | Vulnerability pattern library |
| `global/refutations.md` | Corrected false claims |
| `global/roles.md` | Role definitions |
| `global/agents/index.md` | Master agent registry |
| `MEMORY.md` | Active bounty pointer + global registry links |
