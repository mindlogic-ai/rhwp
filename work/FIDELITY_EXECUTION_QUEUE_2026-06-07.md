# RHWP Fidelity Execution Queue - 2026-06-07

Purpose: run the renderer-fidelity loop for hours without drifting into
random patches. This queue is for the current visual-drift state after the
page-count fixes: all three focus docs have matching page counts, but visible
Hancom fidelity is still not production-grade.

## Current Baseline

Visual authority:

```bash
python3 harness/fidelity_category_status.py --with-gallery --out work/FIDELITY_VISUAL_STATUS_2026-06-07.md overseas_training accountability_eval 15_3740450_research_admin_innovation_meeting_template
```

Current board:

| doc | class | Hancom | RHWP | worst page | mean diff |
|---|---:|---:|---:|---:|---:|
| overseas_training | visual_drift | 4 | 4 | 1 | 24.74 |
| accountability_eval | visual_drift | 6 | 6 | 4 | 16.84 |
| 15_3740450_research_admin_innovation_meeting_template | visual_drift | 5 | 5 | 3 | 23.38 |

Gallery pages:

- `/tmp/diff/_review_category_status_2026-06-07_overseas_training/index.html`
- `/tmp/diff/_review_category_status_2026-06-07_accountability_eval/index.html`
- `/tmp/diff/_review_category_status_2026-06-07_15_3740450_research_admin_innovation_meeting_template/index.html`

## Fastest Loop

1. Work category-by-category, not document-by-document.
2. Use one worst page as the probe target and two other docs as immediate
   visual guards.
3. Run SVG-only probes first when the hypothesis is paint/scale/positioning.
   Do not rebuild Rust for every guess.
4. Patch Rust only after a probe improves the target without obvious harm on
   guard pages.
5. Add a structural test for the rule. Tests may use fixture text as an oracle
   assertion; renderer code may not.
6. Gate every kept patch with:

```bash
docker compose --env-file .env.docker run --rm dev cargo test --lib <focused_test> -j 1 -- --nocapture
docker compose --env-file .env.docker run --rm dev cargo fmt --check
python3 scripts/check_renderer_overfit.py
docker compose --env-file .env.docker run --rm -e CARGO_BUILD_JOBS=1 dev cargo build --release --bin rhwp -j 1
bash harness/gate.sh --no-build
python3 harness/fidelity_category_status.py --with-gallery --out work/FIDELITY_VISUAL_STATUS_2026-06-07.md overseas_training accountability_eval 15_3740450_research_admin_innovation_meeting_template
```

## Non-Monkeypatch Contract

Allowed renderer discriminators:

- font family class and measured local availability
- paint backend behavior such as rasterized stroke width or text scale
- table border/cell geometry and declared-vs-measured row/cell dimensions
- paragraph, table, picture, wrap mode, TAC, anchor, and page/body geometry
- line segment/cache geometry, vpos shape, and repeat-header/page-break flags

Forbidden renderer discriminators:

- filename, document id, fixture id
- body text/title strings
- single page number without a structural condition
- paragraph/cell indices in production code
- any condition whose only proof is "this one fixture looks better"

## Priority A - Table-Heavy Visual Metric Calibration

Targets:

- `15_3740450_research_admin_innovation_meeting_template` page 3
  - Symptom: page count correct, images present, but table block is too low,
    lighter, and vertically looser than Hancom.
- `accountability_eval` page 4
  - Symptom: page count correct, content present, but table/text scale and
    density diverge heavily from Hancom.
- `overseas_training` page 1
  - Guard plus secondary target: table is too light/thin and geometry differs.

Likely code:

- `src/renderer/svg.rs`
- `src/renderer/web_canvas.rs`
- `src/renderer/style_resolver.rs`
- `src/renderer/layout/table_layout.rs`
- `src/renderer/layout/text_measurement.rs`
- `src/renderer/height_measurer.rs`

Probe order:

1. SVG paint probes: black/gray stroke width, text visual size, image/table
   opacity or rasterization effects.
2. Table vertical density probes: row padding, cell paragraph line advance, and
   declared-vs-measured row floors.
3. Only then try anchor/page-flow changes. Previous anchor probes worsened the
   overseas target.

Acceptance:

- The probe improves the chosen target and does not worsen the other two docs.
- The Rust patch uses a structural rendering rule and gets a focused unit test.
- The 3-doc visual board improves or stays neutral on all docs.

## Live Source Refresh - 2026-06-07 Night

Refreshed the current live-source set after the fixed TAC row-grid patch:

```bash
python3 harness/fidelity_category_status.py --with-gallery --out work/FIDELITY_LIVE_SOURCE_STATUS_2026-06-07.md 05_3781559_medschool_car_2bu_je_plan 15_3740450_research_admin_innovation_meeting_template 20_3727659_resume_2605_ai accountability_eval accountability_eval_fitted accountability_eval_fitted_oracle meeting_summary overseas_training report_form
```

Result:

- `05_3781559_medschool_car_2bu_je_plan`: Hancom 4 / RHWP 3, but still excluded
  from renderer patching. Earlier reconciliation shows this staged source also
  renders 3 pages on clean HEAD while the cached Hancom PDF has 4 pages, so this
  needs original-source regeneration or fixture recalibration before use.
- `accountability_eval`: current live target, Hancom 6 / RHWP 6, worst page 3
  mean `16.31`.
- `meeting_summary`: Hancom 3 / RHWP 3, still visual drift after fixed TAC
  row-grid, worst page 1 mean `18.86`; second-pass line/font probes are banked
  because no structural patch candidate emerged.
- `overseas_training`: Hancom 4 / RHWP 4, worst page 1 mean `21.42`; current
  role is guard/secondary target after the host-line and SVG thin-stroke fixes.
- `15_3740450_research_admin_innovation_meeting_template`: Hancom 5 / RHWP 5,
  worst page 3 mean `23.36`; photo-row candidates remain banked/rejected.
