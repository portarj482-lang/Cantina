import { createHash } from 'node:crypto';

export interface SoliditySourceRange {
  startByte: number;
  endByteExclusive: number;
  startLine: number;
  endLine: number;
  spanSha256: string;
}
export interface SolidityGraphNode { id: string; kind: 'contract' | 'function' | 'modifier'; name: string; source: string; sourceRange?: SoliditySourceRange }
export interface SolidityGraphEdge { from: string; to: string; kind: 'inherits' | 'declares' | 'uses-modifier' | 'calls' }
export interface SolidityKnowledgeGraph { nodes: SolidityGraphNode[]; edges: SolidityGraphEdge[]; unresolvedCalls: Array<{ from: string; name: string; source: string; sourceRange?: SoliditySourceRange }> }

type AstNode = { nodeType?: string; id?: number; name?: string; src?: string; nodes?: AstNode[]; baseName?: AstNode; baseContracts?: AstNode[]; baseNamePath?: string; modifierName?: AstNode; modifiers?: AstNode[]; expression?: AstNode; referencedDeclaration?: number; arguments?: AstNode[] };

type IndexedSource = { bytes: Buffer; lineStarts: number[] };

function sourceRange(src: string | undefined, fileId: number | undefined, sourcePath: string, sources: Record<string, string>, sourceIndex: Map<string, IndexedSource>): SoliditySourceRange | undefined {
  const content = sources[sourcePath];
  if (typeof content !== 'string' || !src) return undefined;
  const [startText, lengthText, srcFileText] = src.split(':');
  const start = Number(startText), length = Number(lengthText), srcFile = Number(srcFileText);
  if (!Number.isSafeInteger(start) || !Number.isSafeInteger(length) || start < 0 || length < 0 || (Number.isInteger(fileId) && srcFile !== fileId)) return undefined;
  let indexed = sourceIndex.get(sourcePath);
  if (!indexed) {
    const bytes = Buffer.from(content, 'utf8');
    const lineStarts = [0];
    for (let index = 0; index < bytes.length; index++) if (bytes[index] === 10) lineStarts.push(index + 1);
    indexed = { bytes, lineStarts };
    sourceIndex.set(sourcePath, indexed);
  }
  const { bytes, lineStarts } = indexed;
  const end = start + length;
  if (end > bytes.length) return undefined;
  const lineAt = (byteOffset: number) => {
    let low = 0, high = lineStarts.length;
    while (low + 1 < high) { const middle = (low + high) >>> 1; if (lineStarts[middle]! <= byteOffset) low = middle; else high = middle; }
    return low + 1;
  };
  return {
    startByte: start,
    endByteExclusive: end,
    startLine: lineAt(start),
    endLine: lineAt(length ? end - 1 : end),
    spanSha256: createHash('sha256').update(bytes.subarray(start, end)).digest('hex'),
  };
}

function identifier(node: AstNode | undefined): string | undefined {
  if (!node) return undefined;
  return node.name ?? node.baseNamePath ?? (node.expression ? identifier(node.expression) : undefined);
}

