"""
Streaming XLSX Writer / Reader

Both sides keep memory flat whatever the row count (DECISION-012):

- `XlsxSheetWriter` — xlsxwriter in constant_memory mode: one row at a time,
  inline strings, styles / validations / freeze panes set up front, and an
  automatic continuation sheet every 1,048,575 data rows.
- `XlsxSheetReader` — stdlib zipfile + expat: rows are parsed straight from the
  compressed stream; shared strings spill to plain scratch files when large;
  DOCTYPE / entity declarations are refused (XML bomb protection).

Both classes are synchronous: callers run them in a worker thread / process.

Python 3.13+
"""

from __future__ import annotations

import mmap
import posixpath
import re
import struct
import zipfile
from collections import OrderedDict
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.parsers import expat

import xlsxwriter

from app.modules.dataexchange.domain.columns import ColumnSpec, HeaderMap, SheetSpec
from app.modules.dataexchange.domain.exceptions import InvalidExcelFileException

EXCEL_MAX_ROWS = 1_048_576                      # per sheet, header included
EXCEL_MAX_CELL_CHARS = 32_767
_LIST_SOURCE_LIMIT = 255                        # Excel limit for an inline dropdown list
_READ_CHUNK = 1 << 20                           # 1 MB of compressed XML per parse step
_REPORT_FILL = "FECACA"
_DIMENSION_END = re.compile(r"[A-Z]+([0-9]+)$")


# =========================================================
# WRITER
# =========================================================

@dataclass(slots=True, frozen=True)
class ExtraColumn:
    """A column appended after the spec columns, e.g. `Row No` / `Reason` in a report."""

    header: str
    width: int = 14


