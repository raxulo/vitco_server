---
phase: 18
plan: 1
status: complete
commit: pending user approval
---

# Plan 18.1 Summary: MCC Visible Member

Branch `feature/mcc-visible-member`, from `feature/collection-summary-filters`.

- `mcc_master.visible_member`: on by default, added to existing SQLite databases at startup.
- Dropdown on MCC create and edit, shown for FAT / SNF and Fixed Rate only. Other types always store Enabled.
- With it disabled, the sample number detail leaves out `vlcc_name` on web and API. The server removes it, based on the MCC asking.
- The collection form lists VLCCs as "UIC: code", and the receipt and recent list don't show the name.
- Sync returns `mcc_info.visible_member`.
- VLCC is left for later, as the user asked.
