export interface AgentProfile {
  id: string;
  stage: string;
  responsibility: string;
  skillPackIds: string[];
  skillVersion: string;
  skillTrustState: string;
  knowledgeCollections: string[];
  toolAllowlist: string[];
  readPermissions: string[];
  writePermissions: string[];
  sandboxProfile: string;
  networkProfile: string;
  maxRuntimeSeconds: number;
  maxOutputTokens: number;
  enabledForEvm: boolean;
  dependencies: string[];
  inputSchema: string;
  outputSchema: string;
  approvalRequired: boolean;
  retryLimit: number;
}

export interface ToolCapability {
  toolId: string;
  description: string;
  implementationStatus: string;
  dispatchEnabled: boolean;
  agentCallable: boolean;
}

interface RawAgentDef {
  id: string;
  stage: string;
  group: string;
  responsibility: string;
  evm?: boolean;
  deps?: string[];
}

const defs: RawAgentDef[] = [
  { id: 'pipeline-orchestrator', stage: 'T0', group: 'orchestration', responsibility: 'Coordinates durable workflow transitions, dependencies, dispatch, retries, cancellation, and recovery.' },
  { id: 'lead-security-auditor', stage: 'T0', group: 'analysis', responsibility: 'Maintains hypotheses, prioritizes candidates, coordinates technical review, and prepares evidence-backed drafts.' },
  { id: 'source-pin', stage: 'S1', group: 'source', responsibility: 'Verifies repository identity, commit SHA, clean build copy, and immutable source manifest.' },
  { id: 'recon', stage: 'S1', group: 'source', responsibility: 'Maps authorized contracts, addresses, chains, compiler configuration, and target facts.' },
  { id: 'pathway-scout', stage: 'S1', group: 'source', responsibility: 'Maps public entrypoints, roles, call paths, and dependencies from the pinned source.' },
  { id: 'bounty-scanner', stage: 'S2', group: 'static', responsibility: 'Generates source-backed vulnerability-pattern leads; never certifies findings.' },
  { id: 'slither-runner', stage: 'S2', group: 'static', responsibility: 'Requests approved Slither profile execution and normalizes actual structured output.' },
  { id: 'aderyn-runner', stage: 'S2', group: 'static', responsibility: 'Requests approved Aderyn profile execution and normalizes actual structured output.' },
  { id: 'forge-inspect-layout', stage: 'S2', group: 'static', responsibility: 'Extracts storage layout and slot metadata from pinned compiler output.' },
  { id: 'layout-diff', stage: 'S2', group: 'static', responsibility: 'Compares source-pinned storage layouts across approved implementations or revisions.' },
  { id: 'sarif-collector', stage: 'S2', group: 'static', responsibility: 'Aggregates, normalizes, and deduplicates scanner SARIF results.' },
  { id: 'solidity-auditor', stage: 'S2', group: 'analysis', responsibility: 'Analyzes access control, state transitions, external calls, and logic flaws.' },
  { id: 'evm-signature', stage: 'S2', group: 'analysis', responsibility: 'Analyzes EIP-7702, ERC-1271, ECDSA, digest handling, and call semantics.' },
  { id: 'forge-unit-runner', stage: 'S3', group: 'dynamic', responsibility: 'Requests the immutable baseline Foundry test profile and records receipts.' },
  { id: 'forge-fuzz-runner', stage: 'S3', group: 'dynamic', responsibility: 'Requests bounded Foundry fuzz runs with recorded seed and budget.' },
  { id: 'forge-invariant-runner', stage: 'S3', group: 'dynamic', responsibility: 'Requests approved Foundry invariant suites under declared bounds.' },
  { id: 'echidna-executor', stage: 'S3', group: 'dynamic', responsibility: 'Requests approved Echidna campaign profiles with enforced budgets.' },
  { id: 'medusa-executor', stage: 'S3', group: 'dynamic', responsibility: 'Requests approved Medusa campaign profiles with enforced budgets.' },
  { id: 'halmos-provers', stage: 'S4', group: 'symbolic', responsibility: 'Requests symbolic suites for explicitly declared properties and assumptions.' },
  { id: 'halmos-arithmetic', stage: 'S4', group: 'symbolic', responsibility: 'Analyzes arithmetic properties, rounding, and solver bounds.' },
  { id: 'halmos-guards', stage: 'S4', group: 'symbolic', responsibility: 'Analyzes authorization properties and guarded state transitions.' },
  { id: 'halmos-proofing', stage: 'S4', group: 'symbolic', responsibility: 'Evaluates declared properties within explicit symbolic bounds and assumptions.' },
  { id: 'halmos-counterexample', stage: 'S4', group: 'symbolic', responsibility: 'Extracts counterexamples and separates them from timeout or unsupported outcomes.' },
  { id: 'counterexample-tracer', stage: 'S4', group: 'dynamic', responsibility: 'Replays supported counterexamples in an approved disposable harness.' },
  { id: 'normalize-file', stage: 'S5', group: 'normalization', responsibility: 'Resolves source paths and rejects paths outside the approved source manifest.' },
  { id: 'normalize-line', stage: 'S5', group: 'normalization', responsibility: 'Validates source excerpts and line ranges against the pinned revision.' },
  { id: 'normalize-rule', stage: 'S5', group: 'normalization', responsibility: 'Maps detector output to program-compatible vulnerability categories.' },
  { id: 'known-tags-scan', stage: 'S6', group: 'overlap', responsibility: 'Checks recorded program known issues, exclusions, and duplicate tags.' },
  { id: 'known-accepted-risk', stage: 'S6', group: 'overlap', responsibility: 'Identifies documented accepted risks and intentional design decisions.' },
  { id: 'known-overlap-annotator', stage: 'S6', group: 'overlap', responsibility: 'Annotates prior audit and disclosure overlap with exact coverage limitations.' },
  { id: 'deep-scanner', stage: 'S6', group: 'analysis', responsibility: 'Searches approved vulnerability-pattern and verified case-study collections.' },
  { id: 'triage-gemini-runner', stage: 'S7', group: 'llm', responsibility: 'Uses Gemini to suggest candidate clustering and falsification plans; output is advisory.' },
  { id: 'triage-schema-guard', stage: 'S7', group: 'normalization', responsibility: 'Rejects invalid schemas, types, unsupported claims, and unapproved enumerations.' },
  { id: 'triage-group', stage: 'S7', group: 'analysis', responsibility: 'Clusters candidates by probable root cause without deleting evidence.' },
  { id: 'triage-rank', stage: 'S7', group: 'analysis', responsibility: 'Prioritizes candidates against the applicable severity rubric and evidence strength.' },
  { id: 'triage-explain', stage: 'S7', group: 'analysis', responsibility: 'Defines concrete confirmation and falsification conditions for each hypothesis.' },
  { id: 'hallucination-dropper', stage: 'S8', group: 'evidence', responsibility: 'Flags unsupported assertions and routes them for evidence correction or inconclusive status.' },
  { id: 'foundry-engineer', stage: 'S9', group: 'dynamic', responsibility: 'Designs deterministic test harnesses, positive controls, negative controls, and regression tests.' },
  { id: 'forge-tester', stage: 'S9', group: 'dynamic', responsibility: 'Requests approved remote test suites and verifies that receipts are actual runner outputs.' },
  { id: 'impact-validator', stage: 'S9', group: 'evidence', responsibility: 'Validates prerequisites, downstream behavior, and measured impact.' },
  { id: 'proof-gate', stage: 'S9', group: 'evidence', responsibility: 'Applies deterministic receipt/evidence checks and records cross-provider discrepancies.' },
  { id: 'review-packet-builder', stage: 'S10', group: 'evidence', responsibility: 'Builds an immutable review packet with source refs, receipts, and artifact digests.' },
  { id: 'independent-reviewer', stage: 'S10', group: 'review', responsibility: 'Independently challenges hypothesis, reproduction, threat model, and impact.' },
  { id: 'report-writer', stage: 'S10', group: 'reporting', responsibility: 'Drafts a report only from validated evidence and clearly stated limitations.' },
  { id: 'g1-idl-mapper', stage: 'SOLANA', group: 'solana', evm: false, responsibility: 'Extracts and validates Anchor IDLs, account schemas, and instruction discriminators.' },
  { id: 'g2-binding-checker', stage: 'SOLANA', group: 'solana', evm: false, responsibility: 'Examines PDA derivations, signer seeds, and CPI authorization.' },
  { id: 'g3-conservation-checker', stage: 'SOLANA', group: 'solana', evm: false, responsibility: 'Tests SPL token and lamport conservation properties.' },
  { id: 'g4-validator-runner', stage: 'SOLANA', group: 'solana', evm: false, responsibility: 'Requests approved local Solana validator tests against pinned state.' },
  { id: 'g5-solana-poc', stage: 'SOLANA', group: 'solana', evm: false, responsibility: 'Designs reproducible Anchor or Bankrun test cases.' },
];

