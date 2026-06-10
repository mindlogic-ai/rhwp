#!/usr/bin/env python3
"""Scan HWPX table rows where declared cell height exceeds saved content height.

This is a read-only fidelity triage helper. It intentionally reports structural
geometry only: table/page-break attributes, row/column/span shape, declared cell
height, saved line-segment extents, and nested table extents.
"""
from __future__ import annotations

import argparse
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


NS = {
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
}
DPI = 96.0


def hu_to_px(raw: str | int | None) -> float:
    if raw is None:
        return 0.0
    return int(raw) * DPI / 7200.0


def find_source(path: Path) -> Path:
    if path.is_file():
        return path
    for name in ("source.hwpx", "source_converted.hwpx", "source_fitted.hwpx"):
        candidate = path / name
        if candidate.exists():
            return candidate
    raise SystemExit(f"no HWPX source found under {path}")


def direct_text(elem: ET.Element) -> str:
    return " ".join("".join(elem.itertext()).split())


def line_seg_bottom_px(para: ET.Element) -> float:
    bottom = 0.0
    for seg in para.findall(".//hp:lineseg", NS):
        attrs = seg.attrib
        y = hu_to_px(attrs.get("vertpos"))
        h = max(
            hu_to_px(attrs.get("vertsize")),
            hu_to_px(attrs.get("textheight")),
            hu_to_px(attrs.get("spacing")),
        )
        bottom = max(bottom, y + h)
    return bottom


def nested_table_height_px(cell: ET.Element) -> float:
    total = 0.0
    for nested in cell.findall(".//hp:tbl", NS):
        sz = nested.find("hp:sz", NS)
        if sz is not None:
            total += hu_to_px(sz.attrib.get("height"))
            continue
        row_heights = []
        for row in nested.findall("hp:tr", NS):
            heights = []
            for nested_cell in row.findall("hp:tc", NS):
                cell_sz = nested_cell.find("hp:cellSz", NS)
                if cell_sz is not None:
                    heights.append(hu_to_px(cell_sz.attrib.get("height")))
            if heights:
                row_heights.append(max(heights))
        total += sum(row_heights)
    return total


def direct_cells(row: ET.Element) -> list[ET.Element]:
    return row.findall("hp:tc", NS)


def cell_addr(cell: ET.Element) -> tuple[int, int]:
    addr = cell.find("hp:cellAddr", NS)
    if addr is None:
        return (0, 0)
    return (int(addr.attrib.get("rowAddr", "0")), int(addr.attrib.get("colAddr", "0")))


def scan_source(source: Path, min_slack: float, table_index: int | None) -> None:
    print(f"source: {source}")
    with zipfile.ZipFile(source) as zf:
        tables: list[tuple[str, ET.Element]] = []
        for name in sorted(n for n in zf.namelist() if n.startswith("Contents/section")):
            root = ET.fromstring(zf.read(name))
            for table in root.findall(".//hp:tbl", NS):
                tables.append((name, table))

    for ti, (section, table) in enumerate(tables):
        if table_index is not None and ti != table_index:
            continue
        rows = table.findall("hp:tr", NS)
        attrs = table.attrib
        for ri, row in enumerate(rows):
            row_declared = 0.0
            row_content = 0.0
            cell_notes = []
            for cell in sorted(direct_cells(row), key=cell_addr):
                span = cell.find("hp:cellSpan", NS)
                row_span = int(span.attrib.get("rowSpan", "1")) if span is not None else 1
                col_span = int(span.attrib.get("colSpan", "1")) if span is not None else 1
                if row_span != 1:
                    continue
                cell_sz = cell.find("hp:cellSz", NS)
                declared = hu_to_px(cell_sz.attrib.get("height")) if cell_sz is not None else 0.0
                direct_paras = cell.findall("./hp:subList/hp:p", NS)
                line_bottom = max((line_seg_bottom_px(p) for p in direct_paras), default=0.0)
                nested_h = nested_table_height_px(cell)
                content = max(line_bottom, nested_h)
                row_declared = max(row_declared, declared)
                row_content = max(row_content, content)
                _, col = cell_addr(cell)
                cell_notes.append(
                    f"c{col}:decl={declared:.1f} content={content:.1f} "
                    f"lines={sum(len(p.findall('.//hp:lineseg', NS)) for p in direct_paras)} "
                    f"nested={nested_h:.1f} span={row_span}x{col_span}"
                )
            slack = row_declared - row_content
            if row_declared > 0.0 and slack >= min_slack:
                text = direct_text(row)[:80]
                print(
                    f"table={ti} section={section} row={ri} "
                    f"textWrap={attrs.get('textWrap','')} pageBreak={attrs.get('pageBreak','')} "
                    f"repeatHeader={attrs.get('repeatHeader','')} "
                    f"decl={row_declared:.1f} content={row_content:.1f} slack={slack:.1f} "
                    f"text={text!r}"
                )
                for note in cell_notes:
                    print(f"  {note}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docdir", type=Path)
    parser.add_argument("--table-index", type=int)
    parser.add_argument("--min-slack", type=float, default=60.0)
    args = parser.parse_args()
    scan_source(find_source(args.docdir), args.min_slack, args.table_index)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
