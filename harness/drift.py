#!/usr/bin/env python3
"""Objective fidelity metric — Hancom PDF text positions vs rhwp SVG text positions.

This REPLACES dump-pages' `used vs hwp_used` metric, which LIES on TopAndBottom
docs (counts page-anchored frames by vpos → phantom -300..-500px diffs). This
metric reads ACTUAL rendered glyph y-positions from both engines, so it cannot
be fooled by anchor accounting.

Per page (aligned by index until divergence):
  - line count (glyph rows)
  - median inter-line gap in pt
  - delta(rhwp - hancom)
Reports the FIRST page where the two engines structurally diverge — that localizes
where an extra/missing page creeps in.

Units: pdftotext -bbox emits PDF points (pt). rhwp SVG <text y> is px@96dpi;
pt = px * 0.75. Gaps are compared, so absolute page offset cancels.

Usage: drift.py <docdir>            # e.g. /tmp/diff/form_07_______________41KB
       drift.py <docdir> --json
"""
import sys, os, re, subprocess, json, statistics, glob

PX_TO_PT = 0.75
LINE_TOL_PT = 3.0  # words within this yMin band = same line


def hancom_lines_per_page(pdf):
    out = subprocess.run(["pdftotext", "-bbox", pdf, "-"],
                         capture_output=True, text=True).stdout
    pages, cur = [], None
    for line in out.splitlines():
        if re.search(r'<page\b', line):
            cur = []
            pages.append(cur)
            continue
        m = re.search(r'<word xMin="[\d.]+" yMin="([\d.]+)" xMax="[\d.]+" yMax="([\d.]+)"', line)
        if m and cur is not None:
            cur.append((float(m.group(1)) + float(m.group(2))) / 2.0)  # y-center
    return [collapse_lines(ys) for ys in pages]


def svg_lines_per_page(docdir):
    svgs = sorted(glob.glob(os.path.join(docdir, "rhwp_svg_cur", "*.svg")),
                  key=lambda p: re.sub(r'\d+', lambda m: m.group().zfill(6), p))
    out = []
    for sv in svgs:
        s = open(sv, encoding="utf-8", errors="replace").read()
        ys = [float(y) * PX_TO_PT for y in re.findall(r'<text[^>]*\by="([\d.]+)"', s)]
        out.append(collapse_lines(ys))
    return out


def collapse_lines(ys):
    """Group near-equal y values into distinct text lines; return sorted centers."""
    if not ys:
        return []
    ys = sorted(ys)
    lines, cur = [], [ys[0]]
    for y in ys[1:]:
        if y - cur[-1] <= LINE_TOL_PT:
            cur.append(y)
        else:
            lines.append(sum(cur) / len(cur))
            cur = [y]
    lines.append(sum(cur) / len(cur))
    return lines


def median_gap(lines):
    if len(lines) < 2:
        return 0.0
    gaps = [b - a for a, b in zip(lines, lines[1:]) if 0 < b - a < 200]
    return statistics.median(gaps) if gaps else 0.0


def main():
    docdir = sys.argv[1].rstrip("/")
    as_json = "--json" in sys.argv
    pdf = os.path.join(docdir, "hancom.pdf")
    if not os.path.exists(pdf):
        print(f"NO hancom.pdf in {docdir}", file=sys.stderr); sys.exit(2)
    hc = hancom_lines_per_page(pdf)
    rh = svg_lines_per_page(docdir)
    rows, first_div = [], None
    n = max(len(hc), len(rh))
    for i in range(n):
        h = hc[i] if i < len(hc) else []
        r = rh[i] if i < len(rh) else []
        hg, rg = median_gap(h), median_gap(r)
        diverge = (abs(len(h) - len(r)) > 2) or (abs(hg - rg) > 4 and h and r)
        if diverge and first_div is None:
            first_div = i + 1
        rows.append(dict(page=i + 1, h_lines=len(h), r_lines=len(r),
                         h_gap=round(hg, 1), r_gap=round(rg, 1),
                         gap_delta=round(rg - hg, 1)))
    result = dict(doc=os.path.basename(docdir), hancom_pages=len(hc), rhwp_pages=len(rh),
                  first_divergent_page=first_div, pages=rows)
    if as_json:
        print(json.dumps(result, ensure_ascii=False))
        return
    print(f"== {result['doc']}: hancom={len(hc)}p rhwp={len(rh)}p  first_divergence=p{first_div} ==")
    print(f"{'pg':>3} {'h_lines':>7} {'r_lines':>7} {'h_gap':>6} {'r_gap':>6} {'Δgap':>6}")
    for r in rows:
        flag = "  <-- DIVERGES" if r["page"] == first_div else ""
        print(f"{r['page']:>3} {r['h_lines']:>7} {r['r_lines']:>7} {r['h_gap']:>6} {r['r_gap']:>6} {r['gap_delta']:>6}{flag}")


if __name__ == "__main__":
    main()
