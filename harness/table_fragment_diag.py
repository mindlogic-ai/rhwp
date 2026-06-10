#!/usr/bin/env python3
"""Diagnose RHWP partial-table fragments against HWPX row/span structure.

Usage:
    python3 harness/table_fragment_diag.py /tmp/diff/accountability_eval_fitted_oracle

The script is intentionally read-only. It answers the question that comes up
when a table page-count matches but visual row bands drift:

* which rows RHWP placed on each page;
* which source rows start inside that fragment;
* which row-spanning cells are being carried from earlier rows;
* what horizontal table bands the current SVG emitted.
"""

from __future__ import annotations

import argparse
import collections
import math
import re
import subprocess
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


NS = {"hp": "http://www.hancom.co.kr/hwpml/2011/paragraph"}
PAGE_RE = re.compile(r"^=== 페이지 (\d+) ")
PARTIAL_RE = re.compile(r"PartialTable\s+pi=(\d+)\s+ci=(\d+)\s+rows=(\d+)\.\.(\d+)")
LINE_RE = re.compile(
    r"<line\b[^>]*x1=\"([0-9.]+)\"[^>]*y1=\"([0-9.]+)\"[^>]*x2=\"([0-9.]+)\"[^>]*y2=\"([0-9.]+)\""
)
TEXT_RE = re.compile(r"<text\b[^>]*\by=\"([0-9.]+)\"[^>]*>(.*?)</text>", re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
FONT_SIZE_RE = re.compile(r'font-size="([^"]+)"')
FONT_FAMILY_RE = re.compile(r'font-family="([^"]+)"')
FONT_WEIGHT_RE = re.compile(r'font-weight="([^"]+)"')


@dataclass(frozen=True)
class Cell:
    row: int
    col: int
    row_span: int
    col_span: int
    height_hu: int
    line_segs: int
    text: str


@dataclass(frozen=True)
class Fragment:
    page: int
    pi: int
    ci: int
    start: int
    end: int


def hu_to_px(value: int, dpi: float = 96.0) -> float:
    return value * dpi / 7200.0


def find_source(docdir: Path) -> Path:
    for name in ("source.hwpx", "source_converted.hwpx", "source_fitted.hwpx"):
        path = docdir / name
        if path.exists():
            return path
    raise SystemExit(f"no HWPX source found under {docdir}")


def parse_table(hwpx: Path, table_index: int) -> tuple[ET.Element, list[Cell]]:
    with zipfile.ZipFile(hwpx) as zf:
        sections = sorted(name for name in zf.namelist() if name.startswith("Contents/section"))
        tables: list[ET.Element] = []
        for name in sections:
            root = ET.fromstring(zf.read(name))
            tables.extend(root.findall(".//hp:tbl", NS))
    if table_index >= len(tables):
        raise SystemExit(f"table index {table_index} out of range; found {len(tables)} table(s)")
    table = tables[table_index]
    cells: list[Cell] = []
    for tc in table.findall(".//hp:tc", NS):
        addr = tc.find("hp:cellAddr", NS)
        span = tc.find("hp:cellSpan", NS)
        size = tc.find("hp:cellSz", NS)
        if addr is None or span is None or size is None:
            continue
        text = " ".join("".join(tc.itertext()).split())
        line_segs = len(tc.findall(".//hp:lineseg", NS))
        cells.append(
            Cell(
                row=int(addr.attrib["rowAddr"]),
                col=int(addr.attrib["colAddr"]),
                row_span=int(span.attrib.get("rowSpan", "1")),
                col_span=int(span.attrib.get("colSpan", "1")),
                height_hu=int(size.attrib.get("height", "0")),
                line_segs=line_segs,
                text=text[:28],
            )
        )
    return table, sorted(cells, key=lambda c: (c.row, c.col))


def parse_fragments(docdir: Path) -> list[Fragment]:
    candidates = [
        docdir / "dump_pages_current.txt",
        docdir / "dump_pages_after_repeat_header.txt",
        docdir / "dump_pages.txt",
    ]
    dump = next((path for path in candidates if path.exists()), None)
    if dump is None:
        return []
    page = 0
    fragments: list[Fragment] = []
    for line in dump.read_text(encoding="utf-8", errors="ignore").splitlines():
        if match := PAGE_RE.search(line):
            page = int(match.group(1))
            continue
        if match := PARTIAL_RE.search(line):
            fragments.append(
                Fragment(
                    page=page,
                    pi=int(match.group(1)),
                    ci=int(match.group(2)),
                    start=int(match.group(3)),
                    end=int(match.group(4)),
                )
            )
    return fragments


def svg_horizontal_bands(docdir: Path, page: int) -> list[float]:
    svg = docdir / "rhwp_svg_cur" / f"source_{page:03d}.svg"
    if not svg.exists():
        return []
    ys: list[float] = []
    for match in LINE_RE.finditer(svg.read_text(encoding="utf-8", errors="ignore")):
        x1, y1, x2, y2 = map(float, match.groups())
        if abs(y1 - y2) <= 0.05 and abs(x2 - x1) >= 200.0:
            ys.append(round(y1, 1))
    return sorted(set(ys))


def svg_text_stats(docdir: Path, page: int) -> tuple[int, list[float]]:
    svg = docdir / "rhwp_svg_cur" / f"source_{page:03d}.svg"
    if not svg.exists():
        return 0, []
    ys: list[float] = []
    for y_raw, body in TEXT_RE.findall(svg.read_text(encoding="utf-8", errors="ignore")):
        text = TAG_RE.sub("", body).strip()
        if text:
            ys.append(round(float(y_raw), 1))
    return len(ys), sorted(set(ys))


def svg_font_stats(docdir: Path, page: int) -> dict[str, list[tuple[str, int]]]:
    svg = docdir / "rhwp_svg_cur" / f"source_{page:03d}.svg"
    if not svg.exists():
        return {}
    text = svg.read_text(encoding="utf-8", errors="ignore")
    return {
        "font_size": collections.Counter(FONT_SIZE_RE.findall(text)).most_common(4),
        "font_family": collections.Counter(FONT_FAMILY_RE.findall(text)).most_common(2),
        "font_weight": collections.Counter(FONT_WEIGHT_RE.findall(text)).most_common(4),
    }


def local_font_hint(font_stats: dict[str, list[tuple[str, int]]]) -> str | None:
    families = font_stats.get("font_family") or []
    if not families:
        return None
    primary = families[0][0].split(",")[0].strip().strip("'").strip('"')
    if primary in {"맑은 고딕", "Malgun Gothic"}:
        mac_candidates = [
            Path("/Library/Fonts/Malgun Gothic.ttf"),
            Path("/Library/Fonts/malgun.ttf"),
            Path.home() / "Library/Fonts/Malgun Gothic.ttf",
            Path.home() / "Library/Fonts/malgun.ttf",
        ]
        if not any(path.exists() for path in mac_candidates):
            return "primary Malgun font not found locally; browser/PDF fallback may be thinner"
    return None


def parse_pages(raw: str) -> list[int]:
    pages: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_raw, end_raw = part.split("-", 1)
            start = int(start_raw)
            end = int(end_raw)
            step = 1 if end >= start else -1
            pages.extend(range(start, end + step, step))
        else:
            pages.append(int(part))
    return pages


def row_height_px(cells: list[Cell]) -> dict[int, float]:
    heights: dict[int, float] = {}
    for cell in cells:
        if cell.row_span != 1:
            continue
        heights[cell.row] = max(heights.get(cell.row, 0.0), hu_to_px(cell.height_hu))
    return heights


def image_dark_pixels(path: Path, threshold: int) -> tuple[int, tuple[int, int]]:
    try:
        from PIL import Image
    except ImportError as exc:
        raise SystemExit("Pillow is required for --font-audit") from exc
    with Image.open(path) as image:
        rgba = image.convert("RGBA")
        width, height = rgba.size
        dark = 0
        for red, green, blue, alpha in rgba.getdata():
            if alpha == 0:
                continue
            # Luma keeps colored borders out of the "black text ink" signal
            # unless they are also visually dark.
            luma = 0.2126 * red + 0.7152 * green + 0.0722 * blue
            if luma < threshold:
                dark += 1
    return dark, (width, height)


def svg_size(svg: Path) -> tuple[float, float]:
    head = svg.read_text(encoding="utf-8", errors="ignore")[:1600]
    match = re.search(r'<svg[^>]*\bwidth="([0-9.]+)"[^>]*\bheight="([0-9.]+)"', head)
    if match:
        return float(match.group(1)), float(match.group(2))
    match = re.search(r'<svg[^>]*\bviewBox="[0-9.]+ [0-9.]+ ([0-9.]+) ([0-9.]+)"', head)
    if match:
        return float(match.group(1)), float(match.group(2))
    return 794.0, 1123.0


def raster_svg(svg: Path, png: Path) -> None:
    width, height = svg_size(svg)
    target_w = 1400
    target_h = max(1, round(height * target_w / width))
    page_html = (
        "<!doctype html><meta charset='utf-8'>"
        "<style>html,body{margin:0;background:white}"
        "body{display:inline-block}"
        "img{display:block;width:100%;height:auto}</style>"
        f"<img id='page' src='file://{svg.resolve()}' style='width:{target_w}px'>"
    )
    js = r"""
const { chromium } = require('playwright');
const [html, png, w, h] = process.argv.slice(1);
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    viewport: { width: Number(w), height: Number(h) },
    deviceScaleFactor: 1,
  });
  await page.goto('file://' + html, { waitUntil: 'networkidle' });
  await page.locator('#page').evaluate(img => img.decode ? img.decode() : Promise.resolve());
  const size = await page.evaluate(() => ({
    width: Math.ceil(document.documentElement.scrollWidth),
    height: Math.ceil(document.documentElement.scrollHeight),
  }));
  await page.setViewportSize({
    width: Math.max(Number(w), size.width),
    height: Math.max(Number(h), size.height),
  });
  await page.screenshot({ path: png, fullPage: true });
  await browser.close();
})().catch(err => { console.error(err); process.exit(1); });
"""
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as handle:
        handle.write(page_html)
        html_path = handle.name
    try:
        result = subprocess.run(
            ["node", "-e", js, html_path, str(png), str(target_w), str(target_h)],
            check=False,
            cwd=Path(__file__).resolve().parents[1],
            text=True,
            capture_output=True,
        )
        if result.returncode != 0 or not png.exists():
            raise SystemExit(f"Chromium SVG raster failed for {svg}: {result.stderr[-1200:]}")
    finally:
        Path(html_path).unlink(missing_ok=True)


def rhwp_png_path(docdir: Path, page: int) -> Path | None:
    candidates = [
        docdir / f"rhwp_review_p-{page}.png",
        docdir / f"rhwp_review_p-{page:02d}.png",
        docdir / f"rhwp_p-{page}.png",
        docdir / f"rhwp_p-{page:02d}.png",
        docdir / "look" / f"page-{page:02d}.png",
        docdir / "look" / f"page-{page}.png",
    ]
    return next((path for path in candidates if path.exists()), None)


def hancom_png_path(docdir: Path, page: int) -> Path:
    candidates = [
        docdir / f"hancom_p-{page}.png",
        docdir / f"hancom_p-{page:02d}.png",
    ]
    return next((path for path in candidates if path.exists()), candidates[0])


def print_font_audit(docdir: Path, pages: list[int], threshold: int) -> None:
    print("font_audit:")
    for page in pages:
        hancom = hancom_png_path(docdir, page)
        rhwp = rhwp_png_path(docdir, page)
        if not hancom.exists() or rhwp is None:
            print(
                f"  p{page:02d}: missing_images "
                f"hancom={hancom.exists()} rhwp={rhwp is not None}"
            )
            continue
        hancom_dark, hancom_size = image_dark_pixels(hancom, threshold)
        rhwp_dark, rhwp_size = image_dark_pixels(rhwp, threshold)
        ratio = rhwp_dark / hancom_dark if hancom_dark else math.nan
        font_stats = svg_font_stats(docdir, page)
        family = (font_stats.get("font_family") or [("", 0)])[0][0]
        weights = font_stats.get("font_weight", [])
        sizes = font_stats.get("font_size", [])
        print(
            f"  p{page:02d}: "
            f"hancom_dark={hancom_dark} rhwp_dark={rhwp_dark} "
            f"ratio={ratio:.2f} "
            f"hancom_size={hancom_size[0]}x{hancom_size[1]} "
            f"rhwp_size={rhwp_size[0]}x{rhwp_size[1]} "
            f"font_family={family!r} font_size={sizes[:2]} "
            f"font_weight={weights[:2]}"
        )
        hint = local_font_hint(font_stats)
        if hint:
            print(f"    font_hint={hint}")


def source_svg_path(docdir: Path, page: int) -> Path | None:
    candidates = [
        docdir / "rhwp_svg_cur" / f"source_{page:03d}.svg",
        docdir / "rhwp_svg_fresh" / f"source_{page:03d}.svg",
    ]
    return next((path for path in candidates if path.exists()), None)


def write_weight_probe_svg(source: Path, dest: Path, weight: str) -> None:
    text = source.read_text(encoding="utf-8", errors="ignore")
    style = f"<style>text:not([font-weight]){{font-weight:{weight};}}</style>"
    patched = re.sub(r"(<svg\b[^>]*>)", r"\1" + style, text, count=1)
    dest.write_text(patched, encoding="utf-8")


def print_weight_probe(docdir: Path, pages: list[int], weight: str, threshold: int) -> None:
    outdir = docdir / f"font_probe_weight_{weight}"
    outdir.mkdir(exist_ok=True)
    print(f"weight_probe: weight={weight} outdir={outdir}")
    for page in pages:
        hancom = hancom_png_path(docdir, page)
        source_svg = source_svg_path(docdir, page)
        if not hancom.exists() or source_svg is None:
            print(
                f"  p{page:02d}: missing_inputs "
                f"hancom={hancom.exists()} svg={source_svg is not None}"
            )
            continue
        probe_svg = outdir / f"source_{page:03d}_weight_{weight}.svg"
        probe_png = outdir / f"source_{page:03d}_weight_{weight}.png"
        write_weight_probe_svg(source_svg, probe_svg, weight)
        raster_svg(probe_svg, probe_png)
        hancom_dark, _ = image_dark_pixels(hancom, threshold)
        probe_dark, probe_size = image_dark_pixels(probe_png, threshold)
        ratio = probe_dark / hancom_dark if hancom_dark else math.nan
        print(
            f"  p{page:02d}: hancom_dark={hancom_dark} "
            f"probe_dark={probe_dark} ratio={ratio:.2f} "
            f"probe_size={probe_size[0]}x{probe_size[1]} png={probe_png}"
        )


def summarize_fragment(fragment: Fragment, cells: list[Cell]) -> None:
    starts = [cell for cell in cells if fragment.start <= cell.row < fragment.end]
    carried = [
        cell
        for cell in cells
        if cell.row < fragment.start < cell.row + max(cell.row_span, 1)
    ]
    row_heights = row_height_px(cells)
    fragment_heights = [
        round(row_heights.get(row, 0.0), 1) for row in range(fragment.start, fragment.end)
    ]
    fragment_height_sum = round(sum(fragment_heights), 1)
    print(
        f"page {fragment.page:02d}: rows={fragment.start}..{fragment.end} "
        f"starts={len(starts)} carried={len(carried)} "
        f"saved_line_segs={sum(cell.line_segs for cell in starts)} "
        f"source_row_h_sum={fragment_height_sum}"
    )
    if fragment_heights:
        print(f"  source_row_h={fragment_heights}")
    if carried:
        print("  carried:")
        for cell in carried[:12]:
            print(
                f"    r{cell.row}c{cell.col} span={cell.row_span} "
                f"h={cell.height_hu} segs={cell.line_segs} text={cell.text!r}"
            )
    boundary_rows = sorted({fragment.start, fragment.end - 1})
    for row in boundary_rows:
        row_cells = [cell for cell in starts if cell.row == row]
        if row_cells:
            preview = ", ".join(
                f"c{cell.col}/rs{cell.row_span}/h{cell.height_hu}/segs{cell.line_segs}/{cell.text!r}"
                for cell in row_cells[:8]
            )
            print(f"  row {row}: {preview}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docdir", type=Path)
    parser.add_argument("--table-index", type=int, default=0)
    parser.add_argument(
        "--font-audit",
        action="store_true",
        help="also compare Hancom/RHWP dark-pixel density and SVG font metadata",
    )
    parser.add_argument(
        "--pages",
        default="1,5,11",
        help="page list/range for --font-audit, e.g. 1,5,11 or 1-11",
    )
    parser.add_argument(
        "--dark-threshold",
        type=int,
        default=96,
        help="luma threshold used by --font-audit dark-pixel counts",
    )
    parser.add_argument(
        "--weight-probe",
        metavar="WEIGHT",
        help="write/rasterize SVG copies with non-bold text forced to this CSS weight",
    )
    args = parser.parse_args()

    source = find_source(args.docdir)
    table, cells = parse_table(source, args.table_index)
    fragments = parse_fragments(args.docdir)
    print(f"source: {source}")
    print(
        "table: "
        f"repeatHeader={table.attrib.get('repeatHeader')} "
        f"pageBreak={table.attrib.get('pageBreak')} "
        f"rows={table.attrib.get('rowCnt')} cols={table.attrib.get('colCnt')} "
        f"cells={len(cells)}"
    )
    if not fragments:
        print("no dump_pages_current.txt-style fragments found")
        return 1
    for fragment in fragments:
        summarize_fragment(fragment, cells)
        bands = svg_horizontal_bands(args.docdir, fragment.page)
        if bands:
            print(f"  svg_h_bands={bands[:18]}")
        text_count, text_ys = svg_text_stats(args.docdir, fragment.page)
        if text_count:
            print(f"  svg_text_runs={text_count} svg_text_y={text_ys[:18]}")
        font_stats = svg_font_stats(args.docdir, fragment.page)
        if font_stats:
            print(
                "  svg_fonts="
                f"size={font_stats.get('font_size', [])} "
                f"weight={font_stats.get('font_weight', [])}"
            )
            hint = local_font_hint(font_stats)
            if hint:
                print(f"  font_hint={hint}")
    if args.font_audit:
        print_font_audit(args.docdir, parse_pages(args.pages), args.dark_threshold)
    if args.weight_probe:
        print_weight_probe(
            args.docdir,
            parse_pages(args.pages),
            args.weight_probe,
            args.dark_threshold,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