- Accepted meeting-template page-3 repeated photo-grid render-area fix. The
  source class is a non-TAC `TopAndBottom` repeated photo-grid table with
  `pageBreak=CELL`, picture-only cells, and picture declarations moderately
  taller than the cell inner box. The previous pagination/row-height candidate
  was correctly rejected because it changed the document from 5 pages to 6
  pages. This accepted patch is render-only: it broadens the render-side
  photo-grid detector to include `CellBreak` while preserving the old
  RowBreak-only predicate for row-height/pagination code, then paints repeated
  photo-grid pictures at declared picture height when the visual excess is
  moderate (`8..32px`), nudged upward by a small fraction of that excess. It
  does not change row heights, cuts, or page count. Probe evidence:
  SVG-only upper image row variants improved page 3 from `23.30` to `22.20`,
  while overseas/accountability/meeting-summary probes were unchanged. Kept
  after focused tests `repeated_photo_picture_fill_area_expands_moderate_visual_excess`
  and `repeated_rowbreak_photo_predicate_is_structural`, `cargo fmt --check`,
  overfit scan, release build, 4-doc visual guard, and `bash harness/gate.sh
  --no-build`. 4-doc board:
  `15_3740450... 23.36 -> 22.38`, `overseas_training 21.42`,
  `accountability_eval 16.31`, `meeting_summary 18.86`, all page counts stable.
- Banked meeting-template page-3 second pass after the photo-grid render-area
  fix. Fresh geometry shows the upper image row now matches Hancom's vertical
  extent closely (`173.9..400.7` vs oracle band ending around `400.6`). The
  remaining lower photo table still has RHWP visible ink bands around `209.9px`
  versus Hancom `226.3px`, but prior pagination/row-height attempts for that
  same class changed the document from 5 pages to 6 pages. A fresh component
  probe after the accepted fix found no safe next renderer rule: base `22.28`,
  hide_text `21.31`, hide_lines `77.99`, stroke-width variants only
  `22.27..22.37`, and font/weight/size variants were small cosmetic shifts
  (`Noto/Pretendard 22.03`, weight_500 `22.10`, font_size_x0.90 `22.16`) that
  overlap already-rejected broad font/paint routes. Do not continue this page
  with stroke/font/row-height tuning unless a new structural discriminator
  appears.
- Rejected accountability page-3 terminal-carried-rowspan render inset
  candidate. Probe evidence was real but not strong enough: throwaway SVG
  shifts on page 3 improved `16.10 -> 15.35` at `+48px`, and adjacent probes
  suggested pages 3/5 like a downward shift while page 2 does not. A narrow Rust
  candidate reserved `0.5 * row_heights[start_row]` only when a continuation
  fragment starts on the final row of a carried rowspan. Focused positive and
  negative helper tests passed, release build passed, and the accountability
  board stayed `6/6`, but document result was effectively flat
  (`16.31 -> 16.30`) and page 4 became worst. Per-page after the candidate:
  p1 `15.04`, p2 `13.21`, p3 `15.88`, p4 `16.30`, p5 `14.25`, p6 `6.77`.
  Reverted. Do not retry a pure top-inset/shift heuristic; the next
  accountability pass needs a pagination/cut rule that explains why Hancom
  carries a shallow row-13 tail onto page 3 without worsening page 4.

Current banked findings:

- Current next-category ranking after the latest probes:
  1. `accountability_eval` page 4 font/rendering parity. This has the clearest
     actionable root signal: `fc-match 'Malgun Gothic'` and `fc-match '맑은 고딕'`
     both fall back to Verdana, while `Noto Sans KR` resolves locally. The
     page-4 audit reports `hancom_dark=57717`, `rhwp_dark=12368`, ratio `0.21`.
     This is not a row-height issue and should be treated as missing/incorrect
     Malgun-compatible font or text rasterizer parity. Guards:
     `overseas_training` page 1 and meeting-template page 3.
  2. `overseas_training` page 1 text/table paint and font availability. It has
     font drift but less severe ink loss (`hancom_dark=90361`,
     `rhwp_dark=67153`, ratio `0.74`) and uses `경기천년바탕 Bold` with existing
     paint-scale/fallback handling.
  3. `15_3740450_research_admin_innovation_meeting_template` page 3 photo-table
     geometry. Many local hypotheses have been rejected below; pause this target
     until a new structural discriminator appears.
- Reusable SVG component probe now lives at:

  ```bash
  python3 harness/svg_component_probe.py --keep --out-dir /tmp/diff/_svg_component_probe_2026-06-07 overseas_training:1 accountability_eval:4 15_3740450_research_admin_innovation_meeting_template:3
  ```

  It writes a TSV with per-variant `mean_diff`, `dark_pixels`, and optional PNG
  paths. Use it before Rust paint/scale patches to avoid rebuilding for guesses.
  Initial 3-page run completed after `python3 -m py_compile
  harness/svg_component_probe.py` passed.
- Fresh 2-doc component probe:

  ```bash
  python3 harness/svg_component_probe.py --keep --out-dir /tmp/diff/_svg_component_probe_next_2026-06-07 accountability_eval:4 overseas_training:1
  ```

  It reconfirms the banked decision. `accountability_eval` page 4: base `16.57`,
  `font_size_x0.90 15.91`, `Noto Sans KR/Pretendard 15.71`, but Noto/Pretendard
  also drops dark pixels to `6438` from base `12368`; broad weight `500/600`
  worsens to `17.00/17.54`. `overseas_training` page 1: base `24.81`,
  `font_size_x0.90 23.97`, `Noto Sans KR/Pretendard 24.18`; thicker strokes
  worsen. Do not land these as CSS-family/weight swaps; use them only as proof
  that text rendering/font availability is the active class.
- Initial probe result preserves the current decision: do not chase thicker
  ruling lines. Thin-stroke expansion worsened all three focus pages
  (`x2.00`: overseas `25.56`, accountability `16.99`, meeting `23.41`), while
  smaller strokes were only tiny metric wins and not a broad visual explanation.
