#!/usr/bin/env bash
# Focus-corpus page-count + overflow gate.
#
# Usage:
#   bash harness/focus_gate.sh quick
#   bash harness/focus_gate.sh medium
#   bash harness/focus_gate.sh all
#   bash harness/focus_gate.sh quick --build
#
# This is intentionally narrower than harness/gate.sh. It does not replace the
# full regression gate before committing; it makes first-pass iteration cheap on
# the user-selected problem set.
set -euo pipefail

RHWP="${RHWP_ROOT:-/Users/jaehoshin/Desktop/mindlogic/factchat/worktree-rhwp-poc/rhwp}"
DIFF="${DIFF_DIR:-/tmp/diff}"
H="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TIER="${1:-quick}"
BUILD=0
if [[ "${2:-}" == "--build" || "${1:-}" == "--build" ]]; then
  BUILD=1
  [[ "${1:-}" == "--build" ]] && TIER="quick"
fi

cd "$RHWP"
if [[ "$BUILD" == "1" ]]; then
  echo "[focus-gate] building working-tree binary (CARGO_BUILD_JOBS=1)..."
  CARGO_BUILD_JOBS=1 docker compose --env-file .env.docker run --rm -e CARGO_BUILD_JOBS=1 dev \
    cargo build --release --bin rhwp
fi

python3 - "$H/focus_set.tsv" "$TIER" > "$DIFF/_focus_docs.txt" <<'PY'
import csv, sys
manifest, tier = sys.argv[1], sys.argv[2]
allowed = {"quick"} if tier == "quick" else {"medium"} if tier == "medium" else {"quick", "medium", "giant"}
with open(manifest, newline="") as f:
    for row in csv.reader(f, delimiter="\t"):
        if not row or row[0].startswith("#"):
            continue
        if row[2] in allowed:
            print(row[0])
PY

echo "[focus-gate] rendering tier=$TIER docs=$(wc -l < "$DIFF/_focus_docs.txt" | tr -d ' ')"
docker compose --env-file .env.docker run --rm -v "$DIFF":/diff dev bash -c '
  set -euo pipefail
  BIN=/app/target/release/rhwp
  while IFS= read -r n; do
    d="/diff/$n"
    src="$d/source.hwpx"
    [ -f "$src" ] || src="$d/source_converted.hwpx"
    if [ ! -f "$src" ]; then
      echo -e "$n\tMISSING\tMISSING"
      continue
    fi
    out=$(mktemp -d)
    log=$("$BIN" export-svg "$src" -o "$out" 2>&1 >/dev/null || true)
    pages=$(ls "$out"/*.svg 2>/dev/null | wc -l | tr -d " ")
    ov=$(printf "%s" "$log" | grep -c LAYOUT_OVERFLOW || true)
    rm -rf "$out"
    echo -e "$n\t$pages\t$ov"
  done < /diff/_focus_docs.txt
' > "$DIFF/_focus_gate_now.tsv"

python3 - "$H/focus_set.tsv" "$H/baseline_pc.tsv" "$DIFF/_focus_gate_now.tsv" "$TIER" <<'PY'
import csv, sys
manifest, baseline_path, now_path, tier = sys.argv[1:]
allowed = {"quick"} if tier == "quick" else {"medium"} if tier == "medium" else {"quick", "medium", "giant"}
baseline = {}
with open(baseline_path) as f:
    for line in f:
        if not line.strip():
            continue
        doc, pages, ov = line.rstrip("\n").split("\t")
        baseline[doc] = (int(pages), int(ov))
expected = {}
with open(manifest, newline="") as f:
    for row in csv.reader(f, delimiter="\t"):
        if not row or row[0].startswith("#") or row[2] not in allowed:
            continue
        expected[row[0]] = {"tier": row[2], "hancom": int(row[3]), "rhwp": int(row[4]), "note": row[5]}
now = {}
with open(now_path) as f:
    for line in f:
        doc, pages, ov = line.rstrip("\n").split("\t")
        if pages != "MISSING":
            now[doc] = (int(pages), int(ov))

improved = []
same = []
regressed = []
overflow = []
missing = []
for doc, meta in expected.items():
    if doc not in now:
        missing.append(doc)
        continue
    pages, ov = now[doc]
    base_pages, base_ov = baseline.get(doc, (meta["rhwp"], 0))
    oracle = meta["hancom"]
    if abs(pages - oracle) < abs(base_pages - oracle):
        improved.append((doc, base_pages, pages, oracle))
    elif abs(pages - oracle) > abs(base_pages - oracle):
        regressed.append((doc, base_pages, pages, oracle))
    else:
        same.append((doc, pages, oracle))
    if ov > base_ov:
        overflow.append((doc, base_ov, ov))

print(f"focus tier={tier}: docs={len(expected)} improved={len(improved)} same={len(same)} regressed={len(regressed)} missing={len(missing)} new_overflow={len(overflow)}")
for doc, b, p, h in improved:
    print(f"  IMPROVE {doc}: {b}->{p} oracle={h}")
for doc, p, h in same:
    marker = "OK" if p == h else "DIFF"
    print(f"  {marker:4} {doc}: {p}/{h}")
for doc, b, p, h in regressed:
    print(f"  REGRESS {doc}: {b}->{p} oracle={h}")
for doc, b, ov in overflow:
    print(f"  +OVERFLOW {doc}: {b}->{ov}")
for doc in missing:
    print(f"  MISSING {doc}")
raise SystemExit(1 if regressed or overflow or missing else 0)
PY
