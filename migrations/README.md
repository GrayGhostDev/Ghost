# Database Migrations

This directory contains Alembic database migrations for the Ghost Backend Framework.

## Quick Start

### Create a new migration
```bash
alembic revision --autogenerate -m "description of changes"
```

### Apply migrations
```bash
alembic upgrade head
```

### Rollback one migration
```bash
alembic downgrade -1
```

### View migration history
```bash
alembic history
```

## Docker Usage

Migrations are automatically run when the Docker container starts (see `tools/docker_entrypoint.py`).

To manually run migrations in Docker:
```bash
docker-compose exec backend alembic upgrade head
```

## Environment Variables

The database connection is configured via environment variables:
- `DATABASE_URL`: Full database URL (overrides all other settings)
- `DB_HOST`: Database host (default: localhost, Docker: postgres)
- `DB_PORT`: Database port (default: 5432)
- `DB_NAME`: Database name (default: ghost)
- `DB_USER`: Database user (default: postgres)
- `DB_PASSWORD`: Database password

## Initial Setup

If this is the first time setting up the database:

1. Ensure the database exists:
```bash
createdb ghost
```

2. Generate initial migration from models:
```bash
alembic revision --autogenerate -m "initial schema"
```

3. Apply the migration:
```bash
alembic upgrade head
```

## Common Commands

```bash
# Create migration
alembic revision --autogenerate -m "add user table"

# Apply all migrations
alembic upgrade head

# Rollback to previous
alembic downgrade -1

# Rollback all
alembic downgrade base

# Show current revision
alembic current

# Show history
alembic history --verbose
```

## Troubleshooting

### Migration conflicts
If you have conflicting migrations from different branches:
```bash
alembic merge -m "merge migrations"
```

### Reset database
To completely reset the database:
```bash
alembic downgrade base
alembic upgrade head
```