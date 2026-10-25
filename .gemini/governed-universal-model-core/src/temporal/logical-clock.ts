/**
 * Lamport logical clock: tracks a causal ordering relation, not elapsed time.
 * A greater timestamp does not prove physical-time order for unrelated events.
 */
export class LamportClock {
  private counter = 0;
  readonly clockId: string;

  constructor(clockId: string) {
    if (!clockId.trim()) throw new Error("clockId is required");
    this.clockId = clockId;
  }

  tick(): number {
    this.counter += 1;
    return this.counter;
  }

  observe(remoteCounter: number): number {
    if (!Number.isSafeInteger(remoteCounter) || remoteCounter < 0) {
      throw new Error("remote counter must be a non-negative safe integer");
    }
    this.counter = Math.max(this.counter, remoteCounter) + 1;
    return this.counter;
  }

  current(): number {
    return this.counter;
  }
}
