#!/usr/bin/env python3
"""Scan rendered diff dirs for continued CellBreak rowspan table fragments.

This read-only triage helper looks for the structural class behind
`accountability_eval` page 4:

* a rendered PartialTable continuation;
* source table has pageBreak="CELL";
* at least one rowspan cell is carried across the fragment start;
* the source table contains small blank separator rows near the fragment;
* the rendered page is underfilled enough that another short band might be
  expected by the oracle.

It does not judge correctness; use it to find guard docs before renderer edits.
"""

from __future__ import annotations

import argparse
import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


NS = {"hp": "http://www.hancom.co.kr/hwpml/2011/paragraph"}
DIFF = Path("/tmp/diff")

PAGE_RE = re.compile(r"^=== 페이지 (\d+) ")
BODY_RE = re.compile(r"body_area: .* h=([0-9.]+)")
USED_RE = re.compile(r"used=([0-9.]+)px")
PARTIAL_RE = re.compile(
    r"PartialTable\s+pi=(\d+)\s+ci=(\d+)\s+rows=(\d+)\.\.(\d+)\s+cont=(true|false)\s+(\d+)x(\d+)"
)


@dataclass(frozen=True)
class Cell:
    row: int
    col: int
    row_span: int
    col_span: int
    height_hu: int
    text: str


@dataclass(frozen=True)
class TableInfo:
    index: int
    rows: int
    cols: int
    page_break: str
    repeat_header: str
    cells: tuple[Cell, ...]


@dataclass(frozen=True)
class Fragment:
    page: int
    body_h: float
    used_h: float
    pi: int
    ci: int
    start: int
    end: int
    cont: bool
    rows: int
    cols: int


def find_source(docdir: Path) -> Path | None:
    for name in ("source.hwpx", "source_converted.hwpx", "source_fitted.hwpx"):
        path = docdir / name
        if path.exists():
            return path
    return None


def hu_to_px(value: int, dpi: float = 96.0) -> float:
    return value * dpi / 7200.0


def parse_tables(source: Path) -> list[TableInfo]:
    tables: list[TableInfo] = []
    with zipfile.ZipFile(source) as zf:
        sections = sorted(name for name in zf.namelist() if name.startswith("Contents/section"))
        for section in sections:
            root = ET.fromstring(zf.read(section))
            for table in root.findall(".//hp:tbl", NS):
                cells: list[Cell] = []
                max_row = -1
                max_col = -1
                for tc in table.findall(".//hp:tc", NS):
                    addr = tc.find("hp:cellAddr", NS)
                    span = tc.find("hp:cellSpan", NS)
                    size = tc.find("hp:cellSz", NS)
                    if addr is None or span is None or size is None:
                        continue
                    row = int(addr.attrib.get("rowAddr", "0"))
                    col = int(addr.attrib.get("colAddr", "0"))
                    row_span = int(span.attrib.get("rowSpan", "1"))
                    col_span = int(span.attrib.get("colSpan", "1"))
                    max_row = max(max_row, row + row_span - 1)
                    max_col = max(max_col, col + col_span - 1)
                    text = "".join(tc.itertext()).strip()
                    cells.append(
                        Cell(
                            row=row,
                            col=col,
                            row_span=row_span,
                            col_span=col_span,
                            height_hu=int(size.attrib.get("height", "0")),
                            text=text,
                        )
                    )
                tables.append(
                    TableInfo(
                        index=len(tables),
                        rows=max_row + 1,
                        cols=max_col + 1,
                        page_break=table.attrib.get("pageBreak", ""),
                        repeat_header=table.attrib.get("repeatHeader", ""),
                        cells=tuple(cells),
                    )
                )
    return tables


