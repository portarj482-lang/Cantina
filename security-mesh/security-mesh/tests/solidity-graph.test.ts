import { createHash } from 'node:crypto';
import { describe, expect, it } from 'vitest';
import { buildSolidityGraph } from '../src/analysis/solidity-graph.js';

const source = 'contract C {\n  function f() public { unknownCall(); }\n}\n';
const start = source.indexOf('function f');
const length = 'function f() public { unknownCall(); }'.length;
const callStart = source.indexOf('unknownCall()');

const units = {
  'src/C.sol': {
    ast: {
      nodeType: 'SourceUnit', id: 0,
      nodes: [{
        nodeType: 'ContractDefinition', id: 1, name: 'C', src: `0:${Buffer.byteLength(source)}:0`,
        nodes: [{
          nodeType: 'FunctionDefinition', id: 2, name: 'f', src: `${start}:${length}:0`,
          body: { nodeType: 'Block', statements: [{
            nodeType: 'ExpressionStatement', src: `${callStart}:${'unknownCall();'.length}:0`,
            expression: { nodeType: 'FunctionCall', src: `${callStart}:${'unknownCall()'.length}:0`, expression: { nodeType: 'Identifier', name: 'unknownCall' } },
          }] },
        }],
      }],
    },
  },
};

describe('Solidity AST source evidence', () => {
  it('maps graph units and unresolved calls to exact source lines and span hashes', () => {
    const graph = buildSolidityGraph(units, { 'src/C.sol': source });
    const fn = graph.nodes.find((node) => node.kind === 'function');
    expect(fn?.sourceRange).toMatchObject({ startLine: 2, endLine: 2, startByte: start, endByteExclusive: start + length });
    expect(fn?.sourceRange?.spanSha256).toBe(createHash('sha256').update(Buffer.from(source).subarray(start, start + length)).digest('hex'));
    expect(graph.unresolvedCalls[0]).toMatchObject({ name: 'unknownCall', sourceRange: { startLine: 2, endLine: 2 } });
    expect(graph.unresolvedCalls[0]?.sourceRange?.spanSha256).toBe(createHash('sha256').update('unknownCall()').digest('hex'));
  });

  it('omits source hashes when source text is not supplied instead of inventing provenance', () => {
    const graph = buildSolidityGraph(units);
    expect(graph.nodes.find((node) => node.kind === 'function')?.sourceRange).toBeUndefined();
  });
});
