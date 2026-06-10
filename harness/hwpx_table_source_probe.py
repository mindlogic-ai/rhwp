#!/usr/bin/env python3
"""Inspect HWPX source table/cell/picture attributes for fidelity triage.

This is read-only and intentionally generic. Use it when visual probes point at
table/image geometry and you need the source table dimensions, cell margins,
picture sizes, crop boxes, and signed object offsets before changing renderer
code.

Usage:
  python3 harness/hwpx_table_source_probe.py /tmp/diff/doc_name --list
  python3 harness/hwpx_table_source_probe.py /tmp/diff/doc_name --table-index 4
"""
from __future__ import annotations

import argparse
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


NS = {
    "hh": "http://www.hancom.co.kr/hwpml/2011/head",
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
}
SIGNED32 = 1 << 32
SIGNED31 = 1 << 31


def find_source(docdir: Path) -> Path:
    if docdir.is_file():
        return docdir
    for name in ("source.hwpx", "source_converted.hwpx", "source_fitted.hwpx"):
        path = docdir / name
        if path.exists():
            return path
    raise SystemExit(f"no HWPX source found under {docdir}")


def signed_i32(raw: str | None) -> int | None:
    if raw is None:
        return None
    value = int(raw)
    return value - SIGNED32 if value >= SIGNED31 else value


def px_from_hu(value: int | None, dpi: float) -> str:
    if value is None:
        return ""
    return f"{value * dpi / 7200.0:.1f}px"


def tables(hwpx: Path) -> list[tuple[str, ET.Element]]:
    out: list[tuple[str, ET.Element]] = []
    with zipfile.ZipFile(hwpx) as zf:
        for name in sorted(n for n in zf.namelist() if n.startswith("Contents/section")):
            root = ET.fromstring(zf.read(name))
            for table in root.findall(".//hp:tbl", NS):
                out.append((name, table))
    return out


def border_fills(hwpx: Path) -> list[ET.Element]:
    with zipfile.ZipFile(hwpx) as zf:
        root = ET.fromstring(zf.read("Contents/header.xml"))
    return root.findall(".//hh:borderFill", NS)


def table_shape(table: ET.Element) -> tuple[int, int, int]:
    cells = table.findall(".//hp:tc", NS)
    max_row = -1
    max_col = -1
    for cell in cells:
        addr = cell.find("hp:cellAddr", NS)
        if addr is None:
            continue
        max_row = max(max_row, int(addr.attrib.get("rowAddr", "0")))
        max_col = max(max_col, int(addr.attrib.get("colAddr", "0")))
    return max_row + 1, max_col + 1, len(cells)


def child_attrs(parent: ET.Element, name: str) -> dict[str, str]:
    elem = parent.find(f"hp:{name}", NS)
    return dict(elem.attrib) if elem is not None else {}


def compact_attrs(attrs: dict[str, str], keys: list[str]) -> str:
    return " ".join(f"{key}={attrs[key]}" for key in keys if key in attrs)


def print_table_list(items: list[tuple[str, ET.Element]]) -> None:
    print("tables:")
    for index, (section, table) in enumerate(items):
        rows, cols, cell_count = table_shape(table)
        size = child_attrs(table, "sz")
        print(
            f"  {index}: {section} rows={rows} cols={cols} cells={cell_count} "
            f"attrs={compact_attrs(table.attrib, ['textWrap', 'pageBreak', 'repeatHeader', 'cellSpacing', 'borderFillIDRef'])} "
            f"size={compact_attrs(size, ['width', 'height', 'widthRelTo', 'heightRelTo'])}"
        )