- Accepted SVG raster thin-stroke calibration: the existing structural SVG
  rule for black strokes `<= 1px` was tightened from `0.35x` to `0.175x`
  rather than adding any fixture-specific condition. Confirmation probe over
  both accountability pages plus guards improved every checked page:
  accountability page 3 `16.35 -> 16.10`, accountability page 4
  `16.40 -> 16.18`, overseas page 1 `21.94 -> 21.57`, meeting page 3
  `23.33 -> 23.30`. Kept patch after focused test
  `thin_black_svg_strokes_are_raster_scaled`, `cargo fmt --check`, overfit
  scan, release build, `bash harness/gate.sh --no-build`
  (`docs=9 improved=0 regressed=0 new_overflow=0`), and 3-doc visual board:
  overseas `21.64 -> 21.42`, accountability `16.50 -> 16.31`, meeting
  `23.38 -> 23.36`. The effect is broad but modest; do not treat it as solving
  the remaining table geometry/font-density drift.
- Component dominance differs by target:
  - `overseas_training` page 1: base `24.81`; `hide_text` `20.15`;
    `hide_lines` `20.43`; `font_size_x0.90` `23.97`.
  - `accountability_eval` page 4: base `16.57`; `hide_text` `13.03`;
    `hide_lines` `12.65`; `font_size_x0.90` `15.91`.
  - `15_3740450_research_admin_innovation_meeting_template` page 3:
    base `23.33`; `hide_text` `22.35`; `hide_lines` `77.99`; this page is
    dominated by table/image geometry, not text-only paint.
- Font substitution remains a rejected broad route. `Noto Sans KR`/`Pretendard`
  lower the metric on the three probe pages (`overseas 24.18`,
  `accountability 15.71`, `meeting 23.08`) but reduce dark-pixel counts sharply
  on text-heavy pages and are not a Hancom/Malgun structural rule. Treat this
  as evidence for a real font availability/rendering investigation, not a CSS
  family swap patch.
- Reusable SVG font-face probe now lives at:

  ```bash
  python3 harness/svg_font_face_probe.py --keep --out-dir /tmp/diff/_svg_font_face_probe_2026-06-07 accountability_eval:4 overseas_training:1 15_3740450_research_admin_innovation_meeting_template:3
  ```

  `python3 -m py_compile harness/svg_font_face_probe.py` passed. The probe
  injects data-URI `@font-face` rules for exact HWP family names such as
  `맑은 고딕`/`Malgun Gothic` without changing renderer code. Result: bundled
  open fonts are not a sufficient fix and should not be promoted as a production
  mapping. `accountability_eval` page 4 stays essentially unchanged
  (`base 16.57`, `malgun_nanum_regular 16.55`,
  `malgun_pretendard_regular 16.56`) while bold/medium mappings regress
  (`malgun_noto_bold 18.94`, `malgun_pretendard_medium 17.18`). Guard pages
  show only tiny improvements from regular mappings and clear regressions from
  broad baseline mappings (`overseas open_korean_baseline 26.59` vs base
  `24.81`; meeting `open_korean_nanum 23.14` vs base `23.33`). Conclusion:
  do not land a bundled `@font-face` substitution patch. The remaining
  accountability gap is more likely text positioning/measurement, rasterizer
  antialiasing, or missing proprietary Malgun/Hancom-compatible metrics than a
  simple available-font-file issue.
- Rejected accountability page-4 split-tolerance candidate: widening the
  non-leading RowBreak partial top-slice allowance to a page-relative overflow
  passed focused helper tests, `cargo fmt --check`, overfit scan, release build,
  `bash harness/gate.sh --no-build`, and produced a clean 3-doc board, but the
  drift trace and visual board were unchanged. With `RHWP_TABLE_DRIFT=1`, page 4
  still reports `cursor_row=21 end_row=27 consumed=635.4 partial_h=635.4
  split_end_limit=0.0 avail_for_rows=680.3`, and the next continuation still
  starts at `cursor_row=27`. The candidate was reverted as a no-op. Do not retry
  generic `+N px` split tolerance; next accountability work needs a deeper row
  unit/cut diagnostic for row 27 and carried rowspan labels.
- Rejected accountability row-27 carried-rowspan split candidate: a temporary
  exact-path trace showed the earlier no-op was caused by the
  `rowspan_touched` branch requiring the fragment-level `start_cut` to be empty.
  On page 4, row 27 has `cursor=21 consumed=635.4 remaining=45.0
  can_intra=true allows_rowbreak=true splittable=true start_cut_empty=false
  block=16..28`, so it never called `advance_row_cut`. Relaxing that so later
  rows after the cursor could split made row 27 cut to
  `end_cut=[1,2,2,2,2,2,2,1]`, changed the page-4 split to
  `cursor_row=21 end_row=28 consumed=677.1 split_end_limit=34.1`, but worsened
  page-4 mean diff to `16.99` and visibly clipped the next row into the bottom
  of the page. This is closer mechanically but visually wrong. Reverted. Next
  attempt should not simply permit row 27 text-unit splitting; investigate why
  Hancom's bottom fragment appears as a separate low band while RHWP's row-unit
  split paints a too-tall/clipped continuation.
- Accepted accountability continued-row render-density fix: partial-table
  rendering used full `resolve_row_heights` for every row touched by a carried
  rowspan label, even when that same row was a split edge with `start_cut` or
  `end_cut` for its own row_span==1 cells. This made page 4's first continued
  row render as a whole row: SVG horizontal gaps started
  `115.2 101.4 115.2 ...` while Hancom starts around `74.4 ...`. Patch:
  `src/renderer/layout/table_partial.rs` now applies
  `row_cut_content_height` to only the split-edge rowspan-touched row when a
  real cut exists; interior rowspan-touched rows remain atomic. Focused helper
  test: `cut_height_applies_to_split_edge_rows_touched_by_carried_rowspan`.
  Evidence: accountability page 4 metric improved from component-probe base
  `16.78` to current board worst `16.50` without page-count changes.
