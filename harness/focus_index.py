#!/usr/bin/env python3
"""Build /tmp/diff/_FOCUS_INDEX.html for the user-selected problem set."""
from __future__ import annotations

import csv
import html
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIFF = Path("/tmp/diff")
FOCUS = ROOT / "focus_set.tsv"
OUT = DIFF / "_FOCUS_INDEX.html"
FOCUS_DIR = DIFF / "_focus"


def rows():
    with FOCUS.open(newline="") as f:
        for row in csv.reader(f, delimiter="\t"):
            if not row or row[0].startswith("#"):
                continue
            doc, kind, tier, hancom, rhwp, note = row
            yield doc, kind, tier, int(hancom), int(rhwp), note


def main() -> int:
    FOCUS_DIR.mkdir(exist_ok=True)
    table_rows = []
    counts = {"quick": 0, "medium": 0, "giant": 0}
    for doc, kind, tier, hancom, rhwp, note in rows():
        counts[tier] = counts.get(tier, 0) + 1
        delta = rhwp - hancom
        status = "OK" if delta == 0 else f"{delta:+d}"
        status_class = "ok" if delta == 0 else "bad"
        source_dir = DIFF / doc
        exists = source_dir.exists()
        focus_link = FOCUS_DIR / doc
        if exists and not focus_link.exists():
            focus_link.symlink_to(Path("..") / doc, target_is_directory=True)
        link = f"_focus/{html.escape(doc)}/" if exists else "#"
        table_rows.append(
            "<tr>"
            f"<td><a href='{link}'>{html.escape(doc)}</a></td>"
            f"<td>{html.escape(kind)}</td>"
            f"<td class='{html.escape(tier)}'>{html.escape(tier)}</td>"
            f"<td>{rhwp}</td><td>{hancom}</td>"
            f"<td class='{status_class}'>{status}</td>"
            f"<td>{html.escape(note)}</td>"
            "</tr>"
        )

    body = "\n".join(table_rows)
    OUT.write_text(
        f"""<!doctype html>
<meta charset="utf-8">
<title>rhwp focus validation set</title>
<style>
body{{font:14px/1.5 -apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;background:#0f1115;color:#e6e6e6;margin:0}}
header{{padding:20px 28px;background:#161a22;border-bottom:1px solid #2a2f3a}}
h1{{font-size:20px;margin:0 0 6px}}
.sub{{color:#9aa4b2}}
main{{padding:22px 28px;max-width:1300px;margin:0 auto}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
th,td{{border-bottom:1px solid #232833;padding:7px 10px;text-align:left;vertical-align:top}}
th{{color:#9aa4b2;font-weight:600}}
a{{color:#9fd0ff;text-decoration:none}}
a:hover{{text-decoration:underline}}
.ok{{color:#5fe08a;font-weight:700}}
.bad{{color:#ff8f8f;font-weight:700}}
.quick{{color:#5fe08a}}
.medium{{color:#ffd166}}
.giant{{color:#ff8f8f}}
code{{background:#0b0d12;padding:1px 5px;border-radius:4px}}
</style>
<header>
  <h1>rhwp focus validation set</h1>
  <div class="sub">User-selected problematic docs · quick {counts.get('quick',0)} · medium {counts.get('medium',0)} · giant {counts.get('giant',0)}</div>
</header>
<main>
  <p>Start with <code>quick</code>. Defer <code>giant</code> until the shorter spacing/table fixes stop moving the cluster.</p>
  <table>
    <thead><tr><th>doc</th><th>kind</th><th>tier</th><th>rhwp pages</th><th>Hancom pages</th><th>delta</th><th>note</th></tr></thead>
    <tbody>
{body}
    </tbody>
  </table>
</main>
""",
        encoding="utf-8",
    )
    (FOCUS_DIR / "index.html").write_text(
        """<!doctype html>
<meta charset="utf-8">
<title>rhwp focus set</title>
<meta http-equiv="refresh" content="0; url=../_FOCUS_INDEX.html">
<a href="../_FOCUS_INDEX.html">Open focus index</a>
""",
        encoding="utf-8",
    )
    print(OUT)
    print(FOCUS_DIR / "index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
