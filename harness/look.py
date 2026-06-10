#!/usr/bin/env python3
"""look.py — vision-first rhwp fidelity loop.

The ONLY oracle is the Hancom render as an image. The ONLY truth is looking at
it. Page-count is a one-line tripwire, nothing more. No pt-gap, no dump-pages
metric — those are lossy proxies that go blind on shapes/boxes/tables/images
(exactly the cases that are hard).

Pipeline (host-only after the SVG export):
  1. (--export) docker rhwp export-svg          → rhwp_svg_cur/*.svg
  2. pdftoppm  hancom.pdf  → hancom_p-N.png      (vector PDF, real fonts)
  3. qlmanage  rhwp svg    → rhwp_p-N.png        (host, real Korean fonts —
                                                  NOT the font-starved raster
                                                  that made the old Gemini
                                                  pass over-flag everything)
  4. stitch    hancom | rhwp, one strip per page → look/page-NN.png
  5. tripwire  print rhwp vs Hancom page count
  6. (--gemini) Gemini-Flash second opinion per page on the real-font strips

Usage:
  look.py <docdir> [--export] [--gemini]
    <docdir>  e.g. /tmp/diff/report_form  (must contain source.hwpx + hancom.pdf)

After it runs, READ look/page-NN.png yourself for every page. The script's job
is to put Hancom and rhwp eye-to-eye at full legibility; the judgment is yours.
"""
import sys, os, re, glob, subprocess, json, base64, urllib.request, tempfile

RHWP = "/Users/jaehoshin/Desktop/mindlogic/factchat/worktree-rhwp-poc/rhwp"
DC = ["docker", "compose", "--env-file", ".env.docker", "run", "--rm",
      "-v", "/tmp/diff:/diff", "dev"]
WIDTH = 980  # px per page column; both engines normalized to this for honesty


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def export_svg(docdir, src):
    name = os.path.basename(docdir.rstrip("/"))
    rel = f"/diff/{name}/{os.path.basename(src)}"
    # clean stale SVGs first — export-svg does NOT delete old pages, so a doc
    # that shrank (e.g. 6→5 after a fix) would leave a phantom page-6 behind
    # and the page-count tripwire would lie.
    for old in glob.glob(os.path.join(docdir, "rhwp_svg_cur", "*.svg")):
        os.remove(old)
    print(f"[1] export-svg {rel} (docker, current binary)…")
    r = sh(DC + ["/app/target/release/rhwp", "export-svg", rel,
                 "-o", f"/diff/{name}/rhwp_svg_cur"], cwd=RHWP)
    if r.returncode:
        print(r.stderr[-800:]); sys.exit("export-svg failed")


def raster_hancom(docdir):
    pdf = os.path.join(docdir, "hancom.pdf")
    sh(["pdftoppm", "-r", "120", "-png", pdf, os.path.join(docdir, "hancom_p")])
    return sorted(glob.glob(os.path.join(docdir, "hancom_p-*.png")),
                  key=lambda p: int(re.search(r"-(\d+)\.png$", p).group(1)))


def raster_rhwp(docdir):
    svgs = sorted(glob.glob(os.path.join(docdir, "rhwp_svg_cur", "*.svg")),
                  key=lambda p: int(re.search(r"(\d+)\.svg$", p).group(1)))
    out = []
    for i, svg in enumerate(svgs, 1):
        png = os.path.join(docdir, f"rhwp_p-{i}.png")
        if raster_svg_chromium(svg, png):
            out.append(png)
            continue
        sh(["qlmanage", "-t", "-s", "1400", svg, "-o", docdir])
        produced = os.path.join(docdir, os.path.basename(svg) + ".png")
        if os.path.exists(produced):
            os.replace(produced, png); out.append(png)
    return out