- Accepted overseas-training first-fragment host-line fix: the first fragment
  of a repeated `RowBreak`/`TopAndBottom` table suppresses host paragraph text,
  but the renderer was still reserving the host line height before drawing the
  table. In `overseas_training` page 1 this moved the main schedule table down
  by one invisible line: RHWP main band started around `185.6` while Hancom
  started around `162.3`. Patch: `src/renderer/layout.rs` now uses only the
  host line spacing for suppressed split-table host advance; focused test:
  `suppressed_split_table_host_advance_uses_spacing_only`. Evidence:
  `overseas_training` board improved `24.74 -> 21.64`, page count stayed `4/4`,
  guards stayed flat (`accountability_eval 16.50`, meeting `23.38`),
  `harness/gate.sh --no-build` reported `regressed=0 new_overflow=0`, and the
  geometry probe now shows RHWP main band `164.6..1030.3` vs Hancom
  `162.3..1037.8`.
  `16.57` to `16.40`; 3-doc board improved `accountability_eval` from
  worst page 4 `16.84` to worst page 3 `16.50` while `overseas_training`
  stayed `24.74` and meeting-template stayed `23.38`. Boundary probe after the
  patch shows RHWP first continued gap `52.3` instead of `115.2`, moving toward
  Hancom's `74.4` and removing visible page-bottom overflow in the render trace.
- Reusable SVG/raster geometry probe now lives at:

  ```bash
  python3 harness/svg_geometry_probe.py 15_3740450_research_admin_innovation_meeting_template:3 --max-bands 40 --max-boxes 16
  ```

  It reports SVG element boxes plus Hancom/RHWP raster ink bands in normalized
  SVG page coordinates. `python3 -m py_compile harness/svg_geometry_probe.py`
  passed.
- Meeting-template page 3 geometry finding: current RHWP page 3 contains
  `PartialTable pi=18 rows=3..6`, blank `pi=19`, heading `pi=20`, then TAC
  photo table `pi=21`. The geometry probe shows the lower photo table is not a
  generic page-flow shift:
  - SVG image bands: `177.7..385.6` and `524.8..982.0`.
  - Hancom raster lower table band: `520.5..981.8`.
  - RHWP raster lower table bands: `523.3..734.9` and `755.3..966.4`.
  - SVG line band for the same lower table: `434.4..968.4`.

  Interpretation: the table's overall vertical region is close, but RHWP paints
  the two image rows as separated bands with a ~20px inter-row gap and slightly
  shorter visible image content. Next fix attempt should inspect structural
  `pi=21` table-cell/image vertical placement, cell padding, and image crop/fit
  semantics. Do not patch this as an arbitrary page/table shift; previous shift
  and height probes worsened the guard metrics.
- Reusable HWPX table-source probe now lives at:

  ```bash
  python3 harness/hwpx_table_source_probe.py /tmp/diff/15_3740450_research_admin_innovation_meeting_template --list
  python3 harness/hwpx_table_source_probe.py /tmp/diff/15_3740450_research_admin_innovation_meeting_template --table-index 4
  ```

  `python3 -m py_compile harness/hwpx_table_source_probe.py` passed. For this
  fixture, render `pi=21` maps to source table index `4`, a `4x2`
  `textWrap=TOP_AND_BOTTOM`, `pageBreak=CELL`, `repeatHeader=1` table. Its
  two picture rows have cell height `15305 HU`, while each picture declares
  `height=17007 HU`, so the pictures are structurally taller than their cells.
  Some picture controls also carry signed negative offsets serialized as
  unsigned wraparound (`vertOffset=4294950285` => `-17011 HU` / `-226.8px`,
  `vertOffset=4294967240` => `-56 HU`). Next renderer investigation should
  focus on image-only table-cell paragraphs where non-TAC `TopAndBottom`
  pictures are taller than the cell and positioned with paragraph-relative
  offsets. This is a reusable class; do not special-case this document.
- Rejected meeting-template page 3 SVG-only photo-cell placement probes:
  moving lower photo images to source row tops or removing the inter-row gap
  worsened the oracle metric. One-off probe output:

  ```text
  base 23.33
  cell_top_keep_h 29.46
  cell_top_fill_h 27.22
  remove_interrow_gap 23.91
  row3_to_row_top 25.30
  ```

  The emitted SVG image tags already use `preserveAspectRatio="none"`, so this
  is not a simple browser aspect-ratio `meet` issue. Do not land a broad
  "fill picture cells from row top" patch. Next attempt should inspect crop/
  source-image semantics, actual image ink bounds, and table row border/clip
  behavior while preserving the existing negative-offset cell-picture clamp
  tests.
- Reusable embedded-image ink probe now lives at:

  ```bash
  python3 harness/svg_image_ink_probe.py 15_3740450_research_admin_innovation_meeting_template:3
  ```

  `python3 -m py_compile harness/svg_image_ink_probe.py` passed. It decodes
  data-URI images from RHWP SVG and reports local/image-page ink bounds. Initial
  page-3 result rejects the "embedded PNG has internal white padding/crop gap"
  hypothesis: all six emitted images have non-white ink boxes spanning their
  full SVG image boxes. Lower photo images report full page ink bounds:
  `85.1,524.8,388.9,749.9`, `399.9,524.8,703.8,749.9`,
  `81.0,756.9,384.9,982.0`, `399.9,756.9,703.8,982.0`.
  Next attempt should inspect row border/clip/line-band contribution and the
  Hancom/RHWP raster-band thresholding around the row divider, not source image
  bytes alone.
