import { AGENT_REGISTRY } from '../agents/registry.js';

export type LayerState = 'active' | 'planned';
export type LayerExecutionMode = 'agent-dispatch' | 'isolated-runner' | 'api-gated';

export interface LayerStep {
  id: string;
  agentId: string;
  dependsOn: string[];
  inputContract: string;
  outputContract: string;
}

/** Shared workflow shell: layer agents propose/transform; parent Oracle owns decisions. */
export interface LayerDefinition {
  id: string;
  version: string;
  state: LayerState;
  executionMode: LayerExecutionMode;
  parentOracle: string;
  purpose: string;
  entryRequirements: string[];
  steps: LayerStep[];
  authorityBoundary: string;
}

export const LAYER_REGISTRY: Readonly<Record<string, LayerDefinition>> = Object.freeze({
  source: {
    id: 'source', version: '1.0.0', state: 'active', executionMode: 'api-gated', parentOracle: 'source-coordinator',
    purpose: 'Bind authorized scope, repository, commit, and source provenance before analysis through the source-pin API gate.',
    entryRequirements: ['active_authorized_scope', 'target_in_scope'],
    steps: [
      { id: 'pin', agentId: 'source-pin', dependsOn: [], inputContract: 'authorized-target-v1', outputContract: 'source-attestation-v1' },
    ],
    authorityBoundary: 'No worker may infer authorization or widen target scope.',
  },
  analysis: {
    id: 'analysis', version: '1.0.0', state: 'active', executionMode: 'agent-dispatch', parentOracle: 'pipeline-orchestrator',
    purpose: 'Produce bounded source-graph and pattern leads, then synthesize review proposals.',
    entryRequirements: ['analysis_workflow', 'bounded_source_input', 'trusted_solc_ast'],
    steps: [
      { id: 'pathway', agentId: 'pathway-scout', dependsOn: [], inputContract: 'solc-ast-v1', outputContract: 'pathway-graph-v1' },
      { id: 'patterns', agentId: 'bounty-scanner', dependsOn: [], inputContract: 'source-map-v1', outputContract: 'pattern-leads-v1' },
      { id: 'strategist', agentId: 'lead-security-auditor', dependsOn: ['pathway', 'patterns'], inputContract: 'analysis-proposals-v1', outputContract: 'strategist-proposal-v1' },
    ],
    authorityBoundary: 'Outputs are leads/proposals only; no finding verdict, gate pass, or state transition.',
  },
  execution: {
    id: 'execution', version: '1.0.0', state: 'active', executionMode: 'isolated-runner', parentOracle: 'execution-coordinator',
    purpose: 'Run approved build, baseline-test, and Slither profiles; PoC/fork profiles remain disabled.',
    entryRequirements: ['human_approved_run', 'verified_scope_and_method', 'pinned_source', 'isolated_runner'],
    steps: [
      { id: 'foundry-tests', agentId: 'forge-unit-runner', dependsOn: [], inputContract: 'approved-suite-request-v1', outputContract: 'runner-receipt-v1' },
      { id: 'static-analysis', agentId: 'slither-runner', dependsOn: [], inputContract: 'approved-static-analysis-v1', outputContract: 'runner-receipt-v1' },
    ],
    authorityBoundary: 'No analysis worker can launch execution; unimplemented or out-of-scope PoCs remain disabled.',
  },
  evidence: {
    id: 'evidence', version: '1.0.0', state: 'active', executionMode: 'api-gated', parentOracle: 'evidence-coordinator',
    purpose: 'Verify artifact integrity, provenance, and required evidence contracts.',
    entryRequirements: ['workflow_evidence'],
    steps: [
      { id: 'verify', agentId: 'proof-gate', dependsOn: [], inputContract: 'evidence-set-v1', outputContract: 'evidence-proposal-v1' },
    ],
    authorityBoundary: 'Verification proposals do not set readiness gates or finding status.',
  },
  review: {
    id: 'review', version: '1.0.0', state: 'active', executionMode: 'api-gated', parentOracle: 'review-coordinator',
    purpose: 'Prepare independent review proposals for human adjudication.',
    entryRequirements: ['evidence_review_stage', 'verified_evidence'],
    steps: [
      { id: 'independent-review', agentId: 'independent-reviewer', dependsOn: [], inputContract: 'finding-evidence-v1', outputContract: 'review-proposal-v1' },
    ],
    authorityBoundary: 'Agents cannot accept findings or authorize submission.',
  },
  reporting: {
    id: 'reporting', version: '1.0.0', state: 'active', executionMode: 'api-gated', parentOracle: 'reporting-coordinator',
    purpose: 'Prepare a report draft from reviewed, evidence-backed findings.',
    entryRequirements: ['supported_finding', 'accepted_review', 'human_authorization_for_submission'],
    steps: [
      { id: 'draft', agentId: 'report-writer', dependsOn: [], inputContract: 'reviewed-finding-v1', outputContract: 'report-draft-v1' },
    ],
    authorityBoundary: 'Drafting is not submission; external submission remains a separate human-authorized action.',
  },
});

export function getLayer(id: string): LayerDefinition | undefined { return LAYER_REGISTRY[id]; }

export function validateLayerRegistry(): string[] {
  const issues: string[] = [];
  const agents = new Set(AGENT_REGISTRY.map((agent) => agent.id));
  for (const [key, layer] of Object.entries(LAYER_REGISTRY)) {
    if (key !== layer.id) issues.push(`layer key/id mismatch: ${key}`);
    const stepIds = new Set(layer.steps.map((step) => step.id));
    if (stepIds.size !== layer.steps.length) issues.push(`duplicate step in layer: ${key}`);
    for (const step of layer.steps) {
      if (!agents.has(step.agentId)) issues.push(`unknown agent ${step.agentId} in layer ${key}`);
      for (const dependency of step.dependsOn) if (!stepIds.has(dependency)) issues.push(`unknown dependency ${dependency} in layer ${key}`);
      if (step.dependsOn.includes(step.id)) issues.push(`self dependency ${step.id} in layer ${key}`);
    }
    if (!layer.authorityBoundary.trim() || !layer.version.trim() || !layer.parentOracle.trim()) issues.push(`missing pinned contract metadata in layer ${key}`);
    if (layer.state === 'active' && !layer.executionMode) issues.push(`active layer ${key} has no execution mode`);
  }
  return issues;
}
