#!/usr/bin/env python3
"""Extract RHWP heading-like paragraphs and map them to Hancom pages."""
from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


DIFF = Path("/tmp/diff")
PAGE_RE = re.compile(r"^=== 페이지 (?P<page>\d+) ")
PARA_RE = re.compile(r'FullParagraph\s+pi=(?P<pi>\d+)\s+h=(?P<h>[0-9.]+).*?"(?P<text>.*)"$')


@dataclass(frozen=True)
class Hit:
    rhwp_page: int
    pi: int
    text: str


def clean(text: str) -> str:
    return " ".join(text.replace("\u00a0", " ").split()).strip()


def is_heading(text: str) -> bool:
    if not text or text == "(빈)":
        return False
    if len(text) > 80:
        return False
    patterns = (
        r"^\d+\s+",
        r"^\d+\.",
        r"^\(\d+\)",
        r"^[가-힣]\.",
        r"^[IVXⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+[.)]",
        r"^□\s*",
        r"^󰊱|^󰊲|^󰊳|^󰊴|^󰊵",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def extract_rhwp_headings(dump: Path) -> list[Hit]:
    hits: list[Hit] = []
    page = 0
    for raw in dump.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if m := PAGE_RE.match(line):
            page = int(m.group("page"))
            continue
        if not page:
            continue
        if m := PARA_RE.search(line):
            text = clean(m.group("text"))
            if is_heading(text):
                hits.append(Hit(page, int(m.group("pi")), text))
    return hits


def hancom_text_pages(pdf: Path) -> list[str]:
    text = subprocess.check_output(
        ["pdftotext", "-layout", str(pdf), "-"],
        text=True,
        errors="ignore",
    )
    return text.split("\f")


def find_hancom_pages(pages: list[str], needle: str) -> list[int]:
    compact = " ".join(needle.split())
    out: list[int] = []
    for idx, body in enumerate(pages, 1):
        body_compact = " ".join(body.split())
        if needle in body or compact in body_compact:
            out.append(idx)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("doc")
    parser.add_argument("--dump", type=Path)
    parser.add_argument("--pdf", type=Path)
    parser.add_argument("--page-min", type=int, default=1)
    parser.add_argument("--page-max", type=int)
    args = parser.parse_args()

    docdir = DIFF / args.doc
    dump = args.dump or docdir / "dump_pages_current.txt"
    pdf = args.pdf or docdir / "hancom.pdf"
    if not dump.exists():
        raise SystemExit(f"missing dump {dump}")
    if not pdf.exists():
        raise SystemExit(f"missing Hancom PDF {pdf}")

    hancom_pages = hancom_text_pages(pdf)
    print("rhwp_page\tpi\thancom_page\tdelta\ttext")
    seen: set[str] = set()
    for hit in extract_rhwp_headings(dump):
        if hit.rhwp_page < args.page_min:
            continue
        if args.page_max is not None and hit.rhwp_page > args.page_max:
            continue
        if hit.text in seen:
            continue
        seen.add(hit.text)
        hp = find_hancom_pages(hancom_pages, hit.text)
        if not hp:
            continue
        print(f"{hit.rhwp_page}\t{hit.pi}\t{hp[0]}\t{hit.rhwp_page - hp[0]}\t{hit.text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
