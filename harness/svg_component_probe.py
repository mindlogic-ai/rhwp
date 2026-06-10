#!/usr/bin/env python3
"""Probe SVG paint components against Hancom oracle pages.

This is a fast, renderer-read-only harness for fidelity triage. It mutates
temporary copies of the current RHWP SVG page, rasters them, and reports whether
text, ruling strokes, font family, weight, or paint scale dominate the visual
diff before we spend time on Rust patches.

Usage:
  python3 harness/svg_component_probe.py overseas_training:1 accountability_eval:4
  python3 harness/svg_component_probe.py --export-current --keep accountability_eval:4
"""
from __future__ import annotations

import argparse
import csv
import fnmatch
import html
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

import review_gallery


RHWP = Path(__file__).resolve().parents[1]
DIFF = Path("/tmp/diff")
GALLERY_LABEL_H = 30
GALLERY_GAP = 12

TEXT_RE = re.compile(r"<text\b[^>]*>.*?</text>", re.DOTALL)
LINE_OR_RECT_RE = re.compile(r"<(?:line|rect)\b[^>]*/?>", re.DOTALL)
STROKE_WIDTH_RE = re.compile(r'(stroke-width=")([0-9.]+)(")')
FONT_FAMILY_RE = re.compile(r'(font-family=")([^"]+)(")')
FONT_WEIGHT_RE = re.compile(r'(font-weight=")([^"]+)(")')
FONT_SIZE_RE = re.compile(r'(font-size=")([0-9.]+)(")')
TEXT_LENGTH_ATTR_RE = re.compile(r'\s+textLength="[^"]+"\s+lengthAdjust="[^"]+"')
FILL_OR_STROKE_BLACK_RE = re.compile(r'(?:fill|stroke)="(?:#000000|#000|black|rgb\(0,\s*0,\s*0\))"', re.I)
CELL_CLIP_RE = re.compile(
    r'<clipPath id="(?P<id>cell-clip-[^"]+)"><rect (?P<attrs>[^>]*)/></clipPath>'
)
CLIPPED_IMAGE_RE = re.compile(
    r'<g clip-path="url\(#(?P<clip>cell-clip-[^)]+)\)">(?P<body>.*?)</g>',
    re.DOTALL,
)
IMAGE_TAG_RE = re.compile(r"<image\b[^>]*>", re.DOTALL)
SVG_ATTR_RE = re.compile(r'([a-zA-Z_:][-a-zA-Z0-9_:.]*)="([^"]*)"')
TEXT_TAG_RE = re.compile(r"<text\b(?P<attrs>[^>]*)>(?P<body>.*?)</text>", re.DOTALL)
ATTR_RE = re.compile(r"([A-Za-z_:][-A-Za-z0-9_:.]*)=(?:\"([^\"]*)\"|'([^']*)')")


@dataclass(frozen=True)
class PageRef:
    doc: str
    page: int


@dataclass(frozen=True)
class Variant:
    name: str
    kind: str
    value: str