class XlsxSheetWriter:

    __slots__ = (
        "_sheet",
        "_columns",
        "_extra",
        "_rows_per_sheet",
        "_workbook",
        "_worksheet",
        "_sheet_count",
        "_row",
        "_rows_written",
        "_text_format",
        "_header_formats",
        "_text_columns",
        "_lists_sheet",
        "_lists_used",
    )

    def __init__(
        self,
        path: Path,
        sheet: SheetSpec,
        *,
        columns: Sequence[ColumnSpec] | None = None,
        extra_columns: Sequence[ExtraColumn] = (),
        rows_per_sheet: int = EXCEL_MAX_ROWS - 1,
        tmpdir: Path | None = None,
    ) -> None:
        options: dict[str, Any] = {
            "constant_memory": True,
            "strings_to_numbers": False,
            "strings_to_formulas": False,
            "strings_to_urls": False,
        }
        if tmpdir is not None:
            options["tmpdir"] = str(tmpdir)

        self._sheet = sheet
        self._columns = tuple(columns) if columns is not None else sheet.export_columns()
        self._extra = tuple(extra_columns)
        self._rows_per_sheet = max(1, min(rows_per_sheet, EXCEL_MAX_ROWS - 1))
        self._workbook = xlsxwriter.Workbook(str(path), options)
        self._text_format = self._workbook.add_format({"num_format": "@"})
        self._header_formats: dict[str, Any] = {}
        self._text_columns = frozenset(
            index for index, column in enumerate(self._columns) if column.is_text_format
        )
        self._lists_sheet = None
        self._lists_used = 0
        self._sheet_count = 0
        self._rows_written = 0
        self._row = 0
        self._worksheet = None
        self._open_sheet()

    @property
    def rows_written(self) -> int:
        return self._rows_written

    @property
    def sheet_count(self) -> int:
        return self._sheet_count

    # ---------------------------------------------------------

    def write_rows(self, rows: Iterable[Sequence[Any]]) -> None:
        text_columns = self._text_columns
        text_format = self._text_format
        for values in rows:
            if self._row > self._rows_per_sheet:
                self._open_sheet()
            worksheet = self._worksheet
            row = self._row
            for index, value in enumerate(values):
                if value is None:
                    continue
                fmt = text_format if index in text_columns else None
                if isinstance(value, str):
                    if value:
                        worksheet.write_string(row, index, value[:EXCEL_MAX_CELL_CHARS], fmt)
                elif isinstance(value, bool):
                    worksheet.write_boolean(row, index, value, fmt)
                elif isinstance(value, (int, float)):
                    worksheet.write_number(row, index, value, fmt)
                else:
                    worksheet.write_string(row, index, str(value)[:EXCEL_MAX_CELL_CHARS], fmt)
            self._row += 1
            self._rows_written += 1

    def write_instructions(self) -> None:
        sheet = self._workbook.add_worksheet("Instructions")
        bold = self._workbook.add_format({"bold": True, "bg_color": "#E5E7EB", "border": 1})
        wrap = self._workbook.add_format({"text_wrap": True, "valign": "top"})
        headers = ("Column", "Section", "Required", "Type", "Allowed values", "Example", "Notes")
        for index, (header, width) in enumerate(zip(headers, (24, 14, 10, 22, 34, 18, 60))):
            sheet.set_column(index, index, width, wrap)
            sheet.write_string(0, index, header, bold)
        sheet.freeze_panes(1, 0)

        row = 1
        for column in self._sheet.columns:
            notes = column.help
            if column.import_only:
                notes = f"{notes} Import only — never exported.".strip()
            sheet.write_row(row, 0, (
                column.header,
                column.section.label,
                "YES" if column.required else "NO",
                column.kind.label,
                ", ".join(column.dropdown),
                column.example,
                notes,
            ))
            row += 1

        row += 1
        for note in (
            "Row 1 is the header. Data starts at row 2. Columns are matched by header name, so their order does not matter.",
            f"Columns marked * are required. The '{self._sheet.column(self._sheet.key_column).header}' column decides whether a row updates an existing record or creates a new one.",
            "When updating, an empty cell keeps the value already saved.",
            "Rows that cannot be imported are listed in a downloadable file with the reason; fix them there and upload that file again.",
        ):
            sheet.write_string(row, 0, note)
            row += 1

    def close(self) -> None:
        self._workbook.close()

    # ---------------------------------------------------------

    def _open_sheet(self) -> None:
        self._sheet_count += 1
        name = self._sheet.name if self._sheet_count == 1 else f"{self._sheet.name} ({self._sheet_count})"
        worksheet = self._workbook.add_worksheet(name[:31])
        worksheet.freeze_panes(1, 0)

        for index, column in enumerate(self._columns):
            width = min(max(len(column.display_header) + 3, 10), 40)
            worksheet.set_column(index, index, width, self._text_format if column.is_text_format else None)
            worksheet.write_string(0, index, column.display_header, self._header_format(column.section.fill))
            if column.dropdown:
                self._add_dropdown(worksheet, index, column)

        offset = len(self._columns)
        for position, extra in enumerate(self._extra):
            worksheet.set_column(offset + position, offset + position, extra.width)
            worksheet.write_string(0, offset + position, extra.header, self._header_format(_REPORT_FILL))

        last_column = offset + len(self._extra) - 1
        if last_column >= 0:
            worksheet.autofilter(0, 0, 0, last_column)

        self._worksheet = worksheet
        self._row = 1

    def _header_format(self, fill: str):
        fmt = self._header_formats.get(fill)
        if fmt is None:
            fmt = self._workbook.add_format({"bold": True, "bg_color": f"#{fill}", "border": 1})
            self._header_formats[fill] = fmt
        return fmt

    def _add_dropdown(self, worksheet, index: int, column: ColumnSpec) -> None:
        values = column.dropdown
        if len(",".join(values)) <= _LIST_SOURCE_LIMIT:
            source: Any = list(values)
        else:
            source = self._list_range(values)
        worksheet.data_validation(1, index, EXCEL_MAX_ROWS - 1, index, {
            "validate": "list",
            "source": source,
            "ignore_blank": True,
            "error_title": column.header[:32],
            "error_message": f"Choose one of: {', '.join(values)}"[:255],
        })

    def _list_range(self, values: Sequence[str]) -> str:
        """Long dropdown lists live in a hidden sheet, one list per column."""
        if self._lists_sheet is None:
            self._lists_sheet = self._workbook.add_worksheet("Lists")
            self._lists_sheet.hide()
        column = self._lists_used
        self._lists_used += 1
        for row, value in enumerate(values):
            self._lists_sheet.write_string(row, column, value)
        letter = xlsxwriter.utility.xl_col_to_name(column)
        return f"=Lists!${letter}$1:${letter}${len(values)}"