const toolsByGroup: Record<string, string[]> = {
  orchestration: ['workflow.read', 'workflow.transition', 'task.dispatch'],
  analysis: ['source.read', 'knowledge.search', 'gemini.triage'],
  source: ['scope.read', 'source-manifest.verify'],
  static: ['source.read', 'scanner.slither', 'scanner.aderyn', 'forge.layout'],
  dynamic: ['suite.request', 'receipt.read'],
  symbolic: ['suite.request', 'symbolic.halmos', 'receipt.read'],
  normalization: ['source-manifest.verify', 'finding.normalize'],
  overlap: ['knowledge.search', 'overlap.annotate'],
  llm: ['gemini.triage'],
  evidence: ['evidence.read', 'receipt.verify', 'artifact.hash'],
  review: ['evidence.read', 'review.submit'],
  reporting: ['evidence.read', 'report.draft'],
  solana: ['solana.suite.request', 'solana.receipt.read'],
};

const sandboxByGroup: Record<string, string> = {
  orchestration: 'analysis-readonly', analysis: 'analysis-readonly', source: 'analysis-readonly', static: 'static-analysis',
  dynamic: 'foundry-test', symbolic: 'symbolic-analysis', normalization: 'evidence-review', overlap: 'analysis-readonly',
  llm: 'analysis-readonly', evidence: 'evidence-review', review: 'evidence-review', reporting: 'reporting', solana: 'solana-test',
};

