#!/usr/bin/env python3
"""Probe SVG line/rect variants inside a page region against Hancom.

This is for table-heavy pages where component probes say ruling/geometry may
matter. It rewrites only `<line>` and border-like `<rect>` elements inside a
Y-region, rasters the variants, and prints mean pixel diff.

Usage:
  python3 harness/svg_line_region_probe.py 15_3740450_research_admin_innovation_meeting_template:3 --y-min 430 --y-max 990 --keep
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

import review_gallery


DIFF = Path("/tmp/diff")
LINE_RE = re.compile(r"<line\b[^>]*/?>", re.DOTALL)
RECT_RE = re.compile(r"<rect\b[^>]*/?>", re.DOTALL)
ATTR_RE = re.compile(r'([A-Za-z_:][-A-Za-z0-9_:.]*)="([^"]*)"')
STROKE_WIDTH_RE = re.compile(r'(stroke-width=")([0-9.]+)(")')


@dataclass(frozen=True)
class PageRef:
    doc: str
    page: int


@dataclass(frozen=True)
class Element:
    tag: str
    kind: str
    x0: float
    y0: float
    x1: float
    y1: float
    horizontal: bool
    vertical: bool


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


def svg_path(ref: PageRef) -> Path:
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


def attrs(tag: str) -> dict[str, str]:
    return {key: value for key, value in ATTR_RE.findall(tag)}


def fattr(values: dict[str, str], name: str, default: float = 0.0) -> float:
    try:
        return float(values.get(name, default))
    except ValueError:
        return default


def element_from_tag(tag: str, kind: str) -> Element | None:
    values = attrs(tag)
    if kind == "line":
        x1 = fattr(values, "x1")
        y1 = fattr(values, "y1")
        x2 = fattr(values, "x2")
        y2 = fattr(values, "y2")
        horizontal = abs(y1 - y2) <= 0.1 and abs(x2 - x1) > 2.0
        vertical = abs(x1 - x2) <= 0.1 and abs(y2 - y1) > 2.0
        return Element(tag, kind, min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2), horizontal, vertical)
    if kind == "rect":
        x = fattr(values, "x")
        y = fattr(values, "y")
        w = fattr(values, "width")
        h = fattr(values, "height")
        if w <= 0.0 or h <= 0.0:
            return None
        fill = values.get("fill", "")
        stroke = values.get("stroke", "")
        if fill.lower() in {"#ffffff", "#fff", "white"} and not stroke:
            return None
        return Element(tag, kind, x, y, x + w, y + h, w >= h, h >= w)
    return None


def in_region(element: Element, y_min: float, y_max: float) -> bool:
    return element.y1 >= y_min and element.y0 <= y_max


def set_stroke_width(tag: str, factor: float) -> str:
    def repl(match: re.Match[str]) -> str:
        return f"{match.group(1)}{float(match.group(2)) * factor:.4g}{match.group(3)}"

    if STROKE_WIDTH_RE.search(tag):
        return STROKE_WIDTH_RE.sub(repl, tag)
    if tag.endswith("/>"):
        return tag[:-2] + f' stroke-width="{factor:.4g}"/>'
    return tag


def rewrite_elements(svg: str, variant: str, y_min: float, y_max: float) -> str:
    def rewrite(kind: str, pattern: re.Pattern[str], text: str) -> str:
        def repl(match: re.Match[str]) -> str:
            tag = match.group(0)
            element = element_from_tag(tag, kind)
            if element is None or not in_region(element, y_min, y_max):
                return tag
            if variant == "hide_all":
                return ""
            if variant == "hide_horizontal" and element.horizontal:
                return ""
            if variant == "hide_vertical" and element.vertical:
                return ""
            if variant == "thin_x0.50":
                return set_stroke_width(tag, 0.50)
            if variant == "thin_x0.75":
                return set_stroke_width(tag, 0.75)
            if variant == "thick_x1.50":
                return set_stroke_width(tag, 1.50)
            if variant == "thick_x2.00":
                return set_stroke_width(tag, 2.00)
            return tag

        return pattern.sub(repl, text)

    svg = rewrite("line", LINE_RE, svg)
    svg = rewrite("rect", RECT_RE, svg)
    return svg


def mean_diff(hancom: Path, candidate: Path) -> float:
    with Image.open(hancom) as opened_left, Image.open(candidate) as opened_right:
        left = opened_left.convert("RGB")
        right = opened_right.convert("RGB").resize(left.size)
        diff = ImageChops.difference(left, right)
        stat = ImageStat.Stat(diff)
        return sum(stat.mean) / 3.0


def element_summary(svg: str, y_min: float, y_max: float) -> dict[str, int]:
    counts = {"line": 0, "hline": 0, "vline": 0, "rect": 0}
    for kind, pattern in (("line", LINE_RE), ("rect", RECT_RE)):
        for match in pattern.finditer(svg):
            element = element_from_tag(match.group(0), kind)
            if element is None or not in_region(element, y_min, y_max):
                continue
            counts[kind] += 1
            if element.horizontal:
                counts["hline"] += 1
            if element.vertical:
                counts["vline"] += 1
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("refs", nargs="+", type=parse_ref)
    parser.add_argument("--y-min", type=float, required=True)
    parser.add_argument("--y-max", type=float, required=True)
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--out-dir", default="")
    args = parser.parse_args()

    variants = [
        "base",
        "hide_all",
        "hide_horizontal",
        "hide_vertical",
        "thin_x0.50",
        "thin_x0.75",
        "thick_x1.50",
        "thick_x2.00",
    ]
    temp: tempfile.TemporaryDirectory[str] | None = None
    if args.out_dir:
        out_root = Path(args.out_dir)
        out_root.mkdir(parents=True, exist_ok=True)
    elif args.keep:
        out_root = DIFF / "_svg_line_region_probe"
        if out_root.exists():
            shutil.rmtree(out_root)
        out_root.mkdir(parents=True)
    else:
        temp = tempfile.TemporaryDirectory(prefix="rhwp-line-probe-")
        out_root = Path(temp.name)

    try:
        print("doc\tpage\tvariant\tmean_diff\tline\thline\tvline\trect\tpng")
        for ref in args.refs:
            source = svg_path(ref)
            hancom = hancom_png_path(ref)
            svg = source.read_text(encoding="utf-8", errors="ignore")
            counts = element_summary(svg, args.y_min, args.y_max)
            ref_out = out_root / f"{ref.doc}_p{ref.page}"
            ref_out.mkdir(parents=True, exist_ok=True)
            for variant in variants:
                out_svg = ref_out / f"{variant}.svg"
                out_png = ref_out / f"{variant}.png"
                out_svg.write_text(
                    svg if variant == "base" else rewrite_elements(svg, variant, args.y_min, args.y_max),
                    encoding="utf-8",
                )
                review_gallery.raster_svg(out_svg, out_png)
                print(
                    "\t".join(
                        [
                            ref.doc,
                            str(ref.page),
                            variant,
                            f"{mean_diff(hancom, out_png):.2f}",
                            str(counts["line"]),
                            str(counts["hline"]),
                            str(counts["vline"]),
                            str(counts["rect"]),
                            str(out_png) if args.keep or args.out_dir else "",
                        ]
                    )
                )
    finally:
        if temp is not None:
            temp.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
