/**
 * A manually advanced simulation clock. It has no connection to wall-clock
 * time and cannot trigger production side effects by itself.
 */
export class SimulationClock {
  private currentValue: number;
  readonly simulationId: string;
  readonly unit: string;

  constructor(simulationId: string, initialTime = 0, unit = "ticks") {
    if (!simulationId.trim()) throw new Error("simulationId is required");
    if (!Number.isFinite(initialTime)) throw new Error("initialTime must be finite");
    this.simulationId = simulationId;
    this.unit = unit;
    this.currentValue = initialTime;
  }

  now(): number {
    return this.currentValue;
  }

  advance(delta: number): number {
    if (!Number.isFinite(delta) || delta < 0) throw new Error("delta must be finite and non-negative");
    this.currentValue += delta;
    return this.currentValue;
  }

  /** Rewind is explicitly simulation-local and never affects external state. */
  rewindTo(target: number): number {
    if (!Number.isFinite(target) || target > this.currentValue) {
      throw new Error("rewind target must be finite and no later than current simulation time");
    }
    this.currentValue = target;
    return this.currentValue;
  }
}
