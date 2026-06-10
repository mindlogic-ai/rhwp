#!/usr/bin/env python3
"""Compare raster backends for one RHWP page against Hancom.

Late-stage table/text drift can come from three different layers:

1. layout/render-tree geometry;
2. SVG text/line emission;
3. the raster backend used to turn RHWP output into pixels.

This probe keeps Hancom as oracle and compares the current browser-rasterized
SVG candidate with an optional native-Skia PNG candidate when a native-Skia
binary is available. It is read-only unless `--native` writes PNGs under the
requested output directory.
"""
from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

import review_gallery
from svg_geometry_probe import (
    hancom_png_path,
    parse_ref,
    rhwp_png_path,
    rhwp_svg_path,
    svg_size,
)
from svg_region_probe import Region, parse_region, svg_to_pixel_box


RHWP = Path(__file__).resolve().parents[1]
DIFF = Path("/tmp/diff")


@dataclass(frozen=True)
class Candidate:
    name: str
    path: Path
    note: str = ""


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=RHWP, capture_output=True, text=True)


def fit_to_match(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    if image.size == size:
        return image
    return image.resize(size)


def luma(red: int, green: int, blue: int) -> float:
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def luma_series(image: Image.Image) -> list[float]:
    return [luma(red, green, blue) for red, green, blue in image.getdata()]


def dark_counts(image: Image.Image, thresholds: list[int]) -> dict[int, int]:
    values = luma_series(image)
    return {threshold: sum(1 for value in values if value < threshold) for threshold in thresholds}


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = round((len(ordered) - 1) * pct)
    return ordered[index]


def luma_summary(image: Image.Image) -> tuple[float, float, float, float]:
    values = luma_series(image)
    return (
        percentile(values, 0.01),
        percentile(values, 0.05),
        percentile(values, 0.10),
        sum(values) / max(1, len(values)),
    )


def metrics(left: Image.Image, right: Image.Image, dark_threshold: int, nonwhite_threshold: int) -> tuple[float, int, int, float]:
    candidate = fit_to_match(right, left.size)
    diff = ImageChops.difference(left, candidate)
    stat = ImageStat.Stat(diff)
    mean = sum(stat.mean) / 3.0
    dark = 0
    nonwhite = 0
    luma_total = 0.0
    for red, green, blue in candidate.getdata():
        value = luma(red, green, blue)
        luma_total += value
        if value < dark_threshold:
            dark += 1
        if max(255 - red, 255 - green, 255 - blue) > nonwhite_threshold:
            nonwhite += 1
    return mean, dark, nonwhite, luma_total / max(1, candidate.width * candidate.height)


def crop(path: Path, box: tuple[int, int, int, int]) -> Image.Image:
    with Image.open(path) as opened:
        return opened.convert("RGB").crop(box)


def full_image(path: Path) -> Image.Image:
    with Image.open(path) as opened:
        return opened.convert("RGB")


def parse_thresholds(value: str) -> list[int]:
    thresholds = []
    for piece in value.split(","):
        piece = piece.strip()
        if not piece:
            continue
        threshold = int(piece)
        if threshold < 0 or threshold > 255:
            raise argparse.ArgumentTypeError(f"threshold must be 0..255: {threshold}")
        thresholds.append(threshold)
    if not thresholds:
        raise argparse.ArgumentTypeError("at least one threshold is required")
    return thresholds


def native_png_candidate(
    ref_doc: str,
    page: int,
    out_dir: Path,
    font_paths: list[Path],
) -> Candidate:
    docdir = DIFF / ref_doc
    src = review_gallery.source_path(docdir)
    if src is None:
        return Candidate("native-skia", Path(), "missing source")
    out_dir.mkdir(parents=True, exist_ok=True)
    rel_src = f"/diff/{ref_doc}/{src.name}"
    rel_out = f"/diff/{out_dir.relative_to(DIFF)}"
    cmd = [
        "docker",
        "compose",
        "--env-file",
        ".env.docker",
        "run",
        "--rm",
        "-v",
        "/tmp/diff:/diff",
    ]
    for font_path in font_paths:
        if font_path.is_absolute():
            cmd.extend(["-v", f"{font_path}:{font_path}:ro"])
    cmd.extend(
        [
            "dev",
            "/app/target/release/rhwp",
            "export-png",
            rel_src,
            "-o",
            rel_out,
            "-p",
            str(page - 1),
        ]
    )
    for font_path in font_paths:
        cmd.extend(["--font-path", str(font_path)])
    result = run(cmd)
    output_lines = (result.stderr + "\n" + result.stdout).strip().splitlines()
    if result.returncode != 0:
        return Candidate("native-skia", Path(), output_lines[-1] if output_lines else "native export failed")
    candidates = sorted(out_dir.glob("*.png"))
    if not candidates:
        note = output_lines[-1] if output_lines else "native export wrote no PNG"
        return Candidate("native-skia", Path(), note)
    note = ""
    if font_paths:
        note = "font_paths=" + ",".join(str(path) for path in font_paths)
    return Candidate("native-skia", candidates[-1], note)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ref", type=parse_ref, help="DOC:PAGE")
    parser.add_argument("--region", action="append", type=parse_region, default=[])
    parser.add_argument("--export-current", action="store_true")
    parser.add_argument("--native", action="store_true", help="try native-Skia export-png via Docker")
    parser.add_argument(
        "--native-font-path",
        action="append",
        type=Path,
        default=[],
        help="pass --font-path to native-Skia export-png; may be repeated",
    )
    parser.add_argument("--out-dir", type=Path, default=DIFF / "_raster_backend_probe")
    parser.add_argument("--dark-threshold", type=int, default=96)
    parser.add_argument("--nonwhite-threshold", type=int, default=8)
    parser.add_argument(
        "--threshold-sweep",
        action="store_true",
        help="print Hancom/candidate dark-pixel counts across luma thresholds",
    )
    parser.add_argument(
        "--sweep-thresholds",
        type=parse_thresholds,
        default=parse_thresholds("64,96,128,160,192,224,240"),
        help="comma-separated luma thresholds for --threshold-sweep",
    )
    args = parser.parse_args()

    docdir = DIFF / args.ref.doc
    if args.export_current:
        review_gallery.export_current(docdir)

    svg_path = rhwp_svg_path(args.ref)
    svg_w, svg_h = svg_size(svg_path.read_text(encoding="utf-8", errors="ignore"))
    hancom = hancom_png_path(args.ref)
    browser_svg = rhwp_png_path(args.ref)
    candidates = [Candidate("browser-svg", browser_svg)]
    if args.native:
        candidates.append(
            native_png_candidate(
                args.ref.doc,
                args.ref.page,
                args.out_dir / args.ref.doc,
                args.native_font_path,
            )
        )

    regions = args.region or [Region("full", 0.0, 0.0, svg_w, svg_h)]
    print("doc\tpage\tregion\tcandidate\tmean_diff\tdark\tnonwhite\tmean_luma\tnote\tpng")
    for region in regions:
        with Image.open(hancom) as opened:
            hancom_image = opened.convert("RGB")
        box = svg_to_pixel_box(region, hancom_image, svg_w, svg_h)
        left = crop(hancom, box)
        for candidate in candidates:
            if not candidate.path.is_file():
                print(
                    f"{args.ref.doc}\t{args.ref.page}\t{region.name}\t{candidate.name}\t"
                    f"\t\t\t\t{candidate.note}\t"
                )
                continue
            right_full = full_image(candidate.path)
            cbox = svg_to_pixel_box(region, right_full, svg_w, svg_h)
            right = right_full.crop(cbox)
            mean, dark, nonwhite, luma = metrics(
                left,
                right,
                args.dark_threshold,
                args.nonwhite_threshold,
            )
            print(
                f"{args.ref.doc}\t{args.ref.page}\t{region.name}\t{candidate.name}\t"
                f"{mean:.2f}\t{dark}\t{nonwhite}\t{luma:.1f}\t{candidate.note}\t{candidate.path}"
            )
            if args.threshold_sweep:
                hancom_counts = dark_counts(left, args.sweep_thresholds)
                candidate_counts = dark_counts(right, args.sweep_thresholds)
                hancom_l01, hancom_l05, hancom_l10, hancom_avg = luma_summary(left)
                candidate_l01, candidate_l05, candidate_l10, candidate_avg = luma_summary(right)
                print(
                    "# sweep\t"
                    f"region={region.name}\tcandidate={candidate.name}\t"
                    f"hancom_luma=p01:{hancom_l01:.1f},p05:{hancom_l05:.1f},p10:{hancom_l10:.1f},avg:{hancom_avg:.1f}\t"
                    f"candidate_luma=p01:{candidate_l01:.1f},p05:{candidate_l05:.1f},p10:{candidate_l10:.1f},avg:{candidate_avg:.1f}"
                )
                for threshold in args.sweep_thresholds:
                    hancom_dark = hancom_counts[threshold]
                    candidate_dark = candidate_counts[threshold]
                    ratio = candidate_dark / hancom_dark if hancom_dark else 0.0
                    print(
                        "# sweep\t"
                        f"threshold={threshold}\thancom_dark={hancom_dark}\t"
                        f"candidate_dark={candidate_dark}\tratio={ratio:.3f}"
                    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
