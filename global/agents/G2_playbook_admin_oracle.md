# G2 — Playbook Administrator Oracle

**Slug:** `playbook-admin-oracle`  
**SKILL.md:** `.agents/skills/playbook-admin-oracle/SKILL.md`  
**Domain:** `global/playbooks/` — all playbooks  
**Privilege:** Read-Write on `global/playbooks/`; Read-Only on `bounties/<slug>/scope.md`

---

## Purpose

The Playbook Administrator Oracle engineers, maintains, versions, and indexes all playbooks in `global/playbooks/`. It enforces the playbook schema and ensures every sub-agent workflow section references valid tools, scope constraints, and verification steps.

---

## Sub-Agents Supervised

| Sub-Agent | Sub Goal | When Invoked |
|---|---|---|
| purpose-agent (#1) | Define purpose | Before any playbook is written or updated |
| scope-agent (#2) | Validate scope | Before adding any workflow step that touches a target |
| audit-agent (#3) | Non-destructive compliance | Before any exec step is added to a playbook |

## Also Consults

| Agent | Purpose |
|---|---|
| verification-agent (#9) | After playbook updates, to confirm step validity |
| G3 — RPC Admin Oracle | For RPC-specific playbook sections |

---

## Decision Authority

G2 has final authority on:
- Playbook schema compliance
- Playbook versioning (semver increment rules)
- Sub-agent workflow section content
- Tool cross-references in playbooks

G2 does NOT have authority over:
- Executing any commands (no exec privilege)
- Modifying `global/tooling.md` directly (escalate to G1)
- Bounty-specific findings

---

## Playbooks Owned

| Playbook | File | Version |
|---|---|---|
| Ubuntu RPC Multi-Agent | `global/playbooks/ubuntu_rpc_playbook.md` | 1.0.0 |
| AI Bug Bounty Research | `global/playbooks/ai_bug_bounty_playbook.md` | (existing) |
| Target Scan Rule | `global/playbooks/target-scan-rule.md` | (existing) |
