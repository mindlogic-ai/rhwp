#!/usr/bin/env python3
"""Print the focus-corpus work queue, grouped by tier."""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FOCUS = ROOT / "focus_set.tsv"


def rows():
    with FOCUS.open(newline="") as f:
        for row in csv.reader(f, delimiter="\t"):
            if not row or row[0].startswith("#"):
                continue
            doc, kind, tier, hancom, rhwp, note = row
            yield {
                "doc": doc,
                "kind": kind,
                "tier": tier,
                "hancom": int(hancom),
                "rhwp": int(rhwp),
                "note": note,
            }


def main() -> int:
    groups = {"quick": [], "medium": [], "giant": []}
    for row in rows():
        groups.setdefault(row["tier"], []).append(row)

    for tier in ("quick", "medium", "giant"):
        print(f"\n== {tier.upper()} ==")
        for row in groups.get(tier, []):
            delta = row["rhwp"] - row["hancom"]
            marker = "OK" if delta == 0 else f"{delta:+d}"
            print(
                f"{row['doc']}\t{row['kind']}\t{row['rhwp']}/{row['hancom']} pages\t{marker}\t{row['note']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
