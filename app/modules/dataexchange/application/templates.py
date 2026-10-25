"""
Exchange Templates

Empty workbooks (header, dropdowns, Instructions) built once per sheet
version and cached on disk, so the template endpoint is a plain file read.
The version is derived from the sheet spec, so changing a column rebuilds it.

Python 3.13+
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from app.modules.dataexchange.domain.columns import SheetSpec
from app.modules.dataexchange.infrastructure.xlsx import XlsxSheetWriter


# Bump when the template layout itself changes (not the columns), to rebuild cached files
_LAYOUT_VERSION = "2-import-columns"


def sheet_version(sheet: SheetSpec) -> str:
    signature = _LAYOUT_VERSION + "|" + "|".join(
        f"{column.key}:{column.display_header}:{int(column.kind)}:{column.dropdown}:{column.help}"
        for column in sheet.columns
    )
    return hashlib.sha1(signature.encode()).hexdigest()[:10]


def template_path(root: Path, sheet: SheetSpec, name: str) -> Path:
    """Path of the cached template; built (atomically) on first use. Synchronous — call via to_thread."""
    folder = root / "templates"
    path = folder / f"{name}-{sheet_version(sheet)}.xlsx"
    if path.is_file():
        return path
    folder.mkdir(parents=True, exist_ok=True)
    partial = folder / f"{path.name}.{os.getpid()}.part"
    # A template is filled in and imported, so it carries the import columns (e.g. Password)
    writer = XlsxSheetWriter(partial, sheet, columns=sheet.import_columns(), tmpdir=folder)
    writer.write_instructions()
    writer.close()
    os.replace(partial, path)                                # concurrent builders: last one wins, same bytes
    return path


def vlcc_template_path(root: Path) -> Path:
    from app.modules.dataexchange.domain.sheets import VLCC_SHEET
    return template_path(root, VLCC_SHEET, "vlccs")


def farmer_template_path(root: Path) -> Path:
    from app.modules.dataexchange.domain.sheets import FARMER_SHEET
    return template_path(root, FARMER_SHEET, "farmers")

