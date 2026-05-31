#!/usr/bin/env bash
# Corpus regression gate — build working-tree binary, then page-count + overflow
# sweep across ALL docs. BLOCKS (exit 1) if any doc moved AWAY from its baseline
# page count or gained overflow. Page-count is reliable for REGRESSION detection
# (it's only unreliable as an IMPROVEMENT signal — that's drift.py's job).
#
#   gate.sh            build + sweep + compare to baseline
#   gate.sh --no-build skip rebuild (binary already current)
#   gate.sh --update-baseline   adopt current as new baseline (after a verified win)
set -uo pipefail
RHWP=/Users/jaehoshin/Desktop/mindlogic/factchat/worktree-rhwp-poc/rhwp
H=/tmp/diff/harness
BASE="$H/baseline_pc.tsv"
cd "$RHWP"

if [[ "${1:-}" != "--no-build" && "${1:-}" != "--update-baseline" ]]; then
  echo "[gate] building working-tree binary (CARGO_BUILD_JOBS=1)..."
  CARGO_BUILD_JOBS=1 docker compose --env-file .env.docker run --rm -e CARGO_BUILD_JOBS=1 dev \
    cargo build --release --bin rhwp > "$H/_gate_build.log" 2>&1
  if ! grep -q 'Finished' "$H/_gate_build.log"; then
    echo "[gate] BUILD FAILED — see $H/_gate_build.log"; tail -15 "$H/_gate_build.log"; exit 1
  fi
fi

docker compose --env-file .env.docker run --rm -v /tmp/diff:/diff dev bash -c '
  BIN=/app/target/release/rhwp
  for d in /diff/*/; do
    n=$(basename "$d"); src="$d/source.hwpx"; [ -f "$src" ] || src="$d/source_converted.hwpx"
    [ -f "$src" ] || continue
    out=$(mktemp -d)
    log=$("$BIN" export-svg "$src" -o "$out" 2>&1 >/dev/null)
    pages=$(ls "$out"/*.svg 2>/dev/null | wc -l | tr -d " ")
    ov=$(printf "%s" "$log" | grep -c LAYOUT_OVERFLOW || true)
    rm -rf "$out"; echo "$n	$pages	$ov"
  done' > "$H/_gate_now.tsv" 2>/dev/null
sort -o "$H/_gate_now.tsv" "$H/_gate_now.tsv"

if [[ "${1:-}" == "--update-baseline" ]]; then
  cp "$H/_gate_now.tsv" "$BASE"; echo "[gate] baseline updated ($(wc -l < "$BASE") docs)"; exit 0
fi
if [[ ! -f "$BASE" ]]; then
  cp "$H/_gate_now.tsv" "$BASE"; echo "[gate] baseline created ($(wc -l < "$BASE") docs); re-run to compare"; exit 0
fi

python3 - "$BASE" "$H/_gate_now.tsv" "$H/_hancom_pages_for_gate.json" <<'PY'
import sys,json,os
base={l.split("\t")[0]:l.strip().split("\t")[1:] for l in open(sys.argv[1]) if l.strip()}
now ={l.split("\t")[0]:l.strip().split("\t")[1:] for l in open(sys.argv[2]) if l.strip()}
hc=json.load(open('/tmp/diff/_hancom_pages.json')) if os.path.exists('/tmp/diff/_hancom_pages.json') else {}
regress, improve, ov_new = [], [], []
for d,(bp,bov) in base.items():
    if d not in now: continue
    np,nov=now[d]
    h=str(hc.get(d,''))
    if np!=bp:
        # moved toward oracle = improve; away = regress
        if h and abs(int(np)-int(h))<abs(int(bp)-int(h)): improve.append((d,bp,np,h))
        elif h and abs(int(np)-int(h))>abs(int(bp)-int(h)): regress.append((d,bp,np,h))
        else: regress.append((d,bp,np,h))  # unknown direction = treat as regress (safe)
    if int(nov)>int(bov): ov_new.append((d,bov,nov))
print(f"[gate] docs={len(now)} improved={len(improve)} regressed={len(regress)} new_overflow={len(ov_new)}")
for d,b,n,h in improve:  print(f"  IMPROVE  {d}: {b}->{n} (oracle {h})")
for d,b,n,h in regress:  print(f"  REGRESS  {d}: {b}->{n} (oracle {h})")
for d,b,n in ov_new:     print(f"  +OVERFLOW {d}: {b}->{n}")
sys.exit(1 if (regress or ov_new) else 0)
PY
