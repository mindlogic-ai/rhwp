#!/usr/bin/env python3
"""Detect HWPX embedded scan/title interleaving candidates.

This is a read-only corpus diagnostic for renderer-fidelity work. It looks for
structural patterns where page/paper-relative scanned page images and 1x3 title
tables are interleaved across nearby paragraphs. That class can require
per-control page ownership; paragraph-level page breaks tend to create blank
pages or reorder titles incorrectly.

Usage:
  python3 harness/embedded_scan_title_diag.py /tmp/diff/wc31_17pg/source.hwpx
  python3 harness/embedded_scan_title_diag.py --corpus /tmp/diff --limit 20
"""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET


NS = {
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
    "hc": "http://www.hancom.co.kr/hwpml/2011/core",
}


@dataclass
class ControlInfo:
    para: int
    index: int
    kind: str
    text: str
    detail: str
    bin_id: str = ""


def route_sequence(controls: list[ControlInfo]) -> list[dict[str, object]]:
    """Annotate an interleaved scan/title run with structural ownership hints.

    This is diagnostic-only. It never inspects fixture names and does not depend
    on title text. For each title band, the next scan/media control is the
    candidate body target a renderer-side router would need to consider.
    """
    sequence: list[dict[str, object]] = []
    for i, ctrl in enumerate(controls):
        entry: dict[str, object] = {
            "para": ctrl.para,
            "index": ctrl.index,
            "kind": ctrl.kind,
            "bin_id": ctrl.bin_id,
            "detail": ctrl.detail,
        }
        if ctrl.kind == "title":
            target = next(
                (
                    c
                    for c in controls[i + 1 :]
                    if c.kind in {"scan", "media", "media_table"}
                ),
                None,
            )
            if target is not None:
                entry["next_body_kind"] = target.kind
                entry["next_body_para"] = target.para
                entry["next_body_bin_id"] = target.bin_id
        sequence.append(entry)
    return sequence


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def text_of(elem: ET.Element) -> str:
    return re.sub(r"\s+", " ", "".join(elem.itertext())).strip()


def is_page_scan(pic: ET.Element) -> tuple[bool, str]:
    pos = pic.find("hp:pos", NS)
    size = pic.find("hp:sz", NS)
    img = pic.find("hc:img", NS)
    if pos is None or size is None:
        return False, ""
    treat = pos.get("treatAsChar") == "1"
    vert = pos.get("vertRelTo")
    horz = pos.get("horzRelTo")
    wrap = pic.get("textWrap", "")
    width = int(size.get("width") or 0)
    height = int(size.get("height") or 0)
    # Structural approximation: near body/page width and tall enough to be a
    # scanned page region. Uses HWP units; avoids content/title matching.
    pageish = (
        not treat
        and vert in {"PAPER", "PAGE"}
        and horz in {"PAPER", "PAGE", "COLUMN"}
        and wrap in {"SQUARE", "TOP_AND_BOTTOM"}
        and width >= 43000
        and height >= 56000
    )
    if not pageish:
        return False, ""
    bin_id = img.get("binaryItemIDRef", "?") if img is not None else "?"
    return True, f"bin={bin_id} wrap={wrap} vert={vert} horz={horz} size={width}x{height}"


def picture_bin_id(pic: ET.Element) -> str:
    img = pic.find("hc:img", NS)
    return img.get("binaryItemIDRef", "") if img is not None else ""


def is_large_media_picture(pic: ET.Element) -> tuple[bool, str]:
    pos = pic.find("hp:pos", NS)
    size = pic.find("hp:sz", NS)
    if pos is None or size is None:
        return False, ""
    width = int(size.get("width") or 0)
    height = int(size.get("height") or 0)
    if width < 43000 or height < 30000:
        return False, ""
    treat = pos.get("treatAsChar") == "1"
    vert = pos.get("vertRelTo")
    horz = pos.get("horzRelTo")
    wrap = pic.get("textWrap", "")
    bin_id = picture_bin_id(pic) or "?"
    return True, f"bin={bin_id} tac={treat} wrap={wrap} vert={vert} horz={horz} size={width}x{height}"


def is_title_table(tbl: ET.Element) -> tuple[bool, str]:
    pos = tbl.find("hp:pos", NS)
    size = tbl.find("hp:sz", NS)
    row_count = int(tbl.get("rowCnt") or 0)
    col_count = int(tbl.get("colCnt") or 0)
    if pos is None or size is None:
        return False, ""
    width = int(size.get("width") or 0)
    height = int(size.get("height") or 0)
    # Typical evidence/title band shape: one row, three columns, body-wide.
    # Deliberately no literal title-text matching.
    if row_count == 1 and col_count == 3 and width >= 43000 and height <= 7000:
        treat = pos.get("treatAsChar") == "1"
        wrap = tbl.get("textWrap", "")
        return True, f"tac={treat} wrap={wrap} size={width}x{height}"
    return False, ""


