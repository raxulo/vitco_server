---
phase: 18
plan: 1
wave: 1
depends_on: []
files_modified:
  - app/modules/mcc/
  - app/modules/collections/mcc_collection/infrastructure/repository.py
  - app/web/mcc/assembler.py
  - app/web/mcc_collection/controller.py
  - app/web/templates/pages/mcc/
  - app/web/templates/pages/mcc_collection/collection_form.html
  - app/api/v1/routers/sync.py
  - app/api/v1/schemas/sync.py
  - app/core/database/drivers/sqlite.py
  - tests/test_mcc_visible_member.py
must_haves:
  - FAT / SNF and Fixed Rate MCCs have a Visible Member dropdown on create and edit; other types don't
  - With it disabled, the sample number detail leaves out only the VLCC name, on web and API
  - Sync returns visible_member
  - Existing MCCs keep showing names
gap_closure: false
---

# Plan 18.1: MCC Visible Member

## Objective
Let an MCC be set so its operator doesn't see which VLCC a sample number belongs to. VLCCs get the same setting later; only MCC is in scope now.

## Decisions
- Default is Enabled, so nothing changes for existing MCCs.
- The MCC asking for the sample decides, not the weight MCC that recorded it.
- The name is removed on the server, so it never reaches the browser or the app. The VLCC id, code and other details stay, because saving the entry needs them.
- One rule in `MccType.shows_member_name`: types other than FAT / SNF and Fixed Rate always show names.

## Tasks

<task type="auto">
  <name>Field, form and sync</name>
  <files>app/modules/mcc/, app/web/mcc/, templates, sync</files>
  <action>Add the column with an ALTER for existing databases, the dropdown shown only for the two types, and the flag in sync.</action>
  <verify>.venv\Scripts\python.exe -m pytest tests/test_mcc_visible_member.py -q</verify>
  <done>The value survives create and edit, and sync returns it.</done>
</task>

<task type="auto">
  <name>Hide the name</name>
  <files>mcc_collection repository, controller, collection_form.html</files>
  <action>Leave the name out of the sample detail, the VLCC dropdown, the receipt and the recent list.</action>
  <verify>Real Chrome on an isolated database</verify>
  <done>The name appears nowhere in the responses for a disabled MCC.</done>
</task>
