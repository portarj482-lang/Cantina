# GUMC + CPI Temporal Interoperability Layer

## Purpose
The Temporal Interoperability Layer (TIL) represents time values with explicit semantics and only performs conversions through registered mappings. It does not claim physical time travel or guarantee that all temporal models are mutually convertible.

## Supported temporal bases
- `utc-instant`: a calendar instant with an explicit timezone offset or `Z`.
- `monotonic-duration`: elapsed-time measurement tied to a specific monotonic clock and lifetime.
- `logical-clock`: event-order counter tied to a clock identity and epoch/run.
- `event-time`: timestamp supplied by the event source.
- `processing-time`: time at which a processor handled an event.
- `simulation-time`: a model-local time coordinate tied to a simulation and epoch.
- `model-version`: ordering/version position in a model lineage.
- `transaction-time`: database record history coordinate.

The schema is an initial engineering taxonomy, not an exhaustive scientific classification.

## Safety rules
1. Never implicitly convert between bases.
2. Keep the source value and provenance; conversions add a derived representation rather than overwriting the source.
3. Unknown mappings defer; invalid mappings reject or isolate.
4. Candidate conversions need evidence references before being marked verified.
5. Conditional/lossy mappings require an explicit limited-acceptance decision.
6. Simulation time must remain isolated from production clocks and side effects.
7. A timestamp is not a causal proof. Distributed ordering requires explicit causal metadata or a suitable logical-clock protocol.
8. Rollback of local state cannot reverse external side effects; use idempotency keys and compensating actions where needed.

## Integration
Import the layer from `src/temporal/index.ts`. CPI can use `evaluateTemporalTransition` to produce a proposal and a policy decision. A separate authorization service must decide whether a transition is allowed in production. This starter module is not an authenticated governance service and its evidence IDs are references, not cryptographic proof.

## Suggested next steps
- Add branded/discriminated types for each basis to prevent invalid combinations at compile time.
- Add a reviewed mapping registry with signatures and versioning.
- Add monotonic clock adapters for each runtime and test process-restart behavior.
- Add Lamport/vector-clock metadata for distributed causality where needed.
- Add persistence, append-only audit records, and independent approval.
- Add property-based tests for conversion invariants and round-trip guarantees.