def is_large_media_table(tbl: ET.Element) -> tuple[bool, str]:
    pos = tbl.find("hp:pos", NS)
    size = tbl.find("hp:sz", NS)
    row_count = int(tbl.get("rowCnt") or 0)
    col_count = int(tbl.get("colCnt") or 0)
    if pos is None or size is None:
        return False, ""
    width = int(size.get("width") or 0)
    height = int(size.get("height") or 0)
    if row_count >= 2 and col_count >= 1 and width >= 43000 and height >= 30000:
        treat = pos.get("treatAsChar") == "1"
        wrap = tbl.get("textWrap", "")
        return True, (
            f"rows={row_count} cols={col_count} tac={treat} "
            f"wrap={wrap} size={width}x{height}"
        )
    return False, ""


def iter_paragraph_controls(section_xml: bytes) -> list[list[ControlInfo]]:
    root = ET.fromstring(section_xml)
    paragraphs: list[list[ControlInfo]] = []
    # Renderer paragraph indices are section top-level body paragraphs. Nested
    # table-cell paragraphs are still used for title text, but they must not
    # increment the reported host paragraph index.
    for para_idx, para in enumerate(root.findall("hp:p", NS)):
        controls: list[ControlInfo] = []
        for elem in para.iter():
            name = local_name(elem.tag)
            if name == "pic":
                ok, detail = is_page_scan(elem)
                if ok:
                    controls.append(
                        ControlInfo(
                            para_idx,
                            len(controls),
                            "scan",
                            "",
                            detail,
                            picture_bin_id(elem),
                        )
                    )
                else:
                    media_ok, media_detail = is_large_media_picture(elem)
                    if media_ok:
                        controls.append(
                            ControlInfo(
                                para_idx,
                                len(controls),
                                "media",
                                "",
                                media_detail,
                                picture_bin_id(elem),
                            )
                        )
            elif name == "tbl":
                ok, detail = is_title_table(elem)
                if ok:
                    controls.append(
                        ControlInfo(para_idx, len(controls), "title", text_of(elem), detail)
                    )
                else:
                    media_ok, media_detail = is_large_media_table(elem)
                    if media_ok:
                        controls.append(
                            ControlInfo(
                                para_idx,
                                len(controls),
                                "media_table",
                                "",
                                media_detail,
                            )
                        )
        paragraphs.append(controls)
    return paragraphs


def diagnose(path: Path) -> dict[str, object]:
    try:
        zf_ctx = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        return {
            "path": str(path),
            "candidate_count": 0,
            "candidates": [],
            "error": "bad-zip",
        }
    with zf_ctx as zf:
        section_names = sorted(
            name
            for name in zf.namelist()
            if name.startswith("Contents/section") and name.endswith(".xml")
        )
        candidates: list[dict[str, object]] = []
        for section_idx, name in enumerate(section_names):
            paragraphs = iter_paragraph_controls(zf.read(name))
            for idx, controls in enumerate(paragraphs):
                if not controls:
                    continue
                has_scan = any(c.kind == "scan" for c in controls)
                has_title = any(c.kind == "title" for c in controls)
                window = [
                    c
                    for para_controls in paragraphs[idx : idx + 8]
                    for c in para_controls
                ]
                window_has_scan = any(c.kind == "scan" for c in window)
                window_has_title = any(c.kind == "title" for c in window)
                # Same-paragraph scan+title or nearby interleaving of both classes.
                if (has_scan and has_title) or (
                    window_has_scan and window_has_title and len(window) >= 3
                ):
                    compact_window: list[ControlInfo] = []
                    seen: set[tuple[int, int, str, str]] = set()
                    for c in window:
                        key = (c.para, c.index, c.kind, c.bin_id)
                        if key in seen:
                            continue
                        seen.add(key)
                        compact_window.append(c)
                    candidates.append(
                        {
                            "section": section_idx,
                            "start_para": idx,
                            "controls": [
                                {
                                    "para": c.para,
                                    "kind": c.kind,
                                    "text": c.text[:80],
                            "detail": c.detail,
                            "bin_id": c.bin_id,
                        }
                        for c in window[:12]
                    ],
                            "route_sequence": route_sequence(compact_window[:12]),
                        }
                    )
        return {"path": str(path), "candidate_count": len(candidates), "candidates": candidates}


def corpus_sources(root: Path) -> list[Path]:
    return sorted(root.glob("*/source.hwpx"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", help="single .hwpx source")
    parser.add_argument("--corpus", type=Path, help="scan corpus directory")
    parser.add_argument("--limit", type=int, default=0, help="limit printed candidates")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args()

    paths: list[Path]
    if args.corpus:
        paths = corpus_sources(args.corpus)
    elif args.source:
        paths = [Path(args.source)]
    else:
        raise SystemExit("provide a source.hwpx or --corpus")

    results = [diagnose(path) for path in paths if path.exists()]
    matches = [r for r in results if r["candidate_count"]]
    if args.json:
        print(json.dumps(matches, ensure_ascii=False, indent=2))
        return 0

    print(f"scanned={len(results)} matches={len(matches)}")
    printed = 0
    for result in matches:
        if args.limit and printed >= args.limit:
            break
        print(f"\n{result['path']} candidates={result['candidate_count']}")
        for cand in result["candidates"][:3]:
            print(f"  section={cand['section']} start_para={cand['start_para']}")
            for ctrl in cand["controls"]:
                label = f"    p{ctrl['para']:<4} {ctrl['kind']:<5} {ctrl['detail']}"
                if ctrl["text"]:
                    label += f" text={ctrl['text']!r}"
                print(label)
        printed += 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
