# Oracle Agent Index

Active Oracle System: 6 Oracles, 24 Sub-Agents  
Last updated: 2026-10-23

---

## Top-Level Oracles

| ID | Slug | SKILL.md | Domain | Sub-Agents |
|---|---|---|---|---|
| G1 | global-admin-oracle | `.agents/skills/global-admin-oracle/SKILL.md` | `global/` knowledge files (tooling, lessons, patterns, refutations, roles, agents) | purpose-agent (consult), scope-agent (consult), verification-agent (consult) |
| G2 | playbook-admin-oracle | `.agents/skills/playbook-admin-oracle/SKILL.md` | `global/playbooks/` — all playbooks | purpose-agent, scope-agent, audit-agent |
| G3 | rpc-admin-oracle | `.agents/skills/rpc-admin-oracle/SKILL.md` | `ubuntu-rpc` skill + all RPC operations | rpcbind-agent, rpcinfo-agent, rpcclient-agent, network-security-agent, firewall-agent, cleanup-agent |
| G4 | dispute-invariant-oracle | `.agents/skills/dispute-invariant-oracle/SKILL.md` | `INV-DISPUTE-01` — Fault dispute, output root proving, and withdrawal finalization | dispute-prove-agent, dispute-finalize-agent, game-resolution-agent, blacklist-maturity-agent, delay-bypass-agent |
| G5 | delayed-weth-invariant-oracle | `.agents/skills/delayed-weth-invariant-oracle/SKILL.md` | `INV-DELAYED-WETH-02` — DelayedWETH timelock, sub-account scoping, balance solvency | weth-unlock-agent, weth-withdraw-agent, weth-solvency-agent, delay-bypass-agent |
| G6 | multiproof-tee-invariant-oracle | `.agents/skills/multiproof-tee-invariant-oracle/SKILL.md` | `INV-MULTIPROOF-03` — AWS Nitro attestation, P-384 verification hints, enclave signer lifecycle | tee-register-agent, tee-validity-agent, attestation-timestamp-agent, inverse-hint-integrity-agent, signer-lifecycle-agent |

---

## Functional Sub-Agents

| # | Slug | SKILL.md | Sub Goal | Inherited Contract / Domain | Supervised by |
|---|---|---|---|---|---|
| 1 | purpose-agent | `.agents/skills/purpose-agent/SKILL.md` | Define purpose before writing | Global | G2 |
| 2 | scope-agent | `.agents/skills/scope-agent/SKILL.md` | Validate in-scope / out-of-scope targets | Global | G2 |
| 3 | audit-agent | `.agents/skills/audit-agent/SKILL.md` | Ensure non-destructive operations | Global | G2 |
| 4 | rpcbind-agent | `.agents/skills/rpcbind-agent/SKILL.md` | Manage rpcbind daemon | Ubuntu RPC | G3 |
| 5 | rpcinfo-agent | `.agents/skills/rpcinfo-agent/SKILL.md` | Query registered RPC programs | Ubuntu RPC | G3 |
| 6 | rpcclient-agent | `.agents/skills/rpcclient-agent/SKILL.md` | Execute SMB/Windows RPC calls | Ubuntu RPC | G3 |
| 7 | network-security-agent | `.agents/skills/network-security-agent/SKILL.md` | Validate network topology & DNS | Ubuntu RPC | G3 |
| 8 | firewall-agent | `.agents/skills/firewall-agent/SKILL.md` | Manage UFW firewall rules | Ubuntu RPC | G3 |
| 9 | verification-agent | `.agents/skills/verification-agent/SKILL.md` | Independently verify outputs | Gatekeeper | Independent (Consulted by G1-G6) |
| 10 | cleanup-agent | `.agents/skills/cleanup-agent/SKILL.md` | Teardown processes & wipe secrets | Ubuntu RPC | G3 |
| 11 | dispute-prove-agent | `.agents/skills/dispute-prove-agent/SKILL.md` | Withdrawal proving & output root proof | `OptimismPortal2.sol` | G4 |
| 12 | dispute-finalize-agent | `.agents/skills/dispute-finalize-agent/SKILL.md` | Withdrawal finalization & reentrancy lock | `OptimismPortal2.sol` | G4 |
| 13 | weth-unlock-agent | `.agents/skills/weth-unlock-agent/SKILL.md` | Sub-account unlock & timestamp reset | `DelayedWETH.sol` | G5 |
| 14 | weth-withdraw-agent | `.agents/skills/weth-withdraw-agent/SKILL.md` | Delay enforcement & ETH withdrawal | `DelayedWETH.sol` | G5 |
| 15 | tee-register-agent | `.agents/skills/tee-register-agent/SKILL.md` | Attestation validation & signer registration | `TEEProverRegistry.sol` | G6 |
| 16 | tee-validity-agent | `.agents/skills/tee-validity-agent/SKILL.md` | Signer validity query & image hash match | `TEEProverRegistry.sol` / `TEEVerifier.sol` | G6 |
| 17 | attestation-timestamp-agent | `.agents/skills/attestation-timestamp-agent/SKILL.md` | Timestamp drift & MAX_AGE verification | `TEEProverRegistry.sol` | G6 |
| 18 | inverse-hint-integrity-agent | `.agents/skills/inverse-hint-integrity-agent/SKILL.md` | P-384 hint transcript & malleability check | `hints.rs` / `NitroValidator` | G6 |
| 19 | signer-lifecycle-agent | `.agents/skills/signer-lifecycle-agent/SKILL.md` | Signer deregistration & hardfork rotation | `TEEProverRegistry.sol` | G6 |
| 20 | weth-solvency-agent | `.agents/skills/weth-solvency-agent/SKILL.md` | Balance solvency & recover/hold audit | `DelayedWETH.sol` | G5 |
| 21 | delay-bypass-agent | `.agents/skills/delay-bypass-agent/SKILL.md` | Falsify delay bypass (dual contract) | `DelayedWETH.sol` & `OptimismPortal2.sol` | G4 & G5 |
| 22 | game-resolution-agent | `.agents/skills/game-resolution-agent/SKILL.md` | Dispute game status & DEFENDER_WINS | `AnchorStateRegistry.sol` / `AggregateVerifier.sol` | G4 |
| 23 | blacklist-maturity-agent | `.agents/skills/blacklist-maturity-agent/SKILL.md` | Blacklist checks & airgap finality delay | `AnchorStateRegistry.sol` | G4 |
| 24 | fixer | `.agents/skills/fixer/SKILL.md` | Secure DevOps Engineering & Hardening | Automation Workflows | G1 |