# =========================================================
# READER
# =========================================================

@dataclass(slots=True, frozen=True)
class RawRow:

    sheet: str
    row_no: int                     # Excel row number (header = 1)
    cells: dict[str, Any]           # column key -> raw value


class _Shared(int):
    """Index into the shared strings table, resolved per batch."""

    __slots__ = ()


# Index file record per shared string: (byte offset, byte length) in the text file
_SPAN = struct.Struct("<QI")


class _SharedStrings:
    """
    Shared strings kept in a list while small, spilled to scratch files when
    large, so memory does not grow with the number of unique values.

    Spilled: UTF-8 text appended to `shared_strings.bin`, and one fixed-size
    (offset, length) record per string in `shared_strings.idx`, so string N is
    found at N * record size. Plain files: no sqlite3 needed.
    """

    __slots__ = (
        "_memory", "_data_path", "_index_path", "_data", "_index",
        "_data_map", "_index_map", "_offset", "_limit", "_cache",
    )

    def __init__(self, scratch_dir: Path, limit: int) -> None:
        self._memory: list[str] | None = []
        self._data_path = scratch_dir / "shared_strings.bin"
        self._index_path = scratch_dir / "shared_strings.idx"
        self._data = None
        self._index = None
        self._data_map: mmap.mmap | None = None
        self._index_map: mmap.mmap | None = None
        self._offset = 0
        self._limit = limit
        self._cache: OrderedDict[int, str] = OrderedDict()

    def add(self, text: str) -> None:
        if self._memory is not None:
            self._memory.append(text)
            if len(self._memory) > self._limit:
                self._spill()
        else:
            self._write(text)

    def finish(self) -> None:
        """All strings are in: map the files for reading (batches are read one after another)."""
        if self._index is None or self._index_map is not None:
            return
        self._data.flush()
        self._index.flush()
        self._index_map = mmap.mmap(self._index.fileno(), 0, access=mmap.ACCESS_READ)
        if self._offset:                                    # mmap can't map an empty file
            self._data_map = mmap.mmap(self._data.fileno(), 0, access=mmap.ACCESS_READ)

    def resolve(self, indexes: set[int]) -> dict[int, str]:
        if self._memory is not None:
            memory = self._memory
            return {index: memory[index] for index in indexes if index < len(memory)}

        self.finish()
        total = len(self._index_map) // _SPAN.size
        found: dict[int, str] = {}
        for index in indexes:
            text = self._cache.get(index)
            if text is not None:
                self._cache.move_to_end(index)
            elif 0 <= index < total:
                offset, length = _SPAN.unpack_from(self._index_map, index * _SPAN.size)
                text = self._data_map[offset:offset + length].decode("utf-8") if length else ""
                self._cache[index] = text
            else:
                continue
            found[index] = text
        while len(self._cache) > 50_000:
            self._cache.popitem(last=False)
        return found

    def close(self) -> None:
        for view in (self._data_map, self._index_map):
            if view is not None:
                view.close()
        self._data_map = self._index_map = None
        if self._index is not None:
            self._data.close()
            self._index.close()
            self._data = self._index = None
            self._data_path.unlink(missing_ok=True)
            self._index_path.unlink(missing_ok=True)

    def _spill(self) -> None:
        self._data_path.parent.mkdir(parents=True, exist_ok=True)
        self._data = open(self._data_path, "w+b")
        self._index = open(self._index_path, "w+b")
        memory, self._memory = self._memory, None
        for text in memory:
            self._write(text)

    def _write(self, text: str) -> None:
        raw = text.encode("utf-8")
        self._index.write(_SPAN.pack(self._offset, len(raw)))
        self._data.write(raw)
        self._offset += len(raw)


