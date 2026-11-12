---
phase: 20
plan: 2
wave: 2
depends_on: [1]
files_modified:
  - alembic.ini
  - app/core/database/migrations/
  - app/core/database/migrator.py
  - app/core/database/drivers/sqlite.py
  - app/core/database/drivers/postgres.py
  - tests/conftest.py
  - quickyee.spec
must_haves:
  - A new database (either dialect) gets its tables from `alembic upgrade head` at startup
  - An existing SQLite database without alembic_version is patched once and stamped, keeping its data
  - Two processes starting together never run the upgrade twice
  - TEST_DATABASE_URL runs the suite on a throw-away Postgres database
gap_closure: false
---

# Plan 20.2: Alembic Migrations

## Objective
Replace `create_all` and the startup ALTER patches with versioned migrations. Research findings 2, 3, 4, 8.

## Tasks

<task type="auto">
  <name>Alembic and baseline</name>
  <files>alembic.ini, app/core/database/migrations/</files>
  <action>env.py that works online with an async engine and from a connection handed over by the app; render_as_batch on SQLite. Autogenerate the baseline from Base.metadata, check it by hand.
  AVOID: calling create_all inside a migration.</action>
  <verify>alembic upgrade head on an empty SQLite file; alembic check reports no differences</verify>
  <done>Baseline creates every table and index of the models.</done>
</task>

<task type="auto">
  <name>Startup migrator</name>
  <files>app/core/database/migrator.py, drivers/sqlite.py, drivers/postgres.py</files>
  <action>SchemaMigrator.upgrade(engine): advisory lock on Postgres; adopt a legacy SQLite database (old create_all + column patches, then stamp); upgrade head. Both drivers call it.
  AVOID: silently swallowing migration errors, as the old patch code did.</action>
  <verify>Start against a copy of a legacy SQLite file and against an empty one</verify>
  <done>Legacy data survives; the version table is at head.</done>
</task>

<task type="auto">
  <name>Tests on either database</name>
  <files>tests/conftest.py, tests/test_schema_migrations.py</files>
  <action>TEST_DATABASE_URL → create and drop quickyee_test_hex. Tests: empty upgrade, legacy adoption, model/migration drift check.</action>
  <verify>.venv\Scripts\python.exe -m pytest -q</verify>
  <done>Suite passes on SQLite.</done>
</task>
