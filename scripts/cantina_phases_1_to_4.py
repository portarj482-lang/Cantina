#!/usr/bin/env python3
"""Conservative local remediation for Cantina audit phases 1-4.
Runs on an existing Git checkout, creates a timestamped backup directory for any
modified original files, and refuses unexpected source layouts. Does not commit,
push, install packages, run destructive actions, or deploy anything.
"""
from pathlib import Path
import datetime
import os
import shutil
import subprocess
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
if not (root / '.git').exists():
    sys.exit('ERROR: Run inside a Cantina Git repository (or pass its directory).')

timestamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
backups = root / '.audit-remediation-backups' / timestamp
changed = []

def modify(relative: str, pairs: list[tuple[str, str]]):
    p = root / relative
    if not p.is_file():
        raise RuntimeError(f'Missing required file: {relative}')
    original = p.read_text(encoding='utf-8')
    result = original
    for old, new in pairs:
        if old in result:
            result = result.replace(old, new)
        elif new in result:
            continue  # previously fixed
        else:
            raise RuntimeError(f'Unexpected content in {relative}; cannot locate {old[:95]!r}')
    if result != original:
        target = backups / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
        p.write_text(result, encoding='utf-8')
        changed.append(relative)
        print('UPDATED', relative)
    else:
        print('UNCHANGED', relative)

def create(relative: str, contents: str):
    p = root / relative
    if p.exists():
        print('EXISTS (not overwritten)', relative)
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(contents, encoding='utf-8')
    changed.append(relative)
    print('CREATED', relative)

