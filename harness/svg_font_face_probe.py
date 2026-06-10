#!/usr/bin/env python3
"""Probe explicit SVG @font-face mappings against Hancom oracle pages.

This is harness-only evidence gathering. It injects data-URI @font-face rules
into temporary copies of current RHWP SVG pages, rasters them with Playwright,
and reports whether a concrete font file improves visual parity before any
renderer/runtime font policy is changed.
"""
from __future__ import annotations

import argparse
import base64
import csv
import fnmatch
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

SVG_OPEN_RE = re.compile(r"(<svg\b[^>]*>)", re.I)
TEXT_RE = re.compile(r"<text\b[^>]*>.*?</text>", re.DOTALL)
FONT_FAMILY_RE = re.compile(r'(font-family=")([^"]+)(")')


@dataclass(frozen=True)
class PageRef:
    doc: str
    page: int


@dataclass(frozen=True)
class FontRule:
    family: str
    font_path: Path
    weight: str = "normal"


@dataclass(frozen=True)
class Variant:
    name: str
    rules: tuple[FontRule, ...]
    rewrite_family: str = ""


def bundled_font(name: str) -> Path:
    for root in (RHWP / "rhwp-studio" / "dist" / "fonts", RHWP / "web" / "fonts"):
        path = root / name
        if path.exists():
            return path
    raise SystemExit(f"missing bundled font: {name}")


