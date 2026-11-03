---
phase: 7
plan: 1
wave: 1
depends_on: []
files_modified:
  - app/modules/administration/application/handler.py
  - app/modules/administration/infrastructure/repository.py
  - app/modules/recyclebin/domain/enums.py
  - app/modules/recyclebin/domain/dto.py
  - app/modules/recyclebin/domain/exceptions.py
  - app/modules/recyclebin/domain/irepository.py
  - app/modules/recyclebin/infrastructure/repository.py
  - app/modules/recyclebin/application/command.py
  - app/modules/recyclebin/application/handler.py
  - app/modules/configurator.py
  - app/modules/dependencies.py
must_haves:
  - Admin / Sub Admin delete is a soft delete and hides the user from Managed Admins
  - Purge removes the record, its whole ownership tree and every dependent row in one transaction
  - Surviving counterparties keep a correct account balance
  - Only Super Admin can list or purge; only soft-deleted records can be purged
---

# Plan 7.1: Soft-delete admins & purge engine

## Objective
Make Admin / Sub Admin deletion soft, and build the `recyclebin` module (domain, infrastructure,
application) that lists soft-deleted records, previews what a purge removes, and purges it.

## Context
- `.gsd/phases/7/RESEARCH.md`
- `app/modules/administration/infrastructure/hierarchy.py` (CON-06)
- `app/modules/payments/application/service.py` (balance deltas)

## Tasks

<task type="auto">
  <name>Task 1: Soft delete for Admin / Sub Admin</name>
  <files>
    app/modules/administration/application/handler.py
    app/modules/administration/infrastructure/repository.py
  </files>
  <action>
    - `UserHandler.delete`: mark `is_deleted`, `is_active=False`, `deleted_at=now_naive_ist()`,
      `deleted_by`; free email / mobile with a `del_<hex6>_` prefix (same as farmer); remove the profile image.
    - `DeleteUserCommand` gets optional `deleted_by`.
    - `UserRepository.update` also writes `deleted_at` / `deleted_by`; `UserRepository.list` skips deleted users.
    - AVOID: changing the MCC / VLCC / farmer delete flows.
  </action>
  <verify>Deleting a Sub Admin keeps the row with is_deleted=1 and it no longer appears in the list.</verify>
  <done>Admin / Sub Admin rows survive a delete and are listed only by the recycle bin.</done>
</task>

<task type="auto">
  <name>Task 2: recyclebin domain + repository</name>
  <files>app/modules/recyclebin/domain/*, app/modules/recyclebin/infrastructure/repository.py</files>
  <action>
    - `DeletedEntityType` (ADMIN, SUB_ADMIN, MCC, VLCC, FARMER); `DeletedRecordDto`, `PurgeImpactDto`;
      `DeletedRecordNotFoundException` (404).
    - `list_deleted(type, search, offset, limit)`, `find_deleted_root(type, id) -> user_id | None`,
      `resolve_tree(user_id) -> PurgeScope`, `impact(scope)`, `purge(scope)` following RESEARCH.md order.
    - Chunk `IN (...)` lists (500 ids); never include a Super Admin in a scope.
    - AVOID: ORM cascades / loading rows one by one — use bulk `delete()` / `update()` statements.
  </action>
  <verify>Purging a VLCC with farmers, collections and a payment to a surviving MCC leaves no orphan rows and fixes the MCC balance.</verify>
  <done>Repository passes the purge tests in Plan 7.2.</done>
</task>

<task type="auto">
  <name>Task 3: application handler + DI</name>
  <files>app/modules/recyclebin/application/*, app/modules/configurator.py, app/modules/dependencies.py</files>
  <action>
    - `ListDeletedRecordsQuery`, `GetPurgeImpactQuery`, `PurgeRecordCommand` (`owner: CurrentUser`).
    - `RecycleBinHandler` (`__slots__`): Super Admin check (`ForbiddenException`), purge inside
      `async with self._database.transaction()`, then removes the purged users' profile images.
    - Register repository + handler in `ModuleConfigurator`; `GetHandler.recycle_bin_handler`.
  </action>
  <verify>Non-super-admin owner raises ForbiddenException.</verify>
  <done>Handler resolvable from the container.</done>
</task>