class XlsxSheetReader:
    """
    Reads every sheet whose header row matches `sheet`, in workbook order, as
    batches of `RawRow`. Use as a context manager.
    """

    __slots__ = (
        "_path",
        "_spec",
        "_scratch_dir",
        "_max_empty_run",
        "_max_rows",
        "_memory_strings",
        "_archive",
        "_shared",
        "_data_sheets",
        "_estimated_rows",
    )

    def __init__(
        self,
        path: Path,
        sheet: SheetSpec,
        *,
        scratch_dir: Path,
        max_empty_run: int = 1000,
        max_rows: int = 5_000_000,
        memory_strings: int = 100_000,
    ) -> None:
        self._path = path
        self._spec = sheet
        self._scratch_dir = scratch_dir
        self._max_empty_run = max_empty_run
        self._max_rows = max_rows
        self._memory_strings = memory_strings
        self._archive: zipfile.ZipFile | None = None
        self._shared: _SharedStrings | None = None
        self._data_sheets: list[tuple[str, str, HeaderMap]] = []
        self._estimated_rows = 0

    def __enter__(self) -> XlsxSheetReader:
        try:
            try:
                self._archive = zipfile.ZipFile(self._path)
            except (zipfile.BadZipFile, OSError) as error:
                raise InvalidExcelFileException(f"Not a valid .xlsx file ({error}).") from None
            self._open()
        except BaseException:
            self.close()
            raise
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    @property
    def estimated_rows(self) -> int:
        return self._estimated_rows

    @property
    def sheet_names(self) -> list[str]:
        return [name for name, _, _ in self._data_sheets]

    def header_map(self) -> HeaderMap:
        return self._data_sheets[0][2]

    def iter_batches(self, size: int) -> Iterator[list[RawRow]]:
        batch: list[RawRow] = []
        total = 0
        for name, member, header in self._data_sheets:
            for row in self._iter_data_rows(name, member, header):
                total += 1
                if total > self._max_rows:
                    raise InvalidExcelFileException(f"The file has more than {self._max_rows:,} rows.")
                batch.append(row)
                if len(batch) >= size:
                    yield self._resolve(batch)
                    batch = []
        if batch:
            yield self._resolve(batch)

    def close(self) -> None:
        if self._shared is not None:
            self._shared.close()
            self._shared = None
        if self._archive is not None:
            self._archive.close()
            self._archive = None

    # ---------------------------------------------------------

    def _open(self) -> None:
        sheets, shared_member = self._workbook_parts()
        self._shared = _SharedStrings(self._scratch_dir, self._memory_strings)
        if shared_member:
            _parse_shared_strings(self._archive, shared_member, self._shared)
        self._shared.finish()

        first_header: HeaderMap | None = None
        for name, member in sheets:
            header_values, last_row = self._first_row(member)
            header = HeaderMap.build(self._spec, header_values)
            if first_header is None:
                first_header = header
            if header.is_valid:
                self._data_sheets.append((name, member, header))
                self._estimated_rows += max(last_row - 1, 0)

        if not self._data_sheets:
            if first_header is None:
                raise InvalidExcelFileException("The workbook has no sheets.")
            raise InvalidExcelFileException(
                f"Required column(s) missing in the header row: {', '.join(first_header.missing_required)}."
            )

    def _workbook_parts(self) -> tuple[list[tuple[str, str]], str | None]:
        names = set(self._archive.namelist())
        if "xl/workbook.xml" not in names:
            raise InvalidExcelFileException("Not an Excel workbook (xl/workbook.xml is missing).")

        relations: dict[str, str] = {}
        shared_member = "xl/sharedStrings.xml" if "xl/sharedStrings.xml" in names else None
        if "xl/_rels/workbook.xml.rels" in names:
            for attrs in _iter_elements(self._archive, "xl/_rels/workbook.xml.rels", "Relationship"):
                target = _resolve_target(attrs.get("Target", ""))
                relations[attrs.get("Id", "")] = target
                if attrs.get("Type", "").endswith("/sharedStrings") and target in names:
                    shared_member = target

        sheets: list[tuple[str, str]] = []
        for position, attrs in enumerate(_iter_elements(self._archive, "xl/workbook.xml", "sheet"), start=1):
            rel_id = next((value for key, value in attrs.items() if key == "id" or key.endswith(":id")), "")
            member = relations.get(rel_id) or f"xl/worksheets/sheet{position}.xml"
            if member in names:
                sheets.append((attrs.get("name", f"Sheet{position}"), member))
        return sheets, shared_member

    def _first_row(self, member: str) -> tuple[list[Any], int]:
        """Header values of row 1 and the last row number from <dimension> (0 if unknown)."""
        dimension = {"last": 0}
        rows = _iter_sheet_rows(self._archive, member, dimension)
        try:
            for row_no, cells in rows:
                if row_no != 1:
                    return [], dimension["last"]
                width = max(cells) + 1 if cells else 0
                values = [cells.get(index) for index in range(width)]
                shared = {value for value in values if isinstance(value, _Shared)}
                lookup = self._shared.resolve(shared) if shared else {}
                return [lookup.get(value, "") if isinstance(value, _Shared) else value for value in values], dimension["last"]
            return [], dimension["last"]
        finally:
            rows.close()

    def _iter_data_rows(self, name: str, member: str, header: HeaderMap) -> Iterator[RawRow]:
        wanted = tuple(header.indexes.items())
        last_row = 1
        empty_run = 0
        rows = _iter_sheet_rows(self._archive, member, None)
        try:
            for row_no, cells in rows:
                if row_no <= 1:
                    continue
                empty_run += row_no - last_row - 1             # rows missing from the XML are empty
                last_row = row_no
                if empty_run >= self._max_empty_run:
                    return
                values = {key: cells.get(index) for key, index in wanted}
                if all(_is_blank(value) for value in values.values()):
                    empty_run += 1
                    if empty_run >= self._max_empty_run:
                        return
                    continue
                empty_run = 0
                yield RawRow(sheet=name, row_no=row_no, cells=values)
        finally:
            rows.close()

    def _resolve(self, batch: list[RawRow]) -> list[RawRow]:
        shared = {value for row in batch for value in row.cells.values() if isinstance(value, _Shared)}
        if not shared:
            return batch
        lookup = self._shared.resolve(shared)
        for row in batch:
            cells = row.cells
            for key, value in cells.items():
                if isinstance(value, _Shared):
                    cells[key] = lookup.get(value, "")
        return batch