const networkByGroup: Record<string, string> = {
  orchestration: 'none', analysis: 'approved-docs-gateway', source: 'none', static: 'none', dynamic: 'approved-rpc-gateway',
  symbolic: 'none', normalization: 'none', overlap: 'approved-docs-gateway', llm: 'approved-docs-gateway',
  evidence: 'runner-internal-only', review: 'none', reporting: 'none', solana: 'none',
};

const specificDependencies: Record<string, string[]> = {
  recon: ['source-pin'],
  'pathway-scout': ['source-pin', 'recon'],
  'layout-diff': ['forge-inspect-layout'],
  'sarif-collector': ['slither-runner', 'aderyn-runner'],
  'forge-fuzz-runner': ['forge-unit-runner'],
  'forge-invariant-runner': ['forge-unit-runner'],
  'halmos-counterexample': ['halmos-provers'],
  'counterexample-tracer': ['halmos-counterexample'],
  'normalize-line': ['normalize-file'],
  'normalize-rule': ['normalize-file', 'normalize-line'],
  'known-accepted-risk': ['known-tags-scan'],
  'known-overlap-annotator': ['known-tags-scan', 'known-accepted-risk'],
  'triage-schema-guard': ['triage-gemini-runner'],
  'triage-group': ['triage-schema-guard'],
  'triage-rank': ['triage-group'],
  'triage-explain': ['triage-schema-guard'],
  'hallucination-dropper': ['triage-schema-guard', 'triage-explain'],
  'foundry-engineer': ['hallucination-dropper'],
  'forge-tester': ['foundry-engineer'],
  'impact-validator': ['forge-tester'],
  'proof-gate': ['impact-validator'],
  'review-packet-builder': ['proof-gate'],
  'independent-reviewer': ['review-packet-builder'],
  'report-writer': ['independent-reviewer'],
  'g2-binding-checker': ['g1-idl-mapper'],
  'g3-conservation-checker': ['g1-idl-mapper'],
  'g4-validator-runner': ['g1-idl-mapper'],
  'g5-solana-poc': ['g2-binding-checker', 'g3-conservation-checker', 'g4-validator-runner'],
};

