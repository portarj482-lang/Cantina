---
name: multi-agent-oracle
description: >-
  Orchestrates the complete 3-Tier Multi-Agent Oracle Architecture for autonomous,
  deterministic security auditing, invariant falsification, and live execution.
  Coordinates Governance Oracles (G1 Global, G2 Playbook, G3 RPC, G7 Findings Normalization),
  Domain Invariant Oracles (G4 Dispute, G5 DelayedWETH, G6 Multiproof TEE),
  Target Sub-Oracles, and Sub-Surface Attestation Agents. Features automated test
  execution harnesses (Forge & Cargo), differential test runners, and proof-of-concept
  verification pipelines.
---

# Multi-Agent Oracle System (MAOS) Skill

## 1. System Overview & Hierarchy

The Multi-Agent Oracle System is a deterministic, role-partitioned architecture designed to conduct deep protocol verification, system invariant audits, and falsification test runs across EVM smart contracts, node precompiles, and zero-knowledge / TEE proof systems.

```mermaid
graph TD
    User([User / Lead Orchestrator]) --> G1[G1: Global Admin Oracle]
    G1 --> G2[G2: Playbook Admin Oracle]
    G1 --> G3[G3: RPC Admin Oracle]
    G1 --> G7[G7: Findings Normalization Oracle]
    
    G2 --> G4[G4: Fault Dispute Invariant Oracle]
    G2 --> G5[G5: DelayedWETH Invariant Oracle]
    G2 --> G6[G6: Multiproof TEE Invariant Oracle]
    
    G7 --> SO1[Pack E Normalization & Registry Governance]
    G7 --> SO2[Pack E Vulnerability Triage & Overlap Analysis]
```

---

## 2. Agent Tier Definitions & Roles

### Tier 1: Governance & Knowledge Oracles
* **G1: Global Admin Oracle (`global-admin-oracle`)**: Authoritative owner of `global/` knowledge bases, tooling registries (`global/tooling.md`), verified patterns (`global/patterns.md`), and cross-bounty lessons.
* **G2: Playbook Admin Oracle (`playbook-admin-oracle`)**: Authoritative owner of operational playbooks in `global/playbooks/` and orchestration workflows.
* **G3: RPC Admin Oracle (`rpc-admin-oracle`)**: Executes system-level RPC audits, socket probing, network isolation, and fork node state configurations.
* **G7: Findings Normalization Oracle (`findings-normalization-oracle`)**: Transforms supported security findings into consistent, machine-readable artifacts (`findings_normalized.json`) adhering to tool registry capability governance, evidence preservation, and explicit confirmation.

### Tier 2: Domain Invariant Oracles
* **G4: Fault Dispute Invariant Oracle (`dispute-invariant-oracle`)**: Verifies state transition game resolutions, l2Sender reentrancy, and subgame DAG validity.
* **G5: DelayedWETH Invariant Oracle (`delayed-weth-invariant-oracle`)**: Verifies WETH balance solvency, sub-account address space partitioning, and timelock monotonicity.
* **G6: Multiproof TEE Invariant Oracle (`multiproof-tee-invariant-oracle`)**: Audits AWS Nitro hardware attestation, PCR validation, P-384 inverse-hint transcripts, and signer lifecycle.

### Tier 3: Target Sub-Oracles & Sub-Surface Attestation Agents
Specialized execution agents that formulate exact boundary condition hypotheses and run localized fuzzing or invariant checks.

---

## 3. Operational Workflow: Bold Invariant Execution

When activated, MAOS enforces **active execution over passive review**:

1. **Hypothesis Formulation (FORM-HYP)**:
   - Identify candidate invariant breaks (e.g., balance conservation, rate-limit bypassing, storage slot collision).
   - Formulate hypothesis $H_n$ with explicit mathematical preconditions and expected postconditions.

2. **Concrete Verification Harness (BUILD-HARNESS)**:
   - Construct dedicated Foundry tests (`test/invariants/` or `test/unit/`) or Rust unit tests (`crates/.../tests/`).
   - Run tests with concrete execution commands:
     ```bash
     forge test --match-test <test_name> -vvvv
     cargo test --package <crate_name> --lib -- <test_name> --nocapture
     ```

3. **Active Falsification & Logging (EXEC-FALSIFY)**:
   - Run property-based fuzzers (Foundry fuzz runs >= 10,000 runs).
   - Capture exact gas consumption, execution traces, reverts, or assertion failures.
   - Record factual outcomes in `facts.md` and state transition logs in `state.md`.

4. **Verdict Categorization (VERDICT)**:
   - **KILLED**: Hypothesis definitively disproven via executable test passing with invariant intact.
   - **PROVEN**: Invariant violated; reproducible PoC trace generated with no external state dependencies.
   - **HOLD**: Requires external conditions not reproducible within bounded execution.

---

## 4. Operational Safety & Prompt Framing Guidelines

To ensure stable automated reasoning and prevent false positives from heuristic safety filters:
- Frame all audit activities using formal verification, protocol defense, and systems architecture terminology.
- Use terms such as:
  - *Invariant boundary validation* instead of penetration jargon.
  - *State falsification harness* instead of attack script.
  - *Timelock monotonicity & revocation verification* instead of access bypass.
  - *Hardware enclave attestation & transcript verification* instead of spoofing.

---

## 5. Toolchain Integrations

| Tool | Binary / Command | Purpose |
|---|---|---|
| **Forge** | `~/.foundry/bin/forge` | EVM contract compilation, fuzzing, trace analysis |
| **Cargo** | `~/.cargo/bin/cargo` | Native Rust precompile compilation & unit/fuzz tests |
| **Cast** | `~/.foundry/bin/cast` | ABI encoding/decoding, storage slot indexing |
| **RPC Prober** | `rpcinfo`, `rpcbind`, `curl` | Local node endpoint validation and dual-mode testing |