VARIANTS = [
    Variant("base", "base", ""),
    Variant("hide_text", "hide_text", ""),
    Variant("hide_lines", "hide_lines", ""),
    Variant("hide_text_gyeonggi", "hide_text_family", "경기천년"),
    Variant("hide_text_noto", "hide_text_family", "Noto Sans KR"),
    Variant("hide_text_malgun", "hide_text_family", "Malgun Gothic|맑은 고딕"),
    Variant("thin_stroke_x0.50", "thin_stroke_factor", "0.50"),
    Variant("thin_stroke_x0.75", "thin_stroke_factor", "0.75"),
    Variant("thin_stroke_x1.00", "thin_stroke_factor", "1.00"),
    Variant("thin_stroke_x1.50", "thin_stroke_factor", "1.50"),
    Variant("thin_stroke_x2.00", "thin_stroke_factor", "2.00"),
    Variant("thin_stroke_x3.00", "thin_stroke_factor", "3.00"),
    Variant("stroke_eq_0.07_x2", "stroke_width_eq_factor", "0.07=2.0"),
    Variant("stroke_eq_0.07_x3", "stroke_width_eq_factor", "0.07=3.0"),
    Variant("stroke_eq_0.0875_x2", "stroke_width_eq_factor", "0.0875=2.0"),
    Variant("stroke_eq_0.105_x2", "stroke_width_eq_factor", "0.105=2.0"),
    Variant("stroke_eq_0.1575_x2", "stroke_width_eq_factor", "0.1575=2.0"),
    Variant("stroke_min_0.12", "stroke_min_width", "0.12"),
    Variant("stroke_min_0.16", "stroke_min_width", "0.16"),
    Variant("stroke_min_0.20", "stroke_min_width", "0.20"),
    Variant("stroke_min_0.30", "stroke_min_width", "0.30"),
    Variant("stroke_min_0.50", "stroke_min_width", "0.50"),
    Variant("stroke_eq_0.07_x5", "stroke_width_eq_factor", "0.07=5.0"),
    Variant("stroke_eq_0.07_x7", "stroke_width_eq_factor", "0.07=7.0"),
    Variant("font_Apple_SD_Gothic_Neo", "font_family", "Apple SD Gothic Neo"),
    Variant("font_Noto_Sans_KR", "font_family", "Noto Sans KR"),
    Variant("font_Pretendard", "font_family", "Pretendard"),
    Variant("font_Nanum_Gothic", "font_family", "Nanum Gothic"),
    Variant("font_AppleGothic", "font_family", "AppleGothic"),
    Variant("weight_500", "font_weight", "500"),
    Variant("weight_600", "font_weight", "600"),
    Variant("weight_gyeonggi_500", "font_family_weight", "경기천년=500"),
    Variant("weight_gyeonggi_600", "font_family_weight", "경기천년=600"),
    Variant("font_size_x0.90", "font_size_factor", "0.90"),
    Variant("font_size_x1.00", "font_size_factor", "1.00"),
    Variant("font_size_x1.10", "font_size_factor", "1.10"),
    Variant("font_size_gyeonggi_x0.90", "font_family_size_factor", "경기천년=0.90"),
    Variant("font_size_gyeonggi_x1.10", "font_family_size_factor", "경기천년=1.10"),
    Variant("font_size_noto_x0.90", "font_family_size_factor", "Noto Sans KR=0.90"),
    Variant("font_size_noto_x1.10", "font_family_size_factor", "Noto Sans KR=1.10"),
    Variant("font_family_bold_attr", "font_family_bold_attr", ""),
    Variant("remove_text_length", "remove_text_length", ""),
    Variant("clamp_cell_image_top", "clamp_cell_image_top", ""),
    Variant("shift_crop_y_15", "shift_crop_y", "15"),
    Variant("image_height_x1.05", "image_height_factor", "1.05"),
    Variant("image_height_x1.08", "image_height_factor", "1.08"),
    Variant("image_height_x1.12", "image_height_factor", "1.12"),
    Variant("image_y_m12", "image_y_shift", "-12"),
    Variant("image_y_m6", "image_y_shift", "-6"),
    Variant("image_y_p6", "image_y_shift", "6"),
    Variant("image_y_p12", "image_y_shift", "12"),
    Variant("image_filter_b95_c110", "image_css_filter", "brightness(0.95) contrast(1.10)"),
    Variant("image_filter_b90_c115", "image_css_filter", "brightness(0.90) contrast(1.15)"),
    Variant("image_filter_b85_c120", "image_css_filter", "brightness(0.85) contrast(1.20)"),
    Variant("shift_y_after_430_p12", "shift_y_after", "430=12"),
    Variant("shift_y_after_430_m12", "shift_y_after", "430=-12"),
    Variant("text_stroke_0.15", "text_stroke", "0.15"),
    Variant("text_stroke_0.25", "text_stroke", "0.25"),
    Variant("text_y_m4", "text_y_shift", "-4"),
    Variant("text_y_m2", "text_y_shift", "-2"),
    Variant("text_y_p2", "text_y_shift", "2"),
    Variant("text_y_p4", "text_y_shift", "4"),
    Variant("normalize_line_advances_1.00", "normalize_line_advances", "1.00"),
    Variant("normalize_line_advances_1.10", "normalize_line_advances", "1.10"),
    Variant("normalize_line_advances_1.18", "normalize_line_advances", "1.18"),
]