- Reusable SVG line-region probe now lives at:

  ```bash
  python3 harness/svg_line_region_probe.py 15_3740450_research_admin_innovation_meeting_template:3 --y-min 430 --y-max 990 --keep --out-dir /tmp/diff/_svg_line_region_probe_2026-06-07
  ```

  `python3 -m py_compile harness/svg_line_region_probe.py` passed. Page-3
  lower-photo-table result rejects row-divider/stroke tuning as a meaningful
  fix. Hiding the table ruling destroys the metric (`hide_all 77.99`,
  `hide_horizontal 63.19`, `hide_vertical 77.99`), while width changes are
  negligible (`thin_x0.50 23.30`, `thin_x0.75 23.31`, `thick_x1.50 23.36`,
  `thick_x2.00 23.40` vs base `23.33`). Do not land a renderer patch that
  only retunes lower-photo-table stroke widths for this target.
- `accountability_eval` active source is not a row-height mismatch:
  `RHWP_TABLE_DRIFT=1` reports `cut_sum=3573.8`, `mt_sum=3573.8`, `diff=+0.0`
  for the 38-row table. Do not tune row heights for this doc without new
  contradictory evidence.
- `accountability_eval` page 4 is primarily font/ink-density drift. After
  fixing the diagnostic to accept both `hancom_p-4.png` and
  `hancom_p-04.png`, `harness/table_fragment_diag.py --font-audit --pages 4`
  reports `hancom_dark=57717`, `rhwp_dark=12368`, `ratio=0.21`.
  CSS weight probes improve but do not solve it: weight 500 gives `0.26`,
  weight 600 gives `0.33`. Do not land broad `font-weight:500/600` for normal
  Malgun cells.
- Active SVG component probes show accountability page 4 mean diff is dominated
  by text, not table ruling: hiding text drops page-4 mean diff from `16.78`
  to `13.48`, while hiding line/rect strokes only drops it to `16.56`.
  Increasing thin stroke width worsens all three focus docs (`x2.0` gives
  overseas `25.44`, accountability `17.07`, meeting `23.32`), so do not undo
  thin-stroke scaling for table-heavy pages.
- Local font-family probes also reject the obvious replacement route:
  `Apple SD Gothic Neo`, `Noto Sans KR`, `Pretendard`, `Nanum Gothic`, and
  `AppleGothic` do not materially improve accountability and tend to worsen
  overseas/meeting guards. Combining those families with CSS weight 500/600
  worsens guards further. This needs a real Hancom/Malgun-compatible font path
  or a lower-level text renderer investigation, not a CSS-family substitution.
- `15_3740450_research_admin_innovation_meeting_template` page 3 is not fixed
  by naive continuation/table motion. SVG probes shifting the continued top
  table or pushing lower content all worsened the visual metric. The table
  involved is source table index 3 (`6x2`, `pageBreak=CELL`,
  `repeatHeader=1`, picture-grid table).
- Rejected mixed TAC/non-TAC photo-row expansion for meeting-template page 3.
  A structural Rust candidate detected repeated photo-grid rows that mix
  treat-as-character and block picture cells and used the full cell box for the
  fill rect in both full and partial table render paths. Focused helper test,
  `cargo fmt --check`, overfit scan, release build, and the 3-doc board ran,
  but the board stayed unchanged (`overseas_training 24.74`,
  `accountability_eval 16.50`, `meeting 23.38`) and the SVG image coordinates
  stayed at `x=82.4..386.3` / `399.9..703.8`. The visible page-3 upper photo
  row is a continued later source row, not the mixed source row; this candidate
  was reverted. Do not retry row-mixed horizontal expansion for this page
  without first mapping the visible row index from the render tree/source table.
- A more aggressive global font-paint shrink improved the pixel score but made
  accountability page 4 visibly too small versus Hancom. It was rejected and
  reverted; visual oracle overrides the mean-diff score.

## Priority B - Remaining Geometry/Page-Order Bugs

Use this only after Priority A stops yielding safe improvements.

Targets:

- overseas schedule table source-order/anchor residuals
- meeting-template page 3 continued photo-grid/table placement
- accountability row-span continuation start positions

Fresh accountability page-3 finding:

- Rejected broad later-row split after fragment start-cut. Page 2 looked
  under-filled because RHWP rendered only to `654.9` while Hancom carries a
  bottom table fragment to `734.5`. A temporary trace confirmed that a
  continuation start row with `start_cut=[1,3,3,4,3,1,3]` was charged as
  `668.9px` by pagination but rendered as `598.3px`. Fixing that accounting
  alone did not move the visual output. Relaxing the rowspan-touched split
  guard from `start_cut.is_empty()` to `r != cursor_row || start_cut.is_empty()`
  did split row 14 onto page 2 (`end_cut=[2,3,1,3,1,1,1]`) and moved page 2
  down to `713.7`, but it also reintroduced later-row overpacking and worsened
  the 3-doc board: `accountability_eval` went from accepted `16.50` to `17.53`
  with worst page 4. Reverted. Do not retry that broad rule without a new
  structural discriminator that excludes the row-27/page-4 regression class.
- Rejected stricter version of the same start-cut/later-row split idea. Added a
  strict helper that allowed a later rowspan-touched row split after fragment
  `start_cut` only when `split_total <= split_budget + 0.5`, while also charging
  the cursor row by cut-height. Focused helper tests and `cargo fmt --check`
  passed, but the 3-doc board still regressed exactly like the broad branch:
  `accountability_eval` `16.50 -> 17.53`, worst page 4; overseas and meeting
  stayed flat. Reverted. Conclusion: the row-14 page-2 split may be locally
  plausible, but this family of pagination changes destabilizes later
  continuation grouping. Next accountability page-3 work should look for a
  render/order/carry-row treatment that changes the top fragment without
  repaginating later rows, or a sharper source-geometry discriminator.
- Rejected slack-gated version of the same idea. Requiring
  `split_total + 15px <= split_budget` should have allowed the row-14 page-2
  split (`58.7 <= 82.1 - 15`) and rejected the near-bottom row-34 split
  (`86.5 > 86.0 - 15`). Focused helper tests and `cargo fmt --check` passed,
  but the 3-doc visual board still regressed to the same result:
  `accountability_eval 16.50 -> 17.53`, worst page 4. Reverted. Treat the
  page-3 top-band mismatch as not safely fixable by this pagination split
  family; the next candidate should be render-side, metric-side, or based on a
  new source invariant.
