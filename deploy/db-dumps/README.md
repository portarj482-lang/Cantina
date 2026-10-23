# Database Dumps & Schema Snapshots

This directory stores reproducible database schema definitions, initial fixtures, and sanitization recipes for local and CI Postgres integration environments.

## Policies & Compliance
- **Zero Live Secrets:** Never commit database dumps containing customer credentials, live production records, private keys, or actual user session data.
- **Anonymization:** Any fixtures placed here must be synthetic or fully scrubbed mock records.
- **Format:** Prefer compressed DDL SQL migrations or `.sql.gz` dumps.

## Restoring Local Test Database
```bash
# Start local Postgres instance (Docker or local service)
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/cantina_audit"

# Apply base schema migrations
psql "$DATABASE_URL" -f security-mesh/migrations/001_initial_schema.sql
```
