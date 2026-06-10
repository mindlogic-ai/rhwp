#!/usr/bin/env python3
"""Build Hancom/RHWP side-by-side strips for semantically aligned page pairs."""
from __future__ import annotations

import argparse
import html
from pathlib import Path

from PIL import Image, ImageDraw

import review_gallery


DIFF = Path("/tmp/diff")
GAP = review_gallery.GAP
LABEL_H = review_gallery.LABEL_H
COLUMN_WIDTH = review_gallery.COLUMN_WIDTH


def parse_pairs(raw: str) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            raise argparse.ArgumentTypeError(f"pair must be HANCOM:RHWP, got {part!r}")
        left, right = part.split(":", 1)
        pairs.append((int(left), int(right)))
    if not pairs:
        raise argparse.ArgumentTypeError("no page pairs supplied")
    return pairs


def page_path(paths: list[Path], page: int) -> Path | None:
    idx = page - 1
    if 0 <= idx < len(paths):
        return paths[idx]
    return None


def image_or_missing(path: Path | None, label: str, page: int) -> Image.Image:
    if path is not None and path.exists():
        return review_gallery.fit_width(Image.open(path).convert("RGB"), COLUMN_WIDTH)
    return review_gallery.missing_page(label, page)


def build(outdir: Path, doc: str, pairs: list[tuple[int, int]], export_current: bool) -> None:
    docdir = DIFF / doc
    if export_current:
        review_gallery.export_current(docdir)
    hancom = review_gallery.raster_hancom(docdir)
    svg_pages = review_gallery.svg_pages(docdir)
    rhwp_pages: dict[int, Path] = {}
    for _, rhwp_page in pairs:
        svg = page_path(svg_pages, rhwp_page)
        if svg is None:
            continue
        png = docdir / f"rhwp_review_p-{rhwp_page}.png"
        review_gallery.raster_svg(svg, png)
        rhwp_pages[rhwp_page] = png

    doc_out = outdir / doc
    doc_out.mkdir(parents=True, exist_ok=True)
    rows: list[tuple[int, int, str]] = []
    for hancom_page, rhwp_page in pairs:
        left = image_or_missing(page_path(hancom, hancom_page), "HANCOM", hancom_page)
        right = image_or_missing(rhwp_pages.get(rhwp_page), "RHWP current", rhwp_page)
        height = max(left.height, right.height) + LABEL_H
        strip = Image.new("RGB", (COLUMN_WIDTH * 2 + GAP, height), "#888")
        for col, (label, page, image) in enumerate(
            (("HANCOM", hancom_page, left), ("RHWP current", rhwp_page, right))
        ):
            canvas = Image.new("RGB", (COLUMN_WIDTH, height), "white")
            canvas.paste(image, (0, LABEL_H))
            ImageDraw.Draw(canvas).text((8, 8), f"{label} page {page}", fill="#000")
            strip.paste(canvas, (col * (COLUMN_WIDTH + GAP), 0))
        rel = f"hancom-{hancom_page:03d}_rhwp-{rhwp_page:03d}.png"
        strip.save(doc_out / rel)
        rows.append((hancom_page, rhwp_page, rel))

    body = "\n".join(
        (
            f"<h3>Hancom {hancom_page} / RHWP {rhwp_page}</h3>"
            f'<a href="{html.escape(rel)}"><img src="{html.escape(rel)}"></a>'
        )
        for hancom_page, rhwp_page, rel in rows
    )
    (doc_out / "index.html").write_text(
        f"""<!doctype html><meta charset="utf-8"><title>{html.escape(doc)}</title>
<style>body{{font-family:sans-serif;margin:0;background:#222;color:#eee}}
h1,h3,p{{padding:6px 12px}} img{{display:block;width:100%;height:auto}}</style>
<h1>{html.escape(doc)} paired page review</h1>
<p><a href="../index.html">index</a></p>
{body}
""",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("doc")
    parser.add_argument("--pairs", required=True, type=parse_pairs)
    parser.add_argument("--export-current", action="store_true")
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    build(args.out_dir, args.doc, args.pairs, args.export_current)
    (args.out_dir / "index.html").write_text(
        f"""<!doctype html><meta charset="utf-8"><title>paired page review</title>
<style>body{{font-family:sans-serif;margin:24px}}</style>
<h1>paired page review</h1>
<ul><li><a href="{html.escape(args.doc)}/index.html">{html.escape(args.doc)}</a></li></ul>
""",
        encoding="utf-8",
    )
    print(args.out_dir / "index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
