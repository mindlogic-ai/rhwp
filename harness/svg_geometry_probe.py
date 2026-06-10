#!/usr/bin/env python3
"""Compare coarse RHWP SVG geometry against Hancom/RHWP raster bands.

The component probe answers "which paint class matters?". This script answers
"where are the big blocks?". It avoids fixture-specific logic by reporting
SVG element bands and image-derived ink bands in normalized page coordinates.

Usage:
  python3 harness/svg_geometry_probe.py 15_3740450_research_admin_innovation_meeting_template:3
"""
from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

import review_gallery


DIFF = Path("/tmp/diff")
ATTR_RE = re.compile(r'([A-Za-z_:][-A-Za-z0-9_:.]*)="([^"]*)"')
SVG_SIZE_RE = re.compile(r'<svg[^>]*\bwidth="([0-9.]+)"[^>]*\bheight="([0-9.]+)"')
VIEWBOX_RE = re.compile(r'<svg[^>]*\bviewBox="[0-9.]+ [0-9.]+ ([0-9.]+) ([0-9.]+)"')


@dataclass(frozen=True)
class PageRef:
    doc: str
    page: int


@dataclass(frozen=True)
class Box:
    kind: str
    x0: float
    y0: float
    x1: float
    y1: float
    note: str = ""

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0


