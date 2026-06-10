# RHWP Fidelity Next Category Plan -- 2026-06-08

Current focus: page counts are matching on the active focus set; remaining work is visual fidelity.

## Current Board

Source: `work/FIDELITY_VISUAL_STATUS_FORM07_11P_TINY_TAIL_2026-06-08.md`.

| doc | Hancom | RHWP | worst page | mean diff | class |
|---|---:|---:|---:|---:|---|
| `form_07_______________41KB` | 11 | 11 | 5 | 15.19 | visual drift |
| `accountability_eval` | 6 | 6 | 4 | 15.50 | visual drift |
| `overseas_training` | 4 | 4 | 1 | 21.38 | visual drift |
| `meeting_summary` | 3 | 3 | 1 | 17.86 | visual drift |
| `15_3740450_research_admin_innovation_meeting_template` | 5 | 5 | 2 | 20.86 | visual drift |
| `report_form` | 6 | 6 | 2 | 12.27 | page-count clean |

## Fast Category Order

1. Page-count regressions and wrong-page content.
   - Highest priority because it blocks production use directly.
   - Current active set is clean after the `form_07` final split-tail fix.
2. Image placement and cropping.
   - Usually high-impact and structurally fixable.
   - Prior accepted fixes already improved cropped image placement and photo-grid row handling.
3. Table/grid geometry.
   - Validate with render-tree positions, row split logs, and page-count gate.
   - Fix only through table model facts: wrap mode, TAC/non-TAC, row split, row span, declared cell sizes, picture-only cells.
4. Text paint and metrics.
   - Current main bucket.
   - Harder because visual diff improves weakly under global font knobs and can regress many documents.
   - Needs regional probes before renderer changes.

## Hours-Long Execution Protocol

Run the work as a repeated category loop, not as one-off fixture patches:

1. Pick the highest-impact category from the board.
   - First sort by correctness class: wrong page count/content before visual drift.
   - Then sort by user-visible impact: missing images, table geometry, text density.
   - Work on one doc/page until the structural class is accepted or rejected.
2. Build a fast oracle comparison for that class.
   - Page count/wrong content: `harness/gate.sh --no-build` plus page-start text/render-tree invariant.
   - Image/crop: SVG image boxes, page-positioned image tags, regional image ink bounds.
   - Table geometry: table boundary bands, source table/cell attrs, render-tree table top/bottom.
   - Text paint/metrics: regional pixel probe plus SVG text-run probe.
3. Reject tempting global knobs before touching Rust.
   - Font family/size/weight changes must improve target regions and not worsen the focus board.
   - Stroke width changes must improve both whole-page score and the affected table band.
   - Any patch that only helps one fixture because of its visible text/name is disallowed.
4. Convert evidence into a structural invariant.
   - Acceptable keys: wrap mode, TAC/non-TAC, repeatHeader, row split mode, cell line segments, paragraph/list attrs, border fill type/width, image crop/position model.
   - Unacceptable keys: fixture filename, body text, title text, doc-specific dimensions without a model reason.
5. Patch narrowly, then run the same fast oracle check before full validation.
   - If the target metric improves but another focus doc regresses, revert or narrow the structural condition.
   - If the metric moves but the visual side-by-side looks worse, reject the metric-only patch.
6. Promote only after the acceptance gate.
   - Focused Rust regression.
   - `python3 scripts/check_renderer_overfit.py`.
   - `cargo fmt --check`.
   - Release build.
   - `bash harness/gate.sh --no-build`.
   - Refreshed visual board for the active focus set.

## Probe Evidence

Command:

```bash
python3 harness/svg_component_probe.py --export-current --out-dir /tmp/diff/_probe_visual_queue_components \
  form_07_______________41KB:5 accountability_eval:4 overseas_training:1 meeting_summary:1 \
  15_3740450_research_admin_innovation_meeting_template:2
```

Key results:

| doc/page | base | hide text | hide lines | best simple variant | read |
|---|---:|---:|---:|---:|---|
| `form_07` p5 | 13.29 | 8.07 | 9.36 | font size x0.90 = 12.11 | mixed text + line/table paint; already under board threshold in this probe |
| `accountability_eval` p4 | 15.37 | 12.85 | 12.65 | font size x0.90 = 14.87 | mixed sparse text + geometry/line drift |
| `overseas_training` p1 | 21.54 | 18.75 | 20.43 | font size x0.90 = 21.09 | text dominates, but global font tweaks are weak |
| `meeting_summary` p1 | 17.96 | 15.33 | 15.24 | font size x0.90 = 17.49 | mixed text + line/table drift |
| `meeting_template` p2 | 21.15 | 18.14 | 40.55 | font size x0.90 = 20.66 | image/line/table content remains dominant; do not treat as pure typography |

Family-specific follow-up:

```bash
python3 harness/svg_component_probe.py --out-dir /tmp/diff/_probe_family_components \
  overseas_training:1 15_3740450_research_admin_innovation_meeting_template:2
```

Key family results:

| doc/page | base | hide Gyeonggi text | Gyeonggi size x0.90 | hide Noto text | Noto size x0.90 | read |
|---|---:|---:|---:|---:|---:|---|
| `overseas_training` p1 | 21.54 | 18.97 | 21.11 | 20.51 | 21.36 | Gyeonggi text contributes, but size-only tweak is too weak for a safe renderer patch |
| `meeting_template` p2 | 21.15 | 21.15 | 21.15 | 19.84 | 20.95 | no Gyeonggi text on this page; Noto text contributes but global Noto scaling is weak |

Harness improvement:

```bash
python3 harness/svg_component_probe.py --variant base --variant 'font_size_gyeonggi_*' \
  --out-dir /tmp/diff/_probe_variant_filter_smoke overseas_training:1
```

The `--variant` filter keeps future probe loops fast by running only selected variants.

`overseas_training` geometry probe:

- SVG table line band: `y=164.9..1032.6`.
- Hancom raster table band: `y=162.3..1037.8`.
- RHWP title/table geometry is close enough that the current mismatch is mostly text paint/density, not gross pagination.

Existing renderer state:

- `visual_font_size_scale("경기천년...") == 0.77`.
- `fallback_font_advance_scale("경기천년...") == 0.88`.
- Therefore, do not add another broad Gyeonggi scaling rule without regional proof.

## Next Implementation Loop

Preferred next target: continue visual drift with region-level probes before renderer edits.

Reason:

- Broad text/font changes are weak across both main candidates.
- `overseas_training` p1 is Gyeonggi-heavy, but family-specific size/weight probes do not justify a renderer change.
- `meeting_template` p2 visually looks close despite high raw diff; photo/timeline content makes component hiding hard to interpret.

