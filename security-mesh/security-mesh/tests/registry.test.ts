import { describe, expect, it } from 'vitest';
import { AGENT_REGISTRY, TOOL_CAPABILITY_REGISTRY, validateAgentRegistry } from '../src/agents/registry.js';
import { getSuite } from '../src/tools/registry.js';
import { validateSourceAttestationEvidence } from '../src/policy/source-attestation.js';
import { LAYER_REGISTRY, validateLayerRegistry } from '../src/layers/registry.js';

describe('49-agent registry', () => {
  it('registers exactly 49 unique capability profiles', () => {
    expect(AGENT_REGISTRY).toHaveLength(49);
    expect(validateAgentRegistry()).toEqual([]);
    expect(new Set(AGENT_REGISTRY.map((agent) => agent.id)).size).toBe(49);
  });

  it('keeps every Solana cohort agent disabled in EVM workflows', () => {
    const solana = AGENT_REGISTRY.filter((agent) => agent.stage === 'SOLANA');
    expect(solana).toHaveLength(5);
    expect(solana.every((agent) => !agent.enabledForEvm)).toBe(true);
  });


  it('requires source attestation bound to the exact repository, commit, and safe line references', () => {
    const sourceSha = 'a'.repeat(64);
    const manifest = { evidence_kind: 'source-manifest', metadata: { treeSha256: sourceSha } };
    const attestation = {
      evidence_kind: 'source-attestation',
      metadata: {
        repositoryUrl: 'https://github.com/example/repo.git/',
        commitSha: 'b'.repeat(40),
        repositoryIdentityVerified: true,
        commitObjectVerified: true,
        lineProvenanceVerified: true,
        sourceLineRefs: [{ path: 'src/Wallet.sol', startLine: 10, endLine: 18, excerptSha256: sourceSha }],
      },
    };
    expect(validateSourceAttestationEvidence([manifest, attestation], 'https://github.com/example/repo', 'b'.repeat(40)).ok).toBe(true);
    expect(validateSourceAttestationEvidence([manifest, { ...attestation, metadata: { ...attestation.metadata, commitSha: 'c'.repeat(40) } }], 'https://github.com/example/repo', 'b'.repeat(40)).ok).toBe(false);
    expect(validateSourceAttestationEvidence([manifest, { ...attestation, metadata: { ...attestation.metadata, sourceLineRefs: [{ path: '../outside.sol', startLine: 1, endLine: 1, excerptSha256: sourceSha }] } }], 'https://github.com/example/repo', 'b'.repeat(40)).ok).toBe(false);
  });

  it('defines the revocation suite as a positive reproduction oracle, not a secure-behavior oracle', () => {
    const suite = getSuite('revocation');
    expect(suite).toBeDefined();
    expect(suite?.requiredAssertions).toContain('post_revocation_erc1271_accepts_same_signature');
    expect(suite?.requiredAssertions).toContain('same_digest_and_signature');
    expect(suite?.requiredAssertions).not.toContain('revoked_owner_rejected');
    expect(suite?.dispatchEnabled).toBe(false);
  });

  it('advertises the approval-gated Gemini endpoint without enabling agent dispatch', () => {
    const gemini = TOOL_CAPABILITY_REGISTRY.find((tool) => tool.toolId === 'gemini.triage');
    expect(gemini?.implementationStatus).toBe('implemented-metadata-or-api');
    expect(gemini?.dispatchEnabled).toBe(false);
    expect(gemini?.agentCallable).toBe(false);
  });

  it('does not give agents arbitrary shell execution tools', () => {
    for (const agent of AGENT_REGISTRY) {
      expect(agent.toolAllowlist.some((tool) => /shell|exec\.arbitrary/i.test(tool))).toBe(false);
      expect(agent.skillVersion).toBeTruthy();
      expect(agent.sandboxProfile).toBeTruthy();
    }
  });
});

describe('shared layer workflow registry', () => {
  it('validates all layer agent bindings and dependencies', () => {
    expect(validateLayerRegistry()).toEqual([]);
  });

  it('activates implemented layers and records their runtime mode', () => {
    expect(Object.values(LAYER_REGISTRY).filter((layer) => layer.state === 'active').map((layer) => layer.id)).toEqual(['source', 'analysis', 'execution', 'evidence', 'review', 'reporting']);
    expect(LAYER_REGISTRY.analysis.steps.map((step) => step.agentId)).toEqual(['pathway-scout', 'bounty-scanner', 'lead-security-auditor']);
    expect(LAYER_REGISTRY.execution.executionMode).toBe('isolated-runner');
    expect(LAYER_REGISTRY.execution.steps.map((step) => step.agentId)).toEqual(['forge-unit-runner', 'slither-runner']);
    expect(LAYER_REGISTRY.reporting.executionMode).toBe('api-gated');
  });
});
