"""
ExchangeStorage (Plan 1.3, task 1).
"""

from __future__ import annotations

import io
from uuid import uuid4

import pytest
from starlette.datastructures import UploadFile

from app.modules.dataexchange.domain.exceptions import ExcelFileTooLargeException, ExcelStorageFullException
from app.modules.dataexchange.infrastructure.storage import ExchangeStorage

MB = 1024 * 1024


def _storage(tmp_path, *, max_upload: int = 10 * MB, min_free: int = 0) -> ExchangeStorage:
    return ExchangeStorage(tmp_path / "exchange", max_upload_bytes=max_upload, min_free_bytes=min_free)


def _upload(data: bytes) -> UploadFile:
    return UploadFile(file=io.BytesIO(data), filename="farmers.xlsx")


async def test_save_upload_streams_file_byte_identical(tmp_path):
    storage = _storage(tmp_path)
    data = bytes(range(256)) * 9000                        # ~2.3 MB, several 1 MB chunks
    dest = storage.upload_dir(uuid4()) / "source.xlsx"

    written = await storage.save_upload_file(dest, _upload(data))

    assert written == len(data)
    assert dest.read_bytes() == data
    assert not dest.with_name("source.xlsx.part").exists()


async def test_upload_over_limit_raises_and_leaves_no_file(tmp_path):
    storage = _storage(tmp_path, max_upload=1 * MB)
    dest = storage.upload_dir(uuid4()) / "source.xlsx"

    with pytest.raises(ExcelFileTooLargeException):
        await storage.save_upload_file(dest, _upload(b"x" * (2 * MB)))

    assert list(dest.parent.iterdir()) == []


async def test_write_stream_limit_is_exact(tmp_path):
    storage = _storage(tmp_path)
    dest = storage.job_dir(uuid4()) / "chunk.part0"

    async def chunks():
        yield b"a" * 100
        yield b"b" * 100

    assert await storage.write_stream(dest, chunks(), limit=200) == 200
    with pytest.raises(ExcelFileTooLargeException):
        await storage.write_stream(dest.with_name("other"), chunks(), limit=199)


def test_ensure_free_space_raises_507_when_disk_would_fill(tmp_path):
    storage = _storage(tmp_path, min_free=1 * MB)

    storage.ensure_free_space(1 * MB)                       # plenty of space on the test machine
    with pytest.raises(ExcelStorageFullException) as error:
        storage.ensure_free_space(10 ** 18)                 # an exabyte never fits

    assert error.value.status_code == 507


@pytest.mark.parametrize(
    "name",
    ["../escape.xlsx", "..", ".", "/etc/passwd", "C:\\Windows\\x.xlsx", "", "a/../../b", "sub/file.xlsx", "x" * 200],
)
def test_path_rejects_names_escaping_the_folder(tmp_path, name):
    storage = _storage(tmp_path)
    base = storage.job_dir(uuid4())

    with pytest.raises(ValueError, match="Unsafe file name"):
        storage.path(base, name)


def test_path_accepts_plain_names(tmp_path):
    storage = _storage(tmp_path)
    base = storage.job_dir(uuid4())

    assert storage.path(base, "result.xlsx") == (base / "result.xlsx").resolve()


def test_delete_dir_and_folder_size(tmp_path):
    storage = _storage(tmp_path)
    base = storage.job_dir(uuid4())
    (base / "a.bin").write_bytes(b"1" * 10)
    (base / "b.bin").write_bytes(b"2" * 15)

    assert storage.folder_size(base) == 25
    storage.delete_dir(base)
    storage.delete_dir(base)                                # missing folder is fine
    assert not base.exists()
    assert storage.folder_size(base) == 0
