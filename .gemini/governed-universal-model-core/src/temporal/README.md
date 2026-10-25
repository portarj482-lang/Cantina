# Temporal module

This module treats temporal bases as distinct types of meaning. UTC instants, durations, logical counters, simulation coordinates, and model versions must not be implicitly converted into one another.

- `TemporalMappingRegistry`: explicit mapping catalog; production registration needs authenticated review.
- `LamportClock`: causal-order helper, not a physical clock.
- `SimulationClock`: isolated manually advanced clock.
- `HashLinkedTemporalAudit`: hash-linked in-memory demonstration; not tamper-proof durable storage.
- `evaluateTemporalTransition`: validates a registered conversion and returns a conservative decision.

No component here implements physical time travel. Simulation rewind changes only the simulation-local counter.