/** Builds a call and inheritance graph from solc standard-json AST output. */
export function buildSolidityGraph(sourceUnits: Record<string, unknown>, sources: Record<string, string> = {}): SolidityKnowledgeGraph {
  const nodes: SolidityGraphNode[] = [];
  const edges: SolidityGraphEdge[] = [];
  const unresolvedCalls: SolidityKnowledgeGraph['unresolvedCalls'] = [];
  const sourceIndex = new Map<string, IndexedSource>();
  const units = Object.entries(sourceUnits).sort(([a], [b]) => a.localeCompare(b));
  const parsedUnits = units.flatMap(([source, raw]) => {
    const ast = (raw as { ast?: AstNode }).ast;
    return ast?.nodeType === 'SourceUnit' && Array.isArray(ast.nodes) ? [{ source, ast, fileId: ast.id }] : [];
  });
  const contractIds = new Map<number, string>();
  const declarationIds = new Map<number, string>();
  for (const { source, ast, fileId } of parsedUnits) {
    for (const contract of ast.nodes ?? []) {
      if (contract.nodeType !== 'ContractDefinition' || !contract.name) continue;
      const contractId = `contract:${source}:${contract.name}`;
      if (Number.isInteger(contract.id)) { contractIds.set(contract.id!, contractId); declarationIds.set(contract.id!, contractId); }
      for (const member of contract.nodes ?? []) {
        if (member.nodeType !== 'FunctionDefinition' && member.nodeType !== 'ModifierDefinition') continue;
        const kind = member.nodeType === 'ModifierDefinition' ? 'modifier' : 'function';
        const name = member.name || (kind === 'function' ? 'constructor' : 'modifier');
        const id = `${kind}:${source}:${contract.name}:${name}:${member.id ?? declarationIds.size}`;
        if (Number.isInteger(member.id)) declarationIds.set(member.id!, id);
      }
    }
  }
  const functions: Array<{ node: AstNode; id: string; source: string; fileId: number | undefined }> = [];

  for (const { source, ast, fileId } of parsedUnits) {
    for (const contract of ast.nodes ?? []) {
      if (contract.nodeType !== 'ContractDefinition' || !contract.name) continue;
      const contractId = `contract:${source}:${contract.name}`;
      const contractSourceRange = sourceRange(contract.src, fileId, source, sources, sourceIndex);
      nodes.push({ id: contractId, kind: 'contract', name: contract.name, source, ...(contractSourceRange ? { sourceRange: contractSourceRange } : {}) });
      for (const base of contract.baseContracts ?? []) {
        const baseName = identifier(base.baseName) ?? identifier(base);
        const baseDeclaration = base.baseName?.referencedDeclaration ?? base.referencedDeclaration;
        if (baseDeclaration !== undefined) {
          const target = contractIds.get(baseDeclaration);
          if (target) edges.push({ from: contractId, to: target, kind: 'inherits' });
          else if (baseName) edges.push({ from: contractId, to: `unresolved:${baseName}`, kind: 'inherits' });
        } else if (baseName) edges.push({ from: contractId, to: `unresolved:${baseName}`, kind: 'inherits' });
      }
      for (const member of contract.nodes ?? []) {
        if (member.nodeType !== 'FunctionDefinition' && member.nodeType !== 'ModifierDefinition') continue;
        const kind = member.nodeType === 'ModifierDefinition' ? 'modifier' : 'function';
        const name = member.name || (kind === 'function' ? 'constructor' : 'modifier');
        const functionId = Number.isInteger(member.id) ? declarationIds.get(member.id!)! : `${kind}:${source}:${contract.name}:${name}:${nodes.length}`;
        const memberSourceRange = sourceRange(member.src, fileId, source, sources, sourceIndex);
        nodes.push({ id: functionId, kind, name, source, ...(memberSourceRange ? { sourceRange: memberSourceRange } : {}) });
        edges.push({ from: contractId, to: functionId, kind: 'declares' });
        if (kind === 'function') functions.push({ node: member, id: functionId, source, fileId });
        for (const modifier of member.modifiers ?? []) {
          const modifierName = identifier(modifier.modifierName);
          if (modifierName) {
            const declaration = modifier.modifierName?.referencedDeclaration;
            const target = declaration === undefined ? undefined : declarationIds.get(declaration);
            edges.push({ from: functionId, to: target ?? `modifier:${source}:${contract.name}:${modifierName}`, kind: 'uses-modifier' });
          }
        }
      }
    }
  }

  const walk = (node: AstNode, from: string, source: string, fileId?: number): void => {
    if (node.nodeType === 'FunctionCall' && node.expression) {
      const targetId = node.expression.referencedDeclaration;
      const name = identifier(node.expression) ?? 'unknown-call';
      const target = targetId === undefined ? undefined : declarationIds.get(targetId);
      if (target) edges.push({ from, to: target, kind: 'calls' });
      else {
        const callSourceRange = sourceRange(node.src, fileId, source, sources, sourceIndex);
        unresolvedCalls.push({ from, name, source, ...(callSourceRange ? { sourceRange: callSourceRange } : {}) });
      }
    }
    for (const [key, value] of Object.entries(node)) {
      if (key === 'src') continue;
      if (Array.isArray(value)) {
        for (const child of value) if (child && typeof child === 'object') walk(child as AstNode, from, source, fileId);
      } else if (value && typeof value === 'object') {
        walk(value as AstNode, from, source, fileId);
      }
    }
  };
  for (const fn of functions) walk(fn.node, fn.id, fn.source, fn.fileId);

  const edgeKey = (edge: SolidityGraphEdge) => `${edge.from}\0${edge.to}\0${edge.kind}`;
  const uniqueEdges = [...new Map(edges.map((edge) => [edgeKey(edge), edge])).values()];
  return { nodes, edges: uniqueEdges, unresolvedCalls };
}