def parse_fragments(docdir: Path) -> list[Fragment]:
    dump = docdir / "dump_pages_current.txt"
    if not dump.exists():
        return []
    page = 0
    body_h = 0.0
    used_h = 0.0
    out: list[Fragment] = []
    for line in dump.read_text(encoding="utf-8", errors="ignore").splitlines():
        if match := PAGE_RE.search(line):
            page = int(match.group(1))
            body_h = 0.0
            used_h = 0.0
            continue
        if match := BODY_RE.search(line):
            body_h = float(match.group(1))
            continue
        if match := USED_RE.search(line):
            used_h = float(match.group(1))
        if match := PARTIAL_RE.search(line):
            out.append(
                Fragment(
                    page=page,
                    body_h=body_h,
                    used_h=used_h,
                    pi=int(match.group(1)),
                    ci=int(match.group(2)),
                    start=int(match.group(3)),
                    end=int(match.group(4)),
                    cont=match.group(5) == "true",
                    rows=int(match.group(6)),
                    cols=int(match.group(7)),
                )
            )
    return out


def row_height_map(table: TableInfo) -> dict[int, float]:
    heights: dict[int, float] = {}
    for cell in table.cells:
        if cell.row_span == 1:
            heights[cell.row] = max(heights.get(cell.row, 0.0), hu_to_px(cell.height_hu))
    return heights


def blank_rows(table: TableInfo) -> set[int]:
    rows: dict[int, list[Cell]] = {}
    for cell in table.cells:
        if cell.row_span == 1:
            rows.setdefault(cell.row, []).append(cell)
    out: set[int] = set()
    for row, cells in rows.items():
        if cells and all(not cell.text.strip() for cell in cells):
            out.add(row)
    return out


def carried_rowspans(table: TableInfo, start: int) -> list[Cell]:
    return [
        cell
        for cell in table.cells
        if cell.row_span > 1 and cell.row < start < cell.row + cell.row_span
    ]


def matching_tables(tables: list[TableInfo], fragment: Fragment) -> list[TableInfo]:
    return [table for table in tables if table.rows == fragment.rows and table.cols == fragment.cols]


def scan_doc(docdir: Path, min_slack: float) -> list[str]:
    source = find_source(docdir)
    if source is None:
        return []
    fragments = parse_fragments(docdir)
    if not fragments:
        return []
    tables = parse_tables(source)
    rows: list[str] = []
    for fragment in fragments:
        if not fragment.cont:
            continue
        slack = fragment.body_h - fragment.used_h
        if slack < min_slack:
            continue
        for table in matching_tables(tables, fragment):
            if table.page_break != "CELL":
                continue
            carried = carried_rowspans(table, fragment.start)
            if not carried:
                continue
            blanks = blank_rows(table)
            nearby_blanks = sorted(
                row for row in blanks if fragment.start - 2 <= row <= fragment.end + 2
            )
            row_heights = row_height_map(table)
            frag_heights = [
                round(row_heights.get(row, 0.0), 1)
                for row in range(fragment.start, min(fragment.end, table.rows))
            ]
            rows.append(
                "\t".join(
                    [
                        docdir.name,
                        f"p{fragment.page}",
                        f"table={table.index}",
                        f"rows={fragment.start}..{fragment.end}",
                        f"slack={slack:.1f}",
                        f"repeatHeader={table.repeat_header}",
                        f"carried={[(c.row, c.col, c.row_span) for c in carried]}",
                        f"blank_near={nearby_blanks}",
                        f"row_h={frag_heights}",
                    ]
                )
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docdirs", nargs="*", type=Path)
    parser.add_argument("--root", type=Path, default=DIFF)
    parser.add_argument("--min-slack", type=float, default=35.0)
    args = parser.parse_args()

    docdirs = args.docdirs or sorted(path for path in args.root.iterdir() if path.is_dir())
    print(
        "doc\tpage\ttable\trows\tslack\trepeatHeader\tcarried\tblank_near\trow_h"
    )
    count = 0
    for docdir in docdirs:
        for line in scan_doc(docdir, args.min_slack):
            print(line)
            count += 1
    print(f"# matches={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