def parse_ref(raw: str) -> PageRef:
    if ":" not in raw:
        raise argparse.ArgumentTypeError(f"expected DOC:PAGE, got {raw!r}")
    doc, page_raw = raw.rsplit(":", 1)
    if not doc:
        raise argparse.ArgumentTypeError("doc name is empty")
    try:
        page = int(page_raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid page number in {raw!r}") from exc
    if page <= 0:
        raise argparse.ArgumentTypeError("page must be positive")
    return PageRef(doc=doc, page=page)


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


def ensure_current_svg(ref: PageRef, export_current: bool) -> None:
    if export_current:
        review_gallery.export_current(docdir(ref))
    else:
        rhwp_svg_path(ref)


def change_thin_strokes(svg: str, factor: float) -> str:
    def replace_tag(match: re.Match[str]) -> str:
        tag = match.group(0)
        if not FILL_OR_STROKE_BLACK_RE.search(tag):
            return tag

        def replace_width(width_match: re.Match[str]) -> str:
            width = float(width_match.group(2))
            if width > 1.0:
                return width_match.group(0)
            return f'{width_match.group(1)}{width * factor:.4g}{width_match.group(3)}'

        return STROKE_WIDTH_RE.sub(replace_width, tag)

    return LINE_OR_RECT_RE.sub(replace_tag, svg)


def split_width_value(raw: str) -> tuple[float, float]:
    if "=" not in raw:
        raise ValueError(f"expected WIDTH=VALUE, got {raw!r}")
    left, right = raw.rsplit("=", 1)
    return float(left), float(right)


def change_stroke_width_eq(svg: str, target: float, factor: float) -> str:
    def replace_tag(match: re.Match[str]) -> str:
        tag = match.group(0)
        if not FILL_OR_STROKE_BLACK_RE.search(tag):
            return tag

        def replace_width(width_match: re.Match[str]) -> str:
            width = float(width_match.group(2))
            if abs(width - target) > 0.002:
                return width_match.group(0)
            return f'{width_match.group(1)}{width * factor:.4g}{width_match.group(3)}'

        return STROKE_WIDTH_RE.sub(replace_width, tag)

    return LINE_OR_RECT_RE.sub(replace_tag, svg)


def change_stroke_min_width(svg: str, min_width: float) -> str:
    def replace_tag(match: re.Match[str]) -> str:
        tag = match.group(0)
        if not FILL_OR_STROKE_BLACK_RE.search(tag):
            return tag

        def replace_width(width_match: re.Match[str]) -> str:
            width = float(width_match.group(2))
            if width >= min_width:
                return width_match.group(0)
            return f'{width_match.group(1)}{min_width:.4g}{width_match.group(3)}'

        return STROKE_WIDTH_RE.sub(replace_width, tag)

    return LINE_OR_RECT_RE.sub(replace_tag, svg)


def family_patterns(raw: str) -> list[str]:
    return [part for part in raw.split("|") if part]


def text_tag_has_family(tag: str, patterns: list[str]) -> bool:
    match = FONT_FAMILY_RE.search(tag)
    if not match:
        return False
    family = match.group(2)
    return any(pattern in family for pattern in patterns)


def split_family_value(raw: str) -> tuple[list[str], str]:
    if "=" not in raw:
        raise ValueError(f"expected FAMILY=VALUE, got {raw!r}")
    family, value = raw.rsplit("=", 1)
    return family_patterns(family), value


def change_family_font_size(tag: str, factor: float) -> str:
    def replace_size(match: re.Match[str]) -> str:
        return f'{match.group(1)}{float(match.group(2)) * factor:.4g}{match.group(3)}'

    return FONT_SIZE_RE.sub(replace_size, tag)


def change_family_font_weight(tag: str, weight: str) -> str:
    if FONT_WEIGHT_RE.search(tag):
        return FONT_WEIGHT_RE.sub(lambda m: f'{m.group(1)}{weight}{m.group(3)}', tag)
    return tag.replace("<text ", f'<text font-weight="{weight}" ', 1)


def add_bold_attr_for_bold_named_faces(svg: str) -> str:
    def replace_tag(match: re.Match[str]) -> str:
        tag = match.group(0)
        if FONT_WEIGHT_RE.search(tag):
            return tag
        family = FONT_FAMILY_RE.search(tag)
        if not family:
            return tag
        primary = family.group(2).split(",", 1)[0].strip("'\"")
        lower = primary.lower()
        if "bold" not in lower and "extra" not in lower and "굵" not in primary:
            return tag
        return tag.replace("<text ", '<text font-weight="bold" ', 1)

    return TEXT_RE.sub(replace_tag, svg)


def svg_attrs(raw: str) -> dict[str, str]:
    return {match.group(1): match.group(2) for match in SVG_ATTR_RE.finditer(raw)}


def replace_svg_attr(tag: str, name: str, value: float) -> str:
    pattern = re.compile(rf'({re.escape(name)}=")([^"]*)(")')
    replacement = rf"\g<1>{value:.12g}\3"
    if pattern.search(tag):
        return pattern.sub(replacement, tag, count=1)
    return tag.replace("<image ", f'<image {name}="{value:.12g}" ', 1)


def clamp_cell_image_top(svg: str) -> str:
    clip_top: dict[str, float] = {}
    for match in CELL_CLIP_RE.finditer(svg):
        attrs = svg_attrs(match.group("attrs"))
        try:
            clip_top[match.group("id")] = float(attrs["y"])
        except (KeyError, ValueError):
            continue

    def replace_group(match: re.Match[str]) -> str:
        top = clip_top.get(match.group("clip"))
        if top is None:
            return match.group(0)

        def replace_image(image_match: re.Match[str]) -> str:
            tag = image_match.group(0)
            attrs = svg_attrs(tag)
            try:
                y = float(attrs["y"])
            except (KeyError, ValueError):
                return tag
            if y >= top:
                return tag
            return replace_svg_attr(tag, "y", top)

        body = IMAGE_TAG_RE.sub(replace_image, match.group("body"))
        return f'<g clip-path="url(#{match.group("clip")})">{body}</g>'

    return CLIPPED_IMAGE_RE.sub(replace_group, svg)


def shift_crop_y(svg: str, dy: float) -> str:
    crop_ids = set(re.findall(r'<clipPath id="(crop-clip-[^"]+)">', svg))
    if not crop_ids:
        return svg

    def shift_rect(match: re.Match[str]) -> str:
        tag = match.group(0)
        attrs = svg_attrs(tag)
        try:
            y = float(attrs["y"])
        except (KeyError, ValueError):
            return tag
        return replace_svg_attr(tag, "y", y + dy)

    def shift_group(match: re.Match[str]) -> str:
        clip_id = match.group("clip")
        if clip_id not in crop_ids:
            return match.group(0)

        def shift_image(image_match: re.Match[str]) -> str:
            tag = image_match.group(0)
            attrs = svg_attrs(tag)
            try:
                y = float(attrs["y"])
            except (KeyError, ValueError):
                return tag
            return replace_svg_attr(tag, "y", y + dy)

        body = IMAGE_TAG_RE.sub(shift_image, match.group("body"))
        return f'<g clip-path="url(#{clip_id})">{body}</g>'

    svg = re.sub(
        r'<clipPath id="crop-clip-[^"]+"><rect [^>]*/></clipPath>',
        lambda m: re.sub(r"<rect\b[^>]*/>", shift_rect, m.group(0)),
        svg,
    )
    return re.sub(
        r'<g clip-path="url\(#(?P<clip>crop-clip-[^)]+)\)">(?P<body>.*?)</g>',
        shift_group,
        svg,
        flags=re.DOTALL,
    )


def scale_image_height(svg: str, factor: float) -> str:
    def replace_image(match: re.Match[str]) -> str:
        tag = match.group(0)
        attrs = svg_attrs(tag)
        try:
            height = float(attrs["height"])
        except (KeyError, ValueError):
            return tag
        return replace_svg_attr(tag, "height", height * factor)

    return IMAGE_TAG_RE.sub(replace_image, svg)


def shift_image_y(svg: str, dy: float) -> str:
    def replace_image(match: re.Match[str]) -> str:
        tag = match.group(0)
        attrs = svg_attrs(tag)
        try:
            y = float(attrs["y"])
        except (KeyError, ValueError):
            return tag
        return replace_svg_attr(tag, "y", y + dy)

    return IMAGE_TAG_RE.sub(replace_image, svg)


def add_image_css_filter(svg: str, filter_value: str) -> str:
    def replace_image(match: re.Match[str]) -> str:
        tag = match.group(0)
        if " filter=" in tag:
            return tag
        return tag.replace("<image ", f'<image filter="{filter_value}" ', 1)

    return IMAGE_TAG_RE.sub(replace_image, svg)


def split_threshold_shift(raw: str) -> tuple[float, float]:
    if "=" not in raw:
        raise ValueError(f"expected THRESHOLD=SHIFT, got {raw!r}")
    left, right = raw.rsplit("=", 1)
    return float(left), float(right)


def shift_y_after(svg: str, threshold: float, dy: float) -> str:
    y_attr_re = re.compile(r'\by="([^"]+)"')
    y1_attr_re = re.compile(r'\by1="([^"]+)"')
    y2_attr_re = re.compile(r'\by2="([^"]+)"')

    def shift_attr(tag: str, pattern: re.Pattern[str], attr: str) -> str:
        match = pattern.search(tag)
        if not match:
            return tag
        try:
            y = float(match.group(1))
        except ValueError:
            return tag
        if y < threshold:
            return tag
        return replace_svg_attr(tag, attr, y + dy)

    def replace_tag(match: re.Match[str]) -> str:
        tag = match.group(0)
        if tag.startswith("<line"):
            tag = shift_attr(tag, y1_attr_re, "y1")
            tag = shift_attr(tag, y2_attr_re, "y2")
            return tag
        return shift_attr(tag, y_attr_re, "y")

    return re.sub(r"<(?:text|image|rect|line)\b[^>]*>", replace_tag, svg)


def add_text_stroke(svg: str, width: float) -> str:
    def replace_text(match: re.Match[str]) -> str:
        tag = match.group(0)
        if 'stroke="' in tag:
            return tag
        fill = re.search(r'fill="([^"]+)"', tag)
        color = fill.group(1) if fill else "#000000"
        return tag.replace(
            "<text ",
            f'<text stroke="{color}" stroke-width="{width:.3g}" paint-order="stroke fill" ',
            1,
        )

    return TEXT_RE.sub(replace_text, svg)


def shift_text_y(svg: str, dy: float) -> str:
    def replace_text(match: re.Match[str]) -> str:
        tag = match.group(0)
        attrs = svg_attrs(tag)
        try:
            y = float(attrs["y"])
        except (KeyError, ValueError):
            return tag
        return replace_svg_attr(tag, "y", y + dy)

    return TEXT_RE.sub(replace_text, svg)


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


def normalize_line_advances(svg: str, step_font_ratio: float) -> str:
    matches = list(TEXT_TAG_RE.finditer(svg))
    if not matches:
        return svg
    tags = []
    groups: dict[float, list[int]] = {}
    for idx, match in enumerate(matches):
        attrs = attr_map(match.group("attrs"))
        body = html.unescape(re.sub(r"<[^>]+>", "", match.group("body"))).strip()
        x = parse_float(attrs.get("x"))
        y = parse_float(attrs.get("y"))
        font_size = parse_float(attrs.get("font-size"))
        tags.append((match, attrs, body, x, y, font_size))
        if body and x > 0.0 and y > 0.0 and font_size > 0.0 and len(body) == 1:
            groups.setdefault(round(y), []).append(idx)

    new_tags: dict[int, str] = {}
    for indices in groups.values():
        if len(indices) < 8:
            continue
        indices = sorted(indices, key=lambda i: tags[i][3])
        xs = [tags[i][3] for i in indices]
        steps = [b - a for a, b in zip(xs, xs[1:]) if b > a]
        if not steps:
            continue
        font_size = sorted(tags[i][5] for i in indices)[len(indices) // 2]
        current_median = sorted(steps)[len(steps) // 2]
        target_step = font_size * step_font_ratio
        # Only normalize visibly expanded lines; leave dense numeric/compressed rows alone.
        if current_median <= target_step + 0.5:
            continue
        x0 = xs[0]
        for pos, idx in enumerate(indices):
            match, _attrs, _body, _x, _y, _font_size = tags[idx]
            target_x = x0 + pos * target_step
            tag = match.group(0)
            tag = re.sub(r'x="[^"]+"', f'x="{target_x:.4f}"', tag, count=1)
            new_tags[idx] = tag

    if not new_tags:
        return svg
    out = []
    last = 0
    for idx, (match, *_rest) in enumerate(tags):
        out.append(svg[last : match.start()])
        out.append(new_tags.get(idx, match.group(0)))
        last = match.end()
    out.append(svg[last:])
    return "".join(out)


def apply_variant(svg: str, variant: Variant) -> str:
    if variant.kind == "base":
        return svg
    if variant.kind == "hide_text":
        return TEXT_RE.sub("", svg)
    if variant.kind == "hide_text_family":
        patterns = family_patterns(variant.value)
        return TEXT_RE.sub(lambda m: "" if text_tag_has_family(m.group(0), patterns) else m.group(0), svg)
    if variant.kind == "hide_lines":
        return LINE_OR_RECT_RE.sub("", svg)
    if variant.kind == "thin_stroke_factor":
        return change_thin_strokes(svg, float(variant.value))
    if variant.kind == "stroke_width_eq_factor":
        target, factor = split_width_value(variant.value)
        return change_stroke_width_eq(svg, target, factor)
    if variant.kind == "stroke_min_width":
        return change_stroke_min_width(svg, float(variant.value))
    if variant.kind == "font_family":
        return FONT_FAMILY_RE.sub(lambda m: f'{m.group(1)}{variant.value}{m.group(3)}', svg)
    if variant.kind == "font_weight":
        if FONT_WEIGHT_RE.search(svg):
            return FONT_WEIGHT_RE.sub(lambda m: f'{m.group(1)}{variant.value}{m.group(3)}', svg)
        return TEXT_RE.sub(lambda m: m.group(0).replace("<text ", f'<text font-weight="{variant.value}" ', 1), svg)
    if variant.kind == "font_family_weight":
        patterns, weight = split_family_value(variant.value)
        return TEXT_RE.sub(
            lambda m: change_family_font_weight(m.group(0), weight)
            if text_tag_has_family(m.group(0), patterns)
            else m.group(0),
            svg,
        )
    if variant.kind == "font_size_factor":
        factor = float(variant.value)

        def replace_size(match: re.Match[str]) -> str:
            return f'{match.group(1)}{float(match.group(2)) * factor:.4g}{match.group(3)}'

        return FONT_SIZE_RE.sub(replace_size, svg)
    if variant.kind == "font_family_size_factor":
        patterns, value = split_family_value(variant.value)
        factor = float(value)
        return TEXT_RE.sub(
            lambda m: change_family_font_size(m.group(0), factor)
            if text_tag_has_family(m.group(0), patterns)
            else m.group(0),
            svg,
        )
    if variant.kind == "font_family_bold_attr":
        return add_bold_attr_for_bold_named_faces(svg)
    if variant.kind == "remove_text_length":
        return TEXT_LENGTH_ATTR_RE.sub("", svg)
    if variant.kind == "clamp_cell_image_top":
        return clamp_cell_image_top(svg)
    if variant.kind == "shift_crop_y":
        return shift_crop_y(svg, float(variant.value))
    if variant.kind == "image_height_factor":
        return scale_image_height(svg, float(variant.value))
    if variant.kind == "image_y_shift":
        return shift_image_y(svg, float(variant.value))
    if variant.kind == "image_css_filter":
        return add_image_css_filter(svg, variant.value)
    if variant.kind == "shift_y_after":
        threshold, dy = split_threshold_shift(variant.value)
        return shift_y_after(svg, threshold, dy)
    if variant.kind == "text_stroke":
        return add_text_stroke(svg, float(variant.value))
    if variant.kind == "text_y_shift":
        return shift_text_y(svg, float(variant.value))
    if variant.kind == "normalize_line_advances":
        return normalize_line_advances(svg, float(variant.value))
    raise AssertionError(f"unknown variant kind: {variant.kind}")


def fit_to_match(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    if image.size == size:
        return image
    return image.resize(size)


def mean_diff(left: Path, right: Path) -> float:
    with Image.open(left) as opened_left, Image.open(right) as opened_right:
        oracle = opened_left.convert("RGB")
        candidate = fit_to_match(opened_right.convert("RGB"), oracle.size)
        diff = ImageChops.difference(oracle, candidate)
        stat = ImageStat.Stat(diff)
        return sum(stat.mean) / 3.0


def dark_pixels(path: Path, threshold: int = 96) -> int:
    with Image.open(path) as opened:
        rgba = opened.convert("RGBA")
    dark = 0
    for red, green, blue, alpha in rgba.getdata():
        if alpha == 0:
            continue
        luma = 0.2126 * red + 0.7152 * green + 0.0722 * blue
        if luma < threshold:
            dark += 1
    return dark


def probe_one(
    ref: PageRef, out_dir: Path, keep: bool, variants: list[Variant]
) -> list[dict[str, str]]:
    source_svg = rhwp_svg_path(ref)
    hancom_png = hancom_png_path(ref)
    svg_text = source_svg.read_text(encoding="utf-8", errors="ignore")
    rows: list[dict[str, str]] = []
    ref_dir = out_dir / f"{ref.doc}_p{ref.page}"
    ref_dir.mkdir(parents=True, exist_ok=True)

    for variant in variants:
        variant_svg = ref_dir / f"{variant.name}.svg"
        variant_png = ref_dir / f"{variant.name}.png"
        variant_svg.write_text(apply_variant(svg_text, variant), encoding="utf-8")
        review_gallery.raster_svg(variant_svg, variant_png)
        rows.append(
            {
                "doc": ref.doc,
                "page": str(ref.page),
                "variant": variant.name,
                "mean_diff": f"{mean_diff(hancom_png, variant_png):.2f}",
                "dark_pixels": str(dark_pixels(variant_png)),
                "png": str(variant_png) if keep else "",
            }
        )

    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("refs", nargs="+", type=parse_ref, help="one or more DOC:PAGE references")
    parser.add_argument("--export-current", action="store_true", help="refresh rhwp_svg_cur before probing")
    parser.add_argument("--keep", action="store_true", help="keep probe SVG/PNG artifacts and print paths")
    parser.add_argument("--out-dir", default="", help="artifact directory; default is a temp dir unless --keep")
    parser.add_argument(
        "--variant",
        action="append",
        default=[],
        help="variant name or shell-style pattern to run; may be repeated",
    )
    args = parser.parse_args()

    for ref in args.refs:
        ensure_current_svg(ref, args.export_current)

    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    if args.out_dir:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
    elif args.keep:
        out_dir = DIFF / "_svg_component_probe"
        if out_dir.exists():
            shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True)
    else:
        temp_dir = tempfile.TemporaryDirectory(prefix="rhwp-svg-probe-")
        out_dir = Path(temp_dir.name)

    try:
        variants = VARIANTS
        if args.variant:
            variants = [
                variant
                for variant in VARIANTS
                if any(fnmatch.fnmatch(variant.name, pattern) for pattern in args.variant)
            ]
            if not variants:
                raise SystemExit(f"no variants matched: {', '.join(args.variant)}")
        rows: list[dict[str, str]] = []
        for ref in args.refs:
            rows.extend(probe_one(ref, out_dir, keep=args.keep or bool(args.out_dir), variants=variants))
        writer = csv.DictWriter(
            sys.stdout,
            fieldnames=["doc", "page", "variant", "mean_diff", "dark_pixels", "png"],
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