def default_variants() -> list[Variant]:
    malgun_aliases = ("맑은 고딕", "Malgun Gothic")
    serif_aliases = (
        "바탕",
        "Batang",
        "휴먼명조",
        "Nanum Myeongjo",
        "Noto Serif KR",
        "AppleMyungjo",
    )
    gyeonggi_serif_aliases = ("경기천년바탕 Bold",)
    gyeonggi_sans_aliases = ("경기천년제목 Medium", "경기천년제목V Bold")

    def rules(families: tuple[str, ...], font_name: str, weight: str = "normal") -> tuple[FontRule, ...]:
        font_path = bundled_font(font_name)
        return tuple(FontRule(family=family, font_path=font_path, weight=weight) for family in families)

    def combined(*groups: tuple[FontRule, ...]) -> tuple[FontRule, ...]:
        merged: list[FontRule] = []
        for group in groups:
            merged.extend(group)
        return tuple(merged)

    return [
        Variant("base", ()),
        Variant("malgun_noto_regular", rules(malgun_aliases, "NotoSansKR-Regular.woff2")),
        Variant("malgun_noto_bold", rules(malgun_aliases, "NotoSansKR-Bold.woff2", "700")),
        Variant("malgun_pretendard_regular", rules(malgun_aliases, "Pretendard-Regular.woff2")),
        Variant("malgun_pretendard_medium", rules(malgun_aliases, "Pretendard-Medium.woff2", "500")),
        Variant("malgun_nanum_regular", rules(malgun_aliases, "NanumGothic-Regular.woff2")),
        Variant("malgun_spoqa_regular", rules(malgun_aliases, "SpoqaHanSans-Regular.woff2")),
        Variant("serif_noto_regular", rules(serif_aliases, "NotoSerifKR-Regular.woff2")),
        Variant("serif_nanum_regular", rules(serif_aliases, "NanumMyeongjo-Regular.woff2")),
        Variant(
            "open_korean_baseline",
            combined(
                rules(malgun_aliases, "NotoSansKR-Regular.woff2"),
                rules(serif_aliases, "NotoSerifKR-Regular.woff2"),
                rules(gyeonggi_serif_aliases, "NotoSerifKR-Bold.woff2", "700"),
                rules(gyeonggi_sans_aliases, "NotoSansKR-Bold.woff2", "700"),
            ),
        ),
        Variant(
            "open_korean_nanum",
            combined(
                rules(malgun_aliases, "NanumGothic-Regular.woff2"),
                rules(serif_aliases, "NanumMyeongjo-Regular.woff2"),
                rules(gyeonggi_serif_aliases, "NanumMyeongjo-Bold.woff2", "700"),
                rules(gyeonggi_sans_aliases, "NanumGothic-Bold.woff2", "700"),
            ),
        ),
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


def font_mime(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".woff2":
        return "font/woff2"
    if suffix == ".woff":
        return "font/woff"
    if suffix in {".otf", ".ttf"}:
        return "font/opentype"
    return "application/octet-stream"


def font_format(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".woff2":
        return "woff2"
    if suffix == ".woff":
        return "woff"
    if suffix == ".ttf":
        return "truetype"
    return "opentype"


def css_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def font_face_css(rules: tuple[FontRule, ...]) -> str:
    lines: list[str] = []
    for rule in rules:
        data = base64.b64encode(rule.font_path.read_bytes()).decode("ascii")
        lines.append(
            "@font-face{"
            f'font-family:"{css_escape(rule.family)}";'
            f"font-weight:{rule.weight};"
            "font-style:normal;"
            f'src:url("data:{font_mime(rule.font_path)};base64,{data}") format("{font_format(rule.font_path)}");'
            "}"
        )
    return "\n".join(lines)


def inject_style(svg: str, css: str) -> str:
    if not css:
        return svg
    style = f"<defs><style><![CDATA[\n{css}\n]]></style></defs>\n"
    if "<defs>" in svg:
        return svg.replace("<defs>", f"<defs><style><![CDATA[\n{css}\n]]></style>\n", 1)
    return SVG_OPEN_RE.sub(lambda match: match.group(1) + "\n" + style, svg, count=1)


def rewrite_text_family(svg: str, family: str) -> str:
    if not family:
        return svg
    return FONT_FAMILY_RE.sub(lambda match: f'{match.group(1)}{family}{match.group(3)}', svg)


def apply_variant(svg: str, variant: Variant) -> str:
    return inject_style(rewrite_text_family(svg, variant.rewrite_family), font_face_css(variant.rules))


def filter_variants(variants: list[Variant], patterns: list[str] | None) -> list[Variant]:
    if not patterns:
        return variants
    selected = [
        variant
        for variant in variants
        if any(fnmatch.fnmatchcase(variant.name, pattern) for pattern in patterns)
    ]
    if not selected:
        available = ", ".join(variant.name for variant in variants)
        raise SystemExit(
            f"no font-face variants matched {patterns!r}; available variants: {available}"
        )
    return selected


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


def text_family_summary(svg: str) -> str:
    families: set[str] = set()
    for text_tag in TEXT_RE.findall(svg):
        match = FONT_FAMILY_RE.search(text_tag)
        if not match:
            continue
        family = (
            match.group(2)
            .replace("&apos;", "'")
            .replace("&quot;", '"')
            .replace("&amp;", "&")
        )
        families.add(family)
    return " | ".join(sorted(families))


def text_count(svg: str) -> int:
    return len(TEXT_RE.findall(svg))


def probe_one(ref: PageRef, variants: list[Variant], out_dir: Path, keep: bool) -> list[dict[str, str]]:
    source_svg = rhwp_svg_path(ref)
    hancom_png = hancom_png_path(ref)
    svg_text = source_svg.read_text(encoding="utf-8", errors="ignore")
    ref_dir = out_dir / f"{ref.doc}_p{ref.page}"
    ref_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []

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
                "text_nodes": str(text_count(svg_text)),
                "families": text_family_summary(svg_text),
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
        default=None,
        help="variant glob to run; repeatable, e.g. --variant base --variant 'open_korean_*'",
    )
    args = parser.parse_args()

    for ref in args.refs:
        ensure_current_svg(ref, args.export_current)

    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    if args.out_dir:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
    elif args.keep:
        out_dir = DIFF / "_svg_font_face_probe"
        if out_dir.exists():
            shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True)
    else:
        temp_dir = tempfile.TemporaryDirectory(prefix="rhwp-svg-font-face-probe-")
        out_dir = Path(temp_dir.name)

    try:
        rows: list[dict[str, str]] = []
        variants = filter_variants(default_variants(), args.variant)
        for ref in args.refs:
            rows.extend(probe_one(ref, variants, out_dir, keep=args.keep or bool(args.out_dir)))
        writer = csv.DictWriter(
            sys.stdout,
            fieldnames=[
                "doc",
                "page",
                "variant",
                "mean_diff",
                "dark_pixels",
                "text_nodes",
                "families",
                "png",
            ],
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
