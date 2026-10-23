import { buildSolidityGraph } from '../analysis/solidity-graph.js';
import { enqueueAgentTask } from './task-queue.js';
import { pool } from '../db/pool.js';
import type { AgentHandler } from './worker.js';
import { getLayer } from '../layers/registry.js';
import { normalizeSourcePath } from '../policy/scope.js';

const object = (value: unknown): value is Record<string, unknown> => Boolean(value && typeof value === 'object' && !Array.isArray(value));
function boundedSolcAst(input: Record<string, unknown>): boolean {
  if (!object(input.solcSourceUnits)) return false;
  let serialized: string;
  try { serialized = JSON.stringify(input.solcSourceUnits); } catch { return false; }
  if (Buffer.byteLength(serialized) > 4 * 1024 * 1024) return false;
  const stack: Array<{ value: unknown; depth: number }> = [{ value: input.solcSourceUnits, depth: 0 }];
  let visited = 0;
  while (stack.length) {
    const { value, depth } = stack.pop()!;
    if (!value || typeof value !== 'object') continue;
    if (depth > 128 || ++visited > 200_000) return false;
    for (const child of Object.values(value)) stack.push({ value: child, depth: depth + 1 });
  }
  return true;
}

function boundedSources(input: Record<string, unknown>): boolean {
  if (!object(input.sources) || Object.keys(input.sources).length > 1000) return false;
  let total = 0;
  for (const [path, content] of Object.entries(input.sources)) {
    if (!normalizeSourcePath(path) || typeof content !== 'string') return false;
    total += Buffer.byteLength(content);
    if (total > 4 * 1024 * 1024) return false;
  }
  return true;
}