Next useful diagnostic:

- Add or run a regional text harness that compares title/header/body cell bands independently.
- For `overseas_training` p1, measure baseline and dark-pixel density separately for the title, header row, and body table.
- For `meeting_template` p2, measure text-only regions above the timeline separately from image/photo regions.

Implemented diagnostic:

```bash
python3 harness/svg_region_probe.py overseas_training:1 \
  --region title:56,98,726,146 \
  --region header:56,164,737,214 \
  --region body_top:56,214,737,503 \
  --region body_mid:56,503,737,831 \
  --region body_bottom:56,831,737,1038

python3 harness/svg_region_probe.py 15_3740450_research_admin_innovation_meeting_template:2 \
  --region top_text:70,94,720,210 \
  --region contract_table:70,210,720,315 \
  --region timeline:70,315,720,655 \
  --region photo_table:70,655,720,1020
```

Regional result summary:

| doc/page | region | mean diff | dark-pixel delta | read |
|---|---:|---:|---:|---|
| `overseas_training` p1 | title | 29.36 | -32.0% | RHWP title ink is lighter/shorter than oracle |
| `overseas_training` p1 | header | 34.81 | -81.0% | header/table band is the worst regional signal |
| `overseas_training` p1 | body_top | 30.12 | -67.0% | body table bands are fragmented in RHWP |
| `overseas_training` p1 | body_mid | 27.47 | -63.7% | same fragmented/lighter table-text signal |
| `overseas_training` p1 | body_bottom | 30.39 | -73.1% | same fragmented/lighter table-text signal |
| `meeting_template` p2 | top_text | 22.11 | +4.6% | top paragraph text is close; not primary target |
| `meeting_template` p2 | contract_table | 32.19 | -67.3% | table region is weak/sparse in RHWP |
| `meeting_template` p2 | timeline | 24.81 | -13.6% | timeline alignment/paint remains moderate |
| `meeting_template` p2 | photo_table | 39.84 | -2.1% | photo table geometry/edge differences dominate despite similar ink |

Enhanced regional metrics added:

- `harness/svg_region_probe.py` now reports dark pixels, non-white pixels, and mean luma.
- This separates black text/ruling problems from gray fills, photos, and colored timeline content.

Enhanced read:

| doc/page | region | dark delta | non-white delta | luma delta | read |
|---|---:|---:|---:|---:|---|
| `overseas_training` p1 | header | -81.0% | +2.5% | +21.0 | fills are present, but dark text/rulings are much lighter/sparser |
| `overseas_training` p1 | body_top | -67.0% | -20.2% | +14.3 | missing/shifted light content plus weak dark ink |
| `overseas_training` p1 | body_mid | -63.7% | -14.3% | +12.5 | same table-body pattern |
| `meeting_template` p2 | top_text | +4.6% | +19.0% | -0.9 | not the primary target |
| `meeting_template` p2 | contract_table | -67.3% | -2.1% | +11.6 | dark table/text ink sparse, light fill coverage similar |
| `meeting_template` p2 | timeline | -13.6% | -2.2% | +1.7 | moderate alignment/paint issue |
| `meeting_template` p2 | photo_table | -2.1% | +2.3% | +1.5 | geometry/edge/image differences dominate |

Interpretation:

- Do not accept a global font-size/font-family tweak. Family probes were weak, and regional probes show mixed causes.
- `overseas_training` p1 needs a table-cell/ruling/text-band investigation, especially header/body table rendering, not another broad Gyeonggi rule.
- `meeting_template` p2 should be treated as region-specific: contract table and photo-table edges/images, not top text.

Candidate rejects from regional variant scoring:

```bash
python3 harness/svg_region_probe.py overseas_training:1 \
  --candidate-png /tmp/diff/_probe_family_components/overseas_training_p1/font_size_gyeonggi_x0.90.png \
  --region header:56,164,737,214 --region body_top:56,214,737,503 --region body_mid:56,503,737,831

python3 harness/svg_region_probe.py overseas_training:1 \
  --candidate-png /tmp/diff/_probe_family_components/overseas_training_p1/thin_stroke_x3.00.png \
  --region header:56,164,737,214 --region body_top:56,214,737,503 --region body_mid:56,503,737,831
```

- Gyeonggi size x0.90 weakly improves region mean diff but reduces already sparse RHWP ink further; reject as a renderer patch.
- Noto-only family replacement and Gyeonggi weight 500 show the same weak/non-structural pattern; reject.
- Thin stroke x3 worsens the header badly (`34.81 -> 39.62`) and worsens body regions; reject a general stroke-width patch.
- Gyeonggi size x1.10 also worsens `overseas_training` p1 regions:
  - header `34.81 -> 35.38`
  - body_top `30.12 -> 30.67`
  - body_mid `27.47 -> 28.21`
  Reject larger Gyeonggi text as a renderer patch.
- Gyeonggi weight 600 also worsens the same regions:
  - header `34.81 -> 35.17`
  - body_top `30.12 -> 31.01`
  - body_mid `27.47 -> 28.24`
  Reject heavier Gyeonggi text as a renderer patch.

Source-border evidence for `overseas_training`:

```bash
python3 harness/hwpx_table_source_probe.py /tmp/diff/overseas_training/source.hwpx --border-fills 5,6,7,8,9,10,11,12,13,14
```

## Accountability Eval Page 4 -- CellBreak Rowspan Slice Attempt

Target:

- `accountability_eval` page 4.
- RHWP page count already matches Hancom: 6/6.
- The visual miss is a bottom-table underfill: Hancom has lower horizontal rules around
  `y=657.7`, `688.9`, and `734.5`; RHWP originally stopped at `y=629.2`.

Structural evidence:

```bash
docker compose --env-file .env.docker run --rm -e RHWP_TABLE_DRIFT=1 \
  -v /tmp/diff:/diff dev /app/target/release/rhwp \
  dump-pages /diff/accountability_eval/source.hwpx -p 2,3,4
```

- Page 4 before candidate:
  - `PartialTable rows=21..27`
  - `start_cut=[2,2,3,3,3,3,1]`
  - `end_cut=[]`
  - `used=635.4px` out of `680.3px`.
- Neighbor fragments use `668.9px`, `671.4px`, and `677.2px`, so page 4 is the anomalous underfill.
- Source table is `pageBreak=CELL`; a carried rowspan label overlaps the next row.

Rejected candidate:

- Allow a CellBreak table row touched by a carried rowspan label to emit a partial top slice
  when row-local cells are splittable and the geometry budget fits.
