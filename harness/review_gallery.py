#!/usr/bin/env python3
"""Build a non-cropping visual review gallery for fidelity work.

This is the tracked replacement for one-off /tmp/diff/_gallery3.py scripts.
It intentionally uses the same truth model as harness/look.py:

  left  = Hancom PDF raster, oracle
  right = current rhwp SVG raster, candidate

The generated HTML labels git HEAD and dirty state so stale boards are obvious.
By default every page is shown. Use --max-pages only when the user explicitly
wants to skip huge documents.

Usage:
  python3 harness/review_gallery.py /tmp/diff/_review_live wc35_15pg --export-current
  python3 harness/review_gallery.py /tmp/diff/_review_live --all --max-pages 12
"""
from __future__ import annotations

import argparse
import base64
import glob
import html
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw


RHWP = Path(__file__).resolve().parents[1]
DIFF = Path("/tmp/diff")
COLUMN_WIDTH = 900
GAP = 12
LABEL_H = 30
SVG_OPEN_RE = re.compile(r"(<svg\b[^>]*>)", re.I)
FONT_FAMILY_RE = re.compile(r'font-family="([^"]+)"')
FONT_ENTRY_RE = re.compile(
    r"\{\s*name:\s*'([^']+)'\s*,\s*file:\s*'([^']+)'\s*(?:,\s*format:\s*'([^']+)')?",
    re.S,
)
_FONT_FACE_CSS_CACHE: dict[tuple[str, ...], str] = {}


def run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def git_value(args: list[str], fallback: str = "unknown") -> str:
    result = run(["git", *args], cwd=RHWP)
    value = result.stdout.strip()
    return value or fallback


def natural_key(path: Path) -> int:
    match = re.search(r"(\d+)(?=\.[^.]+$)", path.name)
    return int(match.group(1)) if match else 1


def svg_pages(docdir: Path, subdir: str = "rhwp_svg_cur") -> list[Path]:
    return sorted((docdir / subdir).glob("*.svg"), key=natural_key)


def source_path(docdir: Path) -> Path | None:
    for name in ("source.hwpx", "source.hwp", "source_converted.hwpx"):
        path = docdir / name
        if path.exists():
            return path
    return None


def export_current(docdir: Path) -> None:
    src = source_path(docdir)
    if src is None:
        raise SystemExit(f"no source.hwpx/source.hwp in {docdir}")
    out = docdir / "rhwp_svg_cur"
    out.mkdir(exist_ok=True)
    for old in out.glob("*.svg"):
        old.unlink()
    rel_src = f"/diff/{docdir.name}/{src.name}"
    rel_out = f"/diff/{docdir.name}/rhwp_svg_cur"
    cmd = [
        "docker",
        "compose",
        "--env-file",
        ".env.docker",
        "run",
        "--rm",
        "-v",
        "/tmp/diff:/diff",
        "dev",
        os.environ.get("RHWP_BIN", "/app/target/release/rhwp"),
        "export-svg",
        rel_src,
        "-o",
        rel_out,
    ]
    result = run(cmd, cwd=RHWP)
    if result.returncode != 0:
        sys.stderr.write(result.stderr[-1200:])
        raise SystemExit(f"export-svg failed for {docdir.name}")


def raster_hancom(docdir: Path) -> list[Path]:
    pdf = docdir / "hancom.pdf"
    if not pdf.exists():
        return []
    existing = sorted(docdir.glob("hancom_p-*.png"), key=natural_key)
    if existing:
        return existing
    result = run(["pdftoppm", "-r", "120", "-png", str(pdf), str(docdir / "hancom_p")])
    if result.returncode != 0:
        sys.stderr.write(result.stderr[-1200:])
        raise SystemExit(f"pdftoppm failed for {docdir.name}")
    return sorted(docdir.glob("hancom_p-*.png"), key=natural_key)


