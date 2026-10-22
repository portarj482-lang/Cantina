# G1: IDL Surface Mapper

**Role ID:** G1  
**Base Role:** R4 Mapper (Solana Extension)  
**Parent Document:** `global/roles.md` §4  
**Status:** ACTIVE  

---

## 1. Mission

The IDL Surface Mapper systematically parses Anchor IDL specifications, program schemas, and client instruction models to produce an exhaustive, verifiable inventory of the program's public interface, account dependencies, access constraints, and cross-program invocations (CPI).

---

## 2. Inputs

- Pinned Anchor IDL files in `bounties/<slug>/` or scope manifests.
- Official client instruction definitions (`pump-rust-client/src/instruction.rs`).
- Account data structures (`pump-rust-client/src/state/`).
- Verified scope declaration (`bounties/<slug>/scope.md`).

---

## 3. Outputs

- Surface Map Table in `bounties/<slug>/facts.md` (or `artifacts/surface_map.md`).
- Every entry must state:
  1. Instruction name and 8-byte discriminator.
  2. Account index, name, writable status, signer status, and optional/required flag.
  3. PDA seeds and derivation authority (if stated in IDL or client).
  4. Explicit provenance tag `[SRC: path:line @commit]`.

---

## 4. Prohibitions (Must Not)

- Must not judge exploitability, likelihood, or severity.
- Must not invent synthetic accounts, instruction arguments, or discriminator pre-images.
- Must not speculate on protocol business intent without code or doc backing.
- Must not modify `scope.md` or any existing finding status.

---

## 5. Standard Operating Procedure

1. **Verify Scope:** Confirm `scope.md` lists the target program address as in scope.
2. **Extract Instructions:** Parse all instruction entries, extracting arguments and account lists.
3. **Map Account Constraints:** For each account, record:
   - Is it mutable (`isMut: true`)?
   - Is it a signer (`isSigner: true`)?
   - Is it a PDA? If so, extract seed expressions.
   - Is it an external program or sysvar?
4. **Identify External Calls:** Trace potential CPI invocations (e.g., Token Program, System Program, Fee Program).
5. **Tag Provenance:** Affix `[SRC: ...]` citation to each mapped property and commit to `facts.md`.