- Internal split result moved in the intended direction:
  - Page 4 became `rows=21..28`
  - `end_cut=[1,2,2,2,2,2,2,1]`
  - `used=677.1px`
  - page count stayed 6/6.
- But visual board worsened:
  - `accountability_eval` worst page stayed p4 but mean diff moved to `15.83`
    from the previous `~15.49-15.50` range.
- Boundary probe after candidate:
  - RHWP added a bottom line at `y=670.9`.
  - Hancom lower rules are around `y=688.9` and `y=734.5`.
  - The added slice lands too high/short and increases mismatch.
- Region probe after candidate:
  - `bottom_gap` mean diff worsened to `14.06`.
  - `lower_table` mean diff worsened to `19.74`.

Conclusion:

- Do not keep the simple CellBreak-rowspan top-slice rule.
- The real issue is not only "row 27 missing"; row bands above it are already vertically
  distributed differently, and Hancom appears to carry one or two lower row fragments after
  a different per-row height distribution.
- Next diagnostic should inspect row-height authority for `rows=21..27` under carried
  rowspan labels, not just force an extra row slice at the bottom.

Follow-up row-height authority evidence:

```bash
python3 harness/fidelity_category_status.py --with-gallery \
  --out work/FIDELITY_VISUAL_STATUS_ACCOUNTABILITY_RESTORED_BASELINE_2026-06-08.md \
  accountability_eval

python3 harness/table_fragment_diag.py /tmp/diff/accountability_eval --pages 3-5 --font-audit
python3 harness/table_boundary_probe.py accountability_eval:3
python3 harness/table_boundary_probe.py accountability_eval:4
python3 harness/table_boundary_probe.py accountability_eval:5
python3 harness/svg_region_probe.py accountability_eval:4 \
  --region full:30,50,1100,760 \
  --region bottom_gap:30,620,1100,760 \
  --region lower_table:30,520,1100,740
```

- Restored baseline board after backing out the rejected candidate:
  - `accountability_eval` remains 6/6 pages.
  - Worst page is p4, mean diff `15.49`.
- Page 4 source/RHWP row authority:
  - Fragment is `rows=21..27`, `start_cut=[2,2,3,3,3,3,1]`, `end_cut=[]`.
  - `source_row_h=[115.2,101.4,115.2,96.5,115.2,91.7]`, sum `635.2`.
  - RHWP SVG horizontal line gaps exactly follow this authority after the cut head:
    `52.3,101.4,115.2,96.5,115.2,91.7`.
- Hancom p4 horizontal gaps are different:
  - `74.4,114.4,97.6,114.4,92.0,106.4,31.2,45.6`.
  - Hancom has lower table bands at `657.7`, `688.9`, and `734.5`, while RHWP stops at
    `629.2`.
- Page 5 has a related continuation pattern:
  - RHWP SVG gaps include the stored blank separator row `30.9` after the first row:
    `106.5,30.9,116.9,131.7,106.5,115.2,69.4`.
  - Hancom p5 gaps are `71.2,131.2,106.4,115.2,124.0,111.2`, without the same visible
    early blank-separator cadence.
- Region evidence:
  - `bottom_gap` has Hancom content bands `620.0..658.4;688.8..735.2`.
  - RHWP has no dark table content in that region.

Current read:

- RHWP is not randomly drifting here; it is obeying stored cell row heights too literally
  for a continued `CellBreak` table with carried rowspan labels.
- Hancom appears to repack the continuation body: some carried-rowspan/blank-separator
  geometry is compressed or shifted, which creates room for an additional lower short band.
- A safe renderer fix needs a structural rule for continued CellBreak tables with carried
  rowspans and blank separator rows. Forcing a top slice of row 27 is insufficient and
  visually worse.

Cross-doc guard scan:

```bash
python3 harness/cellbreak_rowspan_scan.py --min-slack 25.0
python3 harness/cellbreak_rowspan_scan.py --min-slack 0.0
```

- A reusable scanner now lives at `harness/cellbreak_rowspan_scan.py`.
- With `--min-slack 25.0`, matches are limited to:
  - `accountability_eval` p4 and p6.
  - `accountability_eval_fitted_oracle` variants, which are not a separate guard doc.
- With `--min-slack 0.0`, all matches are still only `accountability_eval` variants.
- Guard docs checked:
  - `form_07` has continued CellBreak table `rows=6..12`, but no carried rowspans.
  - `overseas_training` has continued CellBreak table pages with some carried rowspans,
    but not the same blank-separator/underfilled-fragment pattern.
  - `meeting_template` continuation is photo/image-grid shaped, not this text-rowspan class.

Decision:

- Do not patch a CellBreak carried-rowspan compression rule yet. The only current match is
  `accountability_eval`, so a renderer change would be under-guarded and likely overfit in
  effect even if the condition is structural.
- Keep the scanner as the way to find more guards when new wild docs are added to `/tmp/diff`.
- Move to the next category unless another independent document with the same class appears.

## Overseas Training Page 1 -- Table Ink/Text Density

Target:

- `overseas_training` page 1.
- Page count is clean: 4/4.
- Boundary geometry is close: SVG horizontal lines line up with Hancom bands, but rasterized
  RHWP dark ink is far too sparse in table header/body regions.

Current probes:

```bash
python3 harness/svg_region_probe.py overseas_training:1 \
  --region title:56,98,726,146 \
  --region header:56,164,737,214 \
  --region body_top:56,214,737,503 \
  --region body_mid:56,503,737,831 \
  --region body_bottom:56,831,737,1038

python3 harness/table_boundary_probe.py overseas_training:1
python3 harness/svg_text_region_probe.py overseas_training:1 --region header:56,164,737,214
python3 harness/svg_text_region_probe.py overseas_training:1 --region body_top:56,214,737,503
python3 harness/svg_text_region_probe.py overseas_training:1 --region body_mid:56,503,737,831
```

Findings:

- Region dark deltas remain severe:
  - header: `-81.1%`
  - body_top: `-67.6%`
  - body_mid: `-64.4%`
  - body_bottom: `-73.8%`
- SVG horizontal line positions are close to Hancom; this is not a gross table-placement bug.
- Source borders include many `0.12mm`, `0.2mm`, and `0.5mm` table rules.
- SVG emits many `0.12mm` table borders as subpixel strokes:
  - `0.12mm -> ~0.07px`
  - `0.2mm -> ~0.105px`
  - `0.5mm -> ~0.1575px`
- Text bands are dominated by Gyeonggi font-family runs:
  - header: `경기천년제목 Medium`, `경기천년바탕 Bold`
  - body: mostly `경기천년바탕 Bold`, `경기천년제목 Medium`, plus some `나눔고딕 ExtraBold`.

