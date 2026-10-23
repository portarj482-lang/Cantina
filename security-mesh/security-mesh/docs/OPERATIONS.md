# Antigravity Security Mesh — Operations Manual

**Version:** 0.1.0\
**Status:** ACTIVE\
**Audience:** Platform Operators, Security Auditors, Runner Administrators

---

## 1. Overview & Trust Boundaries

The Antigravity Security Mesh is designed as a **fail-closed, evidence-first internal research platform**.
Operators must understand the critical operational boundaries:

1. **API Host:** Binds by default to `127.0.0.1:8788`. Must never be exposed to public networks without a secure reverse proxy (TLS termination, mutual TLS or SSO authentication, rate limiting).
2. **Database:** PostgreSQL storing scopes, target records, workflows, artifacts metadata, and the append-only `execution_audit` table.
3. **Runner Hosts:** Dedicated hosts with Docker access running `runner/worker.mjs` / `runner/run.mjs`. Workload containers execute with `network=none`, `read-only` root filesystems, dropped capabilities (`cap-drop=ALL`), and resource limits. Workload containers never receive runner tokens or Docker socket access.

---

## 2. Cryptographic Key & Credential Lifecycle

### 2.1 Runner Key Registration and Rotation
Each isolated runner must have a dedicated Ed25519 keypair and runner ID.

#### Registration:
1. Generate an Ed25519 keypair:
   ```bash
   openssl genpkey -algorithm ed25519 -out runner-private.pem
   openssl pkey -in runner-private.pem -pubout -out runner-public.pem
   ```
2. Register the public key via `POST /v1/runners/register` with `x-admin-token` and `x-actor-id`.
3. The API returns a one-time runner token (`tokenReturnedOnce: true`) and stores the SHA-256 hash in `runner_identities`.
4. Deploy the private key (`RUNNER_PRIVATE_KEY_PEM`) and token (`RUNNER_TOKEN`) strictly to the runner host.

#### Rotation:
1. Re-registering with the same `runnerId` and a new public key automatically rotates the stored key and token, invalidating previous credentials.
2. Active leases for the runner continue until lease expiration; subsequent claims require the new token and signature.

#### Revocation:
- Immediate revocation is triggered via `POST /v1/runners/:id/revoke`.
- This disables the runner identity and cancels any currently active leases, marking running jobs as `failed`.

### 2.2 System Token Rotation
- `ADMIN_API_TOKEN`: Controls scope and runner registration. Rotate by updating `.env` / environment secrets and restarting the API service.
- `HUMAN_APPROVAL_TOKEN`: Authorizes execution runs, reviews, and draft reports. Distinct from API and admin tokens.
- `API_TOKEN`: Used for read and workflow dispatch operations.

---

## 3. Database Operations & Migration Lifecycle

### 3.1 Migration Discipline
- Migrations are stored in `migrations/*.sql` and applied sequentially via `npm run db:migrate`.
- The `_migrations` table records migration filename, SHA-256 checksum, and execution timestamp.
- **Drift Detection:** If any historical migration file is modified after being applied, `npm run db:migrate` fails closed and halts execution. Never edit already-applied migrations; append a new forward-only `.sql` migration file.

### 3.2 Backup and Restore Verification Procedure
1. **Periodic Backup:**
   ```bash
   pg_dump -Fc -U mesh -d security_mesh_integration > /backups/mesh_backup_$(date +%Y%m%d_%H%M%S).dump
   ```
2. **Restore Verification Procedure (Monthly in isolated test environment):**
   ```bash
   createdb -U mesh mesh_restore_test
   pg_restore -U mesh -d mesh_restore_test /backups/mesh_backup_latest.dump
   ```
3. **Audit Chain Integrity Verification:**
   After restoring, verify the cryptographic hash chain using `GET /v1/audit/verify`.
   Ensure `valid: true` and `entriesChecked` matches expected position.

---

## 4. Artifact Retention & Storage Policy

1. **Content-Addressed Storage:** Artifact bytes are stored in `artifacts/<sha256[0..2]>/<sha256>`.
2. **Integrity Rule:** Bytes are written only after verifying their SHA-256 matches caller expectations and size is below `MAX_ARTIFACT_BYTES` (10 MB).
3. **Retention Guidelines:**
   - **Execution Logs (`run-*.log`):** Retain for a minimum of 90 days.
   - **Source Manifests (`source-manifest.json`):** Retain indefinitely as provenance records for registered findings.
   - **Attestation & Evidence Artifacts:** Retain indefinitely.
4. **Safe Pruning:** Artifacts referenced by `artifact_manifests` where the parent workflow is `approved` or has associated findings must never be deleted.

---

## 5. Audit Chain Export & External Notarization

To protect against privileged database operator rewrites:
1. Call `GET /v1/audit/export` periodically (e.g. daily cron).
2. The endpoint returns the latest `chainHeadPosition` and `chainHeadRecordHash` along with verification status.
3. Export and sign the chain head externally or commit to an immutable append-only ledger/transparency log.

---

## 6. Disaster Recovery Runbook

| Incident | Immediate Containment | Recovery Action |
|---|---|---|
| **Runner Credential Compromise** | Call `POST /v1/runners/:id/revoke` | Rotate runner keypair, inspect logs for unverified runs, re-execute affected suites. |
| **Suspected Audit Log Tampering** | Call `GET /v1/audit/verify` | The SHA-256 chain will pinpoint the exact tampered entry. Restore from verified backup up to the last valid chain head. |
| **API Credential Leak** | Kill API process | Rotate all tokens in secrets store (`.env`), restart API, audit API logs for unauthorized calls during window. |
| **Database Failure** | Switch to replica or restore dump | Follow Section 3.2 restore verification and verify audit chain head against external notarization. |
