#!/usr/bin/env python3
"""Find near-page-bottom one-line paragraph tails in RHWP dump-pages output.

This is a diagnostic harness for fidelity work. It does not decide correctness;
it surfaces structural candidates where RHWP packs a short final paragraph into
the last few pixels of a page and the next page begins with a fresh paragraph.
Those are the cases to compare against the Hancom oracle before adding any
pagination rule.
"""
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path


DIFF = Path("/tmp/diff")

PAGE_RE = re.compile(r"^=== 페이지 (?P<page>\d+) .*?===$")
BODY_RE = re.compile(r"body_area: .* h=(?P<h>[0-9.]+)")
COL_RE = re.compile(r"단 (?P<col>\d+) \(items=(?P<items>\d+), used=(?P<used>[0-9.]+)px")
PARA_RE = re.compile(
    r"(?P<kind>FullParagraph|PartialParagraph)\s+"
    r"pi=(?P<pi>\d+)\s+"
    r"(?:lines=(?P<start>\d+)\.\.(?P<end>\d+)\s+)?"
    r"h=(?P<h>[0-9.]+).*?"
    r"vpos=(?P<vpos>[0-9.\-]+(?:\.\.[0-9.\-]+)?)\s+"
    r'"(?P<text>.*)"$'
)
TABLE_RE = re.compile(r"Table\s+pi=(?P<pi>\d+)")


@dataclass
class Item:
    kind: str
    pi: int
    h: float
    text: str = ""
    vpos: str = ""
    start_line: int | None = None
    end_line: int | None = None

    @property
    def visible(self) -> bool:
        return bool(self.text.strip()) and self.text.strip() != "(빈)"

    @property
    def line_count(self) -> int:
        if self.start_line is not None and self.end_line is not None:
            return max(0, self.end_line - self.start_line)
        # dump-pages does not print line_count directly. Heights up to about
        # 36px are usually single-line body/list/head paragraphs in the staged
        # corpus; this scanner deliberately reports "one-line-ish", not truth.
        return 1 if self.h <= 36.0 else 2


@dataclass
class Page:
    page: int
    body_h: float = 0.0
    used: float = 0.0
    items: list[Item] = field(default_factory=list)

    @property
    def remaining(self) -> float:
        return self.body_h - self.used


def clean_text(text: str, limit: int = 90) -> str:
    text = " ".join(text.replace("\u00a0", " ").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def parse_dump(path: Path) -> list[Page]:
    pages: list[Page] = []
    current: Page | None = None
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if m := PAGE_RE.match(line):
            current = Page(page=int(m.group("page")))
            pages.append(current)
            continue
        if current is None:
            continue
        if m := BODY_RE.search(line):
            current.body_h = float(m.group("h"))
            continue
        if m := COL_RE.search(line):
            # Current harness focuses single-column dumps; for multi-column,
            # keep the max used column as the page-bottom risk signal.
            current.used = max(current.used, float(m.group("used")))
            continue
        if m := PARA_RE.search(line):
            current.items.append(
                Item(
                    kind=m.group("kind"),
                    pi=int(m.group("pi")),
                    h=float(m.group("h")),
                    text=m.group("text"),
                    vpos=m.group("vpos"),
                    start_line=int(m.group("start")) if m.group("start") else None,
                    end_line=int(m.group("end")) if m.group("end") else None,
                )
            )
            continue
        if m := TABLE_RE.search(line):
            current.items.append(Item(kind="Table", pi=int(m.group("pi")), h=0.0))
    return pages


def last_visible_para(page: Page) -> Item | None:
    for item in reversed(page.items):
        if item.kind in {"FullParagraph", "PartialParagraph"} and item.visible:
            return item
    return None


def first_visible_item(page: Page) -> Item | None:
    for item in page.items:
        if item.kind == "Table":
            return item
        if item.kind in {"FullParagraph", "PartialParagraph"} and item.visible:
            return item
    return None


def scan(
    pages: list[Page],
    max_tail_h: float,
    max_remaining: float,
    min_used_ratio: float,
) -> list[tuple[Page, Item, Page, Item | None]]:
    rows: list[tuple[Page, Item, Page, Item | None]] = []
    for idx, page in enumerate(pages[:-1]):
        if page.body_h <= 0.0:
            continue
        used_ratio = page.used / page.body_h
        if used_ratio < min_used_ratio or page.remaining > max_remaining:
            continue
        tail = last_visible_para(page)
        if tail is None:
            continue
        if tail.h > max_tail_h or tail.line_count != 1:
            continue
        rows.append((page, tail, pages[idx + 1], first_visible_item(pages[idx + 1])))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("doc", nargs="?", help="staged doc name under /tmp/diff")
    parser.add_argument("--dump", type=Path, help="explicit dump-pages file")
    parser.add_argument("--max-tail-h", type=float, default=36.0)
    parser.add_argument("--max-remaining", type=float, default=18.0)
    parser.add_argument("--min-used-ratio", type=float, default=0.965)
    args = parser.parse_args()

    if args.dump:
        dump = args.dump
        doc = args.doc or dump.parent.name
    elif args.doc:
        doc = args.doc
        dump = DIFF / doc / "dump_pages_patched.txt"
        if not dump.exists():
            dump = DIFF / doc / "dump_pages_current.txt"
    else:
        raise SystemExit("provide DOC or --dump")

    pages = parse_dump(dump)
    rows = scan(pages, args.max_tail_h, args.max_remaining, args.min_used_ratio)

    print("doc\tpage\tused\tbody\tremaining\ttail_pi\ttail_h\ttail_vpos\tnext_page\tnext_kind\tnext_pi\ttail_text\tnext_text")
    for page, tail, next_page, next_item in rows:
        next_kind = next_item.kind if next_item else ""
        next_pi = str(next_item.pi) if next_item else ""
        next_text = clean_text(next_item.text) if next_item else ""
        print(
            f"{doc}\t{page.page}\t{page.used:.1f}\t{page.body_h:.1f}\t{page.remaining:.1f}"
            f"\t{tail.pi}\t{tail.h:.1f}\t{tail.vpos}\t{next_page.page}\t{next_kind}\t{next_pi}"
            f"\t{clean_text(tail.text)}\t{next_text}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