Rejected candidates:

```bash
python3 harness/svg_component_probe.py --variant base --variant 'thin_stroke*' \
  --out-dir /tmp/diff/_probe_overseas_stroke \
  overseas_training:1 accountability_eval:4 meeting_summary:1 report_form:2

python3 harness/svg_component_probe.py --variant base --variant 'weight*' \
  --variant 'text_stroke*' --variant 'font_size_gyeonggi*' \
  --out-dir /tmp/diff/_probe_overseas_text \
  overseas_training:1 accountability_eval:4 meeting_summary:1 report_form:2
```

- Thickening table strokes is rejected:
  - `overseas_training` worsens as strokes get thicker (`21.50 -> 22.26` at x3).
  - Guards also worsen (`accountability_eval`, `meeting_summary`, `report_form`).
- Thinning strokes slightly improves mean diff but reduces ink; not a faithful fix for a
  dark-ink deficit.
- `font_size_gyeonggi_x0.90` improves whole-page mean (`21.50 -> 21.03`) but worsens the
  actual ink deficit:
  - header dark delta goes `-81.1% -> -84.8%`
  - body_top `-67.6% -> -75.1%`
  - body_mid `-64.4% -> -71.9%`
  - body_bottom `-73.8% -> -80.4%`
  Reject as metric-cheating.
- `weight_gyeonggi_600` restores some ink but worsens regional mean diff:
  - header `34.80 -> 35.17`
  - body_top `30.09 -> 30.99`
  - body_mid `27.46 -> 28.20`
  - body_bottom `30.23 -> 31.68`
  Reject as a renderer patch.
- `text_stroke_0.15/0.25` worsens target and guard docs.

Current read:

- This is likely a font-face/glyph-rasterization fidelity class, not a simple
  border-width, CSS-weight, text-stroke, or font-size class.
- Do not patch global Gyeonggi scaling/weight/stroke.
- Next useful probe would compare actual available font files/fallbacks and browser
  rasterization against Hancom for Gyeonggi/Nanum families, or look for a source-level
  font substitution table rather than changing renderer geometry.

- Main itinerary table is `textWrap=TOP_AND_BOTTOM`, `pageBreak=CELL`, `repeatHeader=1`, `borderFillIDRef=5`.
- Header cells use border fills `6`, `7`, `8`.
- Body cells use border fills including `9`, `10`, `11`, `12`, `13`, `14`.
- These border fills mix `DOUBLE_SLIM width=0.5 mm`, `SOLID width=0.5 mm`, `SOLID width=0.2 mm`, and `SOLID width=0.12 mm`.
- Current SVG output paints many black table lines around `0.07..0.1575px` because `svg_raster_stroke_width()` scales black strokes <= 1px by `0.175`.
- A border fix is plausible, but only if it is keyed to structural border type/width behavior. A blanket stroke multiplier is already rejected.

Width-class stroke probe:

```bash
python3 harness/svg_component_probe.py --variant base --variant 'stroke_eq_*' --variant 'stroke_min_*' \
  --out-dir /tmp/diff/_probe_stroke_width_classes overseas_training:1

python3 harness/svg_region_probe.py overseas_training:1 \
  --candidate-png /tmp/diff/_probe_stroke_width_classes/overseas_training_p1/stroke_eq_0.0875_x2.png \
  --region header:56,164,737,214 --region body_top:56,214,737,503 --region body_mid:56,503,737,831
```

Rejects:

- `stroke_eq_0.07_x2`, `stroke_eq_0.07_x3`, `stroke_eq_0.0875_x2`, `stroke_eq_0.105_x2`, `stroke_eq_0.1575_x2`, `stroke_min_0.12`, `stroke_min_0.16`, `stroke_min_0.20` are all neutral or worse on whole-page mean diff.
- Regional checks on the least-bad variants either do not move body regions or make header/body mean diff worse.
- Conclusion: do not patch SVG stroke width next. The table drift is more likely line/text vertical placement, text paint, or missing/shifted table-cell content than border thickness alone.

Stronger stroke follow-up:

```bash
python3 harness/svg_component_probe.py \
  --variant base \
  --variant stroke_min_0.30 \
  --variant stroke_min_0.50 \
  --variant stroke_eq_0.07_x5 \
  --variant stroke_eq_0.07_x7 \
  --out-dir /tmp/diff/_probe_stroke_stronger \
  overseas_training:1
```

Whole-page results:

| variant | mean diff | dark pixels | read |
|---|---:|---:|---|
| base | 21.54 | 66778 | current |
| `stroke_min_0.30` | 22.38 | 66836 | worse |
| `stroke_min_0.50` | 23.18 | 86259 | much worse |
| `stroke_eq_0.07_x5` | 22.36 | 66855 | worse |
| `stroke_eq_0.07_x7` | 22.78 | 81809 | worse |

Regional scoring also rejects the stronger variants:

- `stroke_min_0.30`: `table_lines_top` `42.19 -> 45.56`, `body_text_dense` `34.28 -> 35.29`.
- `stroke_min_0.50`: `table_lines_top` `42.19 -> 49.79`, `body_text_dense` `34.28 -> 36.19`.
- `stroke_eq_0.07_x7`: `table_lines_top` `42.19 -> 42.11` only neutral, while `body_text_dense` worsens to `36.11`.

Updated conclusion: table rule geometry is close, and RHWP table lines are very light in raster (`0.07px` black lines in the SVG), but width-only changes are not the fix for this page. They over-darken or disturb other line/text regions without resolving the header/body dark-pixel deficit.

Cell line-segment probe:

```bash
python3 harness/hwpx_table_source_probe.py /tmp/diff/overseas_training/source.hwpx --table-index 1
```

- Header cells have no explicit `vAlign`, one line segment, `vertpos=0`, `vertsize=1400`, `baseline=1190`, `spacing=280`.
- Body cells generally have no explicit `vAlign`, first line `vertpos=0`, and line heights around `900..1200`.
- This weakens a vertical-align-specific hypothesis. If the next patch targets table-cell text, it should investigate text paint/composition/line-height in cell layout rather than simple `vAlign` anchoring.

SVG text-region probe:

```bash
python3 harness/svg_text_region_probe.py overseas_training:1 \
  --region title:56,98,726,146 \
  --region header:56,164,737,214 \
  --region body_top:56,214,737,503 \
  --region body_mid:56,503,737,831 \
  --region body_bottom:56,831,737,1038

python3 harness/svg_text_region_probe.py 15_3740450_research_admin_innovation_meeting_template:2 \
  --region top_text:70,94,720,210 \
  --region contract_table:70,210,720,315 \
  --region timeline:70,315,720,655 \
  --region photo_table:70,655,720,1020
```

