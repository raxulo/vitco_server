# Phase 18 Verification: MCC Visible Member

**Date:** 2026-11-09
**Verdict:** Pass, waiting for the user's review and commit approval

## Test suite

Full suite: **918 passed, 1 failed**. The failure is `test_owner_options_super_admin`, which also fails on `a345c6f`.

`tests/test_mcc_visible_member.py` covers the sample detail on API and web, the type rule, the default, the collection form and sync.

## Real Chrome, isolated database

| Check | Result |
|-------|--------|
| Dropdown on the create form | Shown for FAT / SNF and Fixed Rate, hidden for Normal and Weight |
| Create with Disabled, Enabled and no choice | Stored 0 for FAT / SNF, 1 for Fixed Rate, 1 for Normal |
| Edit | Shows the stored value; Enabled and back to Disabled both save |
| View page | Shows "Visible Member: Disabled" |
| Sample number with Disabled | Quantity 42.50 and 3 cans fill in; VLCC shows as "UIC: V000002" |
| VLCC name in that page's HTML | Not present |
| Server errors | None |
| Real database | Checksum unchanged by these runs |

The dev database gained the column when the dev server reloaded. It has no MCC rows yet, so no data changed.

## Existing problems found, not changed

- **Edit fails for an MCC with blank FAT / SNF limits.** The edit form sends `min_fat`, `max_fat`, `min_snf` and `max_snf` as the text "None", which returns 422. This also blocks changing Visible Member on such an MCC.
- `example.com` emails are accepted on create but refused on edit.

## Scope notes

- Only the sample number flow and the collection form hide the name. Collection lists, the collection view page and reports still show it.
- Sync's `sub_users` still lists VLCC names. The mobile app has to hide them using `mcc_info.visible_member`.