# =========================================================
# EXPAT PARSING
# =========================================================

def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _resolve_target(target: str) -> str:
    if target.startswith("/"):
        return posixpath.normpath(target.lstrip("/"))
    return posixpath.normpath(posixpath.join("xl", target))


def _new_parser() -> expat.XMLParserType:
    parser = expat.ParserCreate()
    parser.buffer_text = True
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)

    def refuse(*_args) -> None:
        raise InvalidExcelFileException("The file contains XML declarations that are not allowed.")

    parser.StartDoctypeDeclHandler = refuse
    parser.EntityDeclHandler = refuse
    return parser


def _feed(archive: zipfile.ZipFile, member: str, parser: expat.XMLParserType) -> Iterator[None]:
    """Feed a zip member to the parser 1 MB at a time, yielding after each step."""
    try:
        with archive.open(member) as handle:
            while chunk := handle.read(_READ_CHUNK):
                parser.Parse(chunk, False)
                yield
        parser.Parse(b"", True)
        yield
    except expat.ExpatError as error:
        raise InvalidExcelFileException(f"The file is damaged ({member}: {error}).") from None
    except (zipfile.BadZipFile, EOFError, OSError) as error:
        raise InvalidExcelFileException(f"The file is damaged ({error}).") from None


def _iter_elements(archive: zipfile.ZipFile, member: str, tag: str) -> list[dict[str, str]]:
    """Attributes of every <tag> element in a small part (workbook.xml, rels)."""
    found: list[dict[str, str]] = []
    parser = _new_parser()

    def start(name: str, attrs: dict[str, str]) -> None:
        if name == tag or name.endswith(f":{tag}"):
            found.append(attrs)

    parser.StartElementHandler = start
    for _ in _feed(archive, member, parser):
        pass
    return found


