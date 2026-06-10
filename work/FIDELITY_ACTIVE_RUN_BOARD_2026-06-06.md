# RHWP Fidelity Active Run Board -- 2026-06-06

Use this board for the next multi-hour renderer run. It supersedes stale
`_gallery3`-based target selection. Hancom/licensed output is still the oracle,
but evidence must come from the current no-crop review gallery or freshly
regenerated artifacts.

## Current Authority

- Active review: `/tmp/diff/_review_active_2026-06-06/index.html`
- Current page-count gate:

```text
bash harness/gate.sh --no-build
[gate] docs=151 improved=6 regressed=0 new_overflow=0
  IMPROVE form_07_______________41KB: 12->11 (oracle 11)
  IMPROVE wc15_7pg: 6->7 (oracle 7)
  IMPROVE wc16_6pg: 5->6 (oracle 6)
  IMPROVE wc17_6pg: 5->6 (oracle 6)
  IMPROVE wc31_17pg: 12->17 (oracle 17)
  IMPROVE wc35_15pg: 16->15 (oracle 15)
```

Do not treat old rows in `work/fidelity_target_queue_2026-06-05.tsv` as current
page-count failures unless the active board or a fresh rerender confirms them.

## Fastest Reliable Loop

1. Pick exactly one family and one first-divergent page.
2. Confirm the failure with current no-crop visual evidence.
3. Extract page-boundary text or dump evidence to locate the first divergence.
4. Add diagnostics behind an env var when needed; do not change behavior yet.
5. Try one structural rule only if the discriminator is geometry/control based.
6. If the probe does not move the target, revert the behavior and keep the note.
7. Accept only after:
   - target improves,
   - no new page-count regression,
   - no new overflow,
   - `python3 scripts/check_renderer_overfit.py` passes,
   - `bash harness/gate.sh --no-build` passes,
   - changed docs are visually reviewed on a no-crop board.

Three failed probe/build cycles in one family means bank the diagnosis and move
to the next family.

## Active Categories

### P1: Multi-column float/page-count failure

Target:

- `wild_02_paper_fig_10MB`
- Oracle/current: Hancom 9 / RHWP 7
- Fresh review: `/tmp/diff/_review_active_2026-06-06/wild_02_paper_fig_10MB/index.html`
- Current diagnosis: `work/P1_WILD02_FLOAT_DIAGNOSIS_2026-06-05.md`

First confirmed boundary error:

- Hancom page 1 ends before the final intro tail beginning `연조직부터...`.
- Hancom page 2 starts with that tail, then section `2. Viscoelasticity...`.
- RHWP page 1 already contains the tail sentence and page 2 starts directly at
  section `2. Viscoelasticity...`.

Rejected probes:

- Render-cursor exception for non-TAC `TopAndBottom` picture: visual local
  improvement but broad gate created DNA/wc26 overflows.
- Same-paragraph host-text pre-jump: local improvement but same broad overflow
  family.
- Cross-column `Square` next-column obstruction reserve: changed page-1 used
  height but page count stayed 7 and the same `pi=2` lines stayed on page 1.
- Skip first inline `ColumnDef` as section initial layout: changed RHWP to
  11 pages versus Hancom 9 and made the whole document too one-column.
- Pre-reserve a top-of-column body-wide `TopAndBottom` object before paragraph
  text: compiled and rendered, but page count stayed 7 and the page-1 visual was
  effectively unchanged.

Accepted partial:

- Top-aligned narrow non-TAC `TopAndBottom` objects now reserve a column band in
  both typeset and render layout. This moved `wild_02` page-1 content lower and
  closer to Hancom without page-count regressions, but it did not fix the
  remaining 9/7 page-count drift.
- Focus board:
  `/tmp/diff/_review_wild_02_topaligned_topbottom_band_2026-06-06/index.html`
  with gallery audit passing.
- Focus tests:
  `top_aligned_narrow_topbottom_float_reserves_column_band` and
  `body_wide_reserved_accepts_top_aligned_narrow_topbottom_float`.

Next useful evidence:

- Compare actual rendered line boxes for paragraph `pi=2` between Hancom PDF
  and RHWP SVG after the accepted top-band change. Dump-pages line segments show
  full `cs=0 sw=38124`; the missing rule is not pre-narrowed line segments.
- The remaining target is the line-fit/page-break decision for `pi=2` column 1:
  RHWP still assigns lines `19..35` to page 1, while Hancom pushes the tail
  beginning `연조직부터...` to page 2.

Guard docs:

- `wc47_6pg`
- `wc51_4pg`
- `wc69_9pg`
- `wc04_4pg`
- `wb03_physics_lab_2pg`
- `huge_01_DNA________33MB`
- `huge_02_DNA_______75MB`
- `wc26_3pg`

### P2: Visual QA after page-count clean

Targets:

- `wc31_17pg`: page-count clean, residual evidence-page visual drift.
- `wc35_15pg`: page-count clean, residual Square formula/table y-placement
  drift around pages 7-8.

Rule:

- Do not spend page-count-fix cycles here unless a fresh board regresses.
- Work these only after `wild_02`, or when the user explicitly prioritizes
  visual polish over page-count blockers.

### P3: Table fit / production preprocessor lane

Targets:

- `accountability_eval`
- `large_01_____________16MB`
- over-wide government/form tables

Rule:

- First reconcile source/oracle mismatch.
- Prefer upload-time HWPX fitting for over-wide tables unless renderer evidence
  points to a structural row/cell height bug.
- Export/reopen validation is mandatory for preprocessor changes.

## Validation Ladder

Use the smallest proof that matches the claim:

```bash
python3 scripts/check_renderer_overfit.py
docker compose --env-file .env.docker run --rm dev cargo test --lib <focused-test> -j 1 -- --nocapture
docker compose --env-file .env.docker run --rm dev cargo build --release -j 1
bash harness/gate.sh --no-build
python3 harness/audit_review_gallery.py /tmp/diff/_review_active_2026-06-06
```

For visual claims, regenerate a focused no-crop board:

```bash
python3 harness/review_gallery.py /tmp/diff/_review_<name> <doc> --export-current
python3 harness/audit_review_gallery.py /tmp/diff/_review_<name>
```

## Anti-overfit Contract

Renderer code may branch on:

- control type,
- wrap mode,
- treat-as-character,
- anchor relation,
- line segment geometry,
- page/body/column geometry,
- table/row/cell dimensions,
- measured visual extents.

Renderer code must not branch on:

- document filename,
- body/title text,
- exact fixture paragraph text,
- page number alone,
- fixture-specific paragraph/control indices outside tests or diagnostics.
