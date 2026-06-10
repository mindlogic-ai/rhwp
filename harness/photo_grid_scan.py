#!/usr/bin/env python3
"""Scan staged HWPX docs for photo-grid table classes.

This is a read-only guard-finder for renderer fidelity work. It looks for
tables with multiple picture cells, mixed treat-as-character/non-TAC pictures,
and negative paragraph-relative offsets. Those are structural clues for the
meeting-template photo-grid fixes; renderer code must not key on filenames or
visible picture placeholder text.
"""
from __future__ import annotations

import argparse
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


DIFF = Path("/tmp/diff")
NS = {
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
}
SIGNED32 = 1 << 32
SIGNED31 = 1 << 31


@dataclass(frozen=True)
class PictureCell:
    row: int
    col: int
    row_span: int
    col_span: int
    treat_as_char: bool
    vert_offset: int
    horz_offset: int
    width: int
    height: int


@dataclass(frozen=True)
class TableHit:
    doc: str
    path: Path
    section: str
    table_index: int
    rows: int
    cols: int
    text_wrap: str
    page_break: str
    repeat_header: str
    pic_cells: tuple[PictureCell, ...]


def signed_i32(raw: str | None) -> int:
    if raw is None:
        return 0
    value = int(raw)
    return value - SIGNED32 if value >= SIGNED31 else value


def int_attr(elem: ET.Element | None, name: str, default: int = 0) -> int:
    if elem is None:
        return default
    raw = elem.attrib.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def child(parent: ET.Element, name: str) -> ET.Element | None:
    return parent.find(f"hp:{name}", NS)


def source_paths(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    for name in ("source.hwpx", "source_converted.hwpx", "source_fitted.hwpx"):
        candidate = root / name
        if candidate.exists():
            return [candidate]
    paths: list[Path] = []
    for docdir in sorted(path for path in root.iterdir() if path.is_dir()):
        for name in ("source.hwpx", "source_converted.hwpx", "source_fitted.hwpx"):
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


def table_shape(table: ET.Element) -> tuple[int, int]:
    max_row = -1
    max_col = -1
    for cell in table.findall(".//hp:tc", NS):
        addr = child(cell, "cellAddr")
        if addr is None:
            continue
        max_row = max(max_row, int_attr(addr, "rowAddr"))
        max_col = max(max_col, int_attr(addr, "colAddr"))
    return max_row + 1, max_col + 1


def picture_cells(table: ET.Element) -> tuple[PictureCell, ...]:
    out: list[PictureCell] = []
    for cell in table.findall(".//hp:tc", NS):
        pics = cell.findall(".//hp:pic", NS)
        if not pics:
            continue
        addr = child(cell, "cellAddr")
        span = child(cell, "cellSpan")
        row = int_attr(addr, "rowAddr")
        col = int_attr(addr, "colAddr")
        row_span = int_attr(span, "rowSpan", 1)
        col_span = int_attr(span, "colSpan", 1)
        for pic in pics:
            pos = child(pic, "pos")
            size = child(pic, "sz")
            out.append(
                PictureCell(
                    row=row,
                    col=col,
                    row_span=row_span,
                    col_span=col_span,
                    treat_as_char=(pos is not None and pos.attrib.get("treatAsChar") == "1"),
                    vert_offset=signed_i32(pos.attrib.get("vertOffset") if pos is not None else None),
                    horz_offset=signed_i32(pos.attrib.get("horzOffset") if pos is not None else None),
                    width=int_attr(size, "width"),
                    height=int_attr(size, "height"),
                )
            )
    return tuple(out)


def scan_one(source: Path) -> list[TableHit]:
    doc = source.parent.name
    hits: list[TableHit] = []
    try:
        with zipfile.ZipFile(source) as zf:
            table_index = 0
            for name in sorted(n for n in zf.namelist() if n.startswith("Contents/section")):
                try:
                    root = ET.fromstring(zf.read(name))
                except ET.ParseError:
                    continue
                for table in root.findall(".//hp:tbl", NS):
                    rows, cols = table_shape(table)
                    pics = picture_cells(table)
                    if len(pics) >= 4 and cols >= 2:
                        hits.append(
                            TableHit(
                                doc=doc,
                                path=source,
                                section=name,
                                table_index=table_index,
                                rows=rows,
                                cols=cols,
                                text_wrap=table.attrib.get("textWrap", ""),
                                page_break=table.attrib.get("pageBreak", ""),
                                repeat_header=table.attrib.get("repeatHeader", ""),
                                pic_cells=pics,
                            )
                        )
                    table_index += 1
    except zipfile.BadZipFile:
        return []
    return hits


def has_mixed_row(hit: TableHit) -> bool:
    by_row: dict[int, set[bool]] = {}
    for pic in hit.pic_cells:
        by_row.setdefault(pic.row, set()).add(pic.treat_as_char)
    return any(len(values) > 1 for values in by_row.values())


def fmt_px(hwpunit: int, dpi: float) -> str:
    return f"{hwpunit * dpi / 7200.0:.1f}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=None)
    parser.add_argument("--paths-file", type=Path, help="newline-delimited HWPX source paths")
    parser.add_argument("--max-bytes", type=int, default=0, help="skip files larger than this; 0 disables")
    parser.add_argument("--only-mixed", action="store_true")
    parser.add_argument("--dpi", type=float, default=96.0)
    args = parser.parse_args()

    print(
        "doc\ttable\tshape\twrap\tbreak\trepeat\tpics\ttac\tnon_tac\t"
        "mixed_row\tneg_offsets\trows\tpath"
    )
    count = 0
    roots = []
    if args.root is not None:
        roots.extend(source_paths(args.root))
    if args.paths_file is not None:
        roots.extend(paths_from_file(args.paths_file))
    if not roots:
        roots.extend(source_paths(DIFF))
    for source in roots:
        if args.max_bytes and source.stat().st_size > args.max_bytes:
            continue
        for hit in scan_one(source):
            mixed = has_mixed_row(hit)
            if args.only_mixed and not mixed:
                continue
            tac = sum(1 for pic in hit.pic_cells if pic.treat_as_char)
            non_tac = len(hit.pic_cells) - tac
            neg = [
                f"r{pic.row}c{pic.col}:v{fmt_px(pic.vert_offset, args.dpi)}"
                for pic in hit.pic_cells
                if pic.vert_offset < 0 or pic.horz_offset < 0
            ]
            rows = ",".join(
                f"r{pic.row}c{pic.col}{'T' if pic.treat_as_char else 'N'}"
                for pic in hit.pic_cells
            )
            print(
                f"{hit.doc}\t{hit.table_index}\t{hit.rows}x{hit.cols}\t"
                f"{hit.text_wrap}\t{hit.page_break}\t{hit.repeat_header}\t"
                f"{len(hit.pic_cells)}\t{tac}\t{non_tac}\t{int(mixed)}\t"
                f"{';'.join(neg)}\t{rows}\t{hit.path}"
            )
            count += 1
    print(f"# matches={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