- Rejected stricter page-4 start-cut carried-rowspan split candidate after the
  accepted stroke calibration. A temporary `RHWP_TABLE_DRIFT` trace showed why
  the candidate was tempting: row 14 after page-2 `start_cut` had
  `split_total=24.6` with only `split_budget=11.5` and should be rejected, while
  row 27 after page-4 `start_cut` had `split_total=41.7` with
  `split_budget=45.0` and appeared to fit. A stricter helper that allowed only
  `consumed_height >= 25` and `split_total <= split_budget` passed focused test
  `later_rowbreak_rowspan_after_start_cut_requires_render_fit` and release
  build, but the candidate 3-doc board regressed accountability:
  `16.31 -> 16.74` with worst page 4; overseas stayed `21.42` and meeting
  stayed `23.36`. Reverted. Conclusion: even a render-budget-fitting row-27
  split is visually wrong in this table; the remaining lag is likely saved
  line-segment/vpos reset packing or row-height interpretation across rows
  21-29, not simply permitting a later carried-rowspan intra-row cut.
- Rejected cursor-row start-cut charge candidate. Geometry probes showed a
  paginator/render mismatch on accountability page 4: pagination charged the
  cursor row 21 at full `cut_row_h` while render used the accepted split-edge
  cut height, leaving visual room but no row 27. A narrow candidate charged a
  carried-rowspan cursor row with non-empty `start_cut` using
  `row_cut_content_height(table, row, start_cut, [])`. Focused helper test
  passed and dump-pages changed page 4 from `rows=21..27` to `rows=21..28`
  (page 5 from `rows=27..34` to `rows=28..35`), which put the expected
  `마케팅/홍보` source row onto page 4. Visual oracle still rejected it:
  accountability worsened `16.31 -> 17.08`, worst page 4; overseas stayed
  `21.42`, meeting stayed `23.36`. Reverted. Conclusion: matching source row
  membership alone is not enough; Hancom's row-height/line-cache packing inside
  this continued fragment differs from both full-height charging and pure
  cut-height charging.
- Rejected meeting page-3 TAC photo-grid row-height candidate. Source table 3
  row 5 is an all-TAC picture-only repeated RowBreak/TopAndBottom photo row:
  stored cell height is `15872 HU` (`211.6px`), while picture height is
  `17007 HU` (`226.8px`). Geometry probes made the candidate tempting because
  Hancom's top photo band is about `226px` while RHWP's SVG line gap is
  `211.6px`. A structural patch added TAC picture height-bearing units for
  repeated photo-grid cells and passed the focused unit test plus fmt/overfit
  and release build. The live fixture rejected it: dump-pages changed the
  meeting document from 5 pages to 6 pages, and the 3-doc board reported
  `15_3740450... page_count_gap 5 6 worst p3 mean 64.43` while overseas and
  accountability stayed flat. Reverted. Conclusion: the top-band visual gap is
  not safely fixable by increasing row-cut height for all-TAC photo rows; the
  table already depends on a shrink-vs-cut dual metric to preserve page count.
  Next meeting work should look at render-only image ink/cropping or local
  partial-fragment visual placement, not pagination/cut height.
- Rejected meeting page-3 render-only aspect/shift probes. SVG postprocessing
  changed only `preserveAspectRatio` for page-3 images: current direct page
  metric was `23.68`; `all_meet=43.07`, `top_meet=30.84`,
  `lower_meet=35.92`, `all_slice=29.73`, `top_slice=25.46`,
  `lower_slice=27.94`. A second postprocess shifted SVG elements after likely
  table boundaries (`y>=175/387/398/434/469/503`) by `-12,-6,+6,+12,+18`;
  every variant worsened from `23.68` (best shifted variants were still about
  `24.84+`). Conclusion: meeting page 3 is not an easy aspect-ratio or simple
  vertical-advance fix. Bank this page unless a more specific image crop or
  table line/cache invariant appears.
- Overseas page-1 remaining drift appears mostly non-structural after the
  accepted host-line and thin-stroke fixes. Table geometry is close:
  Hancom/rhwp raster bands are roughly `96.7..146.3` vs `97.3..146.0` and
  `162.3..1037.8` vs `164.6..1030.3`; SVG line gaps mostly track Hancom
  row-gap sequence. Font audit says RHWP is lighter overall
  (`rhwp_dark/hancom_dark=0.75`), but font-family variants only gave tiny
  improvements (`base=21.58`, best `malgun_nanum_regular=21.31`) and boldening
  worsened. Line-region probes show rules contribute (`hide_horizontal=19.48`),
  but width/opacity probes were not a good fix: thin variants moved only
  `21.58 -> 21.38`, opacity direct render only `20.97 -> 20.83`. Conclusion:
  do not add another broad font/stroke calibration from overseas alone. Need a
  more specific text raster/font availability invariant or a multi-doc stroke
  win before touching `svg.rs` again.
- Accepted meeting_summary fixed TAC row-grid render rule. Page 1 is a simple
  title paragraph plus one 7x2 `treat_as_char`, `TopAndBottom`, `CELL`/RowBreak
  table. Source row heights sum to `903.0px`, matching Hancom line gaps
  (`35.2,98.3,54.4,165.5,167.1,143.1,239.0`), but RHWP rendered a remeasured
  row grid of `918.0px` and put the final horizontal rule at `1040.0px` instead
  of Hancom's `1024.1px`. Added a structural fixed-grid guard in
  `LayoutEngine::resolve_row_heights`: for TAC TopAndBottom CellBreak/RowBreak
  tables with complete declared row heights, matching declared table height, and
  row-span heights that equal their covered row sums, render uses the declared
  row grid before any measured-table/content expansion. Focused test
  `fixed_tac_table_preserves_declared_row_grid` passed. Visual result:
  `meeting_summary 21.00 -> 18.86`, page count stayed `3/3`; guard board held
  overseas `21.42`, accountability `16.31`, meeting-template `23.36`.
  `harness/gate.sh --no-build` passed with `docs=9 improved=0 regressed=0
  new_overflow=0`; overfit scan passed. Post-fix SVG horizontal lines now follow
  the declared/Hancom grid: `122.0,156.9,255.9,309.1,475.8,642.5,785.5,1025.0`.
