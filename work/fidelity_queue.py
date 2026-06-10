#!/usr/bin/env python3
"""Print the 2026-06-05 renderer-fidelity target queue.

This is intentionally read-only. It turns the TSV plan into a practical
operator view for long runs:

    python3 work/fidelity_queue.py
    python3 work/fidelity_queue.py --summary
    python3 work/fidelity_queue.py --category image-float
    python3 work/fidelity_queue.py --target wild_02_paper_fig_10MB
    python3 work/fidelity_queue.py --target wild_02_paper_fig_10MB --commands
    python3 work/fidelity_queue.py --target wild_02_paper_fig_10MB --packet
    python3 work/fidelity_queue.py --check-artifacts
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent
QUEUE = ROOT / "fidelity_target_queue_2026-06-05.tsv"
FACTCHAT_HWPX_ROOT = Path(
    "/Users/jaehoshin/Desktop/mindlogic/factchat/worktree-hwpx-final"
)
DIFF_ROOT = Path("/tmp/diff")
SOURCE_NAMES = ("source.hwpx", "source.hwp", "source_converted.hwpx")


def path_exists(raw: str) -> bool:
    if raw.startswith("http://") or raw.startswith("https://"):
        return True
    path = Path(raw)
    if path.exists():
        return True
    if not path.is_absolute():
        if (ROOT.parent / path).exists():
            return True
        if (FACTCHAT_HWPX_ROOT / path).exists():
            return True
    return False


def source_candidates(doc: str) -> list[Path]:
    return [DIFF_ROOT / doc / name for name in SOURCE_NAMES]


def existing_source(doc: str) -> Path | None:
    return next((path for path in source_candidates(doc) if path.exists()), None)


def has_oracle(doc: str) -> bool:
    docdir = DIFF_ROOT / doc
    if (docdir / "hancom.pdf").exists():
        return True
    if any(docdir.glob("hancom_p-*.png")):
        return True
    gt_png = docdir / "gt_png"
    return gt_png.exists() and any(gt_png.glob("*.png"))


def readiness_issues(row: dict[str, str]) -> list[str]:
    doc = row["doc"]
    issues: list[str] = []
    if doc != "export_roundtrip_probe":
        docdir = DIFF_ROOT / doc
        if not docdir.exists():
            issues.append(f"missing docdir: {docdir}")
        if existing_source(doc) is None:
            candidates = ", ".join(str(path) for path in source_candidates(doc))
            issues.append(f"missing source: expected one of {candidates}")
        if not has_oracle(doc):
            issues.append(
                f"missing oracle: expected hancom.pdf, hancom_p-*.png, or gt_png/*.png under {docdir}"
            )
    for artifact in split_field(row, "visual_artifacts", ";"):
        if not path_exists(artifact):
            issues.append(f"missing visual artifact: {artifact}")
    return issues


def load_rows() -> list[dict[str, str]]:
    with QUEUE.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        header: list[str] | None = None
        rows: list[dict[str, str]] = []
        for raw in reader:
            if not raw:
                continue
            if raw[0].startswith("#"):
                if raw[0].startswith("# priority"):
                    header = [raw[0].lstrip("# "), *raw[1:]]
                continue
            if header is None:
                raise SystemExit(f"missing header in {QUEUE}")
            if len(header) != len(raw):
                raise SystemExit(
                    f"bad row in {QUEUE}: expected {len(header)} fields, got {len(raw)}"
                )
            rows.append(dict(zip(header, raw)))
        return rows


def print_compact(rows: list[dict[str, str]]) -> None:
    for row in rows:
        print(
            f"P{row['priority']} {row['category']:<13} "
            f"{row['doc']:<38} {row['page_or_range']:<12} "
            f"{row['oracle_vs_ours']:<18} {row['symptom']}"
        )


def split_field(row: dict[str, str], name: str, sep: str) -> list[str]:
    return [item.strip() for item in row[name].split(sep) if item.strip()]


def print_summary(rows: list[dict[str, str]]) -> None:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["category"]].append(row)

    for category, category_rows in grouped.items():
        priorities = sorted({row["priority"] for row in category_rows})
        docs = ", ".join(row["doc"] for row in category_rows)
        missing = 0
        for row in category_rows:
            missing += len(readiness_issues(row))
        print(
            f"{category:<13} P{','.join(priorities):<5} "
            f"targets={len(category_rows):<2} readiness_issues={missing}"
        )
        print(f"  {docs}")


def print_commands(row: dict[str, str]) -> None:
    doc = row["doc"]
    print(f"# Target: P{row['priority']} {row['category']} :: {doc}")
    print("python3 work/fidelity_queue.py --target " + doc + " --check-artifacts")
    print("CARGO_BUILD_JOBS=1 docker compose --env-file .env.docker run --rm dev \\")
    print("  cargo build --release --bin rhwp -j 1")

    if doc != "export_roundtrip_probe":
        print(f"python3 harness/review_gallery.py /tmp/diff/_review_{doc}_live {doc} --export-current")
        print(f"python3 harness/look.py /tmp/diff/{doc} --export")
        print("docker compose --env-file .env.docker run --rm -v /tmp/diff:/diff \\")
        print("  -e RHWP_TABLE_DRIFT=1 -e RHWP_TYPESET_DRIFT=1 dev \\")
        print(f"  /app/target/release/rhwp dump-pages /diff/{doc}/source.hwpx \\")
        print(f"  > /tmp/diff/{doc}/dump_pages_current.txt \\")
        print(f"  2> /tmp/diff/{doc}/drift_current.txt")
    else:
        print("cd /Users/jaehoshin/Desktop/mindlogic/factchat/worktree-hwpx-final")
        print("HWP_TEST_URL=http://127.0.0.1:8765/ \\")
        print("  node hwp-agent-spike/tests/export_roundtrip_probe.mjs")

    print("python3 scripts/check_renderer_overfit.py")
    print("bash harness/gate.sh --no-build")
    print("# Visual-check changed docs before LAND. BANK after 3 failed structural probes.")


def print_packet(row: dict[str, str]) -> None:
    doc = row["doc"]
    artifacts = split_field(row, "visual_artifacts", ";")
    primary_files = split_field(row, "primary_files", ";")
    guard_docs = split_field(row, "guard_docs", ",")
    raw_validations = [
        item.strip() for item in row["fast_validation"].split(";") if item.strip()
    ]
    standard_validations = {
        "python3 scripts/check_renderer_overfit.py",
        "bash harness/gate.sh --no-build",
    }
    shell_validations = [
        item
        for item in raw_validations
        if item not in standard_validations and " " in item and not item.startswith("Hancom-")
    ]
    manual_validations = [
        item
        for item in raw_validations
        if item not in standard_validations and item not in shell_validations
    ]

    print(f"# Fidelity Run Packet: {doc}")
    print()
    print("## Target")
    print()
    print(f"- priority: P{row['priority']}")
    print(f"- category: {row['category']}")
    print(f"- page/range: {row['page_or_range']}")
    print(f"- oracle vs ours: {row['oracle_vs_ours']}")
    print(f"- symptom: {row['symptom']}")
    print()
    print("## Representative Artifacts")
    print()
    issues = readiness_issues(row)
    readiness = "ready" if not issues else "not ready"
    print(f"- readiness: {readiness}")
    for issue in issues:
        print(f"  - {issue}")
    if doc != "export_roundtrip_probe":
        source = existing_source(doc)
        print(f"- source: {source if source else 'missing'}")
        print(f"- oracle: {'ok' if has_oracle(doc) else 'missing'}")
    for artifact in artifacts:
        marker = "ok" if path_exists(artifact) else "missing"
        print(f"- [{marker}] {artifact}")
    print()
    print("## Likely Owner Files")
    print()
    for item in primary_files:
        print(f"- {item}")
    print()
    print("## Guard Documents")
    print()
    for item in guard_docs:
        print(f"- {item}")
    print()
    print("## Structural Hypothesis")
    print()
    print(f"- category: {row['category']}")
    print("- Fill this before editing. Use only renderer-structural facts:")
    print("  control type, wrap mode, anchor mode, TAC flag, flow/overlap flags,")
    print("  line-segment/vpos shape, table geometry, row split, or measured extents.")
    print("- Forbidden: filename, page number alone, title/body text, paragraph index")
    print("  unless the index is confined to a test/probe artifact.")
    print()
    print("## Fast Commands")
    print()
    print("```bash")
    print("python3 work/fidelity_queue.py --target " + doc + " --check-artifacts")
    print("CARGO_BUILD_JOBS=1 docker compose --env-file .env.docker run --rm dev \\")
    print("  cargo build --release --bin rhwp -j 1")
    if doc != "export_roundtrip_probe":
        print(f"python3 harness/review_gallery.py /tmp/diff/_review_{doc}_live {doc} --export-current")
        print(f"python3 harness/look.py /tmp/diff/{doc} --export")
        print("docker compose --env-file .env.docker run --rm -v /tmp/diff:/diff \\")
        print("  -e RHWP_TABLE_DRIFT=1 -e RHWP_TYPESET_DRIFT=1 dev \\")
        print(f"  /app/target/release/rhwp dump-pages /diff/{doc}/source.hwpx \\")
        print(f"  > /tmp/diff/{doc}/dump_pages_current.txt \\")
        print(f"  2> /tmp/diff/{doc}/drift_current.txt")
    else:
        print("cd /Users/jaehoshin/Desktop/mindlogic/factchat/worktree-hwpx-final")
        print("HWP_TEST_URL=http://127.0.0.1:8765/ \\")
        print("  node hwp-agent-spike/tests/export_roundtrip_probe.mjs")
    for validation in shell_validations:
        print(validation)
    print("python3 scripts/check_renderer_overfit.py")
    print("bash harness/gate.sh --no-build")
    print("```")
    if manual_validations:
        print()
        print("Manual validation:")
        for validation in manual_validations:
            print(f"- {validation}")
    print()
    print("## Acceptance")
    print()
    print(row["acceptance"])
    print()
    print("## Decision Record")
    print()
    print("- before:")
    print("  - oracle pages:")
    print("  - rhwp pages:")
    print("  - visible defect:")
    print("- after:")
    print("  - rhwp pages:")
    print("  - changed docs:")
    print("  - visual checked docs:")
    print("  - residual defect:")
    print("- validation:")
    print("  - native build:")
    print("  - target dump/look:")
    print("  - overfit check:")
    print("  - broad gate:")
    print("  - new overflow:")
    print("- decision: LAND / BANK / REVERT")
    print("- reason:")


def print_detail(row: dict[str, str]) -> None:
    print(f"Target: P{row['priority']} {row['category']} :: {row['doc']}")
    print(f"Page/range: {row['page_or_range']}")
    print(f"Oracle/ours: {row['oracle_vs_ours']}")
    print(f"Symptom: {row['symptom']}")
    print()
    print("Primary files:")
    for item in split_field(row, "primary_files", ";"):
        print(f"- {item}")
    print()
    print("Guard docs:")
    for item in split_field(row, "guard_docs", ","):
        print(f"- {item}")
    print()
    print("Visual artifacts:")
    for item in split_field(row, "visual_artifacts", ";"):
        marker = "ok" if path_exists(item) else "missing"
        print(f"- [{marker}] {item}")
    print()
    print("Fast validation:")
    for item in row["fast_validation"].split("; "):
        print(f"- {item}")
    print()
    print("Acceptance:")
    print(row["acceptance"])
    print()
    print("Checklist:")
    print(
        """Target:
