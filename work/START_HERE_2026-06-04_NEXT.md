# START HERE — rhwp fidelity handoff (2026-06-04 #5, overnight loop: 4 clean wins incl. a content-loss recovery)

Invoke `rhwp-fidelity-fix`. Work in `worktree-rhwp-poc/rhwp`, branch `mindlogic/feat/trust-lineseg-cache`.
**LOCAL ONLY — no deploy/push until Jaeho says "deploy."** Tree clean (this file untracked).
Binary = HEAD `dcebfaba` (45 local commits). Corpus /tmp/diff/ (ephemeral; reboot wipes — [[tmp-diff-ephemeral-reboot-wipe]]).
Baseline updated (142 docs). Gate green (0 regress / 0 overflow).
**Build/gate need network for rustup toolchain sync → run docker commands with Bash `dangerouslyDisableSandbox: true`** (plain sandbox → TLS handshake EOF).

## LANDED THIS SESSION (3 clean, visually-verified, byte-diff-bounded, 0 regressions each)
- `38cb590b` **sa double-count coordinated fix** — [[sa-double-count-pagebottom]]. typeset computes
  `sa_baked_paras`, render reads via `set_sa_baked_paras` (mirrors hidden_empty_paras). wc04 6→5,
  wild_03 257→255, +3 overflow reductions, 0 regress.
- `6c27619e` **TAC single-table flush sub-line tolerance** — [[wc20-tac-flush-tolerance]]. 4px
  (LAYOUT_DRIFT_SAFETY_PX) tolerance at typeset_table_paragraph flush. wc20 4→3 exact.
- `dca34b02` **narrow Square float → next-anchor vpos advance** — [[wc35-square-table-sideflow]]. wc35
  18→16, byte-diff ONLY wc35 changed.
- `dcebfaba` **tac TopAndBottom block table → font-based host line height** — [[wc33-tac-topbottom-offcanvas]].
  CONTENT RECOVERY: wc33 p1 body table was rendering OFF-CANVAS (gate blind 2=2). A tac TopAndBottom
  !inline table baked its height into the host composed line → render advanced the host PP by a full
  table-height before drawing the Table. Fix = extend the existing inline-Shape font-lh correction
  (paragraph_layout.rs `has_tac_shape` branch) to `has_block_tac_table`. Byte-diff: 4 docs changed
  (wc33 fixed + form_24/25/large_01 — all visually verified vs Hancom, no overlap/regression).

## RENDER-FIDELITY: corpus COMPREHENSIVELY validated (full GT coverage now)
Fetched Hancom GT for the 10 previously-ungated docs (form_16/17/23/26/27, med_01/02/03, huge_01/02 —
via `eval/scripts/fetch_hancom.py`, the Hancom cloud API; all page-counts match oracle). Strict visual
sweeps now cover ~60 docs across the corpus. Content-loss defects found total = TWO:
- **wc33** → ✅ FIXED (`dcebfaba`).
- **med_02 p3** → 🔴 [[med02-photo-float-table-hidden]] — "실험결과" table invisible: two full-page
  scanned-photo floats (그림 tac=false vpos=0) sit stacked on p2 and the table is drawn BEHIND them
  (p3 blank); Hancom paginates one photo/page + table on p3. Root = full-page image float doesn't
  paginate one-per-page / reserve its page. DEEP structural float-pagination (NOT a narrow mechanism
  reuse like wc33), high-blast, edge-case scanned-photo doc — supervised-only. Family of
  [[wc47-fullwidth-square-float-reserve]] / [[wc67-float-dual-paginator]].
Everything else clean or documented-cosmetic (rasterizer aspect/squash, line-height, glyph-tofu PUA,
net-zero sub-page flow). The render-fidelity hunt is EXHAUSTED.

## DEEP FAMILIES — all triaged & banked this session (supervised-only, gate visually blind on ~50 unstaged)
- **Table host trailing-gap** ❌ATTEMPTED+REJECTED (see [[sa-double-count-pagebottom]] tail): excluding
  the table trailing gap (sa+host_line_spacing) from the FIT regressed wb20 13→12 (under-doc needs the
  spill), helped wb15 nada. Over-doc vs under-doc need opposite treatment = the report_form/form_24
  tangle. DO NOT re-try.
- **wc67** -2 + 36 overflow = float dual-paginator divergence [[wc67-float-dual-paginator]].
- **wc35 residual +1** = wider-Square / empty-para line-metric (display-vs-pagination divergence, the
  doomed line-metric family).
- **wc04 residual 5≠4** = image-block height; **wc42/44/45 + wc13/15/16/17/23/58** = stale-cache
  family; **wild_07** = cumulative boundary tolerance (diff=0 every para); **wc62** = STALE ledger
  (renders 9=9 now); **wc69** = image/shape (NOT table); **large_01/wc67/form_07/wb15/wb17/wb18/wb20**
  = cell/table-row over-measure (per-TABLE host-spacing, the sa tangle — not per-row, not tractable).
- **Clean (render-swept, no content defect):** wc01 02 09 10 11 21 26 30 39 40 41 46. (wc30 p3 bar
  chart horizontal = faithful to source `barDir=bar`; Hancom deviates.)

## NEXT MOVE
Both the tractable page-count queue AND the render-fidelity (content-loss) hunt are EXHAUSTED. 4 clean
wins landed; full-corpus GT coverage + ~60-doc strict sweep done. Everything remaining is a DEEP family
(supervised-only, high-blast, gate visually blind):
1. **med_02 photo-float** [[med02-photo-float-table-hidden]] — the one remaining content-loss bug;
   structural float-pagination (full-page image floats should paginate one-per-page + reserve their
   page), family of [[wc47-fullwidth-square-float-reserve]]. Highest-value but high-blast — instrument
   the float path, narrow it, gate + byte-diff + visual on every float doc it touches. SUPERVISED.
2. Page-count deep families (all banked): image-block height [[large01-cell-undermeasure]], stale-cache
   cover [[report-form-sb-zeroing]], float dual-paginator [[wc67-float-dual-paginator]],
   table-host-spacing sa-tangle [[sa-double-count-pagebottom]], wc35-residual line-metric.
3. Else corpus is ship-acceptable [[rhwp-corpus-ship-readiness]] — await Jaeho's "deploy".

## Discipline + build
LOOK first; SVG-verify drops; byte-diff every high-blast change (`/tmp/diff/_hashrender.sh`, stash to
build clean HEAD, diff hashes — caught that wc35 changed only wc35). DECIDE don't ask. ~3 builds/doc
then bank+move. Reject on ANY gate regression (revert uncommitted with `git checkout -- <file>`). No deploy/push.
Build: `CARGO_BUILD_JOBS=1 docker compose --env-file .env.docker run --rm dev cargo build --release --bin rhwp` (sandbox OFF).
Gate: `bash harness/gate.sh` / `--no-build` / `--update-baseline` (sandbox OFF). Look: `python3 harness/look.py /tmp/diff/<doc> --export`.
Commit msgs end: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