- Rejected form_07 singleton heading and tiny final-row tail candidates.
  `form_07_______________41KB` is now a real staged target at
  `/tmp/diff/form_07_______________41KB/source.hwpx`; the category board starts
  from Hancom 11 pages vs RHWP 13 pages, while the gate baseline for this
  staged fixture currently records 12 pages / 2 overflow markers. Candidate A
  moved a singleton trailing `PartialParagraph` after a table onto the following
  non-TAC `TopAndBottom` table page. Its focused test passed and the board
  improved `13 -> 12`, but `bash harness/gate.sh --no-build` still failed for
  `form_07` overflow markers (`2 -> 4` in the current dirty renderer state).
  Candidate B absorbed a tiny final-row table continuation tail (`15.8px`) when
  full-row overflow was under 4% of page height. It improved the board to
  `11/11`, but gate reported `+OVERFLOW form_07_______________41KB: 2->3` and
  dump-pages showed page 6 overfilled to `915.0px` against an `876.8px` body.
  Do not retry these as post-pagination movement or full-row absorption. The
  next viable route is to reduce or avoid existing `LAYOUT_OVERFLOW` markers
  structurally, especially around `pi=71` split rendering, before claiming the
  `form_07` page-count fix.
- Rejected form_07 partial-table overflow cleanup candidate. Layout-side
  `layout_partial_table_item` currently adds a hidden host-line advance for the
  first suppressed-host `repeatHeader` + `RowBreak` + `TopAndBottom` fragment
  before `layout_partial_table` applies `vertical_offset`. Removing that hidden
  host advance eliminated the extra `form_07` table overflow markers
  (`pi=64`, `pi=71`) and made `bash harness/gate.sh --no-build` report
  `new_overflow=0`, but it visually regressed guard docs: `overseas_training`
  worsened `21.42 -> 24.56`, and
  `15_3740450_research_admin_innovation_meeting_template` worsened
  `22.38 -> 25.97`. Reverted. Do not retry a blanket suppressed-host advance
  removal; a future fix needs a narrower discriminator, likely tied to the
  `form_07` small continuation-tail geometry rather than every suppressed
  repeated RowBreak/TopAndBottom first fragment.

Rule: bank after three failed Rust build/probe cycles without a clean
structural discriminator.

## Rejected Accountability Eval Candidate -- 2026-06-08

- Candidate: preserve physical SVG stroke width for table-border `LineNode`s
  while keeping the prior thin-black-stroke raster calibration for ordinary
  vector lines.
- Rationale tested: `accountability_eval` page 3 had RHWP dark-pixel density
  around one-third of Hancom, and SVG table borders were emitted as
  `stroke-width="0.07"` after global black hairline scaling.
- Verification:
  - focused test passed for the semantic flag candidate;
  - `cargo fmt --check` passed;
  - release build passed;
  - `python3 scripts/check_renderer_overfit.py` passed;
  - `bash harness/gate.sh --no-build` remained at the known current-source
    `form_07` failure only.
- Rejection: visual board worsened instead of improving:
  - `accountability_eval` `16.31 -> 17.26`;
  - `overseas_training` `21.42 -> 22.90`;
  - `meeting_summary` `18.86 -> 19.01`;
  - meeting-template `22.38 -> 22.63`.
- Decision: reverted. Do not retry a table-border stroke-width floor as the
  next accountability path; the low dark-pixel density is not solved by simply
  thickening table border strokes. The next probe should isolate table-cell
  glyph paint/text composition or continuation-cell line placement.

## Accepted SVG Malgun Paint-Face Calibration -- 2026-06-08

- Candidate: for SVG output only, paint Malgun/`맑은 고딕` text with a single
  `Noto Sans KR` paint face while leaving layout metrics and source font family
  decisions unchanged.
- Structural basis: dense Korean table-cell pages are dominated by SVG text
  paint/composition drift. Component probes showed table-border stroke changes
  regressed, while replacing the Malgun-style SVG paint face improved every
  probed guard page. The effective Chromium raster form had to be a single
  paint face (`font-family="Noto Sans KR"`); adding a fallback stack made
  Chromium return to the old raster path.
- Focused guard:
  - `test_svg_malgun_paints_with_noto_sans_face`
  - `cargo fmt --check`
  - `python3 scripts/check_renderer_overfit.py`
  - `cargo build --release --bin rhwp -j 1`
- Visual result versus current rebuilt baseline:
  - `accountability_eval`: `16.31 -> 15.50` (`6/6`, worst page now 4)
  - `meeting_summary`: `18.86 -> 17.86` (`3/3`)
  - meeting-template: `22.38 -> 22.17` (`5/5`)
  - `report_form`: `12.79 -> 12.27` (`6/6`)
  - `overseas_training`: `21.42 -> 21.38` (`4/4`)
  - `form_07`: unchanged `11/13`, mean `15.19`
- Gate: `bash harness/gate.sh --no-build` still fails only the known dirty
  current-source `form_07` regression/overflow (`12 -> 13`, overflow `2 -> 4`);
  no new gate doc was introduced by this SVG paint change.

## Accepted Human Myeongjo Paint-Size Calibration -- 2026-06-08

- Candidate: paint `휴먼명조` text at `0.88x` visual font size while leaving
  layout/advance metrics unchanged.
- Structural basis: meeting-template page 1 uses missing `휴먼명조` serif text;
  temporary SVG probes showed `휴먼명조`-only scaling improved that page
  (`~22.30 -> 21.37`) without relying on document name or body text.
