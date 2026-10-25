import type { Classification, TaskCategory } from "./types.ts";

/** Transparent starter classifier. Production deployments should replace or augment it with evaluated classifiers. */
export function classifyTask(task: string, requestedAction = ""): Classification {
  const text = `${task} ${requestedAction}`.toLowerCase();
  const rules: Array<{ category: TaskCategory; terms: string[] }> = [
    { category: "external-action", terms: ["send email", "delete", "deploy", "transfer", "purchase", "submit transaction", "execute command", "write to database"] },
    { category: "coding", terms: ["code", "typescript", "python", "compile", "debug", "test", "function", "smart contract"] },
    { category: "research", terms: ["research", "sources", "latest", "look up", "find information"] },
    { category: "analysis", terms: ["analyze", "analysis", "compare", "evaluate", "audit", "determine"] },
    { category: "planning", terms: ["plan", "roadmap", "steps", "architecture", "design"] },
    { category: "writing", terms: ["write", "draft", "rewrite", "summarize", "explain", "translate"] },
    { category: "classification", terms: ["classify", "categorize", "taxonomy", "label"] },
  ];
  const matches = rules.filter(rule => rule.terms.some(term => text.includes(term)));
  if (matches.length === 0) return { taskCategory: "unknown", confidence: 0.25, rationale: ["No explicit rule matched; do not treat this as a reliable semantic classification."], needsHumanReview: true };
  // Action-oriented matches take precedence; multiple non-action matches are ambiguous.
  const chosen = matches.find(m => m.category === "external-action") ?? matches[0]!;
  const ambiguous = matches.length > 1 && chosen.category !== "external-action";
  return {
    taskCategory: chosen.category,
    confidence: ambiguous ? 0.55 : 0.78,
    rationale: [`Matched explicit ${chosen.category} vocabulary.`, ...(ambiguous ? ["Multiple categories matched; route conservatively."] : [])],
    needsHumanReview: ambiguous || chosen.category === "external-action",
  };
}
