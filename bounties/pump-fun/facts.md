# Facts: pump-fun

- FACT-001: In-scope smart contract: Pump deployed on Solana Devnet at 6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P. [SRC: scope.md:27 @2026-10-10] Status: CURRENT, captured 2026-10-10.
- FACT-002: In-scope smart contract: Pump Fees deployed on Solana Devnet at pfeeUxB6jkeY1Hxd7CsFCAjcbHA9rWtchMGdZ6VojVZ. [SRC: scope.md:28 @2026-10-10] Status: CURRENT, captured 2026-10-10.
- FACT-003: In-scope smart contract: Pump AMM deployed on Solana Devnet at pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA. [SRC: scope.md:29 @2026-10-10] Status: CURRENT, captured 2026-10-10.
- FACT-004: Only Devnet deployments of smart contracts are in-scope. Mainnet is strictly out-of-scope. [SRC: scope.md:30 @2026-10-10] Status: CURRENT, captured 2026-10-10.
- FACT-005: PoC submissions require Anchor test script (.ts or .rs) or manual reproduction using Solana CLI. [SRC: scope.md:46 @2026-10-10] Status: CURRENT, captured 2026-10-10.
- FACT-006: Verified IDL for Pump exists at pump-public-docs/idl/pump.json matching address 6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P. [SRC: pump-public-docs/idl/pump.json:2 @2026-10-10] Status: CURRENT, captured 2026-10-10.
- FACT-007: Verified IDL for Pump Fees exists at pump-public-docs/idl/pump_fees.json matching address pfeeUxB6jkeY1Hxd7CsFCAjcbHA9rWtchMGdZ6VojVZ. [SRC: pump-public-docs/idl/pump_fees.json:2 @2026-10-10] Status: CURRENT, captured 2026-10-10.
- FACT-008: Verified IDL for Pump AMM exists at pump-public-docs/idl/pump_amm.json matching address pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA. [SRC: pump-public-docs/idl/pump_amm.json:2 @2026-10-10] Status: CURRENT, captured 2026-10-10.
- FACT-009: Ten candidate properties (INV-001 through INV-010) are listed in threat_model.md; they are documentation-derived hypotheses, not verified protocol invariants. [SRC: threat_model.md:68 @2026-10-14] Status: CURRENT, corrected 2026-10-14.
- FACT-010: Synthetic migration calculates pool part quote cost as ceil(pool_quote * out / (pool_base - out)) for buy_v3 and tokens out as floor((in - 1) * pool_base / (pool_quote + in - 1)) for buy_exact_quote_in_v3. [SRC: pump-public-docs/docs/SYNTHETIC_MIGRATION.md:34 @2026-10-10] Status: CURRENT, captured 2026-10-10.
- FACT-011: PumpSwap virtual quote reserves are adjusted downward by protocol and creator fees waiting in the quote vault, rendering virtual_quote_reserves negative on non-boosted pools. [SRC: pump-public-docs/docs/VIRTUAL_QUOTE_RESERVES_FEE_ADJUSTMENT.md:15 @2026-10-10] Status: CURRENT, captured 2026-10-10.
- FACT-012: Pipeline runner deployed at global/tools/run_pipeline.sh providing stage execution with automated ledger logging and scope hash validation. [SRC: global/tools/run_pipeline.sh:1 @2026-10-11] Status: CURRENT, captured 2026-10-11.
- FACT-013: Provenance audit reported 0 flags in 2 finding files; this result is not a six-gate readiness check. [TOOL: scans/2026-10-11_gate/gate_audit.json] Status: CURRENT, corrected 2026-10-14.
- FACT-014: The F-001 TypeScript harness's internal assertions passed in an offline simulation; it manually models migration and sweeps and does not invoke the Pump program. This does not establish deployed-program behavior. [TOOL: logs/poc_ledger_2026-10-11.jsonl] Status: CURRENT, corrected 2026-10-14.
- FACT-015: F-001 was refuted only within the assumptions encoded in its offline model. The model and documentation do not establish the deployed `migrate_v2` instruction's behavior. [UNKNOWN] Status: CURRENT, corrected 2026-10-14.
- FACT-016: Official Rust SDK crate pump-rust-client v0.4.0 (git sha 4196facf3845d57315ef685b9a470aece190cb3e) downloaded from crates.io and extracted into bounties/pump-fun/pump-rust-client; provides BPF artifacts for pump.so, pump_amm.so, pump_fees.so, and exact math and instruction models. [SRC: pump-rust-client/.cargo_vcs_info.json:3 @2026-10-11] Status: CURRENT, captured 2026-10-11.



- FACT-017: The H-003 harness computes a decimal-scaling comparison from hard-coded values; it does not execute the target program, and its result is not proof of scale invariance. [UNKNOWN] Status: CURRENT, corrected 2026-10-14.
- FACT-018: The H-004 harness does not establish the deployed program's accepted quote-mint set or Token-2022 extension behavior. Those behaviors remain unverified against the target program. [UNKNOWN] Status: CURRENT, corrected 2026-10-14.
- FACT-019: The H-005 harness does not execute either program's CTO instructions; signer and account validation behavior remains unverified against the target program. [UNKNOWN] Status: CURRENT, corrected 2026-10-14.
- FACT-020: The H-006 harness does not execute `extend_account`; permissioning, idempotence, and denial-of-service impact remain unverified against the target program. [UNKNOWN] Status: CURRENT, corrected 2026-10-14.
