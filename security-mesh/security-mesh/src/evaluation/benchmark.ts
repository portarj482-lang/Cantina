export interface BenchmarkCase {
  id: string;
  expectedFinding: boolean;
  detectedFinding: boolean;
  pocExpected?: boolean;
  pocReproduced?: boolean;
  durationMs?: number;
  costUsd?: number;
}

export interface BenchmarkScore {
  cases: number;
  truePositives: number;
  falsePositives: number;
  falseNegatives: number;
  trueNegatives: number;
  precision: number | null;
  recall: number | null;
  f1: number | null;
  pocReproductionRate: number | null;
  meanDurationMs: number | null;
  totalCostUsd: number | null;
}

/** Scores only labeled benchmark results; it does not determine reportability or severity. */
export function scoreBenchmark(results: BenchmarkCase[]): BenchmarkScore {
  const ids = new Set<string>();
  let tp = 0, fp = 0, fn = 0, tn = 0;
  const poc = results.filter((item) => item.pocExpected !== undefined && item.pocReproduced !== undefined);
  for (const item of results) {
    if (!item.id || ids.has(item.id)) throw new Error('Benchmark case IDs must be non-empty and unique.');
    ids.add(item.id);
    if (item.expectedFinding && item.detectedFinding) tp++;
    else if (!item.expectedFinding && item.detectedFinding) fp++;
    else if (item.expectedFinding) fn++;
    else tn++;
  }
  const precision = tp + fp ? tp / (tp + fp) : null;
  const recall = tp + fn ? tp / (tp + fn) : null;
  const f1 = precision !== null && recall !== null && precision + recall > 0 ? 2 * precision * recall / (precision + recall) : null;
  const durations = results.flatMap((item) => item.durationMs !== undefined && Number.isFinite(item.durationMs) && item.durationMs >= 0 ? [item.durationMs] : []);
  const costs = results.flatMap((item) => item.costUsd !== undefined && Number.isFinite(item.costUsd) && item.costUsd >= 0 ? [item.costUsd] : []);
  return {
    cases: results.length, truePositives: tp, falsePositives: fp, falseNegatives: fn, trueNegatives: tn,
    precision, recall, f1,
    pocReproductionRate: poc.length ? poc.filter((item) => item.pocExpected === item.pocReproduced).length / poc.length : null,
    meanDurationMs: durations.length ? durations.reduce((sum, value) => sum + value, 0) / durations.length : null,
    totalCostUsd: costs.length ? costs.reduce((sum, value) => sum + value, 0) : null,
  };
}
