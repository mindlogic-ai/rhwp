#!/usr/bin/env python3
"""Map semantic headings to Hancom PDF pages and RHWP dump pages.

This is a lightweight drift diagnostic for renderer fidelity work. It lets a
guard doc prove whether RHWP is merely visually different on the same page or
semantically ahead/behind Hancom by whole pages.
"""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path


DIFF = Path("/tmp/diff")


def read_needles(args: argparse.Namespace) -> list[str]:
    needles: list[str] = []
    if args.needles_file:
        needles.extend(
            line.strip()
            for line in args.needles_file.read_text(encoding="utf-8", errors="ignore").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
    needles.extend(args.needle)
    if not needles:
        raise SystemExit("provide at least one --needle or --needles-file line")
    return needles


def hancom_pages(pdf: Path, needle: str) -> list[int]:
    if not pdf.exists():
        return []
    text = subprocess.check_output(
        ["pdftotext", "-layout", str(pdf), "-"],
        text=True,
        errors="ignore",
    )
    return [page for page, body in enumerate(text.split("\f"), 1) if needle in body]


def rhwp_page_bodies(dump: Path) -> list[tuple[int, str]]:
    if not dump.exists():
        return []
    text = dump.read_text(encoding="utf-8", errors="ignore")
    chunks = re.split(r"\n=== 페이지 (\d+) .*?===\n", text)
    pages: list[tuple[int, str]] = []
    for idx in range(1, len(chunks), 2):
        pages.append((int(chunks[idx]), chunks[idx + 1]))
    return pages


def rhwp_pages(pages: list[tuple[int, str]], needle: str) -> list[int]:
    normalized = needle.replace("        ", " ").replace("8        ", "8. ")
    compact = " ".join(needle.split())
    out: list[int] = []
    for page, body in pages:
        body_compact = " ".join(body.split())
        if needle in body or normalized in body or compact in body_compact:
            out.append(page)
    return out


def fmt_pages(pages: list[int]) -> str:
    return ",".join(str(page) for page in pages[:12])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("doc", help="staged doc name under /tmp/diff")
    parser.add_argument("--needle", action="append", default=[], help="heading/text to locate")
    parser.add_argument("--needles-file", type=Path, help="newline-delimited headings")
    parser.add_argument("--pdf", type=Path, help="override Hancom PDF path")
    parser.add_argument("--dump", type=Path, help="override RHWP dump-pages path")
    args = parser.parse_args()

    docdir = DIFF / args.doc
    pdf = args.pdf or docdir / "hancom.pdf"
    dump = args.dump or docdir / "dump_pages_current.txt"
    needles = read_needles(args)
    rhwp_bodies = rhwp_page_bodies(dump)

    print("needle\thancom_pages\trhwp_pages\tfirst_delta")
    for needle in needles:
        hp = hancom_pages(pdf, needle)
        rp = rhwp_pages(rhwp_bodies, needle)
        delta = ""
        if hp and rp:
            delta = str(rp[0] - hp[0])
        print(f"{needle}\t{fmt_pages(hp)}\t{fmt_pages(rp)}\t{delta}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