Key results:

| doc/page | region | SVG text runs | chars | read |
|---|---:|---:|---:|---|
| `overseas_training` p1 | title | 22 | 22 | title text is present, Gyeonggi title face, bold, 18.48px |
| `overseas_training` p1 | header | 19 | 19 | header text is present, mixed Gyeonggi title/body, 14.37px/12.32px |
| `overseas_training` p1 | body_top | 394 | 394 | dense table text is present; not a missing-text bug |
| `overseas_training` p1 | body_mid | 382 | 382 | dense table text is present; investigate paint/position/rasterization |
| `overseas_training` p1 | body_bottom | 251 | 251 | dense table text is present |
| `meeting_template` p2 | top_text | 0 | 0 | this region is not SVG text-run driven under the current box; do not use it for text-font fixes |
| `meeting_template` p2 | contract_table | 113 | 113 | Noto table text present; contract-table drift is still table/text-band specific |
| `meeting_template` p2 | timeline | 0 | 0 | timeline drift is not a text-run class |
| `meeting_template` p2 | photo_table | 66 | 66 | photo-table labels present, but high drift likely comes from images/edges/geometry |

Interpretation:

- `overseas_training` p1 sparse dark ink is not caused by missing SVG text nodes.
- The next structural probe should compare emitted text baselines/bands against source line segment metrics and Hancom ink bands.
- `meeting_template` p2 should be split into contract table text vs timeline/photo geometry; do not use a full-page score to justify text changes.

SVG cell-text placement probe:

```bash
python3 harness/svg_cell_text_probe.py overseas_training:1 --y-range 160,1038
python3 harness/svg_cell_text_probe.py 15_3740450_research_admin_innovation_meeting_template:2 --y-range 210,1020
```

Key results:

- `overseas_training` p1 has no text outside cell clips and no near-edge clipping flags in the focus table.
- Header cells place first text baselines at about `72%` of the cell height (`top_pad=21.3px` in a `29.6px` cell).
- Row-span date/location cells center text around `46-52%` of tall span cells.
- Dense schedule body cells often begin around `13-22%` of their cell height, then use multiple bands.
- `meeting_template` p2 contract/photo label cells are also not clipped; their first baselines sit around `40-66%` depending cell height.

Interpretation:

- Reject simple cell clipping as the cause of current sparse ink.
- Reject simple vertical-align anchoring as the immediate next patch; source cells mostly lack explicit `vAlign`, and emitted text is inside clips.
- Next structural target should shift from "is text present/clipped?" to "why does the rasterized text/rule ink carry much less dark coverage than Hancom despite present SVG text and aligned SVG rules?" Candidate sub-classes:
  - SVG text paint/rasterization for missing Korean fonts after visual size scaling.
  - `textLength`/`lengthAdjust` and per-glyph splitting causing lighter output than Hancom in table cells.
  - Font fallback weight/face mismatch specific to absent Gyeonggi table faces, but only if proven regionally without harming the board.

Table boundary probe:

```bash
python3 harness/table_boundary_probe.py overseas_training:1 --min-width-ratio 0.25 --svg-line-min-len 300
python3 harness/table_boundary_probe.py overseas_training:1 --min-width-ratio 0.25 --min-dark 120 --svg-line-min-len 300
```

Key results:

- Hancom has 19 long dark horizontal bands.
- RHWP raster has 0 long dark horizontal bands even with dark threshold lowered to 120.
- RHWP SVG has 19 horizontal line elements with close y positions and gaps.
- SVG stroke distribution in the focus table includes `('#000000', 0.07)` for 14 horizontal lines, plus a few `1.0`, `0.1575`, `0.105`.

Interpretation:

- Table rule geometry is close.
- Raster darkness is not Hancom-like, but width-only mutation probes are rejected, so a renderer patch must not simply inflate strokes globally.

Accepted text-emission candidate: single-character clusters should not force `textLength`.

Probe:

```bash
python3 harness/svg_component_probe.py \
  --variant base \
  --variant remove_text_length \
  --out-dir /tmp/diff/_probe_text_length \
  overseas_training:1 \
  15_3740450_research_admin_innovation_meeting_template:2
```

Whole-page probe results:

| doc/page | base | remove_text_length | read |
|---|---:|---:|---|
| `overseas_training` p1 | 21.54 | 21.50 | slight improvement |
| `meeting_template` p2 | 21.15 | 20.99 | improvement |
| `form_07` p5 | 13.29 | 13.28 | neutral/slight improvement |
| `accountability_eval` p4 | 15.37 | 15.36 | neutral/slight improvement |
| `meeting_summary` p1 | 17.96 | 17.96 | neutral |
| `report_form` p2 | 12.13 | 12.02 | improvement |

Regional probe results:

- `overseas_training` p1: neutral/slight improvement in `header_full`, `body_text_dense`, and `left_span`; header text itself unchanged.
- `meeting_template` p2: `contract_table` improves `32.19 -> 30.92`, `photo_table` improves `39.84 -> 39.68`.

Renderer patch:

- `src/renderer/svg.rs`: `svg_text_length_attrs()` now returns no `textLength` for one-character clusters.
- Rationale: normal paragraph/table text is emitted as per-character clusters. Forcing SVG `textLength`/`lengthAdjust` on a single glyph can distort static rasterization and hurt Hancom fidelity. Multi-codepoint clusters and char-overlap-specific paths are left alone.
- Focused test: `src/renderer/svg/tests.rs::test_svg_single_char_clusters_do_not_force_text_length`.

Validation:

```bash
docker compose --env-file .env.docker run --rm dev cargo test --lib renderer::svg::tests::test_svg_single_char_clusters_do_not_force_text_length -j 1
python3 scripts/check_renderer_overfit.py
docker compose --env-file .env.docker run --rm dev cargo fmt --check
docker compose --env-file .env.docker run --rm dev cargo build --release --bin rhwp -j 1
bash harness/gate.sh --no-build
python3 harness/fidelity_category_status.py --with-gallery \
  --out work/FIDELITY_VISUAL_STATUS_TEXT_LENGTH_2026-06-08.md \
  form_07_______________41KB accountability_eval overseas_training meeting_summary \
  15_3740450_research_admin_innovation_meeting_template report_form
```

Visual board after patch:

| doc | Hancom | RHWP | worst page | mean diff | read |
|---|---:|---:|---:|---:|---|
| `form_07_______________41KB` | 11 | 11 | 5 | 15.19 | unchanged from board |
| `accountability_eval` | 6 | 6 | 4 | 15.49 | slight improvement |
| `overseas_training` | 4 | 4 | 1 | 21.35 | slight improvement |
| `meeting_summary` | 3 | 3 | 1 | 17.86 | unchanged |
| `15_3740450_research_admin_innovation_meeting_template` | 5 | 5 | 2 | 20.69 | improvement |
| `report_form` | 6 | 6 | 2 | 12.15 | improvement |

Gate:

- `[gate] docs=10 improved=1 regressed=0 new_overflow=0`.
- Page counts remain clean on the active focus board.

## Current Bucket: Meeting Template Page 2 Image/Table Geometry

Target:

- `15_3740450_research_admin_innovation_meeting_template` page 2 remains the
  worst visual page on the active board after the textLength fix.
- Current board: Hancom 5 pages, RHWP 5 pages, worst page 2, mean diff 20.69.

Fresh probes:

```bash
python3 harness/svg_image_ink_probe.py 15_3740450_research_admin_innovation_meeting_template:2
python3 harness/svg_region_probe.py 15_3740450_research_admin_innovation_meeting_template:2 \
  --region contract_table:70,210,720,315 \
  --region timeline:70,315,720,655 \
  --region photo_table_top:70,655,720,760 \
  --region photo_table_images:70,760,720,1020 \
  --region full_photo_table:70,655,720,1020
python3 harness/svg_text_region_probe.py 15_3740450_research_admin_innovation_meeting_template:2 \
  --region contract_table:70,210,720,315 \
  --region timeline:70,315,720,655 \
  --region photo_table_top:70,655,720,760 \
  --region photo_table_images:70,760,720,1020 \
  --region full_photo_table:70,655,720,1020
python3 harness/hwpx_table_source_probe.py /tmp/diff/15_3740450_research_admin_innovation_meeting_template/source.hwpx --table-index 4
python3 harness/table_boundary_probe.py 15_3740450_research_admin_innovation_meeting_template:2 --min-width-ratio 0.25 --svg-line-min-len 250
python3 harness/svg_image_ink_probe.py 15_3740450_research_admin_innovation_meeting_template:3
```

Evidence:

- Page 2 image body has near-equal ink/luma totals but high mean diff, so this
  is likely alignment/crop/geometry rather than missing image data.
- Page 2 text probe shows no SVG text in the timeline/photo body regions; this
  is not primarily a typography bucket.
- Source table 4 has 4 picture cells. One picture has a large negative
  paragraph-relative vertical offset (`vertOffset=-17011`, about `-226.8px`).
- Current page 2 SVG image boxes:
  - full-width image: `75.6,497.9,718.1,649.9`
  - left photo: `82.4,748.1,386.3,1024.7`
  - right photo: `399.9,645.3,703.8,1009.4`
- Page 2 table lines show a large final table gap: line y values
  `659.3`, `695.3`, `731.2`, `1011.5`. The right photo starts above the
  table's top photo/header band, consistent with a negative-offset picture
  being applied against the wrong fragment/cell origin.
- Page 3 renders six image blocks cleanly, so the renderer is not generally
  dropping images in this file.

Current hypothesis:

- A non-TAC picture inside a split/repeated table cell with negative
  paragraph-relative vertical offset is being positioned too high relative to
  the current page fragment. The likely fix target is the table-cell picture
  placement path, not fonts or global image scaling.

Rejected for this bucket:

- Broad font changes: text probes show the main failing image/timeline regions
  contain no SVG text.
- Global stroke-width changes: already neutral/worse on `overseas_training`.
- Missing-image hypothesis: page 3 proves later image groups render; page 2
  mismatch is geometry/alignment.
- SVG-level cell image top clamp:
  `python3 harness/svg_component_probe.py --variant base --variant clamp_cell_image_top ...`
  produced no score or dark-pixel change on the target or focus photo docs
  (`meeting_template` p2 stayed `20.99`). The bad photo is not simply an SVG
  image above its emitted `cell-clip`; the likely issue is upstream fragment
  row geometry / picture fill area.

Accepted candidate: mixed TAC/non-TAC photo row alignment.

- Authoritative page dump:
  `PartialTable pi=18 ci=0 rows=0..3 cont=false` on page 2 and
  `PartialTable pi=18 ci=0 rows=3..6 cont=true` on page 3.
- Source paragraph 18 is a 6x2 RowBreak TopAndBottom photo grid. Row 2 mixes
  a non-TAC picture-only left cell and a TAC cropped picture-only right cell.
- Existing renderer logic derived a small y-offset for mixed photo rows, but
  only applied it to non-TAC pictures. The cropped TAC side stayed about 15px
  higher.
- Diagnostic probe:
  `shift_crop_y_15` improved target page 2 from `20.99 -> 20.50` and was
  neutral on `accountability_eval`, `overseas_training`, `meeting_summary`,
  and `report_form`.
- Renderer patch:
  `src/renderer/layout/table_layout.rs::mixed_photo_grid_picture_y_offset()`
  now applies the same derived offset to both TAC and non-TAC picture cells
  when a repeated photo-grid row contains both picture modes.
- Partial-table and full-table repeated-photo branches both call the shared
  helper.
- Focused regression:
  `mixed_photo_grid_offset_aligns_tac_and_non_tac_siblings`.

Validation:

```bash
docker compose --env-file .env.docker run --rm dev cargo test --lib mixed_photo_grid_offset_aligns_tac_and_non_tac_siblings -j 1
python3 scripts/check_renderer_overfit.py
docker compose --env-file .env.docker run --rm dev cargo fmt --check
docker compose --env-file .env.docker run --rm dev cargo build --release --bin rhwp -j 1
bash harness/gate.sh --no-build
python3 harness/fidelity_category_status.py --with-gallery \
  --out work/FIDELITY_VISUAL_STATUS_MIXED_PHOTO_TAC_OFFSET_2026-06-08.md \
  form_07_______________41KB accountability_eval overseas_training meeting_summary \
  15_3740450_research_admin_innovation_meeting_template report_form
```

Results:

- Focused test passed.
- Overfit scan passed with 8 known baseline findings.
- `cargo fmt --check` passed after formatting.
- Release build passed.
- Gate: `[gate] docs=10 improved=1 regressed=0 new_overflow=0`.
- Board: no page-count regressions. `meeting_template` remains 5/5 pages.
- `meeting_template` worst page moved from p2 to p3, worst score
  `20.69 -> 20.64`.
- Target page-2 photo-table regional score improved:
  `full_photo_table 39.68 -> 37.27`, `photo_table_images 40.21 -> 39.81`.

