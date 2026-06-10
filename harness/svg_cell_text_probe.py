#!/usr/bin/env python3
"""Inspect RHWP SVG table-cell text placement.

This read-only probe associates `<g clip-path="url(#cell-clip-N)">` groups with
their clip rectangles and summarizes text baselines inside each cell. It helps
separate missing text from table-cell baseline/clip/position issues before
touching renderer code.

Usage:
  python3 harness/svg_cell_text_probe.py overseas_training:1 --y-range 160,1038
"""
from __future__ import annotations

import argparse
import html
import re
from collections import Counter
from dataclasses import dataclass

from svg_geometry_probe import parse_ref, rhwp_svg_path


CLIP_RE = re.compile(
    r'<clipPath\s+id="(?P<id>cell-clip-[^"]+)">\s*'
    r'<rect\s+(?P<attrs>[^>]*)/>\s*</clipPath>',
    re.DOTALL,
)
GROUP_RE = re.compile(
    r'<g\s+clip-path="url\(#(?P<id>cell-clip-[^)]+)\)">(?P<body>.*?)</g>',
    re.DOTALL,
)
TEXT_RE = re.compile(r"<text\b(?P<attrs>[^>]*)>(?P<body>.*?)</text>", re.DOTALL)
ATTR_RE = re.compile(r"([A-Za-z_:][-A-Za-z0-9_:.]*)=(?:\"([^\"]*)\"|'([^']*)')")


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    width: float
    height: float

    @property
    def x1(self) -> float:
        return self.x + self.width

    @property
    def y1(self) -> float:
        return self.y + self.height


@dataclass(frozen=True)
class TextRun:
    x: float
    y: float
    font_size: float
    font_family: str
    font_weight: str
    text: str


def attr_map(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, double, single in ATTR_RE.findall(raw):
        out[key] = html.unescape(double or single)
    return out


def parse_float(raw: str | None, default: float = 0.0) -> float:
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def parse_range(raw: str) -> tuple[float, float]:
    parts = raw.split(",")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("expected y0,y1")
    try:
        y0, y1 = (float(part) for part in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("invalid y range") from exc
    if y1 <= y0:
        raise argparse.ArgumentTypeError("expected y1 > y0")
    return y0, y1


def primary_font(font_family: str) -> str:
    return font_family.split(",", 1)[0].strip().strip("'\"") or "-"


def parse_clips(svg: str) -> dict[str, Rect]:
    clips: dict[str, Rect] = {}
    for match in CLIP_RE.finditer(svg):
        attrs = attr_map(match.group("attrs"))
        clips[match.group("id")] = Rect(
            x=parse_float(attrs.get("x")),
            y=parse_float(attrs.get("y")),
            width=parse_float(attrs.get("width")),
            height=parse_float(attrs.get("height")),
        )
    return clips


def parse_text_runs(raw: str) -> list[TextRun]:
    runs: list[TextRun] = []
    for match in TEXT_RE.finditer(raw):
        attrs = attr_map(match.group("attrs"))
        text = html.unescape(re.sub(r"<[^>]+>", "", match.group("body"))).strip()
        if not text:
            continue
        runs.append(
            TextRun(
                x=parse_float(attrs.get("x")),
                y=parse_float(attrs.get("y")),
                font_size=parse_float(attrs.get("font-size")),
                font_family=attrs.get("font-family", ""),
                font_weight=attrs.get("font-weight", "normal") or "normal",
                text=text,
            )
        )
    return runs


def line_bands(runs: list[TextRun], bucket: float) -> list[tuple[float, int]]:
    counts: Counter[float] = Counter()
    for run in runs:
        counts[round(run.y / bucket) * bucket] += len(run.text)
    return sorted(counts.items())


def summarize_cell(clip_id: str, rect: Rect, runs: list[TextRun], edge_threshold: float) -> str:
    chars = sum(len(run.text) for run in runs)
    if not runs:
        return (
            f"{clip_id}\t{rect.x:.1f}\t{rect.y:.1f}\t{rect.width:.1f}\t{rect.height:.1f}\t"
            "0\t0\t-\t-\t-\t-\t-\t-"
        )
    min_y = min(run.y for run in runs)
    max_y = max(run.y for run in runs)
    min_x = min(run.x for run in runs)
    max_x = max(run.x for run in runs)
    top_pad = min_y - rect.y
    bottom_pad = rect.y1 - max_y
    left_pad = min_x - rect.x
    right_pad = rect.x1 - max_x
    y_pct = (min_y - rect.y) * 100.0 / max(rect.height, 0.001)
    bands = ";".join(f"{y:.1f}:{count}" for y, count in line_bands(runs, 2.0))
    fonts = Counter(primary_font(run.font_family) for run in runs)
    sizes = Counter(round(run.font_size, 2) for run in runs)
    flags: list[str] = []
    if top_pad < edge_threshold:
        flags.append("near_top")
    if bottom_pad < edge_threshold:
        flags.append("near_bottom")
    if left_pad < -0.5 or right_pad < -0.5:
        flags.append("x_outside")
    if min_y < rect.y - 0.5 or max_y > rect.y1 + 0.5:
        flags.append("y_outside")
    return (
        f"{clip_id}\t{rect.x:.1f}\t{rect.y:.1f}\t{rect.width:.1f}\t{rect.height:.1f}\t"
        f"{len(runs)}\t{chars}\t{top_pad:.1f}\t{bottom_pad:.1f}\t{y_pct:.1f}\t"
        f"{fonts.most_common(1)[0][0]}\t{sizes.most_common(1)[0][0]:g}\t{bands}\t"
        f"{','.join(flags) if flags else '-'}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("ref", type=parse_ref, help="DOC:PAGE reference")
    parser.add_argument("--y-range", type=parse_range, default=None)
    parser.add_argument("--min-chars", type=int, default=1)
    parser.add_argument("--edge-threshold", type=float, default=2.0)
    args = parser.parse_args()

    svg = rhwp_svg_path(args.ref).read_text(encoding="utf-8", errors="ignore")
    clips = parse_clips(svg)
    print(
        "clip\tx\ty\tw\th\ttext_runs\tchars\ttop_pad\tbottom_pad\tfirst_y_pct\t"
        "font\tfont_size\ty_bands\tflags"
    )
    for match in GROUP_RE.finditer(svg):
        clip_id = match.group("id")
        rect = clips.get(clip_id)
        if rect is None:
            continue
        if args.y_range is not None:
            y0, y1 = args.y_range
            if rect.y1 < y0 or rect.y > y1:
                continue
        runs = parse_text_runs(match.group("body"))
        if sum(len(run.text) for run in runs) < args.min_chars:
            continue
        print(summarize_cell(clip_id, rect, runs, args.edge_threshold))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
