# Universal Adaptive Engineering & Safety Rules

## 1. Authority Hierarchy
1. Applicable law, system isolation, and non-destructive safety constraints.
2. Platform execution policy: Ground Rule #2 (No live funds, fork-only execution, zero broadcast transactions).
3. Workspace invariants and approved scope manifests (`scope.md`).
4. Canonical contracts and adapter boundaries (`ArchitectureAdapter`).
5. Task criteria and evidence standards.

## 2. Evidence-Based Verification Standard
- Never claim an invariant, contract, tool, or fix is verified without reproducible evidence.
- A passing test proves behavior only under tested parameters; it is not universal proof.
- Checklists and static AST scans without executed test suites must report `COMPLETED_WITH_LIMITATIONS`.
- Negative controls and adversarial falsification checks are mandatory for all critical invariant evaluations.

## 3. Path Containment & Least Privilege
- All filesystem operations are bounded by `target_context.target_root` or `workspace_root`.
- Strict path containment (`Path.is_relative_to`) must be enforced on all inputs.
- Cross-target scope contamination is strictly prohibited. Standalone targets outside `bounties/` must evaluate without inheriting alien bounty scopes.
