---
phase: 22
plan: 1
wave: 1
depends_on: []
files_modified:
  - app/core/validators.py
  - app/modules/mcc/domain/entities.py
  - app/modules/mcc/domain/dto.py
  - app/modules/mcc/infrastructure/models.py
  - app/modules/mcc/infrastructure/mapper.py
  - app/modules/mcc/infrastructure/repository.py
  - app/modules/mcc/application/command.py
  - app/modules/mcc/application/handler.py
  - app/modules/mcc/presentation/requests.py
  - app/modules/mcc/presentation/response.py
  - app/modules/collections/mcc_collection/domain/clock.py
  - app/core/database/migrations/versions/20261114_0003_mcc_shift_delay.py
  - app/api/v1/schemas/sync.py
  - app/api/v1/schemas/mcc.py
  - app/api/v1/routers/sync.py
  - app/web/mcc/assembler.py
  - app/web/mcc_collection/controller.py
  - app/web/vlcc_collection/controller.py
  - app/web/static/js/collection_form.js
  - app/web/templates/pages/mcc/create_edit.html
  - app/web/templates/pages/mcc/view.html
  - app/web/templates/pages/mcc_collection/collection_form.html
  - app/web/templates/pages/mcc_collection/create_edit.html
  - app/web/templates/pages/vlcc_collection/collection_form.html
  - app/web/templates/pages/vlcc_collection/create_edit.html
  - tests/test_mcc_shift_delay.py
must_haves:
  - MCC has `shift_delay` ("HH:MM", default "00:00"), set in the MCC form's Collection Shifts section as "Shift Delay"
  - Sync API sends it as `mcc_info.shift_delay`
  - A new MCC collection saved from the web is stamped at (now - shift delay), which can fall on the previous day
  - Entry date and shift are read-only on both collection forms; on a new entry they follow the live clock
  - The shift comes from the selected MCC's / VLCC's shift timings
  - Collections saved through the API are not changed
---

# Plan 22.1: MCC Shift Delay and live entry date / shift

## Objective
REQ-50 to REQ-52 (user, 2026-11-14). An MCC that receives milk late records it at the time it was
collected: web entry time = now - the MCC's shift delay. Entry date and shift on the web collection
forms are no longer typed in.

## Decisions (DECISION-029)
- `mcc_master.shift_delay` VARCHAR(5) NOT NULL, default and server default "00:00"; hours 00-23, minutes 00-59.
  Only MCCs have it.
- Web only: the server stamps a new entry itself (`collection_moment`), never trusting the posted date or shift.
  API collections keep the date and shift the app sends (the app applies the delay).
- Shift of a moment: Morning before the unit's morning shift end, otherwise Evening (the rule the dashboard
  already uses for the current shift). It is taken from the delayed time, so 00:30 with a 05:20 delay is the
  previous day's 19:10, Evening. No settings: the split is 12:00.
- Edit keeps the stored date and shift; both are shown read-only.
- The form shows the server's (delayed) clock ticking in the browser, so a wrong PC clock or timezone
  does not matter.

## Tasks

<task type="auto">
  <name>Shift delay on the MCC</name>
  <files>mcc domain / infrastructure / application / presentation, migration 0003, web MCC form and view, sync</files>
  <action>Column, entity, DTO, mapper, repository update, create and edit, request validation ("HH:MM"),
  "Shift Delay" field in Collection Shifts, shown on the MCC view, `mcc_info.shift_delay` in sync.</action>
  <verify>tests/test_mcc_shift_delay.py</verify>
  <done>Create / edit keep the value; blank means 00:00; bad values are refused; sync returns it</done>
</task>

<task type="auto">
  <name>Live, read-only entry date and shift</name>
  <files>collection clock, MCC / VLCC collection controllers, forms, collection_form.js</files>
  <action>`collection_moment(now, shift_delay, morning_end)`; controllers stamp new entries and keep the
  stored values on edit; forms lock the date and shift, which tick from the server clock on a new entry.</action>
  <verify>tests/test_mcc_shift_delay.py; real page check</verify>
  <done>Example 10:44 - 05:44 = 05:00 Morning; 00:30 - 05:20 = previous day 19:10 Evening</done>
</task>
