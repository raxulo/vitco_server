---
phase: 7
---

# Phase 7 Research: Super Admin Recycle Bin

## Goal
A Super-Admin-only page under **General** that lists soft-deleted Admins, Sub Admins, MCCs,
VLCCs and Farmers, and permanently deletes one together with everything that depends on it.

## User decisions (2026-11-04)
- Linked data: **delete it all** (collections, payments, farmers, address, bank, rate charts…).
- Admin / Sub Admin delete becomes a **soft delete** (today it is a hard delete).
- Records below the purged one in the hierarchy: **delete the whole tree**.

## How each entity is soft-deleted today

| Entity | Delete path | Marks |
|--------|-------------|-------|
| Admin / Sub Admin | `UserHandler.delete` → `UserRepository.delete` | **hard** `session.delete(model)` |
| MCC | `MccHandler.delete` | `users` + `mcc_master`: `is_deleted`, `is_active=False` |
| VLCC | `VlccHandler.delete` | `users` + `vlcc_master` |
| Farmer | `FarmerHandler.delete` (`DeleteFarmerCommand`) | `users` + `farmer_master`; email / mobile / code get a `del_` prefix |

Gaps found:
- `UserRepository.update` writes `is_deleted` but never `deleted_at` / `deleted_by`.
- `UserRepository.list` has no `is_deleted` filter (harmless today because admins are hard-deleted).

## Ownership tree (from `Hierarchy` + `created_by`)
Super Admin → Admin → Sub Admins (`users.created_by`) → MCCs (`mcc_master.created_by`) →
VLCCs (`vlcc_master.created_by` = manager or MCC user) → Farmers (`farmer_master.vlcc_id`).
The tree of a user U is the fixed point of:
`users.created_by ∈ U`, `mcc_master.created_by ∈ U`, `vlcc_master.created_by ∈ U`,
`farmer_master.created_by ∈ U` or `farmer_master.vlcc_id ∈ VLCCs of U`. Super Admins are never part of a tree.

## Foreign keys (`PRAGMA foreign_keys=ON`, 47 tables in metadata)

Referencing `users.id` — handled by the purge in this order:

| Table.column | ondelete | Purge action |
|--------------|----------|--------------|
| payment_transfers.sender_id / receiver_id | RESTRICT | reverse survivor balances, delete ledger entries, delete transfers |
| payment_ledger_entries.user_id / counterparty_id / transfer_id | RESTRICT | deleted with their transfer |
| advance_records.user_id / created_by | RESTRICT | delete (items cascade) |
| advance_master.user_id | RESTRICT | delete (items, payments cascade) |
| animals.seller_user_id, product_offers.seller_user_id | RESTRICT | delete (inventory cascades) |
| marketplace_orders.buyer_id | RESTRICT | delete |
| rate_charts.created_by | SET NULL | delete charts not assigned to any surviving owner; the rest keep running with `created_by` NULL |
| rate_chart_assignments.created_by | none | set NULL for surviving assignments |
| mcc_master.user_id, vlcc_master.user_id, farmer_master.user_id | none / RESTRICT / CASCADE | master rows deleted first |
| addresses, bank_accounts, fixed_rate_configs, milk_quality_configs (.user_id) | none | delete after the masters that point at them |
| users.created_by, vlcc_master.created_by, farmer_master.created_by | none | inside the tree; survivors set NULL (defensive) |
| account_balances, payment_pair_balances, device_item_versions, excel_jobs, rate_chart_assignments.owner_id | CASCADE | automatic |
| media.uploaded_by, item/unit/route/advance_master.created_by | SET NULL | automatic (shared masters stay) |

Referencing the masters: `mcc_collections.mcc_id/vlcc_id`, `vlcc_collections.vlcc_id/farmer_id`,
`dispatches.vlcc_id` (all RESTRICT) → deleted before the masters.
`mcc_master/vlcc_master.settings_id` → `settings` rows of purged masters are deleted when no survivor uses them.

## Payments and surviving counterparties
A transfer moves `amount`: sender `-amount` (DEBIT entry), receiver `+amount` (CREDIT entry), and
`account_balances.balance` is a running sum. Deleting a transfer with a survivor on the other side
would leave the survivor's balance wrong, so before deleting, each survivor ledger entry of a purged
transfer is reversed on `account_balances` (CREDIT → −amount, DEBIT → +amount).
Pair balances always involve a purged user and cascade away.

## Live data (dev DB, read-only check)
users 20 (1 deleted farmer), mcc_master 3, vlcc_master 4, farmer_master 10 (1 deleted).
