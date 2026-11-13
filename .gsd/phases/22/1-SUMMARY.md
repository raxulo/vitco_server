---
phase: 22
plan: 1
status: complete
verified: 2026-11-14
---

# Plan 22.1 Summary: MCC Shift Delay and live entry date / shift

## Delivered (REQ-50 to REQ-52, DECISION-029)
- `mcc_master.shift_delay` VARCHAR(5) NOT NULL, default "00:00" (migration `0003`; it only adds the column when it
  is missing). Entity, DTO, mapper, repository update, create / edit commands, responses.
- MCC web form: "Shift Delay" (HH:MM) in Collection Shifts; blank = 00:00; "5:30" becomes "05:30"; anything
  outside 00:00-23:59 is refused. Shown on the MCC view. Sync: `mcc_info.shift_delay`.
- Follow-up (user, 2026-11-14): the field types the ":" itself ("0544" -> "05:44", "7" -> "07:"), hours stop at
  23 and minutes at 59, and the delay can be at most the morning shift start time as a whole time (checked live
  in the form and by `apply_shift_delay_rule` on the server).
- Follow-up 2 (user, 2026-11-14): FAT / SNF MCCs only (`MccType.supports_shift_delay`). The field is shown and
  enabled only for that type (also on the first render); other types save "00:00", and `MccDto.applied_shift_delay`
  makes sync and web entries ignore a delay left from a type change. The MCC view shows it for FAT / SNF only.
- `collection_moment(now, shift_delay, morning_end)` in `mcc_collection/domain/clock.py`: entry time =
  now - delay (to the second) and its shift (Morning before morning end, otherwise Evening; 12:00 without settings).
- Web create (MCC and VLCC): the server stamps the date and shift and ignores the posted ones. VLCC: no delay,
  the VLCC's own timings. Web edit keeps the stored date and shift.
- Both collection forms: date and shift locked; a new entry's date ticks every second from the server's clock
  (`data-live-clock`, `static/js/collection_form.js`) and the shift follows it (`data-morning-end`). The weight
  MCC's next sample number uses the same clock. The VLCC farmer picker now moves focus to the weight.
- The MCC collection edit page posted to `/create` (would add a second entry); it now posts to its edit route.
- API collections are not touched.

## Verification
- `tests/test_mcc_shift_delay.py`: 32 passed (SQLite and PostgreSQL), including the user's two examples
  (10:44 - 05:44 = 05:00 Morning; 11/10 00:30 - 05:20 = 10/10 19:10 Evening).
- Full suite on SQLite after both follow-ups: 1025 passed; 1 failure is the known order-dependent `test_owner_options_super_admin`.
  `test_large_import_throughput` misses its 1,000 rows/s bar on this busy machine (759/s), and does the same on
  f2d93a1 (790/s), so it is not caused by this change.
- PostgreSQL: related suites 61 passed. /verify on a real server with a PostgreSQL database at 0002: 16/16 (form,
  view, edit, bad value refused, sync, live clock, MCC entry at 01:15 saved as previous day 19:55 Evening, VLCC
  entry at now, API entry unchanged, upgrade to 0003, existing MCCs 00:00), 0 server errors.
- Not checked in a real browser: the per-second ticking itself (the rendered values and the JS logic were reviewed).

## Found, not fixed
- MCC and VLCC collection edit routes fail (`collection_number` no longer exists on the DTOs / models). No page
  links to them.