function dependenciesFor(def: RawAgentDef): string[] {
  const specific = specificDependencies[def.id];
  if (specific) return specific;
  if (def.stage === 'S2') return ['source-pin', 'recon', 'pathway-scout'];
  if (def.stage === 'S3' || def.stage === 'S4') return ['source-pin', 'pathway-scout'];
  if (def.stage === 'S5') return ['source-pin'];
  if (def.stage === 'S6') return ['normalize-rule'];
  if (def.stage === 'S7') return ['normalize-rule', 'known-tags-scan'];
  if (def.stage === 'S8') return ['triage-schema-guard'];
  if (def.stage === 'S9') return ['hallucination-dropper'];
  if (def.stage === 'S10') return ['proof-gate'];
  return [];
}

export const AGENT_REGISTRY: readonly AgentProfile[] = Object.freeze(
  defs.map((def) => ({
    id: def.id,
    stage: def.stage,
    responsibility: def.responsibility,
    skillPackIds: def.group === 'solana' ? ['solana-security'] : [
      'evm-security-basics',
      ...(def.group === 'dynamic' ? ['reproducible-testing'] : []),
      ...(def.id === 'evm-signature' ? ['eip7702-erc1271-revocation'] : []),
      ...(def.group === 'evidence' || def.group === 'review' || def.group === 'reporting' ? ['evidence-provenance'] : []),
    ],
    skillVersion: '1.0.0',
    skillTrustState: 'candidate',
    knowledgeCollections: def.group === 'solana' ? ['solana-approved-docs'] : ['solidity-approved-docs', 'verified-case-memory'],
    toolAllowlist: toolsByGroup[def.group] ?? [],
    readPermissions: ['workflow', 'scope', 'approved-source', 'approved-knowledge'],
    writePermissions: def.group === 'reporting' ? ['report-draft'] : def.group === 'evidence' ? ['evidence-annotations'] : ['task-output'],
    sandboxProfile: sandboxByGroup[def.group] ?? 'analysis-readonly',
    networkProfile: networkByGroup[def.group] ?? 'none',
    maxRuntimeSeconds: def.group === 'symbolic' ? 900 : def.group === 'dynamic' ? 600 : 120,
    maxOutputTokens: def.group === 'llm' ? 6000 : 3000,
    enabledForEvm: def.evm !== false,
    dependencies: def.deps ?? dependenciesFor(def),
    inputSchema: `${def.id}.input.v1`,
    outputSchema: `${def.id}.output.v1`,
    approvalRequired: ['dynamic', 'symbolic', 'solana', 'reporting'].includes(def.group),
    retryLimit: 2,
  }))
);