function patternLeads(sources: Record<string, unknown>) {
  const rules: Array<{ id: string; pattern: RegExp; reason: string }> = [
    { id: 'tx-origin', pattern: /\btx\s*\.\s*origin\b/g, reason: 'Review authorization assumptions and intermediary behavior.' },
    { id: 'delegatecall', pattern: /\.\s*delegatecall\s*\(/g, reason: 'Review target control, storage context, and access restrictions.' },
    { id: 'low-level-call', pattern: /\.\s*call\s*(?:\{[^}]*\})?\s*\(/g, reason: 'Review external-call ordering, return handling, and reentrancy guards.' },
    { id: 'signature-recovery', pattern: /\becrecover\s*\(/g, reason: 'Review digest domain, malleability, signer authorization, and replay protection.' },
    { id: 'timestamp-dependency', pattern: /\bblock\s*\.\s*timestamp\b/g, reason: 'Review time-window tolerances and whether value depends on precise timing.' },
    { id: 'unchecked-block', pattern: /\bunchecked\s*\{/g, reason: 'Review arithmetic bounds and invariants around unchecked operations.' },
    { id: 'selfdestruct', pattern: /\bselfdestruct\s*\(/g, reason: 'Review lifecycle assumptions under the target chain semantics.' },
  ];
  const leads: Array<{ ruleId: string; sourcePath: string; line: number; excerpt: string; reviewQuestion: string }> = [];
  for (const [sourcePath, raw] of Object.entries(sources)) {
    const content = String(raw);
    const lines = content.split('\n');
    const lineStarts = [0];
    for (let index = 0; index < content.length; index++) if (content.charCodeAt(index) === 10) lineStarts.push(index + 1);
    for (const rule of rules) {
      rule.pattern.lastIndex = 0;
      for (const match of content.matchAll(rule.pattern)) {
        const offset = match.index ?? 0;
        let low = 0, high = lineStarts.length;
        while (low + 1 < high) { const middle = (low + high) >> 1; if (lineStarts[middle]! <= offset) low = middle; else high = middle; }
        const line = low + 1;
        leads.push({ ruleId: rule.id, sourcePath, line, excerpt: lines[low]!.trim().slice(0, 500), reviewQuestion: rule.reason });
        if (leads.length >= 1000) return leads;
      }
    }
  }
  return leads;
}

/** Built-ins are deterministic and offline. No task input is interpreted as code or a command. */
export const BUILTIN_HANDLERS: ReadonlyMap<string, AgentHandler> = new Map([
  ['pathway-scout', {
    agentId: 'pathway-scout', contractVersion: '1.0.0',
    validateInput: (input) => boundedSolcAst(input) && (input.sources === undefined || boundedSources(input)),
    validateOutput: object,
    run: async (input, { signal }) => {
      if (signal.aborted) throw signal.reason;
      const graph = buildSolidityGraph(input.solcSourceUnits as Record<string, unknown>, object(input.sources) ? input.sources as Record<string, string> : {});
      return {
        analysisType: 'solidity-ast-pathway-graph',
        graph,
        summary: { contracts: graph.nodes.filter((node) => node.kind === 'contract').length,
          functions: graph.nodes.filter((node) => node.kind === 'function').length,
          modifiers: graph.nodes.filter((node) => node.kind === 'modifier').length,
          callEdges: graph.edges.filter((edge) => edge.kind === 'calls').length,
          unresolvedCalls: graph.unresolvedCalls.length,
          sourceLocatedNodes: graph.nodes.filter((node) => node.sourceRange).length,
          sourceLocatedUnresolvedCalls: graph.unresolvedCalls.filter((call) => call.sourceRange).length },
        limitations: ['Graph construction only; no vulnerability claim or execution.', 'AST must come from a separately pinned and trusted solc invocation.', 'Source spans and hashes are included only when matching pinned source text is supplied.'],
      };
    },
  }],
  ['bounty-scanner', {
    agentId: 'bounty-scanner', contractVersion: '1.0.0', validateInput: boundedSources, validateOutput: object,
    run: async (input, { signal }) => {
      if (signal.aborted) throw signal.reason;
      return { analysisType: 'deterministic-pattern-leads', leads: patternLeads(input.sources as Record<string, unknown>),
        caveat: 'Heuristic matches are review leads only; absence of matches is not a security conclusion.' };
    },
  }],
  ['lead-security-auditor', {
    agentId: 'lead-security-auditor', contractVersion: '1.0.0',
    validateInput: (input) => Array.isArray(input.dependencyTaskIds) && input.dependencyTaskIds.length === 2 && input.dependencyTaskIds.every((id) => typeof id === 'string'),
    validateOutput: object,
    run: async (input, { signal, task }) => {
      if (signal.aborted) throw signal.reason;
      const ids = input.dependencyTaskIds as string[];
      const result = await pool.query('SELECT id,agent_id,status,output FROM agent_tasks WHERE workflow_id=$1 AND id=ANY($2::uuid[])', [task.workflow_id, ids]);
      if (result.rows.length !== 2 || result.rows.some((row) => row.status !== 'passed')) throw new Error('Scout outputs are missing or incomplete.');
      const pathway = result.rows.find((row) => row.agent_id === 'pathway-scout')?.output as Record<string, unknown> | undefined;
      const scan = result.rows.find((row) => row.agent_id === 'bounty-scanner')?.output as Record<string, unknown> | undefined;
      if (!pathway || !scan) throw new Error('Expected Scout and pattern-scan outputs are required.');
      return { analysisType: 'strategist-synthesis', candidateLeads: scan.leads ?? [],
        pathwaySummary: pathway.summary ?? {}, nextChecks: ['Manually validate each location against pinned source.', 'Write a falsifiable exploit hypothesis and a negative control.', 'Do not treat a heuristic lead as a finding.'],
        provenance: 'Inputs are caller-supplied and not independently fetched or compiled by this in-process handler.' };
    },
  }],
  ['pipeline-orchestrator', {
    agentId: 'pipeline-orchestrator', contractVersion: '1.0.0',
    validateInput: (input) => boundedSolcAst(input) && boundedSources(input), validateOutput: object,
    run: async (input, { signal, task }) => {
      if (signal.aborted) throw signal.reason;
      const layer = getLayer('analysis');
      if (!layer || layer.state !== 'active') throw new Error('Analysis layer is not enabled.');
      const step = (id: string) => {
        const found = layer.steps.find((item) => item.id === id);
        if (!found) throw new Error(`Analysis layer step is not registered: ${id}`);
        return found;
      };
      const pathway = step('pathway');
      const patterns = step('patterns');
      const strategistStep = step('strategist');
      const ast = await enqueueAgentTask({ workflowId: task.workflow_id, targetRecordId: task.target_record_id, agentId: pathway.agentId, idempotencyKey: `pipeline:${task.id}:${pathway.id}`, contractVersion: '1.0.0', input: { solcSourceUnits: input.solcSourceUnits, sources: input.sources }, dependencyTaskIds: [task.id] });
      const scan = await enqueueAgentTask({ workflowId: task.workflow_id, targetRecordId: task.target_record_id, agentId: patterns.agentId, idempotencyKey: `pipeline:${task.id}:${patterns.id}`, contractVersion: '1.0.0', input: { sources: input.sources }, dependencyTaskIds: [task.id] });
      const strategist = await enqueueAgentTask({ workflowId: task.workflow_id, targetRecordId: task.target_record_id, agentId: strategistStep.agentId, idempotencyKey: `pipeline:${task.id}:${strategistStep.id}`, contractVersion: '1.0.0', input: { dependencyTaskIds: [ast.id, scan.id] }, dependencyTaskIds: [ast.id, scan.id] });
      return { pipeline: `${layer.id}-v${layer.version}`, childTaskIds: [ast.id, scan.id, strategist.id], status: 'dispatched', caveat: 'AST/source inputs are not independently compiled or fetched by this worker.' };
    },
  }],
]);