def parse_ref(raw: str) -> PageRef:
    if ":" not in raw:
        raise argparse.ArgumentTypeError(f"expected DOC:PAGE, got {raw!r}")
    doc, page_raw = raw.rsplit(":", 1)
    try:
        page = int(page_raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid page in {raw!r}") from exc
    if not doc or page <= 0:
        raise argparse.ArgumentTypeError(f"invalid DOC:PAGE reference {raw!r}")
    return PageRef(doc, page)


def docdir(ref: PageRef) -> Path:
    path = DIFF / ref.doc
    if not path.exists():
        raise SystemExit(f"missing /tmp/diff docdir: {path}")
    return path


def rhwp_svg_path(ref: PageRef) -> Path:
    directory = docdir(ref) / "rhwp_svg_cur"
    for name in (
        f"source_{ref.page:03d}.svg",
        f"source_{ref.page}.svg",
        f"page_{ref.page:03d}.svg",
        f"page_{ref.page}.svg",
    ):
        path = directory / name
        if path.exists():
            return path
    raise SystemExit(f"missing RHWP SVG for {ref.doc} page {ref.page}")


def hancom_png_path(ref: PageRef) -> Path:
    directory = docdir(ref)
    for name in (f"hancom_p-{ref.page}.png", f"hancom_p-{ref.page:02d}.png", f"hancom_p-{ref.page:03d}.png"):
        path = directory / name
        if path.exists():
            return path
    generated = review_gallery.raster_hancom(directory)
    for path in generated:
        if review_gallery.natural_key(path) == ref.page:
            return path
    raise SystemExit(f"missing Hancom PNG for {ref.doc} page {ref.page}")


def rhwp_png_path(ref: PageRef) -> Path:
    directory = docdir(ref)
    for name in (
        f"rhwp_review_p-{ref.page}.png",
        f"rhwp_review_p-{ref.page:02d}.png",
        f"rhwp_p-{ref.page}.png",
        f"rhwp_p-{ref.page:02d}.png",
    ):
        path = directory / name
        if path.exists():
            return path
    svg = rhwp_svg_path(ref)
    out = directory / f"rhwp_review_p-{ref.page}.png"
    review_gallery.raster_svg(svg, out)
    return out


def svg_size(svg_text: str) -> tuple[float, float]:
    if match := SVG_SIZE_RE.search(svg_text[:2000]):
        return float(match.group(1)), float(match.group(2))
    if match := VIEWBOX_RE.search(svg_text[:2000]):
        return float(match.group(1)), float(match.group(2))
    return 794.0, 1123.0


def attrs(raw_tag: str) -> dict[str, str]:
    return {key: value for key, value in ATTR_RE.findall(raw_tag)}


def tag_name(elem: ET.Element) -> str:
    if "}" in elem.tag:
        return elem.tag.rsplit("}", 1)[1]
    return elem.tag


def text_content(elem: ET.Element) -> str:
    return "".join(elem.itertext()).strip()


def collect_svg_boxes(svg: Path) -> tuple[float, float, list[Box]]:
    svg_text = svg.read_text(encoding="utf-8", errors="ignore")
    width, height = svg_size(svg_text)
    root = ET.fromstring(svg_text)
    boxes: list[Box] = []

    def walk(elem: ET.Element, in_defs: bool = False) -> None:
        name = tag_name(elem)
        now_in_defs = in_defs or name in {"defs", "clipPath"}
        if not now_in_defs:
            box = element_box(elem)
            if box is not None:
                boxes.append(box)
        for child in elem:
            walk(child, now_in_defs)

    walk(root)
    return width, height, boxes


def float_attr(elem: ET.Element, name: str, default: float = 0.0) -> float:
    raw = elem.attrib.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def element_box(elem: ET.Element) -> Box | None:
    name = tag_name(elem)
    if name == "rect":
        x = float_attr(elem, "x")
        y = float_attr(elem, "y")
        w = float_attr(elem, "width")
        h = float_attr(elem, "height")
        fill = elem.attrib.get("fill", "")
        if w <= 0 or h <= 0:
            return None
        if x == 0.0 and y == 0.0 and fill.lower() in {"#ffffff", "#fff", "white"}:
            return None
        return Box("rect", x, y, x + w, y + h, fill)
    if name == "image":
        x = float_attr(elem, "x")
        y = float_attr(elem, "y")
        w = float_attr(elem, "width")
        h = float_attr(elem, "height")
        if w <= 0 or h <= 0:
            return None
        return Box("image", x, y, x + w, y + h)
    if name == "line":
        x1 = float_attr(elem, "x1")
        y1 = float_attr(elem, "y1")
        x2 = float_attr(elem, "x2")
        y2 = float_attr(elem, "y2")
        stroke_width = float_attr(elem, "stroke-width", 0.0)
        pad = max(0.5, stroke_width / 2.0)
        return Box("line", min(x1, x2), min(y1, y2) - pad, max(x1, x2), max(y1, y2) + pad, elem.attrib.get("stroke", ""))
    if name == "text":
        text = text_content(elem)
        if not text:
            return None
        x = float_attr(elem, "x")
        y = float_attr(elem, "y")
        size = float_attr(elem, "font-size", 10.0)
        text_length = float_attr(elem, "textLength", max(size * 0.55 * len(text), size * 0.5))
        return Box("text", x, y - size, x + text_length, y + size * 0.25, text[:20])
    return None


def merge_ranges(ranges: list[tuple[float, float]], gap: float) -> list[tuple[float, float]]:
    if not ranges:
        return []
    merged: list[tuple[float, float]] = []
    cur_start, cur_end = sorted(ranges)[0]
    for start, end in sorted(ranges)[1:]:
        if start <= cur_end + gap:
            cur_end = max(cur_end, end)
        else:
            merged.append((cur_start, cur_end))
            cur_start, cur_end = start, end
    merged.append((cur_start, cur_end))
    return merged


def svg_kind_bands(boxes: list[Box], kind: str, min_height: float, gap: float) -> list[tuple[float, float]]:
    ranges = [(box.y0, box.y1) for box in boxes if box.kind == kind and box.height >= min_height]
    return merge_ranges(ranges, gap)


def raster_bands(path: Path, svg_height: float, threshold: int, min_rows: int, gap_rows: int) -> list[tuple[float, float, int]]:
    with Image.open(path) as opened:
        image = opened.convert("RGB")
    width, height = image.size
    active: list[tuple[int, int]] = []
    in_band = False
    start = 0
    for y in range(height):
        row_active = 0
        for x in range(width):
            red, green, blue = image.getpixel((x, y))
            if max(red, green, blue) < threshold:
                row_active += 1
        if row_active >= max(1, width // 200):
            if not in_band:
                start = y
                in_band = True
        elif in_band:
            active.append((start, y))
            in_band = False
    if in_band:
        active.append((start, height))

    merged_px = merge_ranges([(float(a), float(b)) for a, b in active], float(gap_rows))
    out: list[tuple[float, float, int]] = []
    for y0, y1 in merged_px:
        if y1 - y0 < min_rows:
            continue
        out.append((y0 * svg_height / height, y1 * svg_height / height, round(y1 - y0)))
    return out


def print_bands(label: str, bands: list[tuple[float, float] | tuple[float, float, int]], max_bands: int) -> None:
    print(f"{label}:")
    if not bands:
        print("  (none)")
        return
    for band in bands[:max_bands]:
        y0, y1 = band[0], band[1]
        extra = f" px_rows={band[2]}" if len(band) > 2 else ""
        print(f"  y={y0:7.1f}..{y1:7.1f} h={y1 - y0:6.1f}{extra}")
    if len(bands) > max_bands:
        print(f"  ... {len(bands) - max_bands} more")


def print_svg_summary(boxes: list[Box], max_boxes: int) -> None:
    print("svg boxes:")
    for kind in ("image", "rect", "line", "text"):
        selected = [box for box in boxes if box.kind == kind]
        print(f"  {kind}: {len(selected)}")
        if kind in {"image", "rect"}:
            for box in sorted(selected, key=lambda b: (b.y0, b.x0))[:max_boxes]:
                print(
                    f"    y={box.y0:7.1f}..{box.y1:7.1f} x={box.x0:7.1f}..{box.x1:7.1f} "
                    f"w={box.width:6.1f} h={box.height:6.1f} {box.note}"
                )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("refs", nargs="+", type=parse_ref)
    parser.add_argument("--threshold", type=int, default=245, help="raster non-white threshold")
    parser.add_argument("--min-raster-rows", type=int, default=6)
    parser.add_argument("--raster-gap-rows", type=int, default=8)
    parser.add_argument("--svg-gap", type=float, default=8.0)
    parser.add_argument("--max-bands", type=int, default=30)
    parser.add_argument("--max-boxes", type=int, default=20)
    args = parser.parse_args()

    for ref in args.refs:
        svg = rhwp_svg_path(ref)
        svg_width, svg_height, boxes = collect_svg_boxes(svg)
        print(f"== {ref.doc} page {ref.page} ==")
        print(f"svg={svg} size={svg_width:.1f}x{svg_height:.1f}")
        print_svg_summary(boxes, args.max_boxes)
        print_bands("svg image bands", svg_kind_bands(boxes, "image", 1.0, args.svg_gap), args.max_bands)
        print_bands("svg rect bands", svg_kind_bands(boxes, "rect", 2.0, args.svg_gap), args.max_bands)
        print_bands("svg line bands", svg_kind_bands(boxes, "line", 0.0, args.svg_gap), args.max_bands)
        print_bands("svg text bands", svg_kind_bands(boxes, "text", 1.0, args.svg_gap), args.max_bands)
        print_bands(
            "hancom raster bands",
            raster_bands(hancom_png_path(ref), svg_height, args.threshold, args.min_raster_rows, args.raster_gap_rows),
            args.max_bands,
        )
        print_bands(
            "rhwp raster bands",
            raster_bands(rhwp_png_path(ref), svg_height, args.threshold, args.min_raster_rows, args.raster_gap_rows),
            args.max_bands,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
