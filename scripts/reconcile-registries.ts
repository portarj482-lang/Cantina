import * as fs from 'fs';
import * as path from 'path';

interface ReconciliationReport {
  timestamp: string;
  totalTsAgents: number;
  totalMdAgents: number;
  governanceOracles: string[];
  reconciledAgents: string[];
  specializedReasoningAgents: string[];
  missingInMd: string[];
  missingInTs: string[];
  status: 'RECONCILED' | 'DRIFT_DETECTED';
}

async function main() {
  const repoRoot = path.resolve('/home/nova/projects/cantina');
  const globalAgentsDir = path.join(repoRoot, 'global', 'agents');
  const reportsDir = path.join(repoRoot, 'maintenance', 'reports');

  if (!fs.existsSync(reportsDir)) {
    fs.mkdirSync(reportsDir, { recursive: true });
  }

  // Load TS Agent Registry
  const registryModule = await import('../security-mesh/security-mesh/dist/agents/registry.js');
  const tsAgents = registryModule.AGENT_REGISTRY;
  const tsAgentIds = new Set<string>(tsAgents.map((a: { id: string }) => a.id));

  // Load Markdown agent files
  const mdFiles = fs.readdirSync(globalAgentsDir).filter(f => f.endsWith('.md'));
  const mdAgentIds = new Set<string>();
  const governanceOracles: string[] = [];

  for (const f of mdFiles) {
    if (f.startsWith('G') && f.includes('oracle')) {
      governanceOracles.push(f.replace('.md', ''));
    } else if (!['AGENT_SET.md', 'CONTRACT.md', 'PLAYBOOKS.md', 'index.md', 'bug-hunting-system.md'].includes(f)) {
      mdAgentIds.add(f.replace('.md', ''));
    }
  }

  // Specialized reasoning agents from bug-hunting-system
  const specializedReasoning = ['hypothesis-analyst', 'independent-falsifier'];

  const missingInMd: string[] = [];
  const reconciledAgents: string[] = [];

  for (const id of tsAgentIds) {
    if (mdAgentIds.has(id)) {
      reconciledAgents.push(id);
    } else {
      missingInMd.push(id);
    }
  }

  const missingInTs: string[] = [];
  for (const id of mdAgentIds) {
    if (!tsAgentIds.has(id) && !specializedReasoning.includes(id)) {
      missingInTs.push(id);
    }
  }

  const isReconciled = missingInMd.length === 0 && missingInTs.length === 0;

  const report: ReconciliationReport = {
    timestamp: new Date().toISOString(),
    totalTsAgents: tsAgents.length,
    totalMdAgents: mdAgentIds.size,
    governanceOracles: governanceOracles.sort(),
    reconciledAgents: reconciledAgents.sort(),
    specializedReasoningAgents: specializedReasoning,
    missingInMd,
    missingInTs,
    status: isReconciled ? 'RECONCILED' : 'DRIFT_DETECTED'
  };

  const reportPath = path.join(reportsDir, 'registry-reconciliation.json');
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2), 'utf-8');

  console.log(`[Reconcile] Status: ${report.status}`);
  console.log(`[Reconcile] Total TS Agents: ${report.totalTsAgents}`);
  console.log(`[Reconcile] Total MD Agents: ${report.totalMdAgents}`);
  console.log(`[Reconcile] Reconciled Agents: ${report.reconciledAgents.length}`);
  console.log(`[Reconcile] Governance Oracles: ${report.governanceOracles.length}`);
  console.log(`[Reconcile] Report saved to: ${reportPath}`);

  if (process.argv.includes('--verify')) {
    if (!isReconciled) {
      console.error(`[Reconcile] Error: Missing in MD: ${missingInMd.join(', ')} | Missing in TS: ${missingInTs.join(', ')}`);
      process.exit(1);
    }
  }
}

main().catch(err => {
  console.error('[Reconcile] Fatal error:', err);
  process.exit(1);
});