Family:
Structural discriminator:
Files changed:

Before:
- oracle pages:
- rhwp pages:
- visible defect:

After:
- rhwp pages:
- visible defect:
- changed-doc list:

Validation:
- native build:
- focus gate:
- full gate:
- overfit check:
- visual checked docs:
- new overflow:
- known residual:

Decision:
- LAND / BANK / REVERT
- reason:"""
    )


def print_artifact_check(rows: list[dict[str, str]]) -> int:
    missing = 0
    for row in rows:
        issues = readiness_issues(row)
        status = "READY" if not issues else "NOT_READY"
        print(
            f"{status:<9} P{row['priority']} {row['category']:<13} "
            f"{row['doc']:<38} {row['page_or_range']}"
        )
        for issue in issues:
            print(f"          - {issue}")
        missing += len(issues)
    if missing:
        print(f"\nartifact check: {missing} readiness issue(s)")
        return 1
    print("\nartifact check: all source, oracle, and visual artifacts exist")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--category", help="filter by category")
    parser.add_argument("--target", help="print detailed entry for doc name")
    parser.add_argument(
        "--summary",
        action="store_true",
        help="print category summary with target counts and missing artifact counts",
    )
    parser.add_argument(
        "--commands",
        action="store_true",
        help="print the fast validation commands for the selected --target",
    )
    parser.add_argument(
        "--packet",
        action="store_true",
        help="print a durable run packet for the selected --target",
    )
    parser.add_argument(
        "--check-artifacts",
        action="store_true",
        help="verify source, oracle, and visual artifact paths referenced by the queue",
    )
    args = parser.parse_args()

    rows = load_rows()
    if args.category:
        rows = [r for r in rows if r["category"] == args.category]
    if args.target:
        rows = [r for r in rows if r["doc"] == args.target]
        if not rows:
            raise SystemExit(f"no target found for {args.target!r}")
    if args.check_artifacts:
        return print_artifact_check(rows)
    if args.summary:
        print_summary(rows)
        return 0
    if args.commands:
        if not args.target:
            raise SystemExit("--commands requires --target")
        print_commands(rows[0])
        return 0
    if args.packet:
        if not args.target:
            raise SystemExit("--packet requires --target")
        print_packet(rows[0])
        return 0
    if args.target:
        print_detail(rows[0])
        return 0
    print_compact(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
