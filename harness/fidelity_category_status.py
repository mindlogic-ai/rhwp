#!/usr/bin/env python3
"""Refresh category-level RHWP fidelity status from current local evidence.

This is deliberately lightweight. It does not decide that a renderer bug is
fixed; it gives the next long run a current source/oracle/page-count/gallery
map so work does not start from stale review boards.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageChops, ImageStat


RHWP = Path(__file__).resolve().parents[1]
DIFF = Path("/tmp/diff")
DEFAULT_DOCS = [
    "wild_02_paper_fig_10MB",
    "overseas_training",
    "meeting_summary",
    "accountability_eval",
    "15_3740450_research_admin_innovation_meeting_template",
    "20_3727659_resume_2605_ai",
    "report_form",
]


@dataclass
class DocStatus:
    doc: str
    source: str
    hancom_pages: int | None
    rhwp_pages: int | None
    dump_ok: bool
    gallery: str
    gallery_ok: bool | None
    visual_worst_page: int | None
    visual_mean_diff: float | None
    notes: str


def run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=RHWP, capture_output=True, text=True, **kwargs)


def source_path(doc: str) -> Path | None:
    docdir = DIFF / doc
    for name in ("source.hwpx", "source.hwp", "source_converted.hwpx"):
        path = docdir / name
        if path.exists():
            return path
    return None


def hancom_page_count(doc: str) -> int | None:
    pages = sorted((DIFF / doc).glob("hancom_p-*.png"))
    if pages:
        return len(pages)
    index = DIFF / "_hancom_pages.json"
    if index.exists():
        try:
            data = json.loads(index.read_text(encoding="utf-8"))
            value = data.get(doc)
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.isdigit():
                return int(value)
        except (OSError, json.JSONDecodeError):
            pass
    return None


def dump_pages(doc: str, src: Path) -> tuple[bool, int | None, str]:
    rel_src = f"/diff/{doc}/{src.name}"
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
        "/app/target/release/rhwp",
        "dump-pages",
        rel_src,
    ]
    result = run(cmd)
    combined = f"{result.stdout}\n{result.stderr}"
    if result.returncode != 0:
        return False, None, combined.strip().splitlines()[-1] if combined.strip() else "dump failed"
    match = re.search(r"\((\d+)페이지\)", combined)
    pages = int(match.group(1)) if match else None
    return True, pages, ""


def build_gallery(doc: str, out_root: Path) -> tuple[str, bool, str]:
    cmd = [
        "python3",
        "harness/review_gallery.py",
        str(out_root),
        doc,
        "--export-current",
    ]
    result = run(cmd)
    if result.returncode != 0:
        note = (result.stderr or result.stdout).strip().splitlines()
        return str(out_root / "index.html"), False, note[-1] if note else "gallery build failed"
    audit = run(["python3", "harness/audit_review_gallery.py", str(out_root)])
    if audit.returncode != 0:
        note = (audit.stdout or audit.stderr).strip().splitlines()
        return str(out_root / "index.html"), False, note[-1] if note else "gallery audit failed"
    return str(out_root / "index.html"), True, ""


def gallery_visual_metric(doc: str, out_root: Path) -> tuple[int | None, float | None, str]:
    doc_dir = out_root / doc
    pages = sorted(doc_dir.glob("page-*.png"))
    if not pages:
        return None, None, "no gallery page strips"
    worst_page: int | None = None
    worst_mean = -1.0
    for idx, page in enumerate(pages, 1):
        with Image.open(page) as opened:
            image = opened.convert("RGB")
        width, height = image.size
        if width < 4 or height <= 30:
            return None, None, f"invalid gallery strip size {width}x{height}"
        gap = 12 if width >= 1812 else 0
        column_width = (width - gap) // 2
        left = image.crop((0, 30, column_width, height))
        right = image.crop((column_width + gap, 30, column_width + gap + column_width, height))
        if right.size != left.size:
            right = right.resize(left.size)
        diff = ImageChops.difference(left, right)
        stat = ImageStat.Stat(diff)
        mean = sum(stat.mean) / 3.0
        if mean > worst_mean:
            worst_mean = mean
            worst_page = idx
    if worst_page is None:
        return None, None, "no gallery metric"
    return worst_page, worst_mean, ""


def classify(status: DocStatus, visual_threshold: float) -> str:
    if status.source == "missing":
        return "source_missing"
    if not status.dump_ok:
        return "dump_failed"
    if status.hancom_pages is None:
        return "oracle_missing"
    if status.rhwp_pages is None:
        return "rhwp_count_unknown"
    if status.rhwp_pages != status.hancom_pages:
        return "page_count_gap"
    if status.gallery_ok is False:
        return "gallery_failed"
    if status.visual_mean_diff is not None and status.visual_mean_diff >= visual_threshold:
        return "visual_drift"
    return "page_count_clean"


def markdown(statuses: list[DocStatus], generated_at: str, visual_threshold: float) -> str:
    lines = [
        f"# RHWP Fidelity Category Status -- {generated_at}",
        "",
        f"Visual drift threshold: mean pixel diff >= {visual_threshold:.1f}.",
        "",
        "| doc | class | hancom | rhwp | worst visual page | mean diff | source | gallery | notes |",
        "|---|---:|---:|---:|---:|---:|---|---|---|",
    ]
    for item in statuses:
        cls = classify(item, visual_threshold)
        hancom = "" if item.hancom_pages is None else str(item.hancom_pages)
        rhwp = "" if item.rhwp_pages is None else str(item.rhwp_pages)
        worst_page = "" if item.visual_worst_page is None else str(item.visual_worst_page)
        mean_diff = "" if item.visual_mean_diff is None else f"{item.visual_mean_diff:.2f}"
        gallery = item.gallery if item.gallery_ok else ""
        source = item.source
        notes = item.notes.replace("|", "/")
        lines.append(
            f"| `{item.doc}` | `{cls}` | {hancom} | {rhwp} | {worst_page} | "
            f"{mean_diff} | `{source}` | {gallery} | {notes} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("docs", nargs="*", default=DEFAULT_DOCS)
    parser.add_argument("--with-gallery", action="store_true")
    parser.add_argument(
        "--visual-threshold",
        type=float,
        default=15.0,
        help="mean pixel diff threshold for classifying page-count-clean docs as visual_drift",
    )
    parser.add_argument(
        "--out",
        default="work/FIDELITY_CATEGORY_STATUS_2026-06-07.md",
        help="markdown summary path, relative to repo unless absolute",
    )
    args = parser.parse_args()

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    statuses: list[DocStatus] = []
    for doc in args.docs:
        src = source_path(doc)
        if src is None:
            statuses.append(
                DocStatus(
                    doc,
                    "missing",
                    hancom_page_count(doc),
                    None,
                    False,
                    "",
                    None,
                    None,
                    None,
                    "no source.hwpx/source.hwp",
                )
            )
            continue
        dump_ok, rhwp_pages, dump_note = dump_pages(doc, src)
        gallery = ""
        gallery_ok: bool | None = None
        gallery_note = ""
        visual_worst_page: int | None = None
        visual_mean_diff: float | None = None
        metric_note = ""
        if args.with_gallery and dump_ok:
            out_root = DIFF / f"_review_category_status_2026-06-07_{doc}"
            gallery, gallery_ok, gallery_note = build_gallery(doc, out_root)
            if gallery_ok:
                visual_worst_page, visual_mean_diff, metric_note = gallery_visual_metric(doc, out_root)
        notes = "; ".join(note for note in (dump_note, gallery_note, metric_note) if note)
        statuses.append(
            DocStatus(
                doc=doc,
                source=str(src),
                hancom_pages=hancom_page_count(doc),
                rhwp_pages=rhwp_pages,
                dump_ok=dump_ok,
                gallery=gallery,
                gallery_ok=gallery_ok,
                visual_worst_page=visual_worst_page,
                visual_mean_diff=visual_mean_diff,
                notes=notes,
            )
        )

    out = Path(args.out)
    if not out.is_absolute():
        out = RHWP / out
    out.write_text(markdown(statuses, generated_at, args.visual_threshold), encoding="utf-8")
    print(out)
    for item in statuses:
        print(
            "\t".join(
                [
                    item.doc,
                    classify(item, args.visual_threshold),
                    "" if item.hancom_pages is None else str(item.hancom_pages),
                    "" if item.rhwp_pages is None else str(item.rhwp_pages),
                    "" if item.visual_worst_page is None else str(item.visual_worst_page),
                    "" if item.visual_mean_diff is None else f"{item.visual_mean_diff:.2f}",
                    item.source,
                ]
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
