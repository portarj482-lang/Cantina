import { LamportClock, SimulationClock, HashLinkedTemporalAudit } from "./index.ts";

const a = new LamportClock("agent-a");
const b = new LamportClock("agent-b");
const first = a.tick();
const merged = b.observe(first);
const simulation = new SimulationClock("scenario-alpha", 0, "steps");
simulation.advance(3);
simulation.rewindTo(1);
const audit = new HashLinkedTemporalAudit();
audit.append({ actor: "demo", action: "simulation.rewound", subjectId: "scenario-alpha", details: { from: 3, to: 1 } });

console.log(JSON.stringify({
  lamport: { agentA: a.current(), agentB: merged },
  simulationTime: simulation.now(),
  auditValid: audit.verify().valid,
  note: "Logical and simulation time are separate from wall-clock time.",
}, null, 2));
