from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

from .storage_interface import StorageInterface


class LocalStorage(StorageInterface):

    def __init__(
        self,
        root_path: str,
    ) -> None:

        self.root = Path(
            root_path
        ).resolve()

        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )

    def _resolve(
        self,
        storage_key: str,
    ) -> Path:

        path = (
            self.root /
            storage_key
        ).resolve()

        if not str(path).startswith(
            str(self.root)
        ):
            raise ValueError(
                "Invalid storage path"
            )

        return path

    async def save(
        self,
        file: BinaryIO,
        storage_key: str,
    ) -> None:

        path = self._resolve(
            storage_key
        )

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with path.open("wb") as destination:

            while chunk := file.read(1024 * 1024):
                destination.write(chunk)        

    async def delete(
        self,
        storage_key: str,
    ) -> None:

        self.remove(storage_key)

    def remove(
        self,
        storage_key: str,
    ) -> None:
        """Synchronous delete (usable from transaction commit / rollback hooks)."""

        path = self._resolve(
            storage_key
        )

        if path.exists():
            path.unlink()

        # Drop folders left empty (e.g. profile/<user_id>/), never the category or root
        parent = path.parent
        while parent != self.root and parent.parent != self.root:
            try:
                parent.rmdir()  # only succeeds when empty
            except OSError:
                break
            parent = parent.parent

    def exists(
        self,
        storage_key: str,
    ) -> bool:

        return self._resolve(
            storage_key
        ).is_file()

    def get_path(
        self,
        storage_key: str,
    ) -> Path:

        return self._resolve(
            storage_key
        )