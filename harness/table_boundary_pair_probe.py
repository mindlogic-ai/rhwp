#!/usr/bin/env python3
"""Compare long horizontal table-rule bands for Hancom:RHWP semantic page pairs."""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

import review_gallery
import table_boundary_probe


DIFF = Path("/tmp/diff")


def parse_pair(raw: str) -> tuple[int, int]:
    if ":" not in raw:
        raise argparse.ArgumentTypeError(f"expected HANCOM:RHWP page pair, got {raw!r}")
    left, right = raw.split(":", 1)
    return int(left), int(right)


def page_path(paths: list[Path], page: int) -> Path:
    idx = page - 1
    if idx < 0 or idx >= len(paths):
        raise SystemExit(f"missing page {page}")
    return paths[idx]


def print_gaps(label: str, bands: list[tuple[float, float, int]]) -> None:
    ys = [start for start, _, _ in bands]
    if len(ys) < 2:
        return
    print(f"{label}_gaps " + " ".join(f"{ys[i + 1] - ys[i]:.1f}" for i in range(len(ys) - 1)))


def probe(doc: str, hancom_page: int, rhwp_page: int, min_dark: int, min_width_ratio: float) -> None:
    docdir = DIFF / doc
    if not docdir.exists():
        raise SystemExit(f"missing docdir {docdir}")
    hancom_paths = review_gallery.raster_hancom(docdir)
    hancom = page_path(hancom_paths, hancom_page)

    svg_paths = review_gallery.svg_pages(docdir)
    svg = page_path(svg_paths, rhwp_page)
    rhwp_png = docdir / f"rhwp_pair_boundary_p-{rhwp_page}.png"
    review_gallery.raster_svg(svg, rhwp_png)
    _, svg_h = review_gallery.svg_size(svg)

    hancom_bands = table_boundary_probe.scale_bands(
        table_boundary_probe.horizontal_bands(hancom, min_dark, min_width_ratio),
        hancom,
        svg_h,
    )
    rhwp_bands = table_boundary_probe.scale_bands(
        table_boundary_probe.horizontal_bands(rhwp_png, min_dark, min_width_ratio),
        rhwp_png,
        svg_h,
    )

    print(f"doc={doc} hancom_page={hancom_page} rhwp_page={rhwp_page} svg_h={svg_h:.1f}")
    table_boundary_probe.print_bands("hancom", hancom_bands)
    print_gaps("hancom", hancom_bands)
    table_boundary_probe.print_bands("rhwp", rhwp_bands)
    print_gaps("rhwp", rhwp_bands)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("doc")
    parser.add_argument("--pair", required=True, type=parse_pair)
    parser.add_argument("--min-dark", type=int, default=260)
    parser.add_argument("--min-width-ratio", type=float, default=0.18)
    args = parser.parse_args()
    probe(args.doc, args.pair[0], args.pair[1], args.min_dark, args.min_width_ratio)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