## Current Bucket: Meeting Template Page 3 Follow-Up

Target after mixed-row patch:

- `15_3740450_research_admin_innovation_meeting_template` still has visual
  drift; worst page moved from page 2 to page 3.
- Board after mixed-row patch: Hancom 5 pages, RHWP 5 pages, worst page 3,
  mean diff 20.64.

Evidence:

- Page 3 has two image-table contexts:
  - `PartialTable pi=18 ci=0 rows=3..6 cont=true` from the continued 6x2
    RowBreak photo grid.
  - `Table pi=21 ci=0` 4x2 TAC RowBreak photo table.
- `svg_text_region_probe` shows text only in the label/header bands. Middle and
  bottom photo regions have no SVG text, so this is not a typography bucket.
- Page 3 has no `crop-clip-*` SVG clips; the page-2 cropped TAC image class is
  not involved.

Rejected probes:

- `shift_crop_y_15`: no effect on page 3 (`20.54 -> 20.54`) because there are
  no crop clips.
- Plain image height scale worsened the target:
  - `image_height_x1.05`: `20.54 -> 24.78`
  - `image_height_x1.08`: `20.54 -> 26.82`
  - `image_height_x1.12`: `20.54 -> 28.92`
- Plain image vertical shifts worsened the target:
  - `image_y_m6`: `20.54 -> 23.18`
  - `image_y_m12`: `20.54 -> 27.22`
  - `image_y_p6`: `20.54 -> 25.76`
  - `image_y_p12`: `20.54 -> 30.32`
- Image CSS darken/contrast filters worsened the target:
  - `image_filter_b95_c110`: `20.54 -> 21.79`
  - `image_filter_b90_c115`: `20.54 -> 23.34`
  - `image_filter_b85_c120`: `20.54 -> 25.32`
- Lower-band y-shift after `y>=430` worsened the target:
  - `shift_y_after_430_p12`: `20.54 -> 23.24`
  - `shift_y_after_430_m12`: `20.54 -> 26.51`

Conclusion:

- Do not patch page 3 from current evidence. The obvious geometry/tonal levers
  all worsen the page. Keep it on the queue, but move to another category until
  a more specific invariant is found.

## Current Bucket: Overseas Training Page 1

Target:

- `overseas_training` page 1 remains the highest-score stable page-count drift
  on the focus board (`21.35`/`21.50` depending on probe raster path).

Evidence:

- Page 1 is a title table plus a large `PartialTable pi=1 ci=0 rows=0..15`
  from a 48x5 CellBreak table.
- Table boundary probe shows horizontal line positions are already close to
  Hancom. Example RHWP/Hancom bands differ by only a few px through most rows.
- Region probe shows RHWP has much lower dark/nonwhite density across dense
  text regions, but earlier font family/weight and stroke-width probes were
  neutral or worse.

Rejected probes:

- Broad Gyeonggi font size/weight changes were already worse:
  `font_size_gyeonggi_x1.10`, `weight_gyeonggi_600`.
- Global thin-line/stroke changes were neutral or worse.
- Text stroke thickening worsened all checked docs:
  - `overseas_training` p1: `21.50 -> 21.73` at `0.15`,
    `21.50 -> 21.92` at `0.25`
  - `accountability_eval` p4: `15.36 -> 15.85` / `16.25`
  - `meeting_summary` p1: `17.96 -> 18.19` / `18.37`
  - `meeting_template` p3: `20.54 -> 20.69` / `20.73`
  - `report_form` p2: `12.02 -> 12.24` / `12.35`

Conclusion:

- Do not apply typography thickening or global table-line changes for
  `overseas_training`. The remaining mismatch needs a more specific structural
  invariant, likely around cell text composition/raster font substitution, not
  a blanket style adjustment.

Font-face probe follow-up:

```bash
python3 harness/svg_font_face_probe.py --variant base --variant 'open_korean_*' \
  --out-dir /tmp/diff/_probe_fontface_overseas_filtered_2026-06-08 \
  overseas_training:1

python3 harness/svg_font_face_probe.py --variant base --variant 'serif_*' \
  --variant 'malgun_pretendard_*' --variant malgun_nanum_regular \
  --out-dir /tmp/diff/_probe_fontface_overseas_light_2026-06-08 \
  overseas_training:1

python3 harness/svg_font_face_probe.py --variant base --variant malgun_nanum_regular \
  --out-dir /tmp/diff/_probe_fontface_malgun_nanum_guards_2026-06-08 \
  accountability_eval:4 meeting_summary:1 report_form:2 \
  15_3740450_research_admin_innovation_meeting_template:3
```

Harness improvement:

- `harness/svg_font_face_probe.py` now supports repeatable `--variant` glob
  filters, matching the component-probe workflow. This keeps font-face checks
  cheap enough to use inside the category loop instead of rastering every
  alias on every guard page.

Rejected font-face candidates:

- `open_korean_baseline` worsened the target from `21.50 -> 22.88`.
- `open_korean_nanum` worsened the target from `21.50 -> 22.15`.
- `malgun_nanum_regular` weakly improved the target whole-page score
  (`21.50 -> 21.27`) and was neutral/slightly positive on guard pages, but
  regional evidence rejects it as a faithful fix:
  - header mean improved only `~35.8 -> 34.68`, while dark ink became even
    sparser (`-82.7%` vs oracle).
  - body_top/body_mid/body_bottom means improved slightly, but dark deltas
    worsened to roughly `-71%`, `-67%`, and `-75%`.
- Therefore, do not patch SVG font-face policy for `overseas_training` yet.
  The score movement is mostly a metric artifact from lighter/less intrusive
  text, not a Hancom-like restoration of table text/ruling density.

## Current Bucket: Meeting Summary Page 1

Target:

- `meeting_summary` page 1 remains visual drift on the focus board:
  Hancom 3 pages, RHWP 3 pages, worst page 1, mean diff `17.86`.
- It is a useful guard for table/text paint because it has no images on the
  page and its table boundaries are close to Hancom.

Probes:

```bash
python3 harness/svg_component_probe.py --variant base --variant hide_text \
  --variant hide_lines --variant remove_text_length --variant 'shift_y_after_*' \
  --out-dir /tmp/diff/_probe_meeting_summary_p1_components_2026-06-08 \
  meeting_summary:1

python3 harness/svg_geometry_probe.py meeting_summary:1

python3 harness/svg_line_region_probe.py meeting_summary:1 --y-min 121 \
  --y-max 1026 --out-dir /tmp/diff/_probe_meeting_summary_p1_lines_2026-06-08

python3 harness/svg_font_face_probe.py --variant base --variant malgun_nanum_regular \
  --variant malgun_pretendard_regular --variant malgun_pretendard_medium \
  --out-dir /tmp/diff/_probe_fontface_meeting_summary_2026-06-08 \
  meeting_summary:1
```

