---
phase: 20
plan: 3
wave: 3
depends_on: [2]
files_modified:
  - whatever the Postgres run of the suite shows
  - README.md
must_haves:
  - The full suite passes on PostgreSQL and on SQLite
  - The app starts on an empty Postgres database, creates the admin and serves the main pages
gap_closure: false
---

# Plan 20.3: Postgres Compatibility & Docs

## Objective
Find and fix what Postgres rejects but SQLite allowed (Research finding 10). Needs the user's local PostgreSQL.

## Tasks

<task type="auto">
  <name>Suite on Postgres</name>
  <files>repositories / queries that fail</files>
  <action>Run the suite with TEST_DATABASE_URL; fix each failure in a way that also runs on SQLite (GROUP BY, casts, VARCHAR length, parameter types).
  AVOID: dialect if/else branches unless no portable form exists.</action>
  <verify>pytest on both databases</verify>
  <done>Same pass count on both; known pre-existing failure only.</done>
</task>

<task type="auto">
  <name>Real start and docs</name>
  <files>README.md</files>
  <action>Start the server on an empty Postgres database, log in, open the main lists and reports. Document setup, the SQLite alternative and how to add a migration.</action>
  <verify>/verify skill</verify>
  <done>Pages load without database errors.</done>
</task>
