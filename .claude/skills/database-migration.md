# Ghost Backend Database Migration

## When to use
When creating, applying, or rolling back database migrations for the Ghost Backend PostgreSQL instance (port 5433).

## Key facts
- **Database:** PostgreSQL on port 5433
- **User:** postgres
- **Database name:** ghost_backend
- **Migration tool:** Raw SQL files (numbered) or Alembic
- **Migrations directory:** `ghost-backend/migrations/`

## Migration file structure
```
ghost-backend/migrations/
├── 001_initial_schema.sql
├── 002_add_sessions_table.sql
├── 003_add_user_roles.sql
├── rollback/
│   ├── 001_initial_schema_rollback.sql
│   ├── 002_add_sessions_table_rollback.sql
│   └── 003_add_user_roles_rollback.sql
└── README.md
```

## Creating a migration

### Step 1: Create migration file
```bash
# Generate timestamp-based filename
MIGRATION_NUM=$(ls ghost-backend/migrations/*.sql 2>/dev/null | wc -l | tr -d ' ')
NEXT_NUM=$(printf "%03d" $((MIGRATION_NUM + 1)))
FILENAME="${NEXT_NUM}_description_of_change.sql"

# Create migration file
touch ghost-backend/migrations/$FILENAME
touch ghost-backend/migrations/rollback/${NEXT_NUM}_description_of_change_rollback.sql
```

### Step 2: Write forward migration
```sql
-- Migration: 004_add_audit_log.sql
-- Date: YYYY-MM-DD
-- Description: Add audit logging table for tracking data access

BEGIN;

CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT now() NOT NULL,
    user_id TEXT NOT NULL,
    action TEXT NOT NULL,
    resource TEXT NOT NULL,
    resource_id TEXT,
    details JSONB,
    ip_address INET
);

CREATE INDEX idx_audit_log_user_id ON audit_log (user_id);
CREATE INDEX idx_audit_log_timestamp ON audit_log (timestamp DESC);
CREATE INDEX idx_audit_log_resource ON audit_log (resource, resource_id);

COMMIT;
```

### Step 3: Write rollback
```sql
-- Rollback: 004_add_audit_log_rollback.sql
-- Reverses: 004_add_audit_log.sql

BEGIN;

DROP INDEX IF EXISTS idx_audit_log_resource;
DROP INDEX IF EXISTS idx_audit_log_timestamp;
DROP INDEX IF EXISTS idx_audit_log_user_id;
DROP TABLE IF EXISTS audit_log;

COMMIT;
```

## Applying migrations

### Apply single migration
```bash
psql -h localhost -p 5433 -U postgres -d ghost_backend -f ghost-backend/migrations/004_add_audit_log.sql
```

### Apply all pending migrations
```bash
# Check current state
psql -h localhost -p 5433 -U postgres -d ghost_backend -c "
SELECT * FROM schema_migrations ORDER BY version DESC LIMIT 5;
"

# Apply pending migrations in order
for f in ghost-backend/migrations/[0-9]*.sql; do
    echo "Applying: $f"
    psql -h localhost -p 5433 -U postgres -d ghost_backend -f "$f"
done
```

### Migration tracking table
```sql
-- Create if not exists
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ DEFAULT now(),
    description TEXT
);

-- Record applied migration
INSERT INTO schema_migrations (version, description)
VALUES ('004', 'Add audit log table');
```

## Rolling back

### Rollback single migration
```bash
psql -h localhost -p 5433 -U postgres -d ghost_backend \
  -f ghost-backend/migrations/rollback/004_add_audit_log_rollback.sql

# Remove from tracking
psql -h localhost -p 5433 -U postgres -d ghost_backend -c "
DELETE FROM schema_migrations WHERE version = '004';
"
```

## Schema verification
```bash
# List all tables
psql -h localhost -p 5433 -U postgres -d ghost_backend -c "
SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;
"

# Check table structure
psql -h localhost -p 5433 -U postgres -d ghost_backend -c "
\d+ <table_name>
"

# List all indexes
psql -h localhost -p 5433 -U postgres -d ghost_backend -c "
SELECT indexname, tablename FROM pg_indexes
WHERE schemaname = 'public' ORDER BY tablename, indexname;
"

# Check for tables without primary keys
psql -h localhost -p 5433 -U postgres -d ghost_backend -c "
SELECT t.tablename
FROM pg_tables t
LEFT JOIN pg_indexes i ON t.tablename = i.tablename AND i.indexname LIKE '%_pkey'
WHERE t.schemaname = 'public' AND i.indexname IS NULL;
"
```

## Migration best practices
- Always wrap migrations in `BEGIN;`/`COMMIT;` for atomicity
- Always create a rollback file alongside the forward migration
- Forward migrations should be backward-compatible (additive changes)
- Test migration and rollback locally before applying to production
- Never modify an already-applied migration — create a new one instead
- Add indexes concurrently for large tables: `CREATE INDEX CONCURRENTLY`
- Record every migration in the tracking table

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Migration fails mid-way | Transaction should rollback automatically (BEGIN/COMMIT) |
| Can't connect to database | Verify PostgreSQL container running: `pg_isready -p 5433` |
| Permission denied | Connect as postgres user, check role permissions |
| Index creation locks table | Use `CREATE INDEX CONCURRENTLY` (outside transaction) |
| Rollback fails | Check for dependent objects (foreign keys, views) |
