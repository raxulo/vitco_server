from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO


class StorageInterface(ABC):

    @abstractmethod
    async def save(
        self,
        file: BinaryIO,
        storage_key: str,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def delete(
        self,
        storage_key: str,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def exists(
        self,
        storage_key: str,
    ) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_path(
        self,
        storage_key: str,
    ) -> Path:
        raise NotImplementedError