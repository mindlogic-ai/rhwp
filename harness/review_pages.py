#!/usr/bin/env python3
"""Build a small Hancom/RHWP side-by-side review for selected pages.

Use this for large guard docs where `review_gallery.py --max-pages N` is too
slow. It reuses the same raster/stitch primitives, but only for explicit page
numbers.
"""
from __future__ import annotations

import argparse
import html
from pathlib import Path

from PIL import Image, ImageDraw

import review_gallery


DIFF = Path("/tmp/diff")
COLUMN_WIDTH = review_gallery.COLUMN_WIDTH
GAP = review_gallery.GAP
LABEL_H = review_gallery.LABEL_H


def parse_pages(raw: str) -> list[int]:
    pages: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_raw, end_raw = part.split("-", 1)
            start = int(start_raw)
            end = int(end_raw)
            pages.extend(range(start, end + 1))
        else:
            pages.append(int(part))
    out = sorted(set(page for page in pages if page > 0))
    if not out:
        raise argparse.ArgumentTypeError("no positive pages supplied")
    return out


def image_or_missing(path: Path | None, label: str, page: int) -> Image.Image:
    if path is not None and path.exists():
        return review_gallery.fit_width(Image.open(path).convert("RGB"), COLUMN_WIDTH)
    return review_gallery.missing_page(label, page)


def page_path(paths: list[Path], page: int) -> Path | None:
    idx = page - 1
    if 0 <= idx < len(paths):
        return paths[idx]
    return None


def build(outdir: Path, doc: str, pages: list[int], export_current: bool) -> None:
    docdir = DIFF / doc
    if export_current:
        review_gallery.export_current(docdir)
    hancom = review_gallery.raster_hancom(docdir)
    svg_pages = review_gallery.svg_pages(docdir)
    rhwp_pages: dict[int, Path] = {}
    for page in pages:
        svg = page_path(svg_pages, page)
        if svg is None:
            continue
        png = docdir / f"rhwp_review_p-{page}.png"
        review_gallery.raster_svg(svg, png)
        rhwp_pages[page] = png

    doc_out = outdir / doc
    doc_out.mkdir(parents=True, exist_ok=True)
    rows: list[tuple[int, str]] = []
    for page in pages:
        left = image_or_missing(page_path(hancom, page), "HANCOM", page)
        right = image_or_missing(rhwp_pages.get(page), "RHWP current", page)
        height = max(left.height, right.height) + LABEL_H
        strip = Image.new("RGB", (COLUMN_WIDTH * 2 + GAP, height), "#888")
        for col, (label, image) in enumerate((("HANCOM", left), ("RHWP current", right))):
            canvas = Image.new("RGB", (COLUMN_WIDTH, height), "white")
            canvas.paste(image, (0, LABEL_H))
            ImageDraw.Draw(canvas).text((8, 8), f"{label} page {page}", fill="#000")
            strip.paste(canvas, (col * (COLUMN_WIDTH + GAP), 0))
        rel = f"page-{page:03d}.png"
        strip.save(doc_out / rel)
        rows.append((page, rel))

    body = "\n".join(
        f'<h3>page {page}</h3><a href="{html.escape(rel)}"><img src="{html.escape(rel)}"></a>'
        for page, rel in rows
    )
    (doc_out / "index.html").write_text(
        f"""<!doctype html><meta charset="utf-8"><title>{html.escape(doc)}</title>
<style>body{{font-family:sans-serif;margin:0;background:#222;color:#eee}}
h1,h3,p{{padding:6px 12px}} img{{display:block;width:100%;height:auto}}</style>
<h1>{html.escape(doc)} selected pages</h1>
<p><a href="../index.html">index</a></p>
{body}
""",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("doc")
    parser.add_argument("--pages", required=True, type=parse_pages)
    parser.add_argument("--export-current", action="store_true")
    args = parser.parse_args()

    outdir = args.out_dir
    outdir.mkdir(parents=True, exist_ok=True)
    build(outdir, args.doc, args.pages, args.export_current)
    (outdir / "index.html").write_text(
        f"""<!doctype html><meta charset="utf-8"><title>selected page review</title>
<style>body{{font-family:sans-serif;margin:24px}}</style>
<h1>selected page review</h1>
<ul><li><a href="{html.escape(args.doc)}/index.html">{html.escape(args.doc)}</a></li></ul>
""",
        encoding="utf-8",
    )
    print(outdir / "index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
