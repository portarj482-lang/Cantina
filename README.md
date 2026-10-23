# Cantina — Security Research Workflow Orchestrator

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
