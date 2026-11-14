---
phase: 23
plan: 1
status: complete
verified: 2026-11-14
---

# Plan 23.1 Summary: Each member of a report on its own printed page

## Request (user, 2026-11-14)
When a report with several members (e.g. Member Ledger) is printed, the first member is on page 1 of the PDF,
the second on page 2, and so on.

## Delivered
- `report_preview.html`: the header of every ledger after the first gets `rp-member-start`
  (`break-before: page` in print); the "****" line between members is screen only. Animal-type groups (VLCC
  Shift Summary) keep running on one page, as before.
- `static/js/report_print.js` (new, used by the MCC and VLCC report pages): prints the preview from a hidden
  iframe as a normal document. The old way printed it as an absolutely positioned box inside the modal, where
  browsers ignore page breaks.
- Payment Summary and Bill Comparison previews are single tables (no members) and print as before, through the
  same frame.

## Verification
- `tests/test_report_print.py`: 4 passed; existing report tests pass.
- Headless Chrome print to PDF of the rendered preview with the frame's styles: 3 members -> 3 pages; a
  60-row member followed by a short one -> 4 pages (the second member starts a new page); 1 member -> 1 page.
- Not clicked through in a real browser session (Print button -> dialog).
