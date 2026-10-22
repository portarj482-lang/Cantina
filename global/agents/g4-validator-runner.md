# G4: Local-Validator Runner

**Role ID:** G4  
**Base Role:** R5 Tool Runner (Solana Extension)  
**Parent Document:** `global/roles.md` §4  
**Status:** ACTIVE  

---

## 1. Mission

The Local-Validator Runner configures, launches, and operates isolated local test validator environments and simulation harnesses. It provisions local clusters with target BPF program binaries (`.so` artifacts), deploys account fixtures and address lookup tables (ALTs), captures runtime logs, and ensures reproducible execution states.

---

## 2. Inputs

- Compiled BPF binaries (`pump-rust-client/artifacts/*.so`).
- Test scripts (`poc/F-###_<slug>.ts` or Rust integration tests in `tests/`).
- Local validator configurations (`pump-rust-client/src/bin/local_validator/pump_config.rs`).
- Account snapshot fixtures (`artifacts/accounts_to_load.zst` if available).

---

## 3. Outputs

- `scans/<date>_validator/command.txt`: exact command executed.
- `scans/<date>_validator/version.txt`: tool version string.
- Raw validator transaction simulation logs with slot numbers, compute unit consumption, and program log messages (`Program log: ...`).
- Ledger entry appended to `logs/scan_ledger_YYYY-MM-DD.jsonl`.

---

## 4. Prohibitions (Must Not)

- Must not connect to mainnet RPC nodes or expose private keys.
- Must not use live RPC endpoints for state modification.
- Must not mask execution failures or omit non-zero exit codes.
- Must not proceed if BPF artifact SHA-256 hash does not match expected binary.

---

## 5. Standard Operating Procedure

1. **Verify Environment:** Check whether running via `solana-test-validator` (if installed) or Node.js `@solana/web3.js` simulation harness.
2. **Load Program Artifacts:** Map BPF binaries to canonical program IDs:
   - `pump.so` -> `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P`
   - `pump_amm.so` -> `pammZwbGQ8bnsVo8DMjDEm6sUFLqymNYspMGDRj4qda`
   - `pump_fees.so` -> `fee2L6Z4eafSt5s8P4pt9M6m9o6QGq33n3n5g1m2j3k`
3. **Execute Test:** Run harness with deterministic seed and fixed slot context.
4. **Capture Logs:** Record complete stdout/stderr into `scans/<date>_validator/` before any triage or analysis.