Findings:

- Geometry is close:
  - Hancom long horizontal bands at `121.5`, `156.7`, `255.0`, `309.4`,
    `474.9`, `642.0`, `785.1`, `1024.1`.
  - RHWP SVG horizontal lines at `122.0`, `156.9`, `255.9`, `309.1`,
    `475.8`, `642.5`, `785.5`, `1025.0`.
  - This is not a table-placement or page-flow bug.
- Text regions show the same sparse-ink class as `overseas_training`:
  - `top_table` dark delta `-69.7%`.
  - `body_a` dark delta `-67.6%`.
  - `body_b` dark delta `-69.6%`.
- `remove_text_length` is neutral on this page (`17.96 -> 17.96`), so the
  accepted single-character `textLength` fix does not explain this remaining
  class.
- Simple vertical shifts are rejected:
  - `shift_y_after_430_p12`: `17.96 -> 19.45`.
  - `shift_y_after_430_m12`: `17.96 -> 19.38`.
- Line/stroke changes are rejected:
  - `thin_x0.50`: `17.96 -> 17.91`, too weak and moves in the wrong
    dark-ink direction.
  - `thick_x1.50`: `17.96 -> 18.00`.
  - `thick_x2.00`: `17.96 -> 18.05`.
  - Hiding lines lowers the raw metric (`15.24`) but is obviously not a
    faithful renderer fix.
- Font-face aliases are rejected:
  - `malgun_nanum_regular`: `17.96 -> 17.90`, but dark pixels drop
    `70284 -> 67114`.
  - `malgun_pretendard_regular`: `17.96 -> 17.92`, dark pixels drop.
  - `malgun_pretendard_medium`: `17.96 -> 17.92`, too weak.

Decision:

- Do not patch `meeting_summary` from current evidence.
- It strengthens the broader conclusion that the remaining table/text visual
  class is not solved by global stroke width, font-face alias, textLength, or
  y-shift changes.
- Keep it as a guard page for future text/rasterization work: any accepted
  table-text fix should improve `meeting_summary` regions without reducing
  dark ink further.

## Current Bucket: Form 07 Page 5

Target:

- `form_07_______________41KB` page 5 remains just above the visual-drift
  threshold on the refreshed board: Hancom 11 pages, RHWP 11 pages, worst page
  5, mean diff `15.19`.
- This page is useful because the document already drove page-count fixes; any
  remaining patch must not disturb the now-correct 11-page split.

Probes:

```bash
python3 harness/svg_component_probe.py --variant base --variant hide_text \
  --variant hide_lines --variant remove_text_length --variant 'shift_y_after_*' \
  --variant 'thin_stroke*' --variant 'stroke_min_*' \
  --out-dir /tmp/diff/_probe_form07_p5_components_2026-06-08 \
  form_07_______________41KB:5

python3 harness/svg_geometry_probe.py form_07_______________41KB:5

python3 harness/svg_region_probe.py form_07_______________41KB:5 \
  --region top:30,40,760,220 \
  --region mid_a:30,220,760,500 \
  --region mid_b:30,500,760,800 \
  --region bottom:30,800,760,1080

python3 harness/svg_text_region_probe.py form_07_______________41KB:5 \
  --region top:30,40,760,220 \
  --region mid_a:30,220,760,500 \
  --region mid_b:30,500,760,800 \
  --region bottom:30,800,760,1080
```

Findings:

- Page has no images.
- Coarse table geometry is close: RHWP SVG has the filled/ruling table band at
  `y=132.3..1003.3`, while Hancom raster table content spans roughly
  `135.1..1004.2`.
- RHWP text is present in all expected regions, mostly `함초롬바탕` 12px.
- Regional read:
  - `top` mean `11.21`, dark delta `-20.2%`, nonwhite delta `+15.7%`.
  - `mid_a` mean `16.59`, dark delta `-15.0%`, nonwhite delta `+10.3%`.
  - `mid_b` mean `17.58`, dark delta `-10.1%`, nonwhite delta `+13.2%`.
  - `bottom` mean `15.48`, dark delta `-29.1%`, nonwhite delta `+7.6%`.
- This is residual table/text/fill raster drift, not a page-flow or image
  placement class.

Rejected candidates:

- `remove_text_length`: neutral (`13.28 -> 13.28` in direct page probe).
- Stroke thickening worsens:
  - `thin_stroke_x1.50`: `13.28 -> 13.35`.
  - `thin_stroke_x2.00`: `13.28 -> 13.42`.
  - `stroke_min_0.50`: `13.28 -> 14.13`.
- Stroke thinning is too weak and not a structural fix:
  - `thin_stroke_x0.50`: `13.28 -> 13.22`.
- Lower-page y-shifts worsen:
  - `shift_y_after_430_p12`: `13.28 -> 13.96`.
  - `shift_y_after_430_m12`: `13.28 -> 13.49`.
- Fill-color mutations are rejected:
  - `#fff7cc -> #ffffff`: `13.28 -> 14.63`.
  - `#fff7cc -> #fffbe6`: `13.28 -> 13.97`.
  - `#fff7cc -> #fff0aa`: `13.28 -> 14.27`.
  - `#fff7cc -> #faf7e8`: `13.28 -> 14.04`.

Decision:

- Do not patch `form_07` page 5 from current evidence.
- Keep it as a guard page for table/text/fill raster work. A future accepted
  fix must preserve the 11/11 page count and improve the mid/bottom regions
  without simply hiding fills or thinning lines.

## Validation Rules

Before accepting any renderer patch:

```bash
python3 scripts/check_renderer_overfit.py
docker compose --env-file .env.docker run --rm dev cargo fmt --check
docker compose --env-file .env.docker run --rm dev cargo build --release --bin rhwp -j 1
bash harness/gate.sh --no-build
python3 harness/fidelity_category_status.py --with-gallery --out work/FIDELITY_VISUAL_STATUS_NEXT_2026-06-08.md \
  form_07_______________41KB accountability_eval overseas_training meeting_summary \
  15_3740450_research_admin_innovation_meeting_template report_form
```

Acceptance:

- No fixture-name/body-text/document-fingerprint conditions in renderer.
- Focused regression test covers the structural invariant.
- No page-count regressions.
- No new overflow.
- Worst-page visual score improves on target without worsening the focus board.
