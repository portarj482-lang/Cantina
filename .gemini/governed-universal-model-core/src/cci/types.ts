export type ComplexityClassLabel = "P" | "NP" | "NP-hard" | "NP-complete" | "unknown" | "not-classified";

export interface ComplexityEvidence {
  readonly kind: "theorem" | "reduction" | "literature" | "empirical-profile" | "heuristic";
  readonly reference: string;
  readonly reviewed: boolean;
}

export interface ComplexityAssessment {
  readonly problemId: string;
  readonly formulation: "decision" | "optimization" | "search" | "verification" | "unknown";
  readonly classLabel: ComplexityClassLabel;
  readonly evidence: readonly ComplexityEvidence[];
  readonly inputSizeDescription: string;
  readonly expectedRuntime?: string;
  readonly memoryBudgetBytes?: number;
  readonly timeBudgetMs?: number;
  readonly status: "established-result" | "empirical-estimate" | "hypothesis" | "unknown";
  readonly caveats: readonly string[];
}

export interface SolverPlan {
  readonly method: "exact" | "heuristic" | "approximation" | "bounded-search" | "defer";
  readonly rationale: string[];
  readonly hardBudgetMs: number;
  readonly requiresIndependentVerification: boolean;
}
