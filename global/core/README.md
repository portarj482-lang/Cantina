# Cantina Core: immutable case state

This is a small, standard-library reference layer for case identity, evidence relationships, and versioned state. It adapts useful ideas from the supplied Tri-Nova description to Cantina's evidence workflow; it is not a port of the linked Tri-Nova module, which was unavailable for inspection.

| Concept | Cantina implementation |
|---|---|
| Identity anchor | Bounty slug, scope SHA-256, optional source commit |
| Closure / invariants | Strict record validation, artifact hashes, safe paths, valid references |
| Topology | Directed acyclic graph linking evidence and research artifacts |
| Governance | Bounded lifecycle: OPEN → STABILIZED → SEALED; no automated report approval |
| Causal history | Sequence number and parent-state SHA-256 |
| Evolution | New immutable successor; a sealed parent can only produce a new OPEN successor |
| Composition root | Existing bounty workflow and agents remain the orchestrators |

The full source review and adaptation decisions are in `tri_nova-adaptation.md`.
It separates implementable controls from duplicated or non-verifiable claims.

Use case_state.schema.json for the serialized contract and case_state.py to verify a snapshot and its in-bounty artifact hashes:

    python global/core/case_state.py --case bounties/<slug>/artifacts/case-state.json --bounty-root bounties/<slug>

For a successor snapshot, pass its previous case file using --parent. This verifies identity continuity, sequence, allowed phase movement, retained graph records, and the parent digest. A VALIDATED result means only that the snapshot is structurally and cryptographically consistent; it is not evidence that a vulnerability is valid or that a report is ready.

The digest is an integrity check, not a signature or proof of authorship. Preserve prior snapshots and their digests in the bounty's normal evidence records.

The case snapshot complements, and does not replace, the existing scope snapshot, ledgers, evidence seal, finding files, or human review.
