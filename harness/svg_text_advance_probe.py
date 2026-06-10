#!/usr/bin/env python3
"""Summarize per-character SVG advances by text line.

RHWP's SVG backend emits one <text> element per visible character on many
Korean table pages. This probe groups text elements by y coordinate and reports
their x-step distribution so text/raster drift can be classified as composed
advance / justification instead of a vague font or antialias issue.
"""
from __future__ import annotations

import argparse
import html
import re
from collections import defaultdict
from dataclasses import dataclass
from statistics import median

from svg_geometry_probe import parse_ref, rhwp_svg_path


TEXT_RE = re.compile(r"<text\b(?P<attrs>[^>]*)>(?P<body>.*?)</text>", re.DOTALL)
ATTR_RE = re.compile(r"([A-Za-z_:][-A-Za-z0-9_:.]*)=(?:\"([^\"]*)\"|'([^']*)')")


@dataclass(frozen=True)
class TextPoint:
    x: float
    y: float
    font_size: float
    font_family: str
    text: str


def attr_map(raw: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for key, double, single in ATTR_RE.findall(raw):
        attrs[key] = html.unescape(double or single)
    return attrs


def parse_float(raw: str | None) -> float:
    if raw is None:
        return 0.0
    try:
        return float(raw)
    except ValueError:
        return 0.0


def primary_font(family: str) -> str:
    return family.split(",", 1)[0].strip().strip("'\"") or "-"


def parse_points(svg: str) -> list[TextPoint]:
    points: list[TextPoint] = []
    for match in TEXT_RE.finditer(svg):
        attrs = attr_map(match.group("attrs"))
        text = html.unescape(re.sub(r"<[^>]+>", "", match.group("body"))).strip()
        if not text:
            continue
        points.append(
            TextPoint(
                x=parse_float(attrs.get("x")),
                y=parse_float(attrs.get("y")),
                font_size=parse_float(attrs.get("font-size")),
                font_family=primary_font(attrs.get("font-family", "")),
                text=text,
            )
        )
    return points


def bucket_y(y: float, bucket: float) -> float:
    return round(y / bucket) * bucket


def line_stats(points: list[TextPoint], y_bucket: float) -> list[tuple[float, list[TextPoint]]]:
    groups: dict[float, list[TextPoint]] = defaultdict(list)
    for point in points:
        groups[bucket_y(point.y, y_bucket)].append(point)
    return sorted((y, sorted(line, key=lambda p: p.x)) for y, line in groups.items())


def fmt(value: float) -> str:
    return f"{value:.2f}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ref", type=parse_ref, help="DOC:PAGE")
    parser.add_argument("--y-min", type=float, default=0.0)
    parser.add_argument("--y-max", type=float, default=99999.0)
    parser.add_argument("--min-chars", type=int, default=8)
    parser.add_argument("--y-bucket", type=float, default=1.0)
    parser.add_argument("--top", type=int, default=40)
    args = parser.parse_args()

    svg = rhwp_svg_path(args.ref).read_text(encoding="utf-8", errors="ignore")
    points = [
        p
        for p in parse_points(svg)
        if args.y_min <= p.y <= args.y_max and p.x > 0.0 and p.font_size > 0.0
    ]
    rows = []
    for y, line in line_stats(points, args.y_bucket):
        if len(line) < args.min_chars:
            continue
        steps = [
            line[idx + 1].x - line[idx].x
            for idx in range(len(line) - 1)
            if line[idx + 1].x > line[idx].x
        ]
        if not steps:
            continue
        font_size = median([p.font_size for p in line])
        step_median = median(steps)
        step_max = max(steps)
        ratio = step_median / font_size if font_size else 0.0
        text = "".join(p.text for p in line)
        fonts = sorted({p.font_family for p in line})
        rows.append((ratio, y, line, steps, font_size, step_median, step_max, text, fonts))

    rows.sort(reverse=True, key=lambda r: r[0])
    print("doc\tpage\ty\tchars\tfont_size\tmedian_step\tmax_step\tstep/font\tfonts\ttext")
    for ratio, y, line, _steps, font_size, step_median, step_max, text, fonts in rows[: args.top]:
        print(
            f"{args.ref.doc}\t{args.ref.page}\t{fmt(y)}\t{len(line)}\t"
            f"{fmt(font_size)}\t{fmt(step_median)}\t{fmt(step_max)}\t"
            f"{fmt(ratio)}\t{','.join(fonts[:3])}\t{text[:120]!r}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
