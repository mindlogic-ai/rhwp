# RHWP Fidelity Hours Runbook — 2026-06-05

Use this when the task is: run for hours, validate quickly, improve visible
render fidelity, and avoid fixture monkeypatches.

## One Command To Pick Work

```bash
cd /Users/jaehoshin/Desktop/mindlogic/factchat/worktree-rhwp-poc/rhwp
python3 work/fidelity_queue.py
python3 work/fidelity_queue.py --target wild_02_paper_fig_10MB
```

Use `work/FIDELITY_GAP_FOCUS_2026-06-05.md` as the concrete failure-family
map. It records the current P0-P4 priorities, exact visual artifacts,
dump-pages evidence, structural XML discriminators, and the recommended
four-hour execution order.

Use `work/FIDELITY_COMMON_PATTERNS_2026-06-05.md` as the longer category
matrix. It maps each common failure pattern to representative docs/pages/images,
likely owner files, safe discriminators, fast validation commands, and
land/bank/revert rules.

The detailed target output gives:
- the exact page/range to inspect,
- the visual gallery artifacts to open first,
- the renderer files that probably own the behavior,
- guard docs that must not regress,
- validation commands,
- acceptance criteria.

## First 30 Minutes

1. Start with a P1 image/float target:
   `wild_02_paper_fig_10MB` or `med_02____2_4MB`.
2. Open the target visual artifact from the queue.
3. Write down the structural shape:
   - inline vs floating vs treat-as-character,
   - wrap mode: Square, TopAndBottom, BehindText, InFrontOfText,
   - anchor base: page, paragraph, cell,
   - declared image/table size vs available body area,
   - whether following flow content paints behind the object.
4. Run native build and the narrow gate before editing:

```bash
CARGO_BUILD_JOBS=1 docker compose --env-file .env.docker run --rm dev \
  cargo build --release --bin rhwp
bash harness/focus_gate.sh quick --build
python3 scripts/check_renderer_overfit.py
```

Do not build WASM/studio in this loop.

Current baseline from 2026-06-05:

```text
bash harness/focus_gate.sh quick --build
focus tier=quick: docs=15 improved=0 same=7 regressed=0 missing=8 new_overflow=0
DIFF form_07_______________41KB: 12/11
MISSING 15_3740450_research_admin_innovation_meeting_template
MISSING 20_3727659_resume_2605_ai
MISSING accountability_eval
MISSING meeting
MISSING meeting_summary
MISSING overseas_training
MISSING report_form
MISSING 05_3781559_medschool_car_2bu_je_plan
```

This means the first validation cleanup is not renderer code: restore or
regenerate the missing quick fixtures before treating quick-gate coverage as
complete. Until then, use the available gallery artifacts for those missing
docs as visual evidence and do not claim full quick-corpus proof.

2026-06-05 fixture staging update:
- Seven missing quick fixtures were found and staged into `/tmp/diff`.
- Re-run `bash work/stage_focus_fixtures.sh` to recreate that local staging.
- Exact source/path/status is tracked in `work/focus_fixture_sources_2026-06-05.tsv`.
- `meeting` remains missing; do not alias it to `wb12_gangjin_meeting_4pg`
  because their expected page counts differ.
- `05_3781559_medschool_car_2bu_je_plan` is a suspect variant: the staged
  licensed `_doc.hwpx` renders 3 pages, while focus expects 4. It likely needs
  a Hancom conversion from the original `.hwp` sample before use.
- Restored docs expose overflow markers that were previously hidden by
  missing fixtures. Treat those as validation-surface findings, not necessarily
  regressions from the current renderer patch until compared against a clean
  baseline run with the same staged sources.

After staging, current quick gate is:

```text
bash harness/focus_gate.sh quick --build
focus tier=quick: docs=15 improved=1 same=12 regressed=1 missing=1 new_overflow=5
IMPROVE report_form: 5->6 oracle=6
DIFF 15_3740450_research_admin_innovation_meeting_template: 6/5
DIFF accountability_eval: 4/11
DIFF form_07_______________41KB: 12/11
REGRESS 05_3781559_medschool_car_2bu_je_plan: 4->3 oracle=4
+OVERFLOW 20_3727659_resume_2605_ai: 0->1
+OVERFLOW accountability_eval: 0->3
+OVERFLOW meeting_summary: 0->2
+OVERFLOW overseas_training: 0->2
+OVERFLOW report_form: 0->1
MISSING meeting
```

Interpretation:
- This is a better quick gate than the previous "missing 8" state because 14/15
  docs now render.
- It is not yet a passing gate.
- `05_3781559...` must be restaged from the original HWP via Hancom HWP->HWPX
  conversion or removed from quick until the correct HWPX is found.
- Overflow baselines for the restored docs need recalibration only after a
  clean baseline branch run with the same staged sources.

2026-06-05 accountability_eval oracle update:
- Fresh Hancom conversion of `/tmp/diff/accountability_eval/source.hwpx`
  produced `/tmp/diff/accountability_eval/hancom.pdf` with 6 pages.
