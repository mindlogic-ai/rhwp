#!/usr/bin/env python3
"""Build a current renderer-fidelity work queue from local evidence.

This script is intentionally conservative. It does not decide a renderer bug is
fixed, and it does not invent patches. It combines the current visual board with
structural scanner output so a long run can pick the next safe category without
repeating already-rejected one-page guesses.
"""
from __future__ import annotations

import argparse
import csv
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


RHWP = Path(__file__).resolve().parents[1]
DEFAULT_BOARD = RHWP / "work" / "FIDELITY_VISUAL_STATUS_CURRENT_CONTINUE_2026-06-08.md"


@dataclass(frozen=True)
class BoardRow:
    doc: str
    cls: str
    hancom: str
    rhwp: str
    worst_page: str
    mean_diff: str
    source: str


@dataclass(frozen=True)
class Decision:
    rank: int
    category: str
    doc: str
    page: str
    status: str
    reason: str
    next_command: str


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=RHWP, capture_output=True, text=True)


def parse_board(path: Path) -> list[BoardRow]:
    rows: list[BoardRow] = []
    if not path.exists():
        raise SystemExit(f"missing board file: {path}")
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| `"):
            continue
        parts = [part.strip() for part in line.strip("|").split("|")]
        if len(parts) < 8:
            continue
        doc = parts[0].strip("`")
        cls = parts[1].strip("`")
        source = parts[6].strip("`")
        rows.append(
            BoardRow(
                doc=doc,
                cls=cls,
                hancom=parts[2],
                rhwp=parts[3],
                worst_page=parts[4],
                mean_diff=parts[5],
                source=source,
            )
        )
    return rows


def parse_tsv(text: str) -> list[dict[str, str]]:
    lines = [line for line in text.splitlines() if line and not line.startswith("#")]
    if not lines:
        return []
    return list(csv.DictReader(lines, delimiter="\t"))


def scanner_rows(command: list[str]) -> list[dict[str, str]]:
    result = run(command)
    if result.returncode != 0:
        return []
    return parse_tsv(result.stdout)


def page_ref(row: BoardRow) -> str:
    if row.worst_page:
        return f"{row.doc}:{row.worst_page}"
    return row.doc


def page_number(row: BoardRow) -> str:
    return row.worst_page or ""


