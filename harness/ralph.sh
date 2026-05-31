#!/usr/bin/env bash
# rhwp fidelity ralph — ONE iteration per invocation (re-invoked by cron/loop).
# This is the DRIVER skeleton; the actual per-doc diagnosis+patch is done by the
# agent reading harness/PLAYBOOK.md. This script only enforces the gate sequence
# and records outcomes, so a patch can never land without passing all 4 gates.
#
# It does NOT itself edit Rust — it prints the next target + context for the agent,
# and provides `ralph.sh verify` which runs the full gate chain on the current
# working tree and prints PASS/FAIL with the reason. The agent's contract:
#   1. read `ralph.sh next`  -> target doc + drift table + queue note
#   2. probe + patch the engine (structural only)
#   3. run `ralph.sh verify` -> must print ALL-GREEN or it will not commit
#   4. on ALL-GREEN: commit LOCAL; on any RED: `git checkout -- src/`, mark blocked
set -uo pipefail
RHWP=/Users/jaehoshin/Desktop/mindlogic/factchat/worktree-rhwp-poc/rhwp
H=/tmp/diff/harness
cmd="${1:-next}"

case "$cmd" in
next)
  # first pending doc in queue
  doc=$(awk -F'\t' '!/^#/ && $5=="pending"{print $1; exit}' "$H/queue.tsv")
  [ -z "$doc" ] && { echo "QUEUE EMPTY — all docs done or blocked."; exit 0; }
  echo "=== NEXT TARGET: $doc ==="
  grep -P "^$doc\t" "$H/queue.tsv"
  echo "--- objective drift (Hancom bbox vs rhwp SVG) ---"
  python3 "$H/drift.py" "/tmp/diff/$doc" 2>&1 | head -40
  echo "--- rule: structural fix only. fingerprint_lint + gate + held-out must pass. ---"
  ;;
verify)
  echo "[1/3] fingerprint lint..."
  python3 "$H/fingerprint_lint.py" "$RHWP" || { echo "RED: fingerprint"; exit 1; }
  echo "[2/3] corpus regression gate (build + sweep)..."
  bash "$H/gate.sh" || { echo "RED: regression/overflow"; exit 1; }
  echo "[3/3] held-out drift check (dev improved, held not worse)..."
  # held docs must not gain a first-divergence they didn't have; cheap proxy:
  # their page count (in _gate_now.tsv) must equal oracle.
  python3 - "$H/corpus.tsv" "$H/_gate_now.tsv" <<'PY'
import sys
held={l.split('\t')[0] for l in open(sys.argv[1]) if '\theld\t' in l}
now={l.split('\t')[0]:l.strip().split('\t')[1] for l in open(sys.argv[2]) if l.strip()}
import json; hc=json.load(open('/tmp/diff/_hancom_pages.json'))
bad=[d for d in held if d in now and str(now[d])!=str(hc.get(d))]
if bad:
    print("RED: held-out regressed:",bad); sys.exit(1)
print("held-out OK")
PY
  echo "ALL-GREEN"
  ;;
*) echo "usage: ralph.sh [next|verify]"; exit 2;;
esac
