"""
Keeps stored files in step with the database transaction (Python 3.13+).

- Files to remove (e.g. a replaced profile image) are deleted only AFTER the
  transaction commits; on rollback they are kept, so no row points at a lost file.
- Files just written are deleted if the transaction ROLLS BACK, so a failed
  request leaves no orphan files behind.

Pending work lives in `session.info`; the listeners are attached once per session.
"""

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

_STATE_KEY = "media_file_cleanup"


class _PendingFiles:
    __slots__ = ("storage", "on_commit", "on_rollback")

    def __init__(self, storage) -> None:
        self.storage = storage
        self.on_commit: list[str] = []
        self.on_rollback: list[str] = []

    def run(self, keys: list[str]) -> None:
        for key in keys:
            try:
                self.storage.remove(key)
            except Exception:
                pass  # a missing / locked file must never break the request
        self.on_commit.clear()
        self.on_rollback.clear()


def _pending(session: AsyncSession, storage) -> _PendingFiles:
    sync_session: Session = session.sync_session
    state = sync_session.info.get(_STATE_KEY)
    if state is None:
        state = _PendingFiles(storage)
        sync_session.info[_STATE_KEY] = state
        event.listen(sync_session, "after_commit", lambda s: state.run(list(state.on_commit)))
        event.listen(sync_session, "after_rollback", lambda s: state.run(list(state.on_rollback)))
    return state


def delete_after_commit(session: AsyncSession, storage, *storage_keys: str) -> None:
    _pending(session, storage).on_commit.extend(storage_keys)


def delete_on_rollback(session: AsyncSession, storage, *storage_keys: str) -> None:
    _pending(session, storage).on_rollback.extend(storage_keys)
