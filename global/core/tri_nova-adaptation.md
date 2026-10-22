# Tri-Nova catalog: Cantina adaptation review

## Review result

The supplied text is a 656 KB, 44,155-line architecture catalog. It repeats engine, adapter, protocol, module, interface, artifact, and atomic-component inventories for several unrelated systems, then expands into abstract cognition, identity, governance, and closure constructs. The catalog is design input, not executable code or evidence that the named controls exist.

The useful transfer is a compact evidence-and-execution contract. Do not reproduce its six-system topology, nested “micro/atomic/molecular” agent hierarchy, or claimed universal guarantees in Cantina.

## Adaptable data and controls

| Source concept | Cantina form | Existing or added support |
|---|---|---|
| Identity anchor and version lineage | Bounty slug, exact scope digest, pinned source commit; stale evidence must not silently cross either boundary | Existing scope lock and continuity checks; `case_state.py` binds a case to these values |
| Immutable state and causal history | Version each case snapshot; link a child to its parent digest and monotonic sequence | `CaseState` is immutable and checks parent identity, sequence, digest, and retained records |
| Topology / traceability | Evidence graph with typed nodes (hypothesis, finding, source, tool, PoC, report, note) and typed links (supports, refutes, derived-from, depends-on) | `case_state.py` validates references, uniqueness, and acyclic topology |
| Artifact integrity | Record a bounty-relative path and SHA-256 for each graph artifact; verify bytes before relying on the snapshot | `case_state.py` rejects unsafe paths and verifies artifact hashes inside the selected bounty root |
| Deterministic execution | Preserve command, tool/version, pinned commit/block, inputs, environment-variable names, seed, limits, output and exit status | Existing run records and scan/PoC ledgers capture much of this; extend only where a concrete workflow lacks a field |
| Bounded runtime | Time, memory, CPU, scope, and path limits; stop safely on missing prerequisites | Existing tool gates and bounty boundaries apply. The catalog's distributed sandbox/runtime is not implemented here |
| Append-only audit and provenance | Preserve run/fact/finding history with source tags and hashes; distinguish source, tool output, PoC, assumption, and unknown | Existing append-only ledgers, evidence seals, provenance tags, and human review remain authoritative |
| Explicit lifecycle and uncertainty | OPEN → STABILIZED → SEALED snapshot lifecycle; “validated” only means structure/integrity checks passed | `case_state.py` reports structural validation only and always leaves authorization false |
| Schema and adapter boundaries | Version serialized records and reject unknown or malformed fields before processing | `case_state.schema.json` and strict parsing provide the case snapshot contract |

## Field-level extraction

These are the useful concrete fields from the catalog's job, execution, result, telemetry, and artifact protocols. Keep them attached to existing bounty records rather than creating a second orchestration system.

- **Case identity:** bounty slug, scope digest, source commit, chain, pinned block, and in-scope target/path. `case_state.py` currently enforces the slug, scope digest, and optional source commit; the other values remain in the bounty's existing scope/manifest records.
- **Hypothesis/evidence:** hypothesis or finding ID, lifecycle status, target, actor/attacker assumptions, invariant, reachability, predicted observation, impact, falsifiers, disposition, and evidence links. Existing hypothesis records and findings are the source of truth; graph node IDs provide links, not replacements.
- **Run request/context:** run ID, stage, tool and version, command, working directory, allowed inputs, environment-variable names (never secret values), timeout/resource limits, pinned commit/block, compiler/tool flags, and deterministic seed. Existing manifests, scan records, and run ledgers already hold most of this; add only fields missing from a real record schema.
- **Run result:** exit status, duration, stdout/stderr artifact paths, test count/outcomes, divergence, and explicit stop reason. Store raw output as an artifact and summaries as derived data; do not treat a summary flag as proof.
- **Artifact/provenance:** artifact ID, type, bounty-relative path, SHA-256, optional byte size, producer/run ID, source commit, and provenance tag (`SRC`, `TOOL`, `POC`, `LOCAL`, `WEB`, `USER`, `ASSUMPTION`, or `UNKNOWN`). The current case graph verifies path and digest; producer, size, and source-specific citations belong to the underlying artifact/run record.
- **Review decision:** policy/gate name, input artifact digests, pass/fail/hold reason, reviewer, and timestamp. Preserve human decisions as explicit records; a machine `PASS` must never imply authorization or report readiness.

The catalog's raw telemetry fields (node IDs, event types, timestamps, and generic payload maps) should not be added as a new always-on collection service. In this repository, capture only bounty-local run events needed to reproduce or audit a test, with secrets excluded and retention bounded by the existing bounty records.

## Do not port as written

- “Universal,” “eternal,” “absolute,” or “guaranteed” properties: they are assertions, not testable implementations.
- Continuous autonomous monitors, enforcement, self-modification, or cross-system dispatch: these exceed the bounty workflow's authorization model and are not needed for evidence management.
- Cryptographic identity, signatures, mutual TLS, immutable storage, or tamper-proof logging: SHA-256 hashes detect changes relative to a trusted copy; they do not authenticate authorship or prevent replacement.
- Confidence/entropy scores as proof: uncertainty may guide prioritization but cannot replace source citations, falsification, scope checks, or reproducible tests.
- Clock synchronization, OS matrices, syscall traces, simulation/geometry/energy engines, and model-training artifacts: these belong to the unrelated execution/engineering systems described in the catalog, not this repository's current smart-contract bounty workflow.
- Hundreds of nested agents and duplicate audit/provenance roles: Cantina already has bounded specialists, validators, ledgers, and human review; duplicating them adds coordination cost without evidence of improved coverage.
- “No reopening” as a claim that evidence can never evolve: a sealed snapshot stays unchanged, while a later review can be represented as a new linked snapshot. Sealing is not submission approval.

## Practical evidence flow

1. Pin the active bounty, scope digest, and source commit.
2. Record a falsifiable hypothesis and its assumptions.
3. Link the hypothesis to exact source, saved tool output, and reproduction artifacts; represent both supporting and refuting evidence.
4. Hash and validate the bounty-relative artifacts, graph, and snapshot lineage.
5. Keep unknowns visible and require human review for finding status or submission decisions.

This is a data-integrity and traceability layer only. It does not execute tests, establish that an artifact is genuine, validate a vulnerability, calculate severity, or authorize testing or disclosure.