def print_border_fills(items: list[ET.Element], ids: set[int] | None) -> None:
    print("border_fills:")
    for idx, border_fill in enumerate(items, start=1):
        if ids is not None and idx not in ids:
            continue
        fill = border_fill.find("hh:fillBrush", NS)
        face = border_fill.find("hh:slash", NS)
        back = ""
        if fill is not None:
            win = fill.find(".//hh:winBrush", NS)
            if win is not None:
                back = compact_attrs(dict(win.attrib), ["faceColor", "hatchColor", "alpha"])
        borders = []
        for name in ("leftBorder", "rightBorder", "topBorder", "bottomBorder"):
            elem = border_fill.find(f"hh:{name}", NS)
            if elem is None:
                continue
            borders.append(f"{name}({compact_attrs(dict(elem.attrib), ['type', 'width', 'color'])})")
        diagonal = ""
        if face is not None:
            diagonal = compact_attrs(dict(face.attrib), ["type", "CrookedSlash"])
        print(f"  {idx}: back={back} diagonal={diagonal} {' '.join(borders)}")


def print_selected_table(index: int, section: str, table: ET.Element, dpi: float) -> None:
    rows, cols, cell_count = table_shape(table)
    print(f"table_index={index} section={section} rows={rows} cols={cols} cells={cell_count}")
    print(f"attrs: {table.attrib}")
    for name in ("sz", "inMargin", "outMargin"):
        print(f"{name}: {child_attrs(table, name)}")
    for cell in table.findall(".//hp:tc", NS):
        addr = child_attrs(cell, "cellAddr")
        span = child_attrs(cell, "cellSpan")
        size = child_attrs(cell, "cellSz")
        margin = child_attrs(cell, "cellMargin")
        paras = cell.findall(".//hp:p", NS)
        line_seg_elems = [seg for para in paras for seg in para.findall(".//hp:lineseg", NS)]
        line_segs = len(line_seg_elems)
        first_seg = line_seg_elems[0].attrib if line_seg_elems else {}
        text = " ".join("".join(cell.itertext()).split())[:80]
        print(
            "\ncell "
            f"addr={addr} span={span} size={size} margin={margin} "
            f"borderFillIDRef={cell.attrib.get('borderFillIDRef', '')} "
            f"vAlign={cell.attrib.get('vAlign', cell.attrib.get('vertAlign', ''))} "
            f"paras={len(paras)} lineSegs={line_segs} "
            f"firstLineSeg={compact_attrs(first_seg, ['textpos', 'vertpos', 'vertsize', 'textheight', 'baseline', 'spacing'])} "
            f"text={text!r}"
        )
        for pic in cell.findall(".//hp:pic", NS):
            pic_size = child_attrs(pic, "sz")
            pos = child_attrs(pic, "pos")
            img_clip = child_attrs(pic, "imgClip")
            img_dim = child_attrs(pic, "imgDim")
            vo = signed_i32(pos.get("vertOffset"))
            ho = signed_i32(pos.get("horzOffset"))
            print(
                "  pic "
                f"attrs={compact_attrs(pic.attrib, ['textWrap', 'textFlow', 'zOrder', 'instid'])} "
                f"size={pic_size} pos={pos} "
                f"signedOffset=(v={vo} {px_from_hu(vo, dpi)}, h={ho} {px_from_hu(ho, dpi)}) "
                f"imgClip={img_clip} imgDim={img_dim}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docdir", type=Path, help="doc directory under /tmp/diff or a .hwpx file")
    parser.add_argument("--list", action="store_true", help="list all source tables")
    parser.add_argument("--table-index", type=int, help="print one source table in detail")
    parser.add_argument("--border-fills", default="", help="comma-separated borderFill IDs to print, or 'all'")
    parser.add_argument("--dpi", type=float, default=96.0)
    args = parser.parse_args()

    source = find_source(args.docdir)
    items = tables(source)
    print(f"source: {source}")
    if args.list or args.table_index is None:
        print_table_list(items)
    if args.border_fills:
        ids = None
        if args.border_fills != "all":
            ids = {int(part) for part in args.border_fills.split(",") if part.strip()}
        print_border_fills(border_fills(source), ids)
    if args.table_index is not None:
        if args.table_index < 0 or args.table_index >= len(items):
            raise SystemExit(f"table index {args.table_index} out of range; found {len(items)}")
        section, table = items[args.table_index]
        print_selected_table(args.table_index, section, table, args.dpi)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
