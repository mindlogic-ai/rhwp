#!/usr/bin/env python3
"""Compare table horizontal-rule boundaries between Hancom and RHWP pages.

This is a read-only fidelity harness. It detects long dark horizontal bands in
the oracle/rhwp rasters and prints them in SVG page coordinates so row-density
differences are visible without hand-measuring screenshots.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

import review_gallery


RHWP = Path(__file__).resolve().parents[1]
DIFF = Path("/tmp/diff")
SVG_LINE_RE = re.compile(r"<line\b[^>]*>", re.I)
ATTR_RE = re.compile(r'([a-zA-Z_:][\w:.-]*)="([^"]*)"')


@dataclass(frozen=True)
class PageRef:
    doc: str
    page: int


def parse_ref(raw: str) -> PageRef:
    if ":" not in raw:
        raise argparse.ArgumentTypeError(f"expected DOC:PAGE, got {raw!r}")
    doc, page_raw = raw.rsplit(":", 1)
    return PageRef(doc=doc, page=int(page_raw))


def docdir(ref: PageRef) -> Path:
    path = DIFF / ref.doc
    if not path.exists():
        raise SystemExit(f"missing /tmp/diff docdir: {path}")
    return path


def rhwp_svg_path(ref: PageRef) -> Path:
    directory = docdir(ref) / "rhwp_svg_cur"
    candidates = [
        directory / f"source_{ref.page:03d}.svg",
        directory / f"source_{ref.page}.svg",
        directory / f"page_{ref.page:03d}.svg",
        directory / f"page_{ref.page}.svg",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise SystemExit(f"missing RHWP SVG for {ref.doc} page {ref.page} under {directory}")


def hancom_png_path(ref: PageRef) -> Path:
    directory = docdir(ref)
    candidates = [
        directory / f"hancom_p-{ref.page}.png",
        directory / f"hancom_p-{ref.page:02d}.png",
        directory / f"hancom_p-{ref.page:03d}.png",
    ]
    for path in candidates:
        if path.exists():
            return path
    generated = review_gallery.raster_hancom(directory)
    for path in generated:
        if review_gallery.natural_key(path) == ref.page:
            return path
    raise SystemExit(f"missing Hancom PNG for {ref.doc} page {ref.page}")


def rhwp_png_path(ref: PageRef, svg: Path) -> Path:
    out = docdir(ref) / f"rhwp_boundary_p-{ref.page}.png"
    review_gallery.raster_svg(svg, out)
    return out


def dark_luma(pixel: tuple[int, ...]) -> bool:
    if len(pixel) == 4 and pixel[3] == 0:
        return False
    red, green, blue = pixel[:3]
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue < 96


def horizontal_bands(path: Path, min_dark: int, min_width_ratio: float) -> list[tuple[int, int, int]]:
    with Image.open(path) as opened:
        image = opened.convert("RGBA")
    width, height = image.size
    threshold = max(min_dark, int(width * min_width_ratio))
    rows: list[tuple[int, int]] = []
    for y in range(height):
        count = 0
        for x in range(width):
            if dark_luma(image.getpixel((x, y))):
                count += 1
        if count >= threshold:
            rows.append((y, count))

    bands: list[tuple[int, int, int]] = []
    if not rows:
        return bands
    start_y = prev_y = rows[0][0]
    max_count = rows[0][1]
    for y, count in rows[1:]:
        if y <= prev_y + 1:
            prev_y = y
            max_count = max(max_count, count)
            continue
        bands.append((start_y, prev_y, max_count))
        start_y = prev_y = y
        max_count = count
    bands.append((start_y, prev_y, max_count))
    return bands


def scale_bands(
    bands: list[tuple[int, int, int]], image_path: Path, svg_height: float
) -> list[tuple[float, float, int]]:
    with Image.open(image_path) as opened:
        _, image_h = opened.size
    scale = svg_height / image_h
    return [(start * scale, end * scale, count) for start, end, count in bands]


def svg_horizontal_lines(svg: Path, min_len: float) -> list[tuple[float, float, float]]:
    lines: list[tuple[float, float, float]] = []
    text = svg.read_text(encoding="utf-8", errors="ignore")
    for match in SVG_LINE_RE.finditer(text):
        attrs = dict(ATTR_RE.findall(match.group(0)))
        try:
            x1 = float(attrs.get("x1", "0"))
            x2 = float(attrs.get("x2", "0"))
            y1 = float(attrs.get("y1", "0"))
            y2 = float(attrs.get("y2", "0"))
        except ValueError:
            continue
        if abs(y1 - y2) <= 0.2 and abs(x2 - x1) >= min_len:
            lines.append((min(y1, y2), min(x1, x2), max(x1, x2)))
    return sorted(lines)


def print_bands(label: str, bands: list[tuple[float, float, int]]) -> None:
    print(f"{label}_bands count={len(bands)}")
    for start, end, count in bands:
        print(f"  y={start:7.1f}..{end:7.1f} h={end - start:5.1f} dark={count}")


def print_gaps(label: str, ys: list[float]) -> None:
    if len(ys) < 2:
        return
    gaps = [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]
    print(f"{label}_gaps count={len(gaps)}")
    print("  " + " ".join(f"{gap:.1f}" for gap in gaps))


def probe(ref: PageRef, min_dark: int, min_width_ratio: float, svg_line_min_len: float) -> None:
    svg = rhwp_svg_path(ref)
    svg_width, svg_height = review_gallery.svg_size(svg)
    hancom = hancom_png_path(ref)
    rhwp = rhwp_png_path(ref, svg)
    hancom_bands = scale_bands(horizontal_bands(hancom, min_dark, min_width_ratio), hancom, svg_height)
    rhwp_bands = scale_bands(horizontal_bands(rhwp, min_dark, min_width_ratio), rhwp, svg_height)
    svg_lines = svg_horizontal_lines(svg, svg_line_min_len)

    print(f"ref={ref.doc}:{ref.page} svg_size={svg_width:.1f}x{svg_height:.1f}")
    print(f"hancom_png={hancom}")
    print(f"rhwp_png={rhwp}")
    print_bands("hancom", hancom_bands)
    print_gaps("hancom", [start for start, _, _ in hancom_bands])
    print_bands("rhwp", rhwp_bands)
    print_gaps("rhwp", [start for start, _, _ in rhwp_bands])
    print(f"svg_horizontal_lines count={len(svg_lines)}")
    for y, x1, x2 in svg_lines:
        print(f"  y={y:7.1f} x={x1:7.1f}..{x2:7.1f} w={x2 - x1:7.1f}")
    print_gaps("svg_line", [y for y, _, _ in svg_lines])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("ref", type=parse_ref)
    parser.add_argument("--min-dark", type=int, default=260)
    parser.add_argument("--min-width-ratio", type=float, default=0.18)
    parser.add_argument("--svg-line-min-len", type=float, default=350.0)
    args = parser.parse_args()
    probe(args.ref, args.min_dark, args.min_width_ratio, args.svg_line_min_len)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
