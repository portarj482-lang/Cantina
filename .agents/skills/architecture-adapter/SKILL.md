---
name: architecture-adapter
description: >-
  Provides host and architecture adaptation interfaces, discovery adapters, and workflow bindings
  to connect universal orchestrators and specialist agent pipelines to heterogeneous runtimes
  (EVM, Solana, Move, CosmWasm, Rust, POSIX/Linux, Cantina workspaces) under USAP.
---

# Architecture Adapter Skill (USAP Architecture)

## Overview
Adapters translate canonical requests into architecture-native operations and evidence. They decouple the universal orchestrator and agent pipelines from specific blockchain runtimes, platforms, operating systems, and repository structures.

---

## Adapter Protocol Contract
Every adapter implements the `ArchitectureAdapter` protocol (`universal_adaptive_engine.adapters.protocol.ArchitectureAdapter`):
1. `discover()`: Inspects the target repository and runtime, returning `TargetContext` and capability matrices.
2. `validate_contract(contract)`: Validates task contracts against architecture-specific safety boundaries.
3. `execute(task)`: Executes authorized operations and returns structured evidence envelopes.
4. `health_check()`: Reports runtime availability without masking failures.

---

## Implemented Adapter Family
- **`TargetDiscoveryAdapter`**: Discovers target repository layout, manifests (`foundry.toml`, `Anchor.toml`, `Cargo.toml`, `Move.toml`), and produces normalized `TargetContext`.
- **`EVMArchitectureAdapter`**: Exposes EVM/Solidity verification capabilities (Foundry `forge test`, `forge fuzz`, Hardhat).
- **`SolanaArchitectureAdapter`**: Exposes Solana/Anchor verification capabilities (`anchor test`, Cargo, account constraint checks).
- **`HostEnvironmentAdapter`**: Maps to standard POSIX/Linux systems, inspecting binaries, system specs, and performing sandboxed file operations with strict path-containment validation.
- **`CantinaBountyAdapter`**: Maps to Cantina Bug Bounty conventions, verifying `TargetContext`, scope lock digests, and bounty-specific safety rules.

---

## TargetContext Resolution & Pipeline Integration

```python
from universal_adaptive_engine.models.target_context import TargetContextResolver
from universal_adaptive_engine.adapters.discovery import TargetDiscoveryAdapter
from universal_adaptive_engine.adapters.evm_adapter import EVMArchitectureAdapter

# 1. Resolve normalized target context
target_ctx = TargetContextResolver.resolve(context={"target_root": "bounties/base"})

# 2. Bind architecture adapter
discovery_adapter = TargetDiscoveryAdapter(target_root=target_ctx.target_root)
if target_ctx.architecture == "evm":
    arch_adapter = EVMArchitectureAdapter(target_ctx)
```

Subagent workflows access target operations exclusively through `self.adapter` and `TargetContext`, ensuring:
- Dynamic discovery without hardcoded repository or contract paths
- Architecture-appropriate test execution (no EVM commands forced on Solana programs)
- Accurate reporting of `NOT_APPLICABLE` or `NOT_VERIFIED` for unavailable runtimes
- Safe filesystem containment within `target_root`
