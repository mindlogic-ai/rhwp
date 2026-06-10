#!/usr/bin/env python3
"""Measure Hancom/RHWP visual drift inside named page regions.

Whole-page mean diff is too blunt for late-stage renderer fidelity work: image
areas, table rulings, and dense Korean text can swamp each other. This probe
keeps the same oracle model as `review_gallery.py`, but reports per-region
diff, ink density, and vertical ink bands in SVG page coordinates.

Usage:
  python3 harness/svg_region_probe.py overseas_training:1 \
    --region title:56,98,726,146 --region header:56,164,737,214

  python3 harness/svg_region_probe.py overseas_training:1 \
    --candidate-png /tmp/diff/_probe_variant/base.png \
    --region header:56,164,737,214
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

import review_gallery
from svg_geometry_probe import hancom_png_path, parse_ref, rhwp_png_path, rhwp_svg_path, svg_size


@dataclass(frozen=True)
class Region:
    name: str
    x0: float
    y0: float
    x1: float
    y1: float


def parse_region(raw: str) -> Region:
    if ":" not in raw:
        raise argparse.ArgumentTypeError(f"expected NAME:x0,y0,x1,y1, got {raw!r}")
    name, coords_raw = raw.split(":", 1)
    if not name:
        raise argparse.ArgumentTypeError("region name is empty")
    parts = coords_raw.split(",")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(f"expected four coordinates in {raw!r}")
    try:
        x0, y0, x1, y1 = (float(part) for part in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid coordinate in {raw!r}") from exc
    if x1 <= x0 or y1 <= y0:
        raise argparse.ArgumentTypeError(f"invalid region bounds in {raw!r}")
    return Region(name=name, x0=x0, y0=y0, x1=x1, y1=y1)


def svg_to_pixel_box(region: Region, image: Image.Image, svg_w: float, svg_h: float) -> tuple[int, int, int, int]:
    width, height = image.size
    x0 = max(0, min(width, round(region.x0 * width / svg_w)))
    y0 = max(0, min(height, round(region.y0 * height / svg_h)))
    x1 = max(0, min(width, round(region.x1 * width / svg_w)))
    y1 = max(0, min(height, round(region.y1 * height / svg_h)))
    if x1 <= x0:
        x1 = min(width, x0 + 1)
    if y1 <= y0:
        y1 = min(height, y0 + 1)
    return x0, y0, x1, y1


def crop_region(path: Path, region: Region, svg_w: float, svg_h: float) -> Image.Image:
    with Image.open(path) as opened:
        image = opened.convert("RGB")
    return image.crop(svg_to_pixel_box(region, image, svg_w, svg_h))


def fit_to_match(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    if image.size == size:
        return image
    return image.resize(size)


def mean_diff(left: Image.Image, right: Image.Image) -> float:
    candidate = fit_to_match(right, left.size)
    diff = ImageChops.difference(left, candidate)
    stat = ImageStat.Stat(diff)
    return sum(stat.mean) / 3.0


def dark_pixels(image: Image.Image, threshold: int) -> int:
    count = 0
    for red, green, blue in image.getdata():
        luma = 0.2126 * red + 0.7152 * green + 0.0722 * blue
        if luma < threshold:
            count += 1
    return count


def nonwhite_pixels(image: Image.Image, threshold: int) -> int:
    count = 0
    for red, green, blue in image.getdata():
        if max(255 - red, 255 - green, 255 - blue) > threshold:
            count += 1
    return count


def mean_luma(image: Image.Image) -> float:
    total = 0.0
    count = 0
    for red, green, blue in image.getdata():
        total += 0.2126 * red + 0.7152 * green + 0.0722 * blue
        count += 1
    return total / max(1, count)


def ink_bands(image: Image.Image, svg_y0: float, svg_y1: float, threshold: int, min_rows: int, gap_rows: int) -> str:
    width, height = image.size
    active: list[tuple[int, int]] = []
    in_band = False
    start = 0
    min_active = max(1, width // 200)
    for y in range(height):
        row_active = 0
        for x in range(width):
            red, green, blue = image.getpixel((x, y))
            if max(red, green, blue) < threshold:
                row_active += 1
        if row_active >= min_active:
            if not in_band:
                start = y
                in_band = True
        elif in_band:
            active.append((start, y))
            in_band = False
    if in_band:
        active.append((start, height))

    merged: list[tuple[int, int]] = []
    for y0, y1 in active:
        if merged and y0 <= merged[-1][1] + gap_rows:
            merged[-1] = (merged[-1][0], max(merged[-1][1], y1))
        else:
            merged.append((y0, y1))

    out: list[str] = []
    region_h = svg_y1 - svg_y0
    for y0, y1 in merged:
        if y1 - y0 < min_rows:
            continue
        band0 = svg_y0 + y0 * region_h / max(1, height)
        band1 = svg_y0 + y1 * region_h / max(1, height)
        out.append(f"{band0:.1f}..{band1:.1f}")
    return ";".join(out) if out else "-"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("ref", type=parse_ref, help="DOC:PAGE reference")
    parser.add_argument("--region", action="append", type=parse_region, required=True)
    parser.add_argument("--export-current", action="store_true")
    parser.add_argument("--candidate-png", default="", help="override RHWP candidate PNG")
    parser.add_argument("--threshold", type=int, default=96)
    parser.add_argument("--nonwhite-threshold", type=int, default=8)
    parser.add_argument("--min-rows", type=int, default=2)
    parser.add_argument("--gap-rows", type=int, default=2)
    args = parser.parse_args()

    if args.export_current:
        review_gallery.export_current(Path("/tmp/diff") / args.ref.doc)

    svg = rhwp_svg_path(args.ref)
    svg_w, svg_h = svg_size(svg.read_text(encoding="utf-8", errors="ignore"))
    hancom = hancom_png_path(args.ref)
    rhwp = Path(args.candidate_png) if args.candidate_png else rhwp_png_path(args.ref)
    if not rhwp.exists():
        raise SystemExit(f"missing candidate PNG: {rhwp}")

    print(
        "doc\tpage\tregion\tmean_diff\thancom_dark\trhwp_dark\tdark_delta_pct\t"
        "hancom_nonwhite\trhwp_nonwhite\tnonwhite_delta_pct\t"
        "hancom_luma\trhwp_luma\tluma_delta\thancom_bands\trhwp_bands"
    )
    for region in args.region:
        left = crop_region(hancom, region, svg_w, svg_h)
        right = crop_region(rhwp, region, svg_w, svg_h)
        right_fit = fit_to_match(right, left.size)
        left_dark = dark_pixels(left, args.threshold)
        right_dark = dark_pixels(right_fit, args.threshold)
        denom = max(1, left_dark)
        delta_pct = (right_dark - left_dark) * 100.0 / denom
        left_nonwhite = nonwhite_pixels(left, args.nonwhite_threshold)
        right_nonwhite = nonwhite_pixels(right_fit, args.nonwhite_threshold)
        nonwhite_delta_pct = (right_nonwhite - left_nonwhite) * 100.0 / max(1, left_nonwhite)
        left_luma = mean_luma(left)
        right_luma = mean_luma(right_fit)
        print(
            f"{args.ref.doc}\t{args.ref.page}\t{region.name}\t"
            f"{mean_diff(left, right):.2f}\t{left_dark}\t{right_dark}\t{delta_pct:+.1f}\t"
            f"{left_nonwhite}\t{right_nonwhite}\t{nonwhite_delta_pct:+.1f}\t"
            f"{left_luma:.1f}\t{right_luma:.1f}\t{right_luma - left_luma:+.1f}\t"
            f"{ink_bands(left, region.y0, region.y1, args.threshold, args.min_rows, args.gap_rows)}\t"
            f"{ink_bands(right_fit, region.y0, region.y1, args.threshold, args.min_rows, args.gap_rows)}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