- Focused guard:
  - `test_human_myeongjo_visual_scale_is_paint_only`
  - `cargo fmt --check`
  - `python3 scripts/check_renderer_overfit.py`
  - `cargo build --release --bin rhwp -j 1`
- Visual result versus previous current board:
  - meeting-template full-doc mean: `22.17 -> 22.12`
  - other six-doc guard entries unchanged within reported precision.
- Gate: `bash harness/gate.sh --no-build` still fails only the known dirty
  current-source `form_07` regression/overflow (`12 -> 13`, overflow `2 -> 4`);
  no new gate doc was introduced.
- Decision: keep as a narrow paint-only calibration, but do not treat it as
  the main meeting-template fix. Remaining drift is still dominated by page 3
  geometry/image/table content.

## Rejected CellBreak Photo-Grid Row-Cut Height Candidate -- 2026-06-08

- Target: meeting-template page 3. Side-by-side and geometry probes show the
  repeated photo-grid table clips photo rows about `13-14px` short: emitted
  image boxes extend to the Hancom-like bottom, but SVG cell clips/borders end
  earlier.
- Candidate: broaden `row_cut_content_height`'s repeated photo-grid row
  exception from `RowBreak` to the existing `is_repeated_photo_grid_table`
  predicate so `CellBreak` photo rows use picture extent.
- Focused test passed, and fmt/overfit/release/gate passed except the known
  `form_07` current-source failure.
- Rejection: refreshed SVG geometry and visual board were unchanged:
  meeting-template full-doc mean stayed `22.12`, page 3 bands remained
  `line 94.0..387.9`, image `173.9..400.7`, so this row-cut path is not the
  authority for the page-3 cell clip/border geometry.
- Decision: reverted. Continue in `layout_partial_table` cell clip/row_y
  construction for repeated photo-grid partials, not `row_cut_content_height`.

## Rejected Partial Photo-Grid Clip-Height Expansion -- 2026-06-08

- Candidate: in `layout_partial_table`, expand repeated photo-grid row heights
  before cell clip/border construction using the existing moderate
  `repeated_photo_picture_fill_area` rule.
- Focused test passed, and fmt/overfit/release/gate passed except the known
  `form_07` current-source failure.
- Rejection: visual board regressed meeting-template full-doc mean
  `22.12 -> 26.86`. Geometry showed the top photo row moved closer
  (`line bottom 387.9 -> 406.8` vs Hancom `400.6`) but it pushed the caption
  and lower photo grid downward (`bottom grid start 523.3 -> 542.6` vs Hancom
  `520.5`), increasing overall drift.
- Decision: reverted. The needed rule is not a uniform row-height expansion.
  Future probes should target image/cell clip-bottom painting for the first
  row or row-local clipping without shifting subsequent rows.

## Accepted Partial Photo-Grid Picture-Cell Unclip -- 2026-06-08

- Candidate: for partial repeated photo-grid tables, keep ordinary table cells
  clipped but disable the cell clip on picture-only photo-grid cells. Row flow,
  row heights, and subsequent content positions are unchanged.
- Structural basis: meeting-template page 3 is a repeated `CellBreak`
  `TopAndBottom` photo-grid partial. SVG probes showed row movement regressed,
  while un clipping only the six photo cell groups improved page 3
  (`22.02 -> 17.28`) without relying on document text/name.
- Focused guard:
  - `repeated_photo_grid_partial_picture_cells_are_unclipped`
  - `cargo fmt --check`
  - `python3 scripts/check_renderer_overfit.py`
  - `cargo build --release --bin rhwp -j 1`
- Visual result:
  - meeting-template full-doc mean: `22.12 -> 21.61`
  - worst page changed from page 3 to page 2
  - guard docs unchanged at reported precision.
- Gate: `bash harness/gate.sh --no-build` still fails only the known dirty
  current-source `form_07` regression/overflow (`12 -> 13`, overflow `2 -> 4`);
  no new gate doc was introduced.
- Remaining risk: page 3 still has visible geometry drift. The unclip improves
  photo visibility, but top photo band now overpaints slightly beyond Hancom;
  future work should tune photo-grid clip bottoms more precisely rather than
  moving row flow.

## Rejected Meeting-Template Page-2 Photo Y-Shift Candidate -- 2026-06-08

- Target: after the photo-cell unclip fix, meeting-template worst visual page
  moved to page 2 (`21.61` full-doc mean).
- SVG probes:
  - shifting the lower photo-grid image down helped page 2
    (`22.07 -> 21.15` at `+15px`);
  - increasing the timeline image height helped page 2 (`22.07 -> 21.18`);
  - combined page-2 SVG-only variant reached `20.27`.
- Rejection: the same repeated-photo-grid downward shift badly regressed page 3
  (`20.60 -> 28.62` at `+15px`, with monotonic worsening from `+4px`
  onward). This is not a reusable renderer rule for photo grids.
- Decision: do not patch photo-grid image y-position globally. Page 2 likely
  needs a different table/image geometry rule, or a more local timeline/image
  rule, before it is safe to change Rust.

## Priority C - Export/Reopen Product Gate

This is separate from visible RHWP fidelity. Before production, validate:

1. Original HWPX opens in Hancom/licensed iframe.
2. Original HWPX opens in hidden RHWP.
3. RHWP applies representative mutation.
4. RHWP exports HWPX.
5. Hancom/licensed iframe reopens exported HWPX.
6. Reopened file is visually sane and not corrupted.

Do not treat magic bytes or a successful download as proof.

## Production Decision

Fastest production-safe architecture is hybrid:

- Hancom/licensed iframe is the visible oracle renderer and final reopen gate.
- RHWP is used for hidden parse/read/mutate/export and increasingly better
  preview.
- Do not expose arbitrary wild-doc RHWP-only rendering as the primary
  production surface until the visual-drift queue is consistently below the
  accepted threshold across a broad corpus.
