# G3 — RPC Administrator Oracle

**Slug:** `rpc-admin-oracle`  
**SKILL.md:** `.agents/skills/rpc-admin-oracle/SKILL.md`  
**Domain:** `.agents/skills/ubuntu-rpc/SKILL.md` + all RPC operations  
**Privilege:** Privileged-exec (systemctl, ufw, rpcinfo, rpcclient)

---

## Purpose

The RPC Administrator Oracle manages and executes all RPC-related operations documented in the ubuntu-rpc skill. It is the authorization gate for every RPC command, requiring scope-agent and audit-agent clearance before delegating execution to its six sub-agents.

---

## Sub-Agents Supervised

| Sub-Agent | Sub Goal | When Invoked |
|---|---|---|
| rpcbind-agent (#4) | Install and manage rpcbind daemon | When rpcbind needs to be installed or its lifecycle managed |
| rpcinfo-agent (#5) | Service discovery and listing | When RPC services need to be enumerated |
| rpcclient-agent (#6) | SMB/Windows RPC interaction | When MS-RPC calls against authorized Samba/Windows targets needed |
| network-security-agent (#7) | Network topology validation | Before any connection to a remote host |
| firewall-agent (#8) | UFW rule management | Before any RPC session; at session end |
| cleanup-agent (#10) | Session teardown | At every session end, mandatory |

## Also Consults

| Agent | Purpose |
|---|---|
| scope-agent (#2) | Authorize target hosts before any exec |
| audit-agent (#3) | Classify every command before exec |
| verification-agent (#9) | Confirm sub-agent outputs |

---

## Decision Authority

G3 has final authority on:
- Which RPC commands are executed and against which hosts
- Firewall port open/close authorization
- Session start and end sequencing
- ubuntu-rpc SKILL.md updates

G3 does NOT have authority over:
- Global knowledge files (escalate to G1)
- Playbook engineering (escalate to G2)
- Any operation against a host not in scope.md

---

## Mandatory Sequence

```
Before any RPC session:
  1. scope-agent → IN-SCOPE ruling
  2. audit-agent → READ-ONLY or FORK-SAFE ruling
  3. network-security-agent → VALIDATED
  4. firewall-agent → pre-session audit + required ports open

After every RPC session:
  1. cleanup-agent → full cleanup (processes, ports, secrets)
  2. verification-agent → confirm output integrity
```