---

## Inherited Contract Finding Architecture

Each functional agent acts as an **Inherited Contract Agent** for its assigned contract when investigating hypotheses and authoring individual vulnerability findings:
- **Contract Context Inheritance**: The agent automatically inherits the target contract's storage layout, proxy architecture, access control invariants, and error tables.
- **Dedicated Finding Ownership**: When a vulnerability is flagged, the corresponding agent takes sole ownership of producing the individual Cantina finding template, assembling the local Foundry/Cargo PoC, running falsification, and obtaining independent verification via `verification-agent (#9)`.

---

## Supervision Map

```
G1 — Global Admin Oracle
├── Delegates playbook changes → G2
├── Delegates RPC operations → G3
├── Delegates Fault Dispute invariants → G4
├── Delegates DelayedWETH invariants → G5
├── Delegates Multiproof TEE invariants → G6
└── Consults → purpose-agent, scope-agent, verification-agent

G2 — Playbook Admin Oracle (reports to G1)
├── Supervises → purpose-agent (#1)
├── Supervises → scope-agent (#2)
├── Supervises → audit-agent (#3)
└── Consults → verification-agent (#9)

G3 — RPC Admin Oracle (reports to G1)
├── Supervises → rpcbind-agent (#4), rpcinfo-agent (#5), rpcclient-agent (#6)
└── Supervises → network-security-agent (#7), firewall-agent (#8), cleanup-agent (#10)

G4 — Dispute Invariant Oracle (reports to G1)
├── Supervises → dispute-prove-agent (#11) [Inherits OptimismPortal2]
├── Supervises → dispute-finalize-agent (#12) [Inherits OptimismPortal2]
├── Supervises → delay-bypass-agent (#21) [Inherits OptimismPortal2 & DelayedWETH]
├── Supervises → game-resolution-agent (#22) [Inherits AnchorStateRegistry & AggregateVerifier]
└── Supervises → blacklist-maturity-agent (#23) [Inherits AnchorStateRegistry]

G5 — DelayedWETH Invariant Oracle (reports to G1)
├── Supervises → weth-unlock-agent (#13) [Inherits DelayedWETH]
├── Supervises → weth-withdraw-agent (#14) [Inherits DelayedWETH]
├── Supervises → weth-solvency-agent (#20) [Inherits DelayedWETH]
└── Supervises → delay-bypass-agent (#21) [Inherits DelayedWETH & OptimismPortal2]

G6 — Multiproof TEE Invariant Oracle (reports to G1)
├── Supervises → tee-register-agent (#15) [Inherits TEEProverRegistry]
├── Supervises → tee-validity-agent (#16) [Inherits TEEProverRegistry & TEEVerifier]
├── Supervises → attestation-timestamp-agent (#17) [Inherits TEEProverRegistry]
├── Supervises → inverse-hint-integrity-agent (#18) [Inherits hints.rs & NitroValidator]
└── Supervises → signer-lifecycle-agent (#19) [Inherits TEEProverRegistry]
```

---

## Activation Rules

- Load an oracle SKILL.md when its domain (global/, playbooks/, ubuntu-rpc, fault dispute, delayed WETH, multiproof TEE) is being modified or audited.
- Load a sub-agent SKILL.md when its specific contract function or invariant test is being executed.
- `verification-agent` is loaded before any finding submission.
- `cleanup-agent` is loaded at every session end without exception.
