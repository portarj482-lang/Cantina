# Isolated Foundry runner

This host-side runner accepts only approved, fixed-profile runs assigned to its registered identity. It can fetch the exact approved commit from public GitHub, GitLab, or Bitbucket repositories (or accept a clean local checkout), archives that commit, and runs fixed `build`, `baseline-tests`, or `slither` profiles. Fetching is outside the analysis container; compilation/scanning is offline inside it. Arbitrary commands, flags, forks, and suite definitions are not accepted. F-001 and other target-specific PoC suites still fail closed until exact harnesses and target authorization are supplied.

Each run executes in a disposable container with no network, read-only root filesystem, read-only source mount, bounded writable tmpfs, no Linux capabilities, no-new-privileges, CPU/memory/PID limits, and a ten-minute timeout. The host runner requires Docker access; do not expose the Docker socket to the workload container.

Configure `FOUNDRY_RUNNER_IMAGE` and `SLITHER_RUNNER_IMAGE` as locally available image references pinned by digest; `.env.example` includes the Foundry image digest pulled and smoke-tested for this setup. The Slither image must contain Slither and a shell, with its version reviewed by the operator. On Windows, the runner auto-detects Docker Desktop's per-user CLI path; set `DOCKER_CLI` if Docker is installed elsewhere. Generate a unique Ed25519 key pair per runner. Register the public key through the admin-only `/v1/runners/register` endpoint; store its one-time token and the private key only in that runner host's secret manager. Production API writes require the registered runner ID, token, assigned run lease, and matching Ed25519 signature. Rotate/revoke identities using the admin API.

Required runner host settings: `SECURITY_MESH_API_URL`, `RUNNER_TOKEN` (one-time-issued per-runner token), `RUNNER_ID`, `RUNNER_PRIVATE_KEY_PEM`, `FOUNDRY_RUNNER_IMAGE`, and `SLITHER_RUNNER_IMAGE` for Slither-enabled workers. An API bearer token is optional for registered production runners.

For a one-off local run, after a human approves the queued run, invoke:

```sh
node runner/run.mjs <workflow-uuid> <run-uuid> [absolute-clean-checkout]
```

Run the polling worker continuously to claim approved jobs automatically:

```sh
npm run runner:worker
```

The worker renews its lease and launches each fixed profile in a no-network container. It fetches only the pinned source commit, uploads a bounded log, and posts an Ed25519-signed receipt. Passing build/baseline/scanner checks is not a vulnerability finding. Fork-based exact PoC suites remain unavailable until a specific authorized target, reviewed harness, assertions, and restricted RPC gateway are implemented.
