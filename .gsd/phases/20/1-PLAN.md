---
phase: 20
plan: 1
wave: 1
depends_on: []
files_modified:
  - requirements.txt
  - quickyee.spec
  - .env.example
  - app/config/settings.py
  - app/config/database.py
  - app/core/database/drivers/postgres.py
  - app/core/database/engine.py
  - app/core/database/mixins.py
  - models with DateTime(timezone=True)
must_haves:
  - asyncpg and alembic pinned; the exe bundles them
  - Default DATABASE_URL is PostgreSQL; a sqlite+aiosqlite URL still works
  - Postgres sessions use Asia/Kolkata and a configurable statement timeout
  - Every timestamp column is naive, so Postgres returns naive IST like SQLite
gap_closure: false
---

# Plan 20.1: Postgres Driver & Configuration

## Objective
Make PostgreSQL the default connection without breaking SQLite. Research: [RESEARCH.md](RESEARCH.md) findings 1, 5, 6, 7, 9.

## Tasks

<task type="auto">
  <name>Dependencies and settings</name>
  <files>requirements.txt, quickyee.spec, .env.example, app/config/settings.py, app/config/database.py</files>
  <action>Pin asyncpg 0.32.0 and alembic 1.20.1. Default DATABASE_URL to postgresql+asyncpg on localhost; add DATABASE_STATEMENT_TIMEOUT_MS; pool 10 + 20. Write .env.example with both URLs.
  AVOID: secrets in .env.example; dropping aiosqlite.</action>
  <verify>.venv\Scripts\python.exe -c "from app.config.database import database_config"</verify>
  <done>Settings load with and without DATABASE_URL in the environment.</done>
</task>

<task type="auto">
  <name>Postgres driver and naive timestamps</name>
  <files>app/core/database/drivers/postgres.py, engine.py, mixins.py, models</files>
  <action>Pass asyncpg server_settings (timezone, statement_timeout, idle-in-transaction timeout) through EngineOptions.connect_args instead of cursor calls on connect. Change DateTime(timezone=True) to DateTime().
  AVOID: changing what SQLite stores.</action>
  <verify>.venv\Scripts\python.exe -m pytest -q (SQLite)</verify>
  <done>SQLite suite unchanged.</done>
</task>
