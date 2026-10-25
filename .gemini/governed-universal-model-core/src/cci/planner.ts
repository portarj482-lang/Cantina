import type { ComplexityAssessment, SolverPlan } from "./types.ts";

/**
 * Conservative resource-planning helper. It does not infer P/NP membership
 * from runtime measurements and never treats a timeout as proof of unsatisfiability.
 */
export function planSolver(
  assessment: ComplexityAssessment,
  options: { budgetMs: number; exactPreferred?: boolean; verifiedCandidateAvailable?: boolean },
): SolverPlan {
  if (!Number.isFinite(options.budgetMs) || options.budgetMs <= 0) {
    throw new Error("budgetMs must be a positive finite number");
  }
  if (assessment.timeBudgetMs !== undefined &&
      (!Number.isFinite(assessment.timeBudgetMs) || assessment.timeBudgetMs <= 0)) {
    throw new Error("assessment.timeBudgetMs must be a positive finite number when provided");
  }
  if (assessment.memoryBudgetBytes !== undefined &&
      (!Number.isSafeInteger(assessment.memoryBudgetBytes) || assessment.memoryBudgetBytes <= 0)) {
    throw new Error("assessment.memoryBudgetBytes must be a positive safe integer when provided");
  }

  if (assessment.status === "unknown" || assessment.classLabel === "unknown" || assessment.classLabel === "not-classified") {
    return {
      method: "defer",
      rationale: ["Complexity or problem formulation is not sufficiently established.", "Collect a formal formulation or benchmark before selecting a strategy."],
      hardBudgetMs: options.budgetMs,
      requiresIndependentVerification: true,
    };
  }

  if (options.verifiedCandidateAvailable) {
    return {
      method: "defer",
      rationale: [
        "A candidate was reported as available, but this planner does not execute or independently verify candidates.",
        "Route the candidate to a separate verifier; do not treat planner output as proof of correctness.",
      ],
      hardBudgetMs: Math.min(options.budgetMs, assessment.timeBudgetMs ?? options.budgetMs),
      requiresIndependentVerification: true,
    };
  }

  if (assessment.classLabel === "NP-complete" || assessment.classLabel === "NP-hard") {
    return {
      method: options.exactPreferred
        ? "bounded-search"
        : "heuristic",
      rationale: [
        "The supplied assessment labels the problem NP-hard or NP-complete; this helper trusts that label only as input metadata.",
        options.exactPreferred
          ? "Use exact search only under a hard resource budget; budget exhaustion means unresolved, not impossible."
          : "Use a heuristic to find candidates, then verify candidates against the original constraints.",
      ],
      hardBudgetMs: Math.min(options.budgetMs, assessment.timeBudgetMs ?? options.budgetMs),
      requiresIndependentVerification: true,
    };
  }

  return {
    method: options.exactPreferred ? "exact" : "bounded-search",
    rationale: ["Select a method according to the declared problem formulation and available budget.", "Empirical timing does not establish a formal complexity class."],
    hardBudgetMs: Math.min(options.budgetMs, assessment.timeBudgetMs ?? options.budgetMs),
    requiresIndependentVerification: true,
  };
}
