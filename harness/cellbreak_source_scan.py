#!/usr/bin/env python3
"""Scan HWPX sources for CellBreak rowspan guard candidates.

This is a source-only prefilter for the `accountability_eval` class. It does
not claim a rendering bug. It finds tables that structurally could exercise a
carried-rowspan continuation:

* pageBreak="CELL";
* at least one cell spans multiple rows;
* one or more blank separator rows;
* a possible split row cuts through the rowspan and is near a blank row.

Rendered `dump_pages_current.txt` evidence is still required before accepting a
renderer patch.
"""
from __future__ import annotations

import argparse
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


NS = {"hp": "http://www.hancom.co.kr/hwpml/2011/paragraph"}


@dataclass(frozen=True)
class Cell:
    row: int
    col: int
    row_span: int
    col_span: int
    height: int
    text: str


@dataclass(frozen=True)
class Table:
    doc: str
    path: Path
    section: str
    index: int
    rows: int
    cols: int
    page_break: str
    repeat_header: str
    cells: tuple[Cell, ...]


def int_attr(elem: ET.Element | None, name: str, default: int = 0) -> int:
    if elem is None:
        return default
    try:
        return int(elem.attrib.get(name, str(default)))
    except ValueError:
        return default


def source_paths(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if (root / "source.hwpx").exists():
        return [root / "source.hwpx"]
    paths: list[Path] = []
    for docdir in sorted(path for path in root.iterdir() if path.is_dir()):
        for name in ("source.hwpx", "source_converted.hwpx", "source_fitted.hwpx", "_doc.hwpx"):
            candidate = docdir / name
            if candidate.exists():
                paths.append(candidate)
                break
    return paths


def paths_from_file(path: Path) -> list[Path]:
    return [
        Path(line.strip())
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()
        if line.strip()
    ]


def doc_name(path: Path) -> str:
    if path.name == "_doc.hwpx":
        return path.parent.name
    if path.name.startswith("source"):
        return path.parent.name
    return path.stem


def parse_tables(path: Path) -> list[Table]:
    out: list[Table] = []
    try:
        with zipfile.ZipFile(path) as zf:
            sections = sorted(name for name in zf.namelist() if name.startswith("Contents/section"))
            for section in sections:
                try:
                    root = ET.fromstring(zf.read(section))
                except ET.ParseError:
                    continue
                for table in root.findall(".//hp:tbl", NS):
                    cells: list[Cell] = []
                    max_row = -1
                    max_col = -1
                    for tc in table.findall(".//hp:tc", NS):
                        addr = tc.find("hp:cellAddr", NS)
                        span = tc.find("hp:cellSpan", NS)
                        size = tc.find("hp:cellSz", NS)
                        row = int_attr(addr, "rowAddr")
                        col = int_attr(addr, "colAddr")
                        row_span = int_attr(span, "rowSpan", 1)
                        col_span = int_attr(span, "colSpan", 1)
                        max_row = max(max_row, row + row_span - 1)
                        max_col = max(max_col, col + col_span - 1)
                        cells.append(
                            Cell(
                                row=row,
                                col=col,
                                row_span=row_span,
                                col_span=col_span,
                                height=int_attr(size, "height"),
                                text="".join(tc.itertext()).strip(),
                            )
                        )
                    out.append(
                        Table(
                            doc=doc_name(path),
                            path=path,
                            section=section,
                            index=len(out),
                            rows=max_row + 1,
                            cols=max_col + 1,
                            page_break=table.attrib.get("pageBreak", ""),
                            repeat_header=table.attrib.get("repeatHeader", ""),
                            cells=tuple(cells),
                        )
                    )
    except zipfile.BadZipFile:
        return []
    return out


def blank_rows(table: Table) -> set[int]:
    by_row: dict[int, list[Cell]] = {}
    for cell in table.cells:
        if cell.row_span == 1:
            by_row.setdefault(cell.row, []).append(cell)
    return {row for row, cells in by_row.items() if cells and all(not cell.text for cell in cells)}


def rowspans(table: Table) -> list[Cell]:
    return [cell for cell in table.cells if cell.row_span > 1]


def candidate_split_rows(table: Table, near: int) -> list[int]:
    blanks = blank_rows(table)
    splits: set[int] = set()
    for cell in rowspans(table):
        for split in range(cell.row + 1, cell.row + cell.row_span):
            if any(abs(split - blank) <= near for blank in blanks):
                splits.add(split)
    return sorted(splits)


def hu_to_px(value: int, dpi: float = 96.0) -> float:
    return value * dpi / 7200.0


def row_height_summary(table: Table, rows: list[int]) -> str:
    heights: dict[int, float] = {}
    for cell in table.cells:
        if cell.row_span == 1:
            heights[cell.row] = max(heights.get(cell.row, 0.0), hu_to_px(cell.height))
    return ",".join(f"{row}:{heights.get(row, 0.0):.1f}" for row in rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="*", type=Path)
    parser.add_argument("--paths-file", type=Path, help="newline-delimited HWPX source paths")
    parser.add_argument("--max-bytes", type=int, default=0, help="skip files larger than this; 0 disables")
    parser.add_argument("--near-blank", type=int, default=2)
    args = parser.parse_args()

    print("doc\ttable\tshape\tbreak\trepeat\trowspans\tblank_rows\tcandidate_splits\trow_h\tpath")
    count = 0
    roots = list(args.roots)
    if args.paths_file is not None:
        roots.extend(paths_from_file(args.paths_file))
    if not roots:
        parser.error("provide at least one root or --paths-file")
    for root in roots:
        for source in source_paths(root):
            if args.max_bytes and source.stat().st_size > args.max_bytes:
                continue
            for table in parse_tables(source):
                if table.page_break != "CELL":
                    continue
                spans = rowspans(table)
                blanks = sorted(blank_rows(table))
                splits = candidate_split_rows(table, args.near_blank)
                if not spans or not blanks or not splits:
                    continue
                rows = sorted(set(blanks + splits))
                span_desc = ",".join(f"r{cell.row}c{cell.col}x{cell.row_span}" for cell in spans[:8])
                print(
                    f"{table.doc}\t{table.index}\t{table.rows}x{table.cols}\t"
                    f"{table.page_break}\t{table.repeat_header}\t{span_desc}\t"
                    f"{','.join(map(str, blanks[:16]))}\t{','.join(map(str, splits))}\t"
                    f"{row_height_summary(table, rows)}\t{table.path}"
                )
                count += 1
    print(f"# matches={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