def by_doc(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    out: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        doc = row.get("doc", "")
        if not doc:
            continue
        out.setdefault(doc, []).append(row)
    return out


def has_independent_docs(rows: list[dict[str, str]], *, exclude_variants: bool = True) -> bool:
    docs = {row.get("doc", "") for row in rows if row.get("doc", "")}
    if exclude_variants:
        docs = {re.sub(r"_fitted.*$", "", doc) for doc in docs}
    return len(docs) >= 2


def decide(
    board: list[BoardRow],
    cellbreak_rows: list[dict[str, str]],
    photo_rows: list[dict[str, str]],
) -> list[Decision]:
    decisions: list[Decision] = []
    cellbreak_by_doc = by_doc(cellbreak_rows)
    photo_by_doc = by_doc(photo_rows)
    independent_cellbreak = has_independent_docs(cellbreak_rows)
    independent_photo = has_independent_docs(photo_rows)

    for row in sorted(
        board,
        key=lambda item: (
            item.cls != "page_count_gap",
            -(float(item.mean_diff) if item.mean_diff else 0.0),
        ),
    ):
        if row.cls == "page_count_clean":
            decisions.append(
                Decision(
                    rank=len(decisions) + 1,
                    category="guard",
                    doc=row.doc,
                    page=page_number(row),
                    status="guard",
                    reason="page count and visual score are currently below drift threshold",
                    next_command=f"python3 harness/fidelity_category_status.py --with-gallery {row.doc}",
                )
            )
            continue

        if row.cls == "page_count_gap":
            decisions.append(
                Decision(
                    rank=len(decisions) + 1,
                    category="page-count",
                    doc=row.doc,
                    page=page_number(row),
                    status="patchable",
                    reason="page-count mismatch outranks visual drift",
                    next_command=f"RHWP_TABLE_DRIFT=1 /app/target/release/rhwp dump-pages /diff/{row.doc}/source.hwpx",
                )
            )
            continue

        if row.doc in photo_by_doc:
            status = "needs-more-guards" if not independent_photo else "probe"
            reason = (
                "photo-grid source class currently appears in only one independent staged document"
                if status == "needs-more-guards"
                else "photo-grid class has independent guard coverage"
            )
            decisions.append(
                Decision(
                    rank=len(decisions) + 1,
                    category="photo-grid",
                    doc=row.doc,
                    page=page_number(row),
                    status=status,
                    reason=reason,
                    next_command=f"python3 harness/photo_grid_scan.py /tmp/diff --only-mixed && python3 harness/svg_image_ink_probe.py {page_ref(row)}",
                )
            )
            continue

        if row.doc in cellbreak_by_doc:
            status = "needs-more-guards" if not independent_cellbreak else "probe"
            reason = (
                "CellBreak carried-rowspan class currently lacks an independent guard document"
                if status == "needs-more-guards"
                else "CellBreak carried-rowspan class has independent guard coverage"
            )
            decisions.append(
                Decision(
                    rank=len(decisions) + 1,
                    category="cellbreak-rowspan",
                    doc=row.doc,
                    page=page_number(row),
                    status=status,
                    reason=reason,
                    next_command=f"python3 harness/cellbreak_rowspan_scan.py --min-slack 0.0 && python3 harness/table_fragment_diag.py /tmp/diff/{row.doc}",
                )
            )
            continue

        if row.cls == "visual_drift":
            decisions.append(
                Decision(
                    rank=len(decisions) + 1,
                    category="table-text-raster",
                    doc=row.doc,
                    page=page_number(row),
                    status="guard-only",
                    reason=(
                        "current evidence rejects broad SVG font/stroke/fill/y-shift knobs; "
                        "use as guard until a backend or cell-composition invariant appears"
                    ),
                    next_command=f"python3 harness/raster_backend_probe.py {page_ref(row)} --native --region focus:X0,Y0,X1,Y1",
                )
            )
            continue

        decisions.append(
            Decision(
                rank=len(decisions) + 1,
                category="unknown",
                doc=row.doc,
                page=page_number(row),
                status="inspect",
                reason=f"unclassified board class {row.cls}",
                next_command=f"python3 harness/svg_geometry_probe.py {page_ref(row)}",
            )
        )

    return decisions


def markdown(
    board: Path,
    decisions: list[Decision],
    cellbreak_rows: list[dict[str, str]],
    photo_rows: list[dict[str, str]],
) -> str:
    lines = [
        f"# RHWP Fidelity Queue -- {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"Board: `{board}`",
        "",
        "| rank | category | doc | page | status | reason | next command |",
        "|---:|---|---|---:|---|---|---|",
    ]
    for decision in decisions:
        lines.append(
            f"| {decision.rank} | `{decision.category}` | `{decision.doc}` | "
            f"{decision.page} | `{decision.status}` | {decision.reason} | "
            f"`{decision.next_command}` |"
        )
    lines.extend(
        [
            "",
            "## Structural Scanner Summary",
            "",
            f"- CellBreak carried-rowspan rows: {len(cellbreak_rows)}.",
            f"- Photo-grid rows: {len(photo_rows)}.",
            "",
            "Interpretation:",
            "",
            "- `patchable`: safe enough to start a structural probe now.",
            "- `probe`: run targeted probes before Rust.",
            "- `needs-more-guards`: do not patch until another independent doc appears.",
            "- `guard-only`: useful for preventing regressions, not current patch source.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--board", type=Path, default=DEFAULT_BOARD)
    parser.add_argument("--out", type=Path, default=RHWP / "work" / "FIDELITY_QUEUE_CURRENT_2026-06-08.md")
    args = parser.parse_args()

    board = args.board if args.board.is_absolute() else RHWP / args.board
    out = args.out if args.out.is_absolute() else RHWP / args.out
    board_rows = parse_board(board)
    cellbreak = scanner_rows(["python3", "harness/cellbreak_rowspan_scan.py", "--min-slack", "0.0"])
    photo = scanner_rows(["python3", "harness/photo_grid_scan.py", "/tmp/diff"])
    decisions = decide(board_rows, cellbreak, photo)
    out.parent.mkdir(parents=True, exist_ok=True)
    text = markdown(board, decisions, cellbreak, photo)
    out.write_text(text, encoding="utf-8")
    print(out)
    for decision in decisions:
        print(
            f"{decision.rank}\t{decision.category}\t{decision.doc}\t"
            f"{decision.page}\t{decision.status}\t{decision.reason}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