def _parse_shared_strings(archive: zipfile.ZipFile, member: str, store: _SharedStrings) -> None:
    parser = _new_parser()
    parts: list[str] = []
    state = {"in_si": False, "in_t": False, "phonetic": 0, "size": 0}

    def start(name: str, _attrs) -> None:
        if name == "si":
            state["in_si"] = True
            parts.clear()
            state["size"] = 0
        elif name == "rPh":
            state["phonetic"] += 1
        elif name == "t" and state["in_si"] and not state["phonetic"]:
            state["in_t"] = True

    def end(name: str) -> None:
        if name == "t":
            state["in_t"] = False
        elif name == "rPh":
            state["phonetic"] -= 1
        elif name == "si":
            store.add("".join(parts))
            state["in_si"] = False

    def chars(data: str) -> None:
        if state["in_t"]:
            state["size"] += len(data)
            if state["size"] > EXCEL_MAX_CELL_CHARS:
                raise InvalidExcelFileException("A text value in the file is longer than Excel allows.")
            parts.append(data)

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = chars
    for _ in _feed(archive, member, parser):
        pass


def _column_index(ref: str) -> int:
    number = 0
    for char in ref:
        code = ord(char)
        if 65 <= code <= 90:
            number = number * 26 + code - 64
        elif 97 <= code <= 122:
            number = number * 26 + code - 96
        else:
            break
    return number - 1


def _number(text: str) -> int | float:
    if "." in text or "e" in text or "E" in text:
        return float(text)
    return int(text)


def _iter_sheet_rows(
    archive: zipfile.ZipFile,
    member: str,
    dimension: dict[str, int] | None,
) -> Iterator[tuple[int, dict[int, Any]]]:
    """Yield (excel row number, {column index: raw value}) straight from the XML stream."""
    parser = _new_parser()
    ready: list[tuple[int, dict[int, Any]]] = []

    row_no = 0
    cells: dict[int, Any] = {}
    column = -1
    cell_type: str | None = None
    parts: list[str] = []
    size = 0
    capture = False

    def start(name: str, attrs: dict[str, str]) -> None:
        nonlocal row_no, cells, column, cell_type, parts, size, capture
        if name == "c":
            ref = attrs.get("r")
            column = _column_index(ref) if ref else column + 1
            cell_type = attrs.get("t")
            parts = []
            size = 0
        elif name == "v" or name == "t":
            capture = True
        elif name == "row":
            number = attrs.get("r")
            row_no = int(number) if number else row_no + 1
            cells = {}
            column = -1
        elif name == "dimension" and dimension is not None:
            match = _DIMENSION_END.search(attrs.get("ref", ""))
            if match:
                dimension["last"] = int(match.group(1))

    def end(name: str) -> None:
        nonlocal capture
        if name == "v" or name == "t":
            capture = False
        elif name == "c":
            text = "".join(parts)
            if cell_type == "s":
                if text:
                    cells[column] = _Shared(int(text))
            elif cell_type in ("inlineStr", "str", "e", "d"):
                cells[column] = text
            elif cell_type == "b":
                cells[column] = text == "1"
            elif text:
                try:
                    cells[column] = _number(text)
                except ValueError:
                    cells[column] = text
        elif name == "row":
            ready.append((row_no, cells))

    def chars(data: str) -> None:
        nonlocal size
        if capture:
            size += len(data)
            if size > EXCEL_MAX_CELL_CHARS:
                raise InvalidExcelFileException("A cell in the file is longer than Excel allows.")
            parts.append(data)

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = chars

    for _ in _feed(archive, member, parser):
        if ready:
            yield from ready
            ready.clear()


__all__ = (
    "EXCEL_MAX_ROWS",
    "ExtraColumn",
    "RawRow",
    "XlsxSheetReader",
    "XlsxSheetWriter",
)
