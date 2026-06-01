# Overnight rhwp fidelity loop — handoff prompt (2026-06-02)

You are continuing the rhwp HWP/HWPX render-fidelity campaign. Invoke the
`rhwp-fidelity-fix` skill first and follow it. Work autonomously for hours.

## Hard rules (non-negotiable)
- **LOCAL-FIRST, DO NOT DEPLOY.** No WASM build-for-deploy, no rsync to factchat
  static/, no Vercel. Native only: `docker compose --env-file .env.docker run --rm
  -e CARGO_BUILD_JOBS=1 dev cargo build --release --bin rhwp` → `dump-pages` /
  `export-svg` → gate → look. Branch: `mindlogic/feat/trust-lineseg-cache`.
- **The winning loop (proven today on form_22 + doc 13):** for each doc —
  1. LOOK FIRST: `python3 harness/look.py /tmp/diff/<doc> --export`, read the
     stitched `look/page-NN.png` (delegate the page-reading triage to a subagent to
     keep context lean — have it return the slip page + defect class).
  2. PROBE THE EXACT VALUE. Don't theorize from the dump. Use the built-in
     `RHWP_TABLE_DRIFT=1` env (prints eff_h/mt_sum/cut_sum/cur_h + TABLE_SPLIT_AVAIL/
     RESULT per table) or an env-gated `RHWP_*_DIAG` probe. **The live paginator is
     TypesetEngine in `src/renderer/typeset.rs`, NOT pagination/engine.rs** (that only
     runs under RHWP_USE_PAGINATOR=1 — probes there are dead).
  3. NARROWEST STRUCTURAL FIX (keys on geometry/linesegs/flags, never doc text —
     `fingerprint_lint.py` enforces this).
  4. GATE: `bash harness/ralph.sh verify` must print **ALL-GREEN** (improved≥1,
     regressed=0, new_overflow=0, held-out OK). RED → `git checkout -- src/` and
     try narrower, or bank + move on.
  5. VISUAL-VERIFY the changed pages: re-run look.py, READ the changed `page-NN.png`,
     confirm they match Hancom (left col). Page count ≠ done.
  6. Strip probes (`grep -rn "_DIAG\|RHWP_F" src/` clean), update
     `harness/baseline_pc.tsv` + `harness/queue.tsv`, commit LOCAL.
- **~3 builds per doc.** If a doc resists a clean+gated fix after ~3 builds, write a
  sharp queue/memory note and MOVE ON. Don't sink 10 builds into one.
- **The lesson that worked today:** both form_22 and doc 13 looked like scary
  "high-risk families" in the notes, but probing the exact overflow value + looking at
  Hancom's actual page revealed each was a surgical few-px fit. DON'T pre-defer a doc
  as a "hard cluster" before you've probed the exact wrong value and looked at Hancom.

## State (verify with the python snippet below)
69/74 docs at oracle. 5 OFF. Today landed: form_22 38→37 (44e8b2c7), doc 13 20→19
(6063881d). Read `harness/queue.tsv` for per-doc diagnoses, and these memories:
`single-col-vpos-reset-418-tradeoff`, `rhwp-dead-leads`, `report-form-sb-zeroing`,
`large01-cell-undermeasure`, `dont-defer-fix-one-by-one`, `look-py-vision-loop`,
`done-means-visually-validated`.

Check current OFF set:
```
cd worktree-rhwp-poc/rhwp && python3 - <<'PY'
import json; o=json.load(open("harness/hancom_pages.json"))
for l in open("harness/baseline_pc.tsv"):
    p=l.split("\t");
    if len(p)<2 or p[0].startswith("#"): continue
    if str(p[1])!=str(o.get(p[0])): print("OFF",p[0],"rhwp="+p[1],"oracle="+str(o.get(p[0])))
PY
```

## Targets, in priority order

1. **form_03_signup_consent_form (rhwp=2, oracle UNKNOWN) — DO THIS FIRST, cheapest.**
   Its oracle isn't in hancom_pages.json — it may already be correct. Stage source
   (`hwpx-lab/samples_wild/form_03_signup_consent_form.hwpx`), regenerate Hancom GT
   (`.claude/skills/rhwp-fidelity-fix/scripts/run_diff.py <file>`), run look.py. If
   rhwp matches Hancom → record the oracle in hancom_pages.json + baseline, mark done
   (likely a free win / bookkeeping gap). If off → triage + fix.

2. **form_07 (12/11) — best-scoped of the genuinely-hard ones.** Diagnosis is
   DONE (queue note): NOT cache-inflation, NOT line-height, NOT reflow (single-pass).
   Real anomaly: pi=89 (단기목표 4-row table) measures **397.2 in the fit context but
   409.0 in the split/continuation context**; the smaller fits whole on p9 (→ correct
   11pp), the larger splits p9/p10 and pushes the 출생관련 nutrition table off p10 → +1.
   Next step: instrument `typeset_block_table` (typeset.rs ~3674) — compare
   `ft.effective_height` (→397.2) vs the cut path `row_cut_content_height`/`cut_row_h`
   sum (→409.0) for pi=89, find the 11.8px source (header-repeat? padding? cell vs
   content), decide which matches Hancom (Hancom fits 단기목표 tail + nutrition on ONE
   page p10), reconcile. HIGH-BLAST (cut path drives every table split) → gate hard +
   visual-verify form_25/27/huge_01/02/med_03/large_01 (all in the gate set).

3. **large_01 (37/39, UNDER-paginate)** — in-cell diagram height under-measured in big
   2x2 TopAndBottom tables → cells too short → packs too much. See
   `large01-cell-undermeasure` memory. Deep cell-height work; probe the in-cell
   diagram measurement. 16MB doc, slow to render.

4. **report_form (5/6)** — KNOWN DEAD-END, lowest priority. 8+ prior cycles; the
   sb/gap/column discriminator family is provably doomed (form_24 counterexample).
   Only untried lead: stop rejecting the vpos-snap (instrument WHY applied=false via
   RHWP_VPOS_DEBUG at height_cursor.rs:203). Risky; needs visual pass on ~60 docs.
   Skip unless the others are exhausted. See `report-form-sb-zeroing`.

5. **accountability_eval (4/11)** — needs a NEW capability (wide-table width-fit +
   reflow: Hancom width-fits & re-wraps wide tables; rhwp draws literal). This is a
   feature, not a fix — likely defer; only scope it out if everything else is done.

## Gotchas
- Sources get cleaned from `/tmp/diff/<doc>/`. Restore from
  `hwpx-lab/samples_wild/` (native .hwpx) or `mindlogic_factchat_server/hwpx_prod_samples/`,
  or for .hwp-origin docs regenerate via run_diff.py. look.py needs `source.hwpx` in the
  dir (for .hwp-origin, the PRODUCTION input is `source_converted.hwpx` — copy it to
  `source.hwpx`; rhwp rendering the raw .hwp binary gives wrong results, segs=0 parser).
- `dump-pages` "used=" metric LIES on TopAndBottom/PartialTable pages — use SVG max-y
  or render, not the metric, to judge real fill.
- The rhwp binary is Linux/docker-only (exec format error natively). All invocations via
  docker. `timeout` is unavailable on macOS host.
- Commit messages end with: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

## Definition of done per doc
lint clean AND `ralph.sh verify` ALL-GREEN (≥1 improved, 0 regressed) AND changed pages
visually match Hancom. Then update baseline_pc.tsv + queue.tsv + relevant memory, commit
LOCAL. NEVER deploy. At the end, write `work/MORNING_STATUS_<date>.md` with what landed,
before/after page counts, and the next targets.
