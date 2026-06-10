#!/usr/bin/env python3
"""Inspect HWPX source paragraphs around renderer paragraph indexes.

This is a read-only triage helper for fidelity work. It prints paragraph text,
line segment geometry, break attributes, and nearby control/table summaries so
renderer dumps can be tied back to structural HWPX metadata without relying on
document text in renderer code.
"""
from __future__ import annotations

import argparse
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


NS = {
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
}


def find_source(path: Path) -> Path:
    if path.is_file():
        return path
    for name in ("source.hwpx", "source_converted.hwpx", "source_fitted.hwpx"):
        candidate = path / name
        if candidate.exists():
            return candidate
    raise SystemExit(f"no HWPX source found under {path}")


def compact(attrs: dict[str, str], keys: tuple[str, ...]) -> str:
    return " ".join(f"{key}={attrs[key]}" for key in keys if key in attrs)


def table_shape(table: ET.Element) -> tuple[int, int, int]:
    max_row = -1
    max_col = -1
    cells = table.findall(".//hp:tc", NS)
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


def para_text(para: ET.Element) -> str:
    parts: list[str] = []
    for text in para.findall(".//hp:t", NS):
        if text.text:
            parts.append(text.text)
    joined = "".join(parts)
    return " ".join(joined.split())


def iter_paragraphs(hwpx: Path) -> list[tuple[str, ET.Element]]:
    out: list[tuple[str, ET.Element]] = []
    with zipfile.ZipFile(hwpx) as zf:
        sections = sorted(name for name in zf.namelist() if name.startswith("Contents/section"))
        for name in sections:
            root = ET.fromstring(zf.read(name))
            for para in root.findall("hp:p", NS):
                out.append((name, para))
    return out


def describe_para(index: int, section: str, para: ET.Element, table_base: int) -> tuple[str, int]:
    text = para_text(para)
    attrs = compact(
        dict(para.attrib),
        (
            "id",
            "paraPrIDRef",
            "styleIDRef",
            "pageBreak",
            "columnBreak",
            "merged",
        ),
    )
    linesegs = para.findall(".//hp:lineseg", NS)
    tables = para.findall("hp:run/hp:tbl", NS)
    pics = para.findall(".//hp:pic", NS)
    shapes = para.findall(".//hp:container", NS) + para.findall(".//hp:shape", NS)

    lines = [
        f"pi={index} section={section} attrs={attrs} text={text[:120]!r}",
        f"  counts: lineSegs={len(linesegs)} directTables={len(tables)} pics={len(pics)} shapes={len(shapes)}",
    ]
    for li, seg in enumerate(linesegs[:5]):
        lines.append(
            "  lineSeg[{li}] ".format(li=li)
            + compact(
                dict(seg.attrib),
                (
                    "textpos",
                    "vertpos",
                    "vertsize",
                    "textheight",
                    "baseline",
                    "spacing",
                    "horzpos",
                    "horzsize",
                ),
            )
        )
    if len(linesegs) > 5:
        lines.append(f"  ... {len(linesegs) - 5} more lineSegs")

    table_index = table_base
    for ci, table in enumerate(tables):
        rows, cols, cell_count = table_shape(table)
        size = child_attrs(table, "sz")
        lines.append(
            f"  table[{ci}] globalTable={table_index} rows={rows} cols={cols} cells={cell_count} "
            f"attrs={compact(dict(table.attrib), ('textWrap', 'pageBreak', 'repeatHeader', 'cellSpacing', 'borderFillIDRef'))} "
            f"size={compact(size, ('width', 'height', 'widthRelTo', 'heightRelTo'))}"
        )
        table_index += 1
    return "\n".join(lines), table_index


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docdir", type=Path)
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    args = parser.parse_args()

    source = find_source(args.docdir)
    paragraphs = iter_paragraphs(source)
    if args.start < 0 or args.end >= len(paragraphs) or args.start > args.end:
        raise SystemExit(f"invalid range; found {len(paragraphs)} paragraphs")

    print(f"source: {source}")
    table_base = 0
    for index, (section, para) in enumerate(paragraphs):
        if args.start <= index <= args.end:
            body, next_table = describe_para(index, section, para, table_base)
            print(body)
            table_base = next_table
        else:
            table_base += len(para.findall("hp:run/hp:tbl", NS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
