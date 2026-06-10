#!/usr/bin/env python3
"""Inspect embedded SVG image boxes and their actual non-white ink bounds.

Use this after geometry probes show an image/table mismatch but box movement
probes fail. It decodes data URI images from an RHWP SVG page and reports the
local ink bounds inside each image, plus page-coordinate ink bounds after
scaling into the emitted SVG image rectangle.

Usage:
  python3 harness/svg_image_ink_probe.py 15_3740450_research_admin_innovation_meeting_template:3
"""
from __future__ import annotations

import argparse
import base64
import io
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


DIFF = Path("/tmp/diff")
IMAGE_TAG_RE = re.compile(r"<image\b[^>]*/?>", re.DOTALL)
ATTR_RE = re.compile(r'([A-Za-z_:][-A-Za-z0-9_:.]*)="([^"]*)"')


@dataclass(frozen=True)
class PageRef:
    doc: str
    page: int


@dataclass(frozen=True)
class ImageProbe:
    index: int
    x: float
    y: float
    width: float
    height: float
    px_width: int
    px_height: int
    ink_box: tuple[int, int, int, int] | None
    dark_box: tuple[int, int, int, int] | None
    nonwhite_ratio: float
    dark_ratio: float
    page_ink_box: tuple[float, float, float, float] | None
    page_dark_box: tuple[float, float, float, float] | None


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


def svg_path(ref: PageRef) -> Path:
    directory = DIFF / ref.doc / "rhwp_svg_cur"
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


def attrs(tag: str) -> dict[str, str]:
    return {key: value for key, value in ATTR_RE.findall(tag)}


def float_attr(values: dict[str, str], name: str) -> float:
    try:
        return float(values[name])
    except (KeyError, ValueError):
        return 0.0


def image_data(values: dict[str, str]) -> bytes | None:
    href = values.get("href") or values.get("xlink:href")
    if not href or not href.startswith("data:"):
        return None
    if "," not in href:
        return None
    header, payload = href.split(",", 1)
    if ";base64" not in header:
        return None
    try:
        return base64.b64decode(payload, validate=False)
    except ValueError:
        return None


def pixel_bounds(
    image: Image.Image,
    *,
    nonwhite_threshold: int,
    dark_threshold: int,
) -> tuple[tuple[int, int, int, int] | None, tuple[int, int, int, int] | None, float, float]:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    ink_min_x = width
    ink_min_y = height
    ink_max_x = -1
    ink_max_y = -1
    dark_min_x = width
    dark_min_y = height
    dark_max_x = -1
    dark_max_y = -1
    ink_count = 0
    dark_count = 0
    for y in range(height):
        for x in range(width):
            red, green, blue, alpha = rgba.getpixel((x, y))
            if alpha == 0:
                continue
            luma = 0.2126 * red + 0.7152 * green + 0.0722 * blue
            if luma < nonwhite_threshold:
                ink_count += 1
                ink_min_x = min(ink_min_x, x)
                ink_min_y = min(ink_min_y, y)
                ink_max_x = max(ink_max_x, x + 1)
                ink_max_y = max(ink_max_y, y + 1)
            if luma < dark_threshold:
                dark_count += 1
                dark_min_x = min(dark_min_x, x)
                dark_min_y = min(dark_min_y, y)
                dark_max_x = max(dark_max_x, x + 1)
                dark_max_y = max(dark_max_y, y + 1)
    area = max(1, width * height)
    ink_box = None if ink_max_x < 0 else (ink_min_x, ink_min_y, ink_max_x, ink_max_y)
    dark_box = None if dark_max_x < 0 else (dark_min_x, dark_min_y, dark_max_x, dark_max_y)
    return ink_box, dark_box, ink_count / area, dark_count / area


def to_page_box(
    local: tuple[int, int, int, int] | None,
    *,
    image_px: tuple[int, int],
    svg_box: tuple[float, float, float, float],
) -> tuple[float, float, float, float] | None:
    if local is None:
        return None
    px_w, px_h = image_px
    x, y, width, height = svg_box
    sx = width / max(1, px_w)
    sy = height / max(1, px_h)
    x0, y0, x1, y1 = local
    return (x + x0 * sx, y + y0 * sy, x + x1 * sx, y + y1 * sy)


def probes_for_svg(path: Path, nonwhite_threshold: int, dark_threshold: int) -> list[ImageProbe]:
    svg = path.read_text(encoding="utf-8", errors="ignore")
    probes: list[ImageProbe] = []
    for index, match in enumerate(IMAGE_TAG_RE.finditer(svg), 1):
        values = attrs(match.group(0))
        data = image_data(values)
        if data is None:
            continue
        try:
            with Image.open(io.BytesIO(data)) as opened:
                image = opened.convert("RGBA")
        except OSError:
            continue
        x = float_attr(values, "x")
        y = float_attr(values, "y")
        width = float_attr(values, "width")
        height = float_attr(values, "height")
        ink_box, dark_box, nonwhite_ratio, dark_ratio = pixel_bounds(
            image,
            nonwhite_threshold=nonwhite_threshold,
            dark_threshold=dark_threshold,
        )
        probes.append(
            ImageProbe(
                index=index,
                x=x,
                y=y,
                width=width,
                height=height,
                px_width=image.width,
                px_height=image.height,
                ink_box=ink_box,
                dark_box=dark_box,
                nonwhite_ratio=nonwhite_ratio,
                dark_ratio=dark_ratio,
                page_ink_box=to_page_box(
                    ink_box,
                    image_px=(image.width, image.height),
                    svg_box=(x, y, width, height),
                ),
                page_dark_box=to_page_box(
                    dark_box,
                    image_px=(image.width, image.height),
                    svg_box=(x, y, width, height),
                ),
            )
        )
    return probes


def fmt_box(box: tuple[float, float, float, float] | tuple[int, int, int, int] | None) -> str:
    if box is None:
        return ""
    return ",".join(f"{value:.1f}" if isinstance(value, float) else str(value) for value in box)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("refs", nargs="+", type=parse_ref)
    parser.add_argument("--nonwhite-threshold", type=int, default=248)
    parser.add_argument("--dark-threshold", type=int, default=96)
    args = parser.parse_args()

    print(
        "\t".join(
            [
                "doc",
                "page",
                "image",
                "svg_box",
                "px_size",
                "ink_box_px",
                "ink_box_page",
                "ink_ratio",
                "dark_box_px",
                "dark_box_page",
                "dark_ratio",
            ]
        )
    )
    for ref in args.refs:
        for probe in probes_for_svg(svg_path(ref), args.nonwhite_threshold, args.dark_threshold):
            print(
                "\t".join(
                    [
                        ref.doc,
                        str(ref.page),
                        str(probe.index),
                        fmt_box((probe.x, probe.y, probe.x + probe.width, probe.y + probe.height)),
                        f"{probe.px_width}x{probe.px_height}",
                        fmt_box(probe.ink_box),
                        fmt_box(probe.page_ink_box),
                        f"{probe.nonwhite_ratio:.4f}",
                        fmt_box(probe.dark_box),
                        fmt_box(probe.page_dark_box),
                        f"{probe.dark_ratio:.4f}",
                    ]
                )
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