def raster_svg_chromium(svg, png):
    """Rasterize SVG at its real page aspect ratio.

    macOS qlmanage creates square thumbnails for some SVGs, which makes the
    review board look bottom-clipped or vertically distorted. Chromium renders
    the SVG in a viewport matching width/height or viewBox.
    """
    text = open(svg, encoding="utf-8", errors="ignore").read(2048)
    m = re.search(r"<svg[^>]*\bwidth=\"([0-9.]+)\"[^>]*\bheight=\"([0-9.]+)\"", text)
    if not m:
        m = re.search(r"<svg[^>]*\bviewBox=\"[0-9.]+ [0-9.]+ ([0-9.]+) ([0-9.]+)\"", text)
    if not m:
        return False
    src_w, src_h = float(m.group(1)), float(m.group(2))
    if src_w <= 0 or src_h <= 0:
        return False
    target_w = 1400
    target_h = max(1, round(src_h * target_w / src_w))
    html = (
        "<!doctype html><meta charset='utf-8'>"
        "<style>html,body{margin:0;background:white}"
        "body{display:inline-block}"
        "img{display:block;width:100%;height:auto}</style>"
        f"<img id='page' src='file://{os.path.abspath(svg)}' style='width:{target_w}px'>"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(html)
        html_path = f.name
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
    try:
        r = sh(["node", "-e", js, html_path, png, str(target_w), str(target_h)], cwd=RHWP)
        return r.returncode == 0 and os.path.exists(png)
    finally:
        try:
            os.remove(html_path)
        except OSError:
            pass


def stitch(docdir, hancom, rhwp):
    from PIL import Image, ImageDraw, ImageFont
    os.makedirs(os.path.join(docdir, "look"), exist_ok=True)
    n = max(len(hancom), len(rhwp))
    written = []
    for i in range(n):
        cols = []
        for label, paths in (("HANCOM", hancom), ("rhwp", rhwp)):
            if i < len(paths):
                im = Image.open(paths[i]).convert("RGB")
                w, h = im.size
                im = im.resize((WIDTH, int(h * WIDTH / w)))
            else:
                im = Image.new("RGB", (WIDTH, 600), "#ffe0e0")  # missing page
                ImageDraw.Draw(im).text((20, 20), f"(no {label} page {i+1})",
                                        fill="red")
            cols.append((label, im))
        H = max(im.size[1] for _, im in cols) + 30
        strip = Image.new("RGB", (WIDTH * 2 + 12, H), "#888")
        for j, (label, im) in enumerate(cols):
            canvas = Image.new("RGB", (WIDTH, H), "white")
            canvas.paste(im, (0, 30))
            ImageDraw.Draw(canvas).text((8, 8), f"{label}  page {i+1}", fill="#000")
            strip.paste(canvas, (j * (WIDTH + 12), 0))
        p = os.path.join(docdir, "look", f"page-{i+1:02d}.png")
        strip.save(p); written.append(p)
    return written


def gemini(strip_paths):
    key = None
    for line in open("/Users/jaehoshin/Desktop/mindlogic/factchat/"
                     "mindlogic_factchat_server/.env"):
        m = re.match(r"GEMINI_API_KEY=(.+)", line.strip())
        if m: key = m.group(1).strip().strip('"\''); break
    if not key:
        print("no GEMINI_API_KEY"); return
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           f"gemini-flash-latest:generateContent?key={key}")
    prompt = ("Left = HANCOM (ground truth). Right = rhwp (candidate renderer) of "
              "the SAME page. Both use real fonts. List ONLY layout/spacing "
              "differences a human would notice: missing/extra vertical gaps "
              "(esp. around shaded section-header boxes), compressed line spacing, "
              "content that overflows the page, or content present in one but not "
              "the other. Ignore tiny sub-pixel glyph/anti-aliasing differences. "
              "Reply 'MATCH' if visually equivalent, else terse bullets.")
    for p in strip_paths:
        b64 = base64.b64encode(open(p, "rb").read()).decode()
        body = {"contents": [{"parts": [
            {"text": prompt},
            {"inline_data": {"mime_type": "image/png", "data": b64}}]}],
            "generationConfig": {"temperature": 1.0}}
        req = urllib.request.Request(url, json.dumps(body).encode(),
                                     {"Content-Type": "application/json"})
        try:
            r = json.load(urllib.request.urlopen(req, timeout=90))
            txt = r["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            txt = f"(gemini error: {e})"
        print(f"\n── {os.path.basename(p)} ──\n{txt}")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    docdir = os.path.abspath(sys.argv[1])
    src = next((os.path.join(docdir, f) for f in ("source.hwpx", "source.hwp")
                if os.path.exists(os.path.join(docdir, f))), None)
    if "--export" in sys.argv:
        export_svg(docdir, src)
    print("[2] raster Hancom…"); hancom = raster_hancom(docdir)
    print("[3] raster rhwp…"); rhwp = raster_rhwp(docdir)
    print("[4] stitch…"); strips = stitch(docdir, hancom, rhwp)
    flag = "  ⚠️ PAGE COUNT DIFFERS" if len(hancom) != len(rhwp) else "  ✓"
    print(f"\n[5] TRIPWIRE  Hancom={len(hancom)}  rhwp={len(rhwp)}{flag}")
    print("    look/  →  " + "  ".join(os.path.basename(s) for s in strips))
    print("    READ every page-NN.png yourself. That is the truth signal.")
    if "--gemini" in sys.argv:
        print("\n[6] Gemini second opinion (real-font strips):"); gemini(strips)


if __name__ == "__main__":
    main()