- `harness/look.py /tmp/diff/accountability_eval --export` produced
  `/tmp/diff/accountability_eval/look/page-01.png` through `page-06.png`.
- The staged source is therefore Hancom 6 / rhwp 4, while the focus manifest
  still expects Hancom 11 / rhwp 4. Treat this as a source/oracle mismatch
  before changing table layout code for the 11-page target.
- The staged-source visual defect is still real: rhwp clips/overpacks the
  over-wide table horizontally and under-paginates it.

2026-06-05 P0 fixture reconciliation:
- Details are recorded in `work/P0_FIXTURE_RECONCILIATION_2026-06-05.md`.
- `meeting` remains missing; no exact local source was found under the bounded
  known trees.
- `05_3781559_medschool_car_2bu_je_plan` is not a current-patch regression:
  the same staged source renders 3 pages on clean HEAD `dcebfaba` and on the
  current patch, while the cached Hancom PDF has 4 pages. The quick baseline's
  rhwp=4 value is stale for this staged source.
- Until P0 is resolved, treat `focus_gate.sh quick` as informative but not a
  clean blocking gate. Keep using `harness/gate.sh --no-build` plus visual
  changed-doc review for landing decisions.

2026-06-05 broad gate after P0 reconciliation:

```text
bash harness/gate.sh --no-build
[gate] docs=149 improved=1 regressed=0 new_overflow=0
  IMPROVE  wc31_17pg: 12->13 (oracle 17)
```

Interpretation:
- The current page-relative scanned-photo patch has no broad page-count
  regression and no new overflow against the full baseline.
- The `wc31_17pg` improvement is a side-effect toward the oracle, but it is not
  a visual fix claim for `wc31`; inspect before using it as product evidence.
- The focus quick gate remains noisy because of unresolved P0 fixture metadata.

2026-06-05 `wild_02_paper_fig_10MB` diagnosis:
- Details are recorded in `work/P1_WILD02_FLOAT_DIAGNOSIS_2026-06-05.md`.
- This is not the same family as `med_02`. `wild_02` uses paragraph-relative,
  column-relative flowing pictures with `TOP_AND_BOTTOM`/`SQUARE` wraps, not
  page-relative full-page scanned images.
- Page 1 shows a missing cross-column/top-band reserve: Hancom starts content
  much lower while rhwp starts at the top and overlaps the figure into the
  right column.
- Page 9 exists in Hancom but not in rhwp, so the fix must preserve late
  logical content, not merely reduce page-1 overlap.
- Bank rather than patch if no narrow cross-column float-reserve discriminator
  appears after three probe/build cycles.

## First 2 Hours

Stay inside one family. Do not bounce between unrelated docs.

For image/float:
- Patch only geometry/anchor/wrap behavior.
- Never branch on filename, document text, or title.
- After every hypothesis, run:

```bash
bash harness/focus_gate.sh quick --build
python3 scripts/check_renderer_overfit.py
```

If the quick gate improves the target, run:

```bash
bash harness/gate.sh --no-build
```

Then inspect all changed docs in `/tmp/diff/_gallery3`, not only the target.

## Hourly Bank / Land / Revert Decision

LAND only when all are true:
- target defect improves visibly,
- page count moves toward Hancom or stays correct,
- no new overflow,
- no unrelated page-count regression,
- changed docs are visually checked,
- `scripts/check_renderer_overfit.py` passes.

BANK the diagnosis when:
- three build/probe cycles fail to find a structural discriminator,
- the fix would need a broad rule that affects many correct docs,
- the visual defect is real but the right abstraction is unclear.

REVERT immediately when:
- a text-only or unrelated green doc changes page count,
- a new image/table overlap appears,
- content disappears,
- the only working condition is document-specific.

## Category Order

1. Image/float content loss and overlap.
   These are hard production blockers because users see missing content.
2. Stale vpos / empty spacer / line segment cache drift.
   These explain many page-count misses but carry higher blast radius.
3. Wide table fit and table height.
   Prefer upload-time HWPX fitting for over-wide tables unless the renderer
   rule is structural and measured.
4. Export/reopen.
   Run after each category fix. HWPX reopen is the production gate; HWP export
   stays gated by document class until reload is proven.

## What Counts As General

General renderer fixes may depend on:
- object/control type,
- wrap mode,
- anchor mode,
- treat-as-character,
- line segment/vpos geometry,
- available page/body/column area,
- declared vs measured object/table extents.

General renderer fixes may not depend on:
- filename,
- fixture slug,
- exact body text,
- exact page number alone,
- hand-picked paragraph indices outside a test/probe.

## Production Readiness Interpretation

Visible-only rhwp is not ready for arbitrary wild docs until P1 image/float and
P2 drift classes stop causing content loss and logical page drift.

The practical production architecture is still hybrid:
- Hancom licensed iframe is the visible renderer,
- rhwp is the hidden parser/edit/export engine,
- exported HWPX must reopen in Hancom before the edit is considered safe.

This runbook improves both paths: visible rhwp gets closer, and hidden rhwp
becomes safer because export/reopen is checked after layout-sensitive changes.