def svg_size(svg: Path) -> tuple[float, float]:
    head = svg.read_text(encoding="utf-8", errors="ignore")[:1600]
    match = re.search(r'<svg[^>]*\bwidth="([0-9.]+)"[^>]*\bheight="([0-9.]+)"', head)
    if match:
        return float(match.group(1)), float(match.group(2))
    match = re.search(r'<svg[^>]*\bviewBox="[0-9.]+ [0-9.]+ ([0-9.]+) ([0-9.]+)"', head)
    if match:
        return float(match.group(1)), float(match.group(2))
    return 794.0, 1123.0


def doc_has_landscape_svg(docdir: Path) -> bool:
    for svg in svg_pages(docdir):
        width, height = svg_size(svg)
        if width > height:
            return True
    return False


def font_mime(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".woff2":
        return "font/woff2"
    if suffix == ".woff":
        return "font/woff"
    if suffix == ".ttf":
        return "font/ttf"
    if suffix == ".otf":
        return "font/otf"
    return "application/octet-stream"


def font_format(path: Path, declared: str | None = None) -> str:
    if declared:
        return declared
    suffix = path.suffix.lower()
    if suffix == ".woff2":
        return "woff2"
    if suffix == ".woff":
        return "woff"
    if suffix == ".ttf":
        return "truetype"
    if suffix == ".otf":
        return "opentype"
    return "opentype"


def css_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def font_registry() -> dict[str, tuple[Path, str | None]]:
    source = RHWP / "rhwp-studio" / "src" / "core" / "font-loader.ts"
    text = source.read_text(encoding="utf-8", errors="ignore")
    registry: dict[str, tuple[Path, str | None]] = {}
    for name, file_name, declared_format in FONT_ENTRY_RE.findall(text):
        if not file_name.startswith("fonts/"):
            continue
        path = RHWP / "web" / file_name
        if path.exists():
            registry[name] = (path, declared_format or None)
    return registry


def svg_font_families(svg_text: str) -> set[str]:
    families: set[str] = set()
    for match in FONT_FAMILY_RE.finditer(svg_text):
        value = html.unescape(match.group(1))
        for part in value.split(","):
            family = part.strip().strip("'\"")
            if family and family not in {"serif", "sans-serif", "monospace"}:
                families.add(family)
    return families


def review_font_css(families: set[str]) -> str:
    available = font_registry()
    matched = tuple(sorted(family for family in families if family in available))
    if not matched:
        return ""
    cached = _FONT_FACE_CSS_CACHE.get(matched)
    if cached is not None:
        return cached
    lines: list[str] = []
    for family in matched:
        path, declared_format = available[family]
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        lines.append(
            "@font-face{"
            f'font-family:"{css_escape(family)}";'
            f'src:url("data:{font_mime(path)};base64,{data}") format("{font_format(path, declared_format)}");'
            "font-style:normal;"
            "font-display:block;"
            "}"
        )
    css = "\n".join(lines)
    _FONT_FACE_CSS_CACHE[matched] = css
    return css


def inject_review_fonts(svg: Path, temp_dir: Path) -> Path:
    svg_text = svg.read_text(encoding="utf-8", errors="ignore")
    css = review_font_css(svg_font_families(svg_text))
    if not css:
        return svg
    style = f"<style><![CDATA[\n{css}\n]]></style>\n"
    if "<defs>" in svg_text:
        patched = svg_text.replace("<defs>", f"<defs>{style}", 1)
    else:
        patched = SVG_OPEN_RE.sub(lambda match: match.group(1) + f"\n<defs>{style}</defs>\n", svg_text, count=1)
    temp_svg = temp_dir / svg.name
    temp_svg.write_text(patched, encoding="utf-8")
    return temp_svg


def raster_svg(svg: Path, png: Path) -> None:
    width, height = svg_size(svg)
    target_w = 1400
    target_h = max(1, round(height * target_w / width))
    page_html = (
        "<!doctype html><meta charset='utf-8'>"
        "<style>html,body{margin:0;background:white}"
        "body{display:inline-block}"
        "img{display:block;width:100%;height:auto}</style>"
        "<img id='page' src='__SVG_URL__' style='width:__TARGET_W__px'>"
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
    with tempfile.TemporaryDirectory(prefix="rhwp-review-svg-") as temp_name:
        temp_dir = Path(temp_name)
        raster_svg_path = inject_review_fonts(svg, temp_dir)
        page_html = page_html.replace("__SVG_URL__", f"file://{raster_svg_path.resolve()}").replace(
            "__TARGET_W__", str(target_w)
        )
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as handle:
            handle.write(page_html)
            html_path = handle.name
        try:
            result = run(["node", "-e", js, html_path, str(png), str(target_w), str(target_h)], cwd=RHWP)
            if result.returncode != 0 or not png.exists():
                sys.stderr.write(result.stderr[-1200:])
                raise SystemExit(f"Chromium SVG raster failed for {svg}")
        finally:
            try:
                os.remove(html_path)
            except OSError:
                pass


def raster_rhwp(docdir: Path) -> list[Path]:
    pages = svg_pages(docdir)
    out: list[Path] = []
    for i, svg in enumerate(pages, 1):
        png = docdir / f"rhwp_review_p-{i}.png"
        raster_svg(svg, png)
        out.append(png)
    return out


def fit_width(image: Image.Image, width: int) -> Image.Image:
    src_w, src_h = image.size
    return image.resize((width, max(1, round(src_h * width / src_w))))


def missing_page(label: str, page: int) -> Image.Image:
    image = Image.new("RGB", (COLUMN_WIDTH, 500), "#ffe0e0")
    ImageDraw.Draw(image).text((20, 20), f"(no {label} page {page})", fill="red")
    return image


def stitch_doc(outdir: Path, docdir: Path, hancom: list[Path], rhwp: list[Path], max_pages: int) -> list[str]:
    doc_out = outdir / docdir.name
    doc_out.mkdir(parents=True, exist_ok=True)
    page_count = max(len(hancom), len(rhwp))
    shown = page_count if max_pages <= 0 else min(page_count, max_pages)
    rows: list[str] = []
    for i in range(shown):
        images: list[tuple[str, Image.Image]] = []
        for label, paths in (("HANCOM", hancom), ("RHWP current", rhwp)):
            if i < len(paths) and paths[i].exists():
                image = fit_width(Image.open(paths[i]).convert("RGB"), COLUMN_WIDTH)
            else:
                image = missing_page(label, i + 1)
            images.append((label, image))
        height = max(image.height for _, image in images) + LABEL_H
        strip = Image.new("RGB", (COLUMN_WIDTH * 2 + GAP, height), "#888")
        for col, (label, image) in enumerate(images):
            canvas = Image.new("RGB", (COLUMN_WIDTH, height), "white")
            canvas.paste(image, (0, LABEL_H))
            ImageDraw.Draw(canvas).text((8, 8), f"{label} page {i + 1}", fill="#000")
            strip.paste(canvas, (col * (COLUMN_WIDTH + GAP), 0))
        rel = f"{docdir.name}/page-{i + 1:02d}.png"
        strip.save(outdir / rel)
        rows.append(rel)
    return rows


def build_doc(outdir: Path, docdir: Path, max_pages: int, export: bool) -> tuple[str, int, int, int, list[str]]:
    if export:
        export_current(docdir)
    hancom = raster_hancom(docdir)
    rhwp = raster_rhwp(docdir)
    rows = stitch_doc(outdir, docdir, hancom, rhwp, max_pages)
    return docdir.name, len(hancom), len(rhwp), max(len(hancom), len(rhwp)), rows


def write_doc_html(outdir: Path, name: str, hancom_pages: int, rhwp_pages: int, total_pages: int, rows: list[str]) -> None:
    truncated = ""
    if len(rows) < total_pages:
        truncated = f" <small style='color:#fa0'>(showing {len(rows)}/{total_pages} pages)</small>"
    body = "\n".join(
        f'<h3>page {i + 1}</h3><a href="{html.escape(Path(row).name)}">'
        f'<img src="{html.escape(Path(row).name)}"></a>'
        for i, row in enumerate(rows)
    )
    page = f"""<!doctype html><meta charset="utf-8"><title>{html.escape(name)}</title>
<style>
body{{font-family:sans-serif;margin:0;background:#222;color:#eee}}
h1,h3,p{{padding:6px 12px}} a{{color:#8cf}} img{{display:block;width:100%;height:auto}}
</style>
<h1>{html.escape(name)} <small>Hancom={hancom_pages}p RHWP={rhwp_pages}p</small>{truncated}</h1>
<p><a href="../index.html">index</a> | Click any strip to open the raw full-height PNG.</p>
{body}
"""
    (outdir / name / "index.html").write_text(page, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("out_dir")
    parser.add_argument("docs", nargs="*")
    parser.add_argument("--all", action="store_true", help="include every /tmp/diff doc with source + Hancom PDF")
    parser.add_argument("--export-current", action="store_true", help="regenerate rhwp_svg_cur with the current binary")
    parser.add_argument("--max-pages", type=int, default=0, help="0 means all pages")
    parser.add_argument("--skip-landscape", action="store_true", help="skip docs whose current RHWP SVG pages are landscape")
    args = parser.parse_args()

    outdir = Path(args.out_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    if args.all:
        docs = sorted(
            d.name for d in DIFF.iterdir()
            if d.is_dir() and (d / "hancom.pdf").exists() and source_path(d) is not None
        )
    else:
        docs = args.docs
    if not docs:
        raise SystemExit("no docs requested")

    head = git_value(["rev-parse", "--short", "HEAD"])
    dirty = "yes" if git_value(["status", "--porcelain"], "") else "no"
    generated_at = datetime.now().isoformat(timespec="seconds")

    results = []
    skipped = []
    for doc in docs:
        docdir = DIFF / doc
        if not docdir.is_dir():
            print(f"skip missing doc: {doc}", file=sys.stderr)
            continue
        export_for_build = args.export_current
        if args.skip_landscape and args.export_current:
            export_current(docdir)
            export_for_build = False
        if args.skip_landscape and doc_has_landscape_svg(docdir):
            print(f"skip landscape doc: {doc}", file=sys.stderr)
            skipped.append(doc)
            continue
        print(f"building {doc}...", flush=True)
        name, hancom_pages, rhwp_pages, total_pages, rows = build_doc(
            outdir, docdir, args.max_pages, export_for_build
        )
        write_doc_html(outdir, name, hancom_pages, rhwp_pages, total_pages, rows)
        results.append((name, hancom_pages, rhwp_pages, total_pages, len(rows)))

    rows_html = []
    for name, hancom_pages, rhwp_pages, total_pages, shown_pages in results:
        match = "yes" if hancom_pages == rhwp_pages else "no"
        shown = f"{shown_pages}/{total_pages}"
        rows_html.append(
            f'<tr><td><a href="{html.escape(name)}/index.html">{html.escape(name)}</a></td>'
            f"<td>{hancom_pages}</td><td>{rhwp_pages}</td><td>{match}</td><td>{shown}</td></tr>"
        )
    skipped_html = ""
    if skipped:
        skipped_html = "<h2>Skipped landscape docs</h2><ul>" + "".join(
            f"<li>{html.escape(name)}</li>" for name in skipped
        ) + "</ul>"
    index = f"""<!doctype html><meta charset="utf-8"><title>RHWP review gallery</title>
<style>
body{{font-family:sans-serif;margin:24px;background:#1a1a1a;color:#eee}}
table{{border-collapse:collapse;width:100%}} td,th{{border:1px solid #444;padding:6px 10px;text-align:left}}
th{{background:#333}} a{{color:#8cf}} tr:hover{{background:#2a2a2a}}
</style>
<h1>RHWP review gallery</h1>
<p>Generated {html.escape(generated_at)} from git HEAD <code>{html.escape(head)}</code>; dirty worktree: <code>{dirty}</code>.</p>
<p>Left = Hancom oracle. Right = current RHWP. Strips are full-height PNGs; no CSS crop is applied.</p>
{skipped_html}
<table><tr><th>doc</th><th>Hancom</th><th>RHWP</th><th>page match</th><th>shown</th></tr>
{''.join(rows_html)}
</table>
"""
    (outdir / "index.html").write_text(index, encoding="utf-8")
    print(f"\nGALLERY: {outdir / 'index.html'} ({len(results)} docs)")


if __name__ == "__main__":
    main()