try:
    # Phase 1: branch, runtime, portable paths, and prepare registry compilation.
    modify('.github/workflows/qrpe-orchestrator.yml', [
        ('branches: [ master ]', 'branches: [ main, master ]'),
        ('node-version: 18', 'node-version: 22'),
        (
            '      - name: Verify Agent & Oracle Registry Reconciliation\n'
            '        run: |\n'
            '          npx --prefix security-mesh/security-mesh tsx scripts/reconcile-registries.ts --verify',
            '      - name: Build Security Mesh Registry\n'
            '        run: |\n'
            '          cd security-mesh/security-mesh\n'
            '          npm run build\n\n'
            '      - name: Verify Agent & Oracle Registry Reconciliation\n'
            '        run: |\n'
            '          cd security-mesh/security-mesh\n'
            '          npx tsx ../../scripts/reconcile-registries.ts --verify'
        ),
        (
            '      - name: Run Python Universal Adaptive Test Suite\n'
            '        run: |\n'
            '          python3 -m unittest discover -s tests/universal_adaptive',
            '      - name: Install Python Dependencies\n'
            '        run: |\n'
            '          python3 -m pip install -e ".[dev]"\n\n'
            '      - name: Run Python Universal Adaptive Test Suite\n'
            '        run: |\n'
            '          python3 -m unittest discover -s tests/universal_adaptive\n\n'
            '      - name: Lint and Typecheck Python\n'
            '        run: |\n'
            '          make lint typecheck'
        ),
        (
            '      - name: Run TypeScript Security Mesh Test Suite\n'
            '        run: |\n'
            '          cd security-mesh/security-mesh\n'
            '          npm ci\n'
            '          npm test',
            '      - name: Run TypeScript Security Mesh Test Suite\n'
            '        run: |\n'
            '          cd security-mesh/security-mesh\n'
            '          npm ci\n'
            '          npm run typecheck\n'
            '          npm test'
        ),
    ])

    modify('scripts/run-qrpe-pipeline.sh', [
        (
            '# Canonical Path: /home/nova/projects/cantina/scripts/run-qrpe-pipeline.sh',
            '# Repository-relative paths for local and CI execution'
        ),
        (
            'REPO_ROOT="/home/nova/projects/cantina"',
            'SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"\n'
            'REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"\n'
            'export REPO_ROOT'
        ),
        (
            'mkdir -p "$REPORT_DIR"\n\nMODE_STR=',
            'if [[ "$DRY_RUN" == true || "$CONFIRM" == false ]]; then\n'
            '  LOG_FILE=/dev/null\n'
            'else\n'
            '  mkdir -p "$REPORT_DIR"\n'
            'fi\n\nMODE_STR='
        ),
        (
            '    --pack) PACK="$2"; shift 2 ;;',
            '    --pack)\n'
            '      if [[ $# -lt 2 || -z "${2:-}" || "$2" == --* ]]; then\n'
            '        echo "ERROR: --pack requires a pack name" >&2\n'
            '        exit 2\n'
            '      fi\n'
            '      PACK="$2"; shift 2 ;;'
        ),
    ])

    modify('scripts/reconcile-registries.ts', [
        (
            "const repoRoot = path.resolve('/home/nova/projects/cantina');",
            "const repoRoot = path.resolve(import.meta.dirname ?? path.dirname(new URL(import.meta.url).pathname), '..');"
        ),
        (
            "const reportPath = path.join(reportsDir, 'registry-reconciliation.json');\n"
            "  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2), 'utf-8');\n\n"
            "  console.log(`[Reconcile] Status: ${report.status}`);\n"
            "  console.log(`[Reconcile] Total TS Agents: ${report.totalTsAgents}`);\n"
            "  console.log(`[Reconcile] Total MD Agents: ${report.totalMdAgents}`);\n"
            "  console.log(`[Reconcile] Reconciled Agents: ${report.reconciledAgents.length}`);\n"
            "  console.log(`[Reconcile] Governance Oracles: ${report.governanceOracles.length}`);\n"
            "  console.log(`[Reconcile] Report saved to: ${reportPath}`);",
            "const reportPath = path.join(reportsDir, 'registry-reconciliation.json');\n"
            "  const isVerify = process.argv.includes('--verify');\n"
            "  if (!isVerify) {\n"
            "    fs.writeFileSync(reportPath, JSON.stringify(report, null, 2), 'utf-8');\n"
            "    console.log(`[Reconcile] Report saved to: ${reportPath}`);\n"
            "  }\n\n"
            "  console.log(`[Reconcile] Status: ${report.status}`);\n"
            "  console.log(`[Reconcile] Total TS Agents: ${report.totalTsAgents}`);\n"
            "  console.log(`[Reconcile] Total MD Agents: ${report.totalMdAgents}`);\n"
            "  console.log(`[Reconcile] Reconciled Agents: ${report.reconciledAgents.length}`);\n"
            "  console.log(`[Reconcile] Governance Oracles: ${report.governanceOracles.length}`);"
        ),
        (
            "'bug-hunting-system.md'].includes(f)) {",
            "'bug-hunting-system.md', 'meta-agent-v2.md'].includes(f)) {"
        ),
    ])

    modify('workflows/pack-a-source/workflow-source-pin.sh', [
        (
            'REPO_ROOT="${REPO_ROOT:-/home/nova/projects/cantina}"',
            'SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"\n'
            'REPO_ROOT="${REPO_ROOT:-$(cd -- "$SCRIPT_DIR/../.." && pwd -P)}"'
        ),
        (
            '    except ImportError:\n'
            '        pass',
            '    except ImportError as exc:\n'
            '        raise RuntimeError("jsonschema is required for validation") from exc'
        ),
    ])

    modify('Makefile', [
        ('python3 -m ruff check universal_adaptive_engine tests || true', 'python3 -m ruff check universal_adaptive_engine tests'),
        ('python3 -m mypy universal_adaptive_engine || true', 'python3 -m mypy universal_adaptive_engine'),
    ])

    create('.github/dependabot.yml', '''version: 2
updates:
  - package-ecosystem: pip
    directory: "/"
    schedule:
      interval: weekly
  - package-ecosystem: npm
    directory: "/security-mesh/security-mesh"
    schedule:
      interval: weekly
  - package-ecosystem: github-actions
    directory: "/"
    schedule:
      interval: weekly
''')

    create('README.md', '''# Cantina — Security Research Workflow Orchestrator

Cantina coordinates authorized smart-contract security research across source
reconnaissance, static and dynamic analysis, symbolic verification, triage,
reporting, and Solana workflows. Only use it on systems within your permitted
assessment scope.

## Prerequisites
- Python 3.10+ (CI uses Python 3.12)
- Node.js 22+ and npm
- Linux or a Linux-compatible environment for Bash workflows
- External scanning tools for packs that invoke them

## Setup and verification
```bash
python3 -m pip install -e '.[dev]'
cd security-mesh/security-mesh && npm ci && npm run build && npm test && cd ../..
make audit
make test
make lint typecheck
./scripts/run-qrpe-pipeline.sh --dry-run
```

The pipeline defaults to dry-run and only permits workflows to perform their
intended changes when given `--confirm`. Review scope, dependencies, generated
artifacts and individual pack preconditions before authorizing a run.

## CI
The workflow in `.github/workflows/qrpe-orchestrator.yml` runs on changes to
`main` and `master`. See `workflows/` for the A–G workflow entrypoints and `scripts/` for
maintenance tooling.

## Security
Never commit API tokens, environment files or private scope data. All security
testing must be explicitly authorized. See the repository's governance and
agent instructions before executing non-dry-run scans.
''')

    modify('.gitignore', [
        ('.orchestrator_state/', '.audit-remediation-backups/\n.orchestrator_state/')
    ])

    for relative in ['scripts/run-qrpe-pipeline.sh', 'workflows/pack-a-source/workflow-source-pin.sh']:
        subprocess.run(['bash', '-n', str(root / relative)], check=True)

    subprocess.run(['git', '-C', str(root), 'diff', '--check'], check=True)

except Exception as exc:
    sys.exit(f'ERROR: {exc}\nPartial edits may have been made. Backups: {backups}')

print(f'\nStatic checks passed. Files modified/created: {len(changed)}')
print(f'Backups: {backups}')
