#!/usr/bin/env python3
"""Audit generated fidelity galleries for truncated or stale visual evidence.

This catches the failure mode from old three-way galleries: a document label can
say Hancom has 17 pages while the HTML only embeds 14 page strips, or generated
PNG strips can have a suspiciously short aspect ratio that makes bottom content
look clipped.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from PIL import Image


DOC_LINK_RE = re.compile(r'<a\s+href="([^"]+)/index\.html"')
IMG_RE = re.compile(r'<img\b[^>]*\bsrc="([^"]*page-\d+\.png)"')
COUNT_PATTERNS = (
    re.compile(r"Hancom=(\d+)p?\s+RHWP=(\d+)p?", re.IGNORECASE),
    re.compile(r"한컴=(\d+)p?\s*[· ]+\s*ours=(\d+)p?", re.IGNORECASE),
    re.compile(r"한컴=(\d+)p?\s*[· ]+\s*upstream=\d+p?\s*[· ]+\s*ours=(\d+)p?", re.IGNORECASE),
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def declared_total(html: str) -> int | None:
    for pattern in COUNT_PATTERNS:
        match = pattern.search(html)
        if match:
            return max(int(match.group(1)), int(match.group(2)))
    return None


def image_paths(doc_index: Path, html: str) -> list[Path]:
    paths: list[Path] = []
    for src in IMG_RE.findall(html):
        paths.append((doc_index.parent / src).resolve())
    return paths


def suspicious_aspect(path: Path) -> str | None:
    if not path.exists():
        return "missing"
    with Image.open(path) as image:
        width, height = image.size
    if width <= 0 or height <= 0:
        return f"invalid-size {width}x{height}"
    # Old 3-column qlmanage strips such as 2304x1103 are visibly short and often
    # hide bottom-edge drift. Current 2-column galleries can be short for valid
    # landscape pages, especially wide tables, so only flag very-wide strips.
    if width >= 2200 and height / width < 0.55:
        return f"suspicious-short {width}x{height}"
    return None


def doc_indexes(root: Path) -> list[Path]:
    index = root / "index.html"
    if not index.exists():
        raise SystemExit(f"missing gallery index: {index}")
    html = read(index)
    links = [root / href / "index.html" for href in DOC_LINK_RE.findall(html)]
    if links:
        return [path for path in links if path.exists()]
    return sorted(path for path in root.glob("*/index.html") if path.parent != root)


def audit(root: Path) -> int:
    failures = 0
    checked = 0
    for doc_index in doc_indexes(root):
        checked += 1
        html = read(doc_index)
        imgs = image_paths(doc_index, html)
        total = declared_total(html)
        if total is not None and len(imgs) < total:
            failures += 1
            print(
                f"TRUNCATED {doc_index.parent.name}: html embeds {len(imgs)} "
                f"page strips but declares {total} pages"
            )
        for path in imgs:
            issue = suspicious_aspect(path)
            if issue:
                failures += 1
                print(f"IMAGE {doc_index.parent.name}/{path.name}: {issue}")
    if failures:
        print(f"\nFAIL: {failures} gallery evidence issue(s) across {checked} doc(s)")
        return 1
    print(f"PASS: no gallery truncation/aspect issues across {checked} doc(s)")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("gallery_dir", help="directory containing index.html")
    args = parser.parse_args()
    raise SystemExit(audit(Path(args.gallery_dir)))


if __name__ == "__main__":
    main()
