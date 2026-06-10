#!/usr/bin/env python3
"""Summarize RHWP SVG text runs inside named page regions.

Use this after pixel-region probes point at sparse table text. It is read-only:
it reports whether a region's SVG has the expected text density, font families,
font sizes, weights, and vertical text bands before changing renderer code.

Usage:
  python3 harness/svg_text_region_probe.py overseas_training:1 \
    --region header:56,164,737,214 --region body_top:56,214,737,503
"""
from __future__ import annotations

import argparse
import html
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from svg_geometry_probe import parse_ref, rhwp_svg_path, svg_size


TEXT_RE = re.compile(r"<text\b(?P<attrs>[^>]*)>(?P<body>.*?)</text>", re.DOTALL)
ATTR_RE = re.compile(r"([A-Za-z_:][-A-Za-z0-9_:.]*)=(?:\"([^\"]*)\"|'([^']*)')")


@dataclass(frozen=True)
class Region:
    name: str
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass(frozen=True)
class TextRun:
    x: float
    y: float
    font_family: str
    font_size: float
    font_weight: str
    text: str


def parse_region(raw: str) -> Region:
    if ":" not in raw:
        raise argparse.ArgumentTypeError(f"expected NAME:x0,y0,x1,y1, got {raw!r}")
    name, coords_raw = raw.split(":", 1)
    parts = coords_raw.split(",")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(f"expected four coordinates in {raw!r}")
    try:
        x0, y0, x1, y1 = (float(part) for part in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid coordinate in {raw!r}") from exc
    if not name or x1 <= x0 or y1 <= y0:
        raise argparse.ArgumentTypeError(f"invalid region {raw!r}")
    return Region(name=name, x0=x0, y0=y0, x1=x1, y1=y1)


def attr_map(raw: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for key, double, single in ATTR_RE.findall(raw):
        attrs[key] = html.unescape(double or single)
    return attrs


def parse_float(raw: str | None, default: float = 0.0) -> float:
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def primary_font(font_family: str) -> str:
    return font_family.split(",", 1)[0].strip().strip("'\"") or "-"


def text_runs(svg: str) -> list[TextRun]:
    runs: list[TextRun] = []
    for match in TEXT_RE.finditer(svg):
        attrs = attr_map(match.group("attrs"))
        text = html.unescape(re.sub(r"<[^>]+>", "", match.group("body"))).strip()
        if not text:
            continue
        runs.append(
            TextRun(
                x=parse_float(attrs.get("x")),
                y=parse_float(attrs.get("y")),
                font_family=attrs.get("font-family", ""),
                font_size=parse_float(attrs.get("font-size")),
                font_weight=attrs.get("font-weight", "normal") or "normal",
                text=text,
            )
        )
    return runs


def in_region(run: TextRun, region: Region) -> bool:
    return region.x0 <= run.x <= region.x1 and region.y0 <= run.y <= region.y1


def band_key(y: float, bucket: float) -> float:
    return round(y / bucket) * bucket


def summarize_region(doc: str, page: int, region: Region, runs: list[TextRun], band_bucket: float) -> None:
    selected = [run for run in runs if in_region(run, region)]
    chars = sum(len(run.text) for run in selected)
    fonts = Counter(primary_font(run.font_family) for run in selected)
    sizes = Counter(round(run.font_size, 2) for run in selected)
    weights = Counter(run.font_weight for run in selected)
    bands: dict[float, int] = defaultdict(int)
    for run in selected:
        bands[band_key(run.y, band_bucket)] += len(run.text)
    font_summary = ";".join(f"{name}:{count}" for name, count in fonts.most_common(5)) or "-"
    size_summary = ";".join(f"{size:g}:{count}" for size, count in sizes.most_common(5)) or "-"
    weight_summary = ";".join(f"{weight}:{count}" for weight, count in weights.most_common(5)) or "-"
    band_summary = ";".join(f"{y:.1f}:{count}" for y, count in sorted(bands.items())) or "-"
    sample = "".join(run.text for run in selected[:24])
    print(
        f"{doc}\t{page}\t{region.name}\t{len(selected)}\t{chars}\t"
        f"{font_summary}\t{size_summary}\t{weight_summary}\t{band_summary}\t{sample[:80]!r}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("ref", type=parse_ref, help="DOC:PAGE reference")
    parser.add_argument("--region", action="append", type=parse_region, required=True)
    parser.add_argument("--band-bucket", type=float, default=2.0)
    args = parser.parse_args()

    svg_path = rhwp_svg_path(args.ref)
    svg = svg_path.read_text(encoding="utf-8", errors="ignore")
    svg_size(svg)
    runs = text_runs(svg)
    print("doc\tpage\tregion\ttext_runs\tchars\tfonts\tfont_sizes\tweights\ty_bands\tsample")
    for region in args.region:
        summarize_region(args.ref.doc, args.ref.page, region, runs, args.band_bucket)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
