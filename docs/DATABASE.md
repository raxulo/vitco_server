# Database

Quickyee runs on **PostgreSQL** by default. SQLite still works (DECISION-025).
The schema is created and updated by **Alembic** migrations, which the app runs on every start (DECISION-026).

## PostgreSQL setup

1. Install PostgreSQL 14 or newer.
2. Create a user and an empty database:

   ```sql
   CREATE USER quickyee WITH PASSWORD 'choose-a-password';
   CREATE DATABASE quickyee OWNER quickyee;
   ```

3. Set the URL in `.env.local` next to `.env`:

   ```
   DATABASE_URL=postgresql+asyncpg://vitco:Vitco123@localhost:5432/vitco
   ```

   `.env.local` overrides `.env` line by line. It's git-ignored and the deploy never copies it,
   so a deploy (which ships the tracked `.env`) can't switch a server back to SQLite.

4. Start the app. It creates every table and the Super Admin from `ADMIN_*` in `.env`.

### Settings

| Setting | Default | Meaning |
|---------|---------|---------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres@localhost:5432/quickyee` | Connection URL |
| `DATABASE_POOL_SIZE` | 10 | Connections kept open per process |
| `DATABASE_MAX_OVERFLOW` | 20 | Extra connections allowed at peak, per process |
| `DATABASE_STATEMENT_TIMEOUT_MS` | 120000 | Longest one statement may run (Postgres only); 0 = no limit |
| `DATABASE_REPLICA_URL` | same as `DATABASE_URL` | Optional read replica |

The API and the Excel worker each have their own pool, so the defaults use at most 60 of
Postgres's usual 100 connections. Lower them if several API processes share one server.

Sessions run in the `Asia/Kolkata` time zone. Every timestamp column is a naive `TIMESTAMP`
holding IST, the same as `now_naive_ist()` writes.

## SQLite

```
DATABASE_URL=sqlite+aiosqlite:///storage/database/realtime_transfer.db
```

Useful for the offline Windows exe and quick local runs. A SQLite database created before
migrations existed is adopted on its first start: missing tables and columns are added, its
rows are kept and it is stamped at revision `0001`.

Nothing is copied between databases. Switching to Postgres starts with an empty database.

A server on PostgreSQL doesn't need Python's `sqlite3` module. Excel import keeps its temporary data in plain
files in the job folder (DECISION-027), and the final data goes into whichever database `DATABASE_URL` names.

## Changing the schema

Every model change needs a migration, and it must run on both databases.

```powershell
.venv\Scripts\alembic revision --autogenerate -m "add phone to farmer_master"
# read and fix the new file in app\core\database\migrations\versions\
.venv\Scripts\alembic upgrade head
.venv\Scripts\alembic check
```

- `alembic` uses `DATABASE_URL` from `.env`. Generate against an up-to-date database.
- On SQLite, column changes are written as `op.batch_alter_table` blocks automatically.
- `tests/test_schema_migrations.py` fails when the models and the migrations differ.

## Tests

```powershell
# SQLite (default)
.venv\Scripts\python.exe -m pytest -q

# PostgreSQL: any existing database on the server; the run creates and drops quickyee_test_<hex>
$env:TEST_DATABASE_URL = "postgresql+asyncpg://postgres:secret@localhost:5432/postgres"
.venv\Scripts\python.exe -m pytest -q
```

The test user needs the `CREATEDB` right.