export function validateAgentRegistry(): string[] {
  const issues: string[] = [];
  const seen = new Set<string>();
  const knownIds = new Set(AGENT_REGISTRY.map((agent) => agent.id));
  for (const agent of AGENT_REGISTRY) {
    if (seen.has(agent.id)) issues.push(`duplicate agent id: ${agent.id}`);
    seen.add(agent.id);
    if (!agent.toolAllowlist.length) issues.push(`agent has no tool allowlist: ${agent.id}`);
    if (!agent.skillPackIds.length || !agent.skillVersion) issues.push(`agent has no versioned skill binding: ${agent.id}`);
    if (agent.skillTrustState !== 'candidate') issues.push(`unreviewed skill is not marked as candidate: ${agent.id}`);
    if (agent.stage === 'SOLANA' && agent.enabledForEvm) issues.push(`Solana agent enabled in EVM workflow: ${agent.id}`);
    if (agent.toolAllowlist.some((tool) => tool.includes('shell') || tool.includes('arbitrary'))) issues.push(`unsafe tool id: ${agent.id}`);
    for (const dependency of agent.dependencies) if (!knownIds.has(dependency)) issues.push(`unknown dependency ${dependency} for ${agent.id}`);
    for (const tool of agent.toolAllowlist) if (!toolDescriptions[tool]) issues.push(`unregistered tool capability ${tool} for ${agent.id}`);
  }
  if (AGENT_REGISTRY.length !== 49) issues.push(`expected 49 agents, found ${AGENT_REGISTRY.length}`);
  return issues;
}

const toolDescriptions: Record<string, string> = {
  'workflow.read': 'Read workflow/task metadata through policy-controlled APIs.',
  'workflow.transition': 'Request a validated workflow state transition; transition endpoint is not yet exposed to agents.',
  'task.dispatch': 'Dispatch only version-matched application-registered handlers through the leased task queue.',
  'source.read': 'Read the exact scope-pinned source manifest and approved source artifacts.',
  'knowledge.search': 'Search approved knowledge collections; RAG retrieval is not yet implemented.',
  'gemini.triage': 'Dormant advisory Gemini provider wrapper; no API route or worker handler is wired in this build.',
  'scope.read': 'Read authorized-scope metadata.',
  'source-manifest.verify': 'Validate a source manifest and deterministic tracked-file digest.',
  'scanner.slither': 'Slither runner adapter; not implemented in this build.',
  'scanner.aderyn': 'Aderyn runner adapter; not implemented in this build.',
  'forge.layout': 'Forge storage-layout adapter; not implemented in this build.',
  'suite.request': 'Create a human-approved queue-only request for a fixed suite ID.',
  'receipt.read': 'Read execution receipts; detailed raw receipts are not yet exposed by the API.',
  'symbolic.halmos': 'Halmos adapter; not implemented in this build.',
  'finding.normalize': 'Normalize source-backed finding metadata; dedicated agent executor not implemented.',
  'overlap.annotate': 'Record overlap/known-issue review annotations through evidence review.',
  'evidence.read': 'Read persisted evidence metadata for a workflow.',
  'receipt.verify': 'Verify signed receipt identity/assertions and artifact hashes.',
  'artifact.hash': 'Compute SHA-256 and persist content-addressed artifact bytes.',
  'review.submit': 'Record a human review decision after evidence checks.',
  'report.draft': 'Create a draft report from verified evidence and human-reviewed claims.',
  'solana.suite.request': 'Solana suite request; disabled for EVM and not implemented.',
  'solana.receipt.read': 'Solana evidence reader; disabled for EVM and not implemented.',
};

const implementedToolIds = new Set([
  'workflow.read', 'scope.read', 'source-manifest.verify', 'suite.request', 'receipt.verify', 'artifact.hash', 'evidence.read', 'review.submit', 'report.draft', 'overlap.annotate', 'gemini.triage',
]);

export const TOOL_CAPABILITY_REGISTRY: readonly ToolCapability[] = Object.freeze(
  [...new Set(AGENT_REGISTRY.flatMap((agent) => agent.toolAllowlist))].sort().map((toolId) => ({
    toolId,
    description: toolDescriptions[toolId] ?? 'Declared tool capability; adapter has not been implemented.',
    implementationStatus: implementedToolIds.has(toolId) ? 'implemented-metadata-or-api' : 'planned',
    dispatchEnabled: false,
    agentCallable: false,
  }))
);
