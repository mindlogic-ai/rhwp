#!/usr/bin/env python3
"""Audit rendered SVG font families against bundled/system font resources.

This is a read-only fidelity triage helper. It answers a narrow question for
the text/raster category: are high-drift pages asking the renderer/browser for
font faces we actually provide, or are they falling through to platform
substitution?

Usage:
  python3 harness/svg_font_resource_audit.py overseas_training:1 meeting_summary:1
"""

from __future__ import annotations

import argparse
import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
DIFF = Path("/tmp/diff")
FONT_LOADER = REPO / "rhwp-studio/src/core/font-loader.ts"
FONT_ATTR_RE = re.compile(r'font-family="([^"]+)"')
FONT_LIST_RE = re.compile(
    r"\{\s*name:\s*'([^']+)'\s*,\s*file:\s*([^,}\n]+)", re.MULTILINE
)
LOCAL_FONT_ROOTS = [
    REPO / "rhwp-studio/dist",
    REPO / "web",
]
SYSTEM_FONT_DIRS = [
    Path("/System/Library/Fonts"),
    Path("/System/Library/Fonts/Supplemental"),
    Path("/Library/Fonts"),
    Path.home() / "Library/Fonts",
]


@dataclass(frozen=True)
class FontResource:
    status: str
    detail: str


def parse_ref(ref: str) -> tuple[str, int]:
    if ":" not in ref:
        raise SystemExit(f"expected DOC:PAGE, got {ref!r}")
    doc, page_s = ref.rsplit(":", 1)
    return doc, int(page_s)


def svg_path(doc: str, page: int) -> Path:
    return DIFF / doc / "rhwp_svg_cur" / f"source_{page:03d}.svg"


def ref_from_svg_path(path: Path) -> tuple[str, int]:
    try:
        relative = path.relative_to(DIFF)
    except ValueError as exc:
        raise SystemExit(f"SVG path is outside {DIFF}: {path}") from exc
    doc = relative.parts[0]
    match = re.fullmatch(r"source_(\d+)\.svg", path.name)
    if not match:
        raise SystemExit(f"unexpected SVG filename: {path}")
    return doc, int(match.group(1))


def iter_all_svg_paths() -> list[Path]:
    return sorted(DIFF.glob("*/rhwp_svg_cur/source_*.svg"))


def primary_font(family: str) -> str:
    return family.split(",", 1)[0].strip().strip("'\"")


def local_font_exists(relative_file: str) -> bool:
    return any((root / relative_file).exists() for root in LOCAL_FONT_ROOTS)


def load_font_registry() -> dict[str, FontResource]:
    if not FONT_LOADER.exists():
        return {}
    text = FONT_LOADER.read_text(encoding="utf-8")
    registry: dict[str, FontResource] = {}
    for name, file_expr in FONT_LIST_RE.findall(text):
        file_expr = file_expr.strip()
        if file_expr.startswith("'") and file_expr.endswith("'"):
            relative_file = file_expr.strip("'")
            if local_font_exists(relative_file):
                resource = FontResource("bundled", relative_file)
            else:
                resource = FontResource("bundled-missing", relative_file)
        elif file_expr.startswith("CDN_"):
            resource = FontResource("cdn", file_expr)
        else:
            resource = FontResource("registered", file_expr)
        registry[name] = resource
    return registry


def system_font_names() -> set[str]:
    names: set[str] = set()
    for base in SYSTEM_FONT_DIRS:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.suffix.lower() not in {".ttf", ".otf", ".ttc"}:
                continue
            stem = path.stem
            names.add(stem)
            names.add(stem.replace("-", " "))
    # fc-match is not always installed on macOS, but use it when present.
    try:
        out = subprocess.run(
            ["fc-list", ":", "family"],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        ).stdout
    except FileNotFoundError:
        out = ""
    for line in out.splitlines():
        for name in line.split(","):
            if name.strip():
                names.add(name.strip())
    return names


def classify(
    font: str, registry: dict[str, FontResource], system_fonts: set[str]
) -> FontResource:
    if not font:
        return FontResource("empty", "-")
    if font in registry:
        return registry[font]
    if font in system_fonts:
        return FontResource("system", "local-system")
    if any(font.startswith(prefix) for prefix in ("경기천년", "한컴 ", "휴먼")):
        return FontResource("missing-office-face", "-")
    if font.startswith("HY"):
        return FontResource("missing-hy-face", "-")
    return FontResource("missing-or-platform-fallback", "-")


def audit_ref(
    ref: str, registry: dict[str, FontResource], system_fonts: set[str]
) -> list[str]:
    doc, page = parse_ref(ref)
    path = svg_path(doc, page)
    if not path.exists():
        raise SystemExit(f"missing SVG for {ref}: {path}")
    return audit_svg(doc, page, path, registry, system_fonts)


def audit_svg(
    doc: str,
    page: int,
    path: Path,
    registry: dict[str, FontResource],
    system_fonts: set[str],
) -> list[str]:
    svg = path.read_text(encoding="utf-8")
    fonts = Counter(primary_font(value) for value in FONT_ATTR_RE.findall(svg))
    rows = []
    for font, runs in fonts.most_common():
        resource = classify(font, registry, system_fonts)
        rows.append(
            "\t".join(
                [
                    doc,
                    str(page),
                    font or "-",
                    str(runs),
                    resource.status,
                    resource.detail,
                ]
            )
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("refs", nargs="*", help="DOC:PAGE references")
    parser.add_argument(
        "--all",
        action="store_true",
        help="audit every /tmp/diff/*/rhwp_svg_cur/source_*.svg page",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="append status/font totals after detailed rows",
    )
    args = parser.parse_args()
    if not args.refs and not args.all:
        parser.error("provide at least one DOC:PAGE ref or --all")

    registry = load_font_registry()
    system_fonts = system_font_names()
    print("doc\tpage\tprimary_font\ttext_runs\tresource_status\tresource_detail")
    rows: list[str] = []
    if args.all:
        for path in iter_all_svg_paths():
            doc, page = ref_from_svg_path(path)
            rows.extend(audit_svg(doc, page, path, registry, system_fonts))
    for ref in args.refs:
        rows.extend(audit_ref(ref, registry, system_fonts))
    for row in rows:
        print(row)

    if args.summary:
        status_runs: Counter[str] = Counter()
        font_runs: Counter[tuple[str, str]] = Counter()
        font_pages: Counter[tuple[str, str]] = Counter()
        for row in rows:
            doc, page, font, runs_s, status, _detail = row.split("\t")
            runs = int(runs_s)
            key = (status, font)
            status_runs[status] += runs
            font_runs[key] += runs
            font_pages[key] += 1
        print()
        print("summary_status\ttext_runs")
        for status, runs in status_runs.most_common():
            print(f"{status}\t{runs}")
        print()
        print("summary_font\tresource_status\ttext_runs\tpages")
        for (status, font), runs in font_runs.most_common():
            print(f"{font}\t{status}\t{runs}\t{font_pages[(status, font)]}")


if __name__ == "__main__":
    main()
