#!/usr/bin/env python3
"""Scan RHWP dump-pages output for heading + near-full-page photo table shapes."""
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


DIFF = Path("/tmp/diff")


PAGE_RE = re.compile(r"\n=== 페이지 (\d+) .*?===\n")
PARA_RE = re.compile(
    r"FullParagraph\s+pi=(?P<pi>\d+)\s+h=(?P<h>[0-9.]+).*?vpos=(?P<vpos>[^ ]+)\s+\"(?P<text>.*)\""
)
TABLE_RE = re.compile(
    r"Table\s+pi=(?P<pi>\d+)\s+ci=(?P<ci>\d+)\s+"
    r"(?P<shape>\d+x\d+)\s+(?P<w>[0-9.]+)x(?P<h>[0-9.]+)px\s+"
    r"wrap=(?P<wrap>\w+)\s+tac=(?P<tac>\w+)\s+vpos=(?P<vpos>[^ ]+)"
)


@dataclass(frozen=True)
class PageItem:
    kind: str
    pi: int
    height: float
    text: str = ""
    shape: str = ""
    wrap: str = ""
    tac: str = ""


def parse_dump(path: Path) -> list[tuple[int, list[PageItem]]]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    chunks = PAGE_RE.split(text)
    pages: list[tuple[int, list[PageItem]]] = []
    for idx in range(1, len(chunks), 2):
        page = int(chunks[idx])
        body = chunks[idx + 1]
        items: list[PageItem] = []
        for line in body.splitlines():
            if m := PARA_RE.search(line):
                items.append(
                    PageItem(
                        kind="para",
                        pi=int(m.group("pi")),
                        height=float(m.group("h")),
                        text=m.group("text"),
                    )
                )
                continue
            if m := TABLE_RE.search(line):
                items.append(
                    PageItem(
                        kind="table",
                        pi=int(m.group("pi")),
                        height=float(m.group("h")),
                        shape=m.group("shape"),
                        wrap=m.group("wrap"),
                        tac=m.group("tac"),
                    )
                )
        pages.append((page, items))
    return pages


def is_heading_text(text: str) -> bool:
    stripped = text.strip()
    if not stripped or stripped == "(빈)":
        return False
    if len(stripped) > 80:
        return False
    return bool(
        re.match(r"^([가-힣]\.|[0-9]+\.|\([0-9]+\)|[□○󰊱-󰊵])", stripped)
    )


def table_rows(shape: str) -> int:
    try:
        return int(shape.split("x", 1)[0])
    except ValueError:
        return 0


def dump_path_for(doc: str, override: str) -> Path:
    if override:
        path = Path(override)
        if path.is_file():
            return path
        candidate = DIFF / doc / override
        if candidate.exists():
            return candidate
        raise SystemExit(f"missing dump override {override!r} for {doc}")
    dump = DIFF / doc / "dump_pages_current.txt"
    if dump.exists():
        return dump
    dump = DIFF / doc / "dump_pages_debug.txt"
    if dump.exists():
        return dump
    raise SystemExit(f"missing dump_pages_current.txt for {doc}")


def scan(doc: str, min_table_height: float, min_rows: int, dump_override: str) -> list[str]:
    dump = dump_path_for(doc, dump_override)
    rows: list[str] = []
    for page, items in parse_dump(dump):
        for idx, item in enumerate(items[:-1]):
            nxt = items[idx + 1]
            prev = items[idx - 1] if idx > 0 else None
            if item.kind != "para" or nxt.kind != "table":
                continue
            if not is_heading_text(item.text):
                continue
            if nxt.wrap != "TopAndBottom" or nxt.height < min_table_height:
                continue
            if table_rows(nxt.shape) < min_rows:
                continue
            rows.append(
                "\t".join(
                    [
                        doc,
                        str(page),
                        str(item.pi),
                        f"{item.height:.1f}",
                        item.text,
                        str(nxt.pi),
                        nxt.shape,
                        f"{nxt.height:.1f}",
                        nxt.tac,
                        prev.kind if prev else "",
                        str(prev.pi) if prev else "",
                        f"{prev.height:.1f}" if prev else "",
                    ]
                )
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docs", nargs="+")
    parser.add_argument("--min-table-height", type=float, default=650.0)
    parser.add_argument("--min-rows", type=int, default=4)
    parser.add_argument("--dump", default="", help="dump filename/path to use instead of dump_pages_current.txt")
    args = parser.parse_args()

    print(
        "doc\tpage\theading_pi\theading_h\theading_text\ttable_pi\tshape\ttable_h\ttac\tprev_kind\tprev_pi\tprev_h"
    )
    for doc in args.docs:
        for row in scan(doc, args.min_table_height, args.min_rows, args.dump):
            print(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
