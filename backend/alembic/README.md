# Database migrations (Alembic)

Schema is versioned with Alembic. The DB URL is resolved from `DATABASE_URL`
via `app.config` (dev default + production safety checks), so the same commands
work in every environment — no DSN is hardcoded in `alembic.ini`.

Run from `backend/`:

```bash
# Apply all migrations to the database in DATABASE_URL
alembic upgrade head

# Autogenerate a new migration after changing app/models/*
alembic revision --autogenerate -m "describe change"

# Roll back the most recent migration
alembic downgrade -1

# Show current revision
alembic current
```

## Existing database

The baseline (`01f614faa2d0`) reflects the full current schema. If your database
was created by the app's `Base.metadata.create_all` (or `seed_from_files.py`)
before Alembic existed, stamp it so Alembic knows it is already at head instead
of trying to recreate the tables:

```bash
alembic stamp head
```

## Notes

- `camions` and `chauffeurs` have a mutual foreign-key cycle (each references
  the other's default). The baseline creates both tables first and adds the two
  cross FKs afterwards with `op.create_foreign_key`. Keep this pattern if you
  regenerate the baseline.
- `Base.metadata.create_all` in `app/main.py` is retained only as an
  offline/test convenience (e.g. the SQLite test suite). Migrations are the
  source of truth for the Postgres schema.
