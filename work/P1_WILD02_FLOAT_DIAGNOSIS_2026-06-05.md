# P1 Wild02 Float Diagnosis -- 2026-06-05

Target: `wild_02_paper_fig_10MB`

Current decision: DIAGNOSE / BANK unless a narrow cross-column float-reserve
discriminator appears. Do not merge this into the `med_02` scanned-photo rule.

## Why This Is A Separate Family

`med_02____2_4MB` is page-relative full-page scanned-photo content:

- `textWrap=SQUARE`
- `vertRelTo=PAPER`
- `horzRelTo=PAPER|PAGE`
- near-full-page image extent
- following flow content paints behind the visual scan page

`wild_02_paper_fig_10MB` is different:

- paragraph-relative pictures,
- column-relative horizontal anchor,
- multi-column flowing text,
- mix of `TOP_AND_BOTTOM` and `SQUARE`,
- no page-relative full-page scan group.

A broad rule that fixes both is probably too dangerous. Treat `wild_02` as
multi-column float reservation / split-flow behavior, not scanned-photo
pagination.

## Visual Evidence

Artifacts:

- `/tmp/diff/wild_02_paper_fig_10MB/look/page-01.png`
- `/tmp/diff/wild_02_paper_fig_10MB/look/page-09.png`
- `/tmp/diff/_gallery3/wild_02_paper_fig_10MB/index.html`
- `/tmp/diff/_gallery3/wild_02_paper_fig_10MB/page-01.png`
- `/tmp/diff/_gallery3/wild_02_paper_fig_10MB/page-09.png`

Observed page 1:

- Hancom reserves a large top band before the title/body text.
- The figure is partly in the right side of the page and text begins far lower.
- rhwp starts the title/body near the top and paints the figure into the right
  column, causing visible text/figure overlap and forward packing.

Observed page 9:

- Hancom has real body content.
- rhwp has no page 9 at all.
- This is not only an overlap bug; it is also under-pagination and late-content
  loss.

Acceptance therefore must include:

- reduced overlap on page 1,
- page count moving from 7 toward Hancom's 9,
- late content no longer missing,
- no regression in multi-column float guard docs.

## Current Dump-Pages Evidence

Command:

```bash
docker compose --env-file .env.docker run --rm -v /tmp/diff:/diff dev \
  /app/target/release/rhwp dump-pages /diff/wild_02_paper_fig_10MB/source.hwpx
```

Result summary:

```text
document loads as 7 rhwp pages

page 1:
  col0 used=695.4px, hwp_used~435.2px, diff=+260.2px
  col1 used=279.5px, hwp_used~279.5px, diff=+0.0px
  items include:
    FullParagraph pi=0
    Shape pi=0 picture
    PartialParagraph pi=2 lines=0..19
    PartialParagraph pi=2 lines=19..35
    Shape pi=2 picture

page 3:
  col1 diff=-33.0px

page 4:
  col0 diff=-163.1px
  col1 diff=-288.0px

page 5:
  col1 diff=-342.1px

page 9:
  missing in rhwp
```

Interpretation:

- Page 1 already shows a large reservation mismatch.
- Later negative diffs show cumulative forward packing after the first float
  decision goes wrong.
- The dump metric is useful here, unlike `med_02`, because line-segment and
  visual drift both point to a flow/reservation issue.

## Structural XML Evidence

Source: `/tmp/diff/wild_02_paper_fig_10MB/source.hwpx`

Relevant controls:

```text
PI 0:
  pic id=1103945075
  textWrap=TOP_AND_BOTTOM
  treatAsChar=0
  flowWithText=1
  allowOverlap=0
  vertRelTo=PARA
  horzRelTo=COLUMN
  vertOffset=0
  horzOffset=40201
  sz width=27420 height=23855

PI 2:
  pic id=1100227298
  textWrap=SQUARE
  treatAsChar=0
  flowWithText=1
  allowOverlap=0
  vertRelTo=PARA
  horzRelTo=COLUMN
  vertOffset=31699
  horzOffset=39522
  sz width=14389 height=12761

PI 4:
  pic id=1103945071
  textWrap=TOP_AND_BOTTOM
  treatAsChar=0
  flowWithText=1
  allowOverlap=0
  vertRelTo=PARA
  horzRelTo=COLUMN
  vertOffset=3492
  horzOffset=39769
  sz width=13438 height=10322

PI 5:
  pic id=1103945079
  textWrap=TOP_AND_BOTTOM
  vertRelTo=PARA
  horzRelTo=COLUMN
  vertOffset=1492
  horzOffset=14956
  sz width=23170 height=12322

  pic id=1103945083
  textWrap=TOP_AND_BOTTOM
  vertRelTo=PARA
  horzRelTo=COLUMN
  vertOffset=1500
  horzOffset=469
  sz width=35619 height=22210
```

## Likely Owner Code

- `src/renderer/typeset.rs`
  - `compute_body_wide_top_reserve_for_para`
  - `fw_square_float_ctrls`
  - `pushdown_groups`
  - multi-column vpos reset handling
- `src/renderer/float_placement.rs`
  - `is_para_topbottom_float`
  - `horizontal_range`
  - `FloatLaneSet`
- `src/renderer/layout/paragraph_layout.rs`
  - Square wrap zone and line-segment column width use

Existing relevant behavior:

- body-wide `TOP_AND_BOTTOM` reserve currently requires object width at least
  `0.8 * body_width`.
- full-width stack/split currently targets terminal galleries with width at
  least `0.9 * column_width`.
- `wild_02` PI0 is not full body width, but its column-relative horizontal
  offset crosses into the other column/page side visually. The missing reserve
  may be about horizontal span crossing a column boundary, not about raw object
  width alone.

## Cross-Column Geometry Probe

Section geometry:

```text
pagePr width=59528 height=84188
colPr colCount=2 sameSz=1 sameGap=2268
dump body_area: x=37.8 y=56.7 w=1046.9 h=680.3
gap: 2268 hu ~= 30.2 px
inferred equal column width: (1046.9 - 30.2) / 2 ~= 508.3 px
col0 approx: x=37.8..546.1
col1 approx: x=576.3..1084.6
```

Computed picture ranges, using `horzRelTo=COLUMN` left alignment:

```text
PI0 TOP_AND_BOTTOM:
  x_abs ~= 573.8..939.4
  width ~= 365.6 px
  y_offset ~= 0.0 px
  height ~= 318.1 px
  body-width fraction ~= 0.35

PI2 SQUARE:
  x_abs ~= 564.8..756.6
  width ~= 191.9 px
  y_offset ~= 422.7 px
  height ~= 170.1 px

PI4 TOP_AND_BOTTOM:
  x_abs ~= 568.1..747.2
  y_offset ~= 46.6 px
  height ~= 137.6 px

PI5 TOP_AND_BOTTOM #1:
  x_abs ~= 237.2..546.1
  y_offset ~= 19.9 px
  height ~= 164.3 px

PI5 TOP_AND_BOTTOM #2:
  x_abs ~= 44.1..519.0
  y_offset ~= 20.0 px
  height ~= 296.1 px
```

Interpretation:

- PI0 is too narrow to pass `compute_body_wide_top_reserve_for_para`'s current
  `shape_w >= body_w * 0.8` test.
- But PI0 begins just before the second column and spans the second-column top
  band. Hancom appears to reserve that top band before flowing the title/body.
- The better discriminator to test next is therefore:
  `TOP_AND_BOTTOM + flowWithText + allowOverlap=false + vertRelTo=PARA +
  horzRelTo=COLUMN + near page/paragraph top + horizontal range crosses a
  column boundary or overlaps a non-host column`.
- This should be implemented only if the resulting native gate shows changes
  limited to float-heavy docs and visual output improves. Otherwise bank it.

## Candidate Hypotheses To Test

### H1 -- Cross-column TopAndBottom reserve

Structural discriminator:

- non-TAC picture/shape,
- `textWrap=TOP_AND_BOTTOM`,
- `flowWithText=1`,
- `allowOverlap=0`,
- `vertRelTo=PARA`,
- `horzRelTo=COLUMN`,
- visual horizontal range crosses from current column into another column or
  outside the body edge,
- object begins near the top of the paragraph/page.

Possible behavior:

- reserve the object's vertical extent for the affected column set before
  flowing paragraph text.

Likely implementation point:

- refine `compute_body_wide_top_reserve_for_para` so "body-wide" can also mean
  "column-relative range crosses into another column near the page top" for
  non-overlapping `TOP_AND_BOTTOM` flow objects.
- raw width alone is insufficient for `wild_02`.

Risk:

- may over-paginate correct two-column documents if "crosses column" is too
  loose.

Probe result:

- Tried a narrow source patch that broadened the body-wide reserve guard for
  non-TAC `TOP_AND_BOTTOM`, `flowWithText=1`, `allowOverlap=0`,
  `vertRelTo=PARA`, `horzRelTo=COLUMN` objects whose computed horizontal range
  overlaps a non-host column.
- Applied the same concept to the pagination reserve and render-tree
  body-wide reserve path, then built `target/release/rhwp`.
- Focused tests passed:
  - `page_relative_scan_group_breaks_before_following_flow`
  - a geometry-only `non_host_column_overlap_detects_offset_float` probe test
- But `wild_02` dump-pages did not improve:
  - page count remained 7, not toward Hancom's 9,
  - page 1 col1 `used` jumped from `279.5px` to `597.5px`,
  - page 1 col1 `diff` worsened from `+0.0px` to `+318.1px`.
- The probe was reverted. Release binary was rebuilt after revert, and
  `wild_02` returned to the baseline 7-page dump with page 1 col1 diff `+0.0px`.

Decision:

- Reject this simple cross-column reserve patch.
- The geometry is real, but reserve must be tied to the actual paragraph
  split/line-segment flow model, not simply added as a body-wide top reserve.
- Next `wild_02` probe should inspect how PI0/PI2 line segments are split and
  how render-time `body_wide_reserved` interacts with `vpos` lazy bases.

### H2 -- Mixed TopAndBottom + Square wrap consistency

Structural discriminator:

- a paragraph sequence has `TOP_AND_BOTTOM` and later `SQUARE` pictures whose
  line segments encode narrowed column widths,
- paginator current height and renderer visual placement disagree.

Possible behavior:

- unify Square wrap anchor reservation with the actual painted object extent.

Risk:

- high. The Square wrap path is already guarded by previous fixes; broad
  changes can regress `wc47`, `wc51`, and science/image docs.

Probe result:

- Tried a narrow text-host pre-reserve candidate: if a paragraph has visible
  text and a non-overlapping, para-relative `TopAndBottom` float starting within
  the first line, reserve the object before laying out that same paragraph's
  text and skip the later duplicate pushdown for that control.
- Focused detector test passed, but target dump rejected the behavior:
  - page count stayed 7, not toward Hancom's 9.
  - page 1 was unchanged: column 0 remained `diff=+260.2px`.
  - later columns worsened badly: page 3 col1 `diff=+333.2px`, page 5 col0
    `diff=-584.1px`, page 5 col2 `diff=+676.0px`.
- Dump evidence:
  `/tmp/diff/wild_02_paper_fig_10MB/dump_pages_text_host_topbottom.txt`
- Decision:
  reverted from source. Do not retry a simple same-paragraph pre-reserve unless
  it is tied to the page/column vpos reset model; plain current-height
  insertion corrupts later multi-column bands.

### H3 -- Multi-column vpos reset semantics

Structural discriminator:

- paragraph line segments reset vpos inside one paragraph across columns/pages,
- current code treats reset as normal continuation while Hancom starts a new
  flow band after float reservation.

Possible behavior:

- refine only when a non-TAC flowing float exists in the same paragraph or
  immediate paragraph band.

Risk:

- very high. Cached line-segment behavior affects many docs.

## Guard Docs

Must visually check any changed docs:

- `wc47_6pg`
- `wc51_4pg`
- `wc69_9pg`
- `wc04_4pg`
- `wb03_physics_lab_2pg`

If any text-only or unrelated green doc changes page count, revert.

## Fast Validation

Use native validation only until a structural fix proves itself:

```bash
CARGO_BUILD_JOBS=1 docker compose --env-file .env.docker run --rm dev \
  cargo build --release --bin rhwp

bash harness/gate.sh --no-build
python3 scripts/check_renderer_overfit.py
python3 harness/look.py /tmp/diff/wild_02_paper_fig_10MB --export
```

Treat `bash harness/focus_gate.sh quick --build` as informative until P0
fixture/oracle cleanup is complete.

## Bank / Land Rule

LAND only if:

- page 1 overlap is visibly reduced,
- rhwp page count moves toward 9,
- late Hancom page 9 content is represented in rhwp,
- changed docs are float-heavy and visually checked,
- full gate reports no new page-count regressions or overflow,
- overfit check passes.

BANK if:

- the only working rule is "all TopAndBottom pictures reserve a new page",
- the rule depends on filename, title text, or page number,
- three probe/build cycles do not produce a clean structural discriminator,
- the patch improves page count but visually worsens multi-column flow.

Current `wild_02` status:

- BANKED for this turn after one rejected H1 probe.
- Not permanently abandoned; it remains P1b, but it should not block landing the
  narrower `med_02` scanned-photo fix.

## Fresh Current-Source Confirmation

Command:

```bash
python3 harness/look.py /tmp/diff/wild_02_paper_fig_10MB --export
docker compose --env-file .env.docker run --rm -v /tmp/diff:/diff \
  -e RHWP_TABLE_DRIFT=1 -e RHWP_TYPESET_DRIFT=1 dev \
  /app/target/release/rhwp dump-pages /diff/wild_02_paper_fig_10MB/source.hwpx \
  > /tmp/diff/wild_02_paper_fig_10MB/dump_pages_current.txt \
  2> /tmp/diff/wild_02_paper_fig_10MB/drift_current.txt
```

Result:

```text
TRIPWIRE Hancom=9 rhwp=7
page 1 col0: used=695.4px, hwp_used≈435.2px, diff=+260.2px
page 1 col1: used=279.5px, hwp_used≈279.5px, diff=+0.0px
page 4 col0: diff=-163.1px
page 4 col1: diff=-288.0px
page 5 col1: diff=-342.1px
page 9: missing in rhwp
```

Visual read:

- Page 1: Hancom reserves a large top band around the right-side figure before
  the title/body. RHWP starts text at the top and lets the figure collide with
  the second-column text.
- Page 9: Hancom has real late body content. RHWP has no page 9.

Next probe should focus on H3: multi-column `vpos` reset and line-segment split
semantics around paragraphs that own non-overlapping flowing floats. Do not
retry the rejected simple body-wide/cross-column reserve or same-paragraph
pre-reserve shapes unless the new evidence explains why those probes overcounted
later columns.

## H3 Diagnostic Probe

Added temporary diagnostic logging gated by `RHWP_MC_FLOAT_DRIFT` in the
multi-column paragraph path. This is behavior-neutral and exists to inspect
line-segment split semantics before trying another renderer rule.

Command:

```bash
docker compose --env-file .env.docker run --rm -v /tmp/diff:/diff \
  -e RHWP_TYPESET_DRIFT=1 \
  -e RHWP_TYPESET_DRIFT_LINES=1 \
  -e RHWP_MC_FLOAT_DRIFT=1 \
  dev /app/target/release/rhwp dump-pages \
  /diff/wild_02_paper_fig_10MB/source.hwpx \
  > /tmp/diff/wild_02_paper_fig_10MB/dump_pages_mc_float_lines.txt \
  2> /tmp/diff/wild_02_paper_fig_10MB/drift_mc_float_lines.txt
```

New evidence:

```text
MC_FLOAT_PARA pi=3 col=0 lines=38 breaks=[0,21]
MC_FLOAT_PART pi=3 part=0 col=0 lines=0..21 first_vpos=23855 last_vpos=49615
MC_FLOAT_PART pi=3 part=1 col=1 lines=21..38 first_vpos=0 last_vpos=20480

pi=4 starts in col=1 and has vpos reset lines 22 and 61
pi=5 starts in col=1 and has vpos reset lines 11 and 41
pi=6 starts in col=1 and has vpos reset lines 6 and 45
pi=7 starts in col=1 and has vpos reset lines 5 and 44
```

Interpretation:

- Only `pi=3` goes through the explicit `typeset_multicolumn_paragraph` path
  because `detect_column_breaks_in_paragraph` currently runs only when
  `st.col_count > 1 && st.current_column == 0`.
- Later paragraphs start while `st.current_column == 1`, so their internal
  `vpos=0` reset bands are handled by the generic line split loop instead.
- The target defect may therefore be less about detecting resets and more about
  how post-reset bands are charged against `current_height` when a flowing float
  is present nearby. The large `TYPESET_DRIFT_PI` gaps for `pi=4..6` are caused
  by computing paragraph-level `vpos_h` across reset bands; a patch must reason
  per reset band, not with whole-paragraph height.

Next safe probe:

- Add a diagnostic-only band summary for generic line-loop splits: for each
  emitted `PartialParagraph`, log `cursor_line..end_line`, first/last vpos,
  cumulative line advance, and the saved vpos band height.
- If the saved band height and charged height diverge specifically on
  post-reset bands with nearby non-overlapping flowing floats, then test a
  narrow per-band accounting rule.
- Do not add another broad reserve or global reset rule until this per-band
  comparison is available.

## H3 Saved-Band Accounting Candidate

Candidate:

- In the generic line split loop, for multi-column post-reset bands
  (`cursor_line > 0`, first saved vpos is `0`), if the saved line-segment band
  height exceeds the composed line-advance height by more than `20px`, charge
  the saved band height as the partial paragraph height.
- This is structural: it uses multi-column state plus saved `LineSeg` geometry,
  not document text or filename.

Target result:

```text
Before:
page 4 col0: used=522.4px, hwp_used≈685.5px, diff=-163.1px

After candidate:
page 4 col0: used=685.5px, hwp_used≈685.5px, diff=+0.0px
MC_LINE_PART pi=5 col=0 lines=11..41
  raw_h=522.4 saved_band_h=685.5 trust_saved=true
```

Limit:

- `wild_02` still renders 7 pages vs Hancom 9.
- Page 1 figure/text overlap remains.
- Therefore this is not the `wild_02` fix by itself. It is a narrow
  measurement/accounting sub-fix that removes one proven underfilled reset band.

Validation:

```text
targeted Rust test: page_relative_scan_group_breaks_before_following_flow ok
renderer overfit check: passed with 8 known baseline findings
broad gate: docs=151 improved=1 regressed=0 new_overflow=0
  IMPROVE wc31_17pg: 12->13 (oracle 17)
target rerender: Hancom=9 rhwp=7
```

Next evidence path:

- The remaining large underfills are page 4 col1 (`diff=-288.0px`) and page 5
  col1 (`diff=-342.1px`).
- Those pages include non-TAC `TopAndBottom` picture/shape items emitted by the
  earlier pushdown path around the `pushdown_groups` logic, not by the generic
  `Control::Shape | Control::Picture` branch. The attempted `MC_SHAPE_CTRL`
  diagnostic did not fire for these items, confirming the wrong branch.
- Next diagnostic should be placed directly around the `pushdown_h` /
  `pushdown_groups` block that pushes `PageItem::Shape` and adjusts
  `st.current_height`, logging `already_accounted`, `top`, `bottom`, `extra`,
  and `current_height` before/after for `TopAndBottom` non-TAC pictures/shapes.

## H3 Pushdown Trace

Added diagnostic-only logging behind `RHWP_FLOAT_PUSHDOWN_DRIFT` in the
`pushdown_h` / `pushdown_groups` block. This changes no behavior unless the env
var is set.

Command:

```bash
docker compose --env-file .env.docker run --rm -v /tmp/diff:/diff \
  -e RHWP_TABLE_DRIFT=1 \
  -e RHWP_TYPESET_DRIFT=1 \
  -e RHWP_FLOAT_PUSHDOWN_DRIFT=1 \
  dev /app/target/release/rhwp dump-pages \
  /diff/wild_02_paper_fig_10MB/source.hwpx \
  > /tmp/diff/wild_02_paper_fig_10MB/dump_pages_float_pushdown.txt \
  2> /tmp/diff/wild_02_paper_fig_10MB/drift_float_pushdown.txt
```

Key trace:

```text
FLOAT_PUSHDOWN: pi=0 ci=1 col=0 action=add accounted=false
  top=0.0 bottom=318.1 obj_h=318.1 extra=318.1
  cur_before=34.7 cur_after=352.7 groups=1

FLOAT_PUSHDOWN: pi=4 ci=0 col=1 action=add accounted=false
  top=46.6 bottom=184.2 obj_h=137.6 extra=137.6
  cur_before=307.2 cur_after=444.8 groups=1

FLOAT_PUSHDOWN: pi=5 ci=0 col=1 action=add accounted=false
  top=19.9 bottom=184.2 obj_h=164.3 extra=164.3
  cur_before=85.3 cur_after=249.6 groups=1

FLOAT_PUSHDOWN: pi=5 ci=1 col=1 action=group_grow accounted=false
  top=20.0 bottom=316.1 obj_h=296.1 extra=296.1
  cur_before=249.6 cur_after=381.5 groups=1
```

Interpretation:

- PI0 is not missing object-height pagination. The engine already adds the
  318.1px TopAndBottom pushdown on page 1.
- The simple cross-column/body-wide reserve failed because it double-counted
  the already-charged PI0 height into column 1 without fixing the line split.
- PI4/PI5 TopAndBottom objects are also charged, including side-by-side group
  growth for the two PI5 pictures.
- Remaining target defects are therefore:
  - render placement: page 1 still paints the PI0 figure over text instead of
    reserving/flowing the same band visually;
  - reset-band accounting: page 4/5 underfills remain around post-reset
    partial paragraphs even after pushdown is applied.

Next safe probe:

- Compare pagination charge to render-time placement for PI0:
  the paginator charges PI0 before PI1/PI2, but the renderer still lets the
  picture/text collide.
- Add render-tree geometry diagnostics around `layout_shape_item` for PI0 and
  the following paragraph y positions before trying another pagination rule.

## Render Cursor Probe

Added diagnostic-only logging behind `RHWP_FLOAT_RENDER_DRIFT` in
`layout_shape_item` for non-TAC pictures.

Command:

```bash
docker compose --env-file .env.docker run --rm -v /tmp/diff:/diff \
  -e RHWP_TABLE_DRIFT=1 \
  -e RHWP_FLOAT_PUSHDOWN_DRIFT=1 \
  -e RHWP_FLOAT_RENDER_DRIFT=1 \
  dev /app/target/release/rhwp export-svg \
  /diff/wild_02_paper_fig_10MB/source.hwpx \
  -o /diff/wild_02_paper_fig_10MB/rhwp_svg_cur \
  > /tmp/diff/wild_02_paper_fig_10MB/export_render_topbottom_probe.stdout \
  2> /tmp/diff/wild_02_paper_fig_10MB/export_render_topbottom_probe.stderr
```

Key finding before the patch:

```text
FLOAT_PUSHDOWN pi=0 ci=1: cur_before=34.7 cur_after=352.7
FLOAT_RENDER   pi=0 ci=1: y_in=99.4 pic_y=56.7 result_y=374.8
LAYOUT_Y       ord=1 pi=0 y_after=99.4
```

Interpretation:

- Pagination already charged the PI0 `TopAndBottom` image.
- Render computed the correct `result_y=374.8`, then the `horzRelTo=Column`
  outside-column guard reset `result_y` back to the saved incoming cursor.
- A narrow render-cursor exception for this case looked plausible, but the full
  corpus gate later proved it unsafe.

Rejected render-cursor patch:

- Keep the outside-column cursor-reset guard for non-`TopAndBottom` pictures.
- Let non-TAC `TopAndBottom` pictures advance the render cursor even when their
  emitted x starts outside the current column.

Focused result:

```text
FLOAT_RENDER pi=0 ci=1: y_in=99.4 pic_y=56.7 result_y=374.8
LAYOUT_Y     ord=1 pi=0 y_after=374.8
LAYOUT_Y     ord=2 pi=1 y_after=394.0
LAYOUT_Y     ord=3 pi=2 y_after=671.3

FLOAT_RENDER pi=4 ci=0: y_in=363.9 pic_y=363.9 result_y=548.1
LAYOUT_Y     ord=1 pi=4 y_after=548.1
```

Focused visual:

- `/tmp/diff/_review_wild_02_render_topbottom_probe/wild_02_paper_fig_10MB/page-01.png`
- Page 1 improves: following flow no longer ignores the charged PI0 image
  height. However, the same-paragraph title still renders above the figure, so
  this is not the full `wild_02` fix and page count remains 7 vs Hancom 9.

- A first-three-page guard contact sheet did not show obvious visual breakage,
  but the full gate is authoritative and rejected the patch after the
  same-family host-text continuation below.

Next remaining `wild_02` issue:

- Same-paragraph host text still starts above the PI0 figure. A render-only
  pre-jump has to preserve the original `para_start_y` anchor for the picture
  while laying the host text lower. Do not simply pre-jump the whole paragraph
  y before `layout_paragraph`, because that would also move the float anchor.

Rejected continuation:

- Tried preserving the original `para_start_y` anchor while laying visible host
  text below a same-paragraph, non-overlapping `TopAndBottom` float emitted
  outside the host column.
- Also tried preventing the later `PageItem::Shape` from rewinding the render
  cursor after that lowered text.
- Focused `wild_02` page 1 improved, but full gate rejected the behavior:

```text
[gate] docs=151 improved=6 regressed=0 new_overflow=3
  +OVERFLOW huge_01_DNA________33MB: 2->5
  +OVERFLOW huge_02_DNA_______75MB: 4->16
  +OVERFLOW wc26_3pg: 0->8
```

- Narrowing to `para_index == 0` plus first multi-column column did not remove
  the overflow regressions.
- Reverted the behavior changes. The diagnostic traces remain useful, but no
  render-cursor or host-text movement is accepted for `wild_02` yet.
- Current safe verification after revert:

```text
python3 scripts/check_renderer_overfit.py
renderer overfit check passed with 8 known baseline finding(s).

bash harness/gate.sh --no-build
[gate] docs=151 improved=6 regressed=0 new_overflow=0
```

## 2026-06-06 fresh no-crop review and boundary diagnosis

Use the refreshed no-crop review board, not the older `_gallery3` evidence:

- Active board: `/tmp/diff/_review_active_2026-06-06/index.html`
- Focus dump: `/tmp/diff/wild_02_paper_fig_10MB/dump_pages_active_2026-06-06.txt`
- Diagnostic dump with line `cs/sw`: `/tmp/diff/wild_02_paper_fig_10MB/drift_cs_sw_active_2026-06-06.txt`

The first real page-boundary error is page 1 overpacking, not bottom clipping:

- Hancom page 1 ends before the final intro tail beginning `연조직부터...`.
- Hancom page 2 starts with that intro tail, then section `2. Viscoelasticity...`.
- RHWP page 1 already contains the tail sentence through `재생 의학 분야에서의 지지체 재료로서도 적합하다.`
- RHWP page 2 starts immediately at section `2. Viscoelasticity...`.

Rendered-line metric:

```text
python3 harness/drift.py /tmp/diff/wild_02_paper_fig_10MB
== wild_02_paper_fig_10MB: hancom=9p rhwp=7p  first_divergence=p2 ==
 pg h_lines r_lines h_gap r_gap  dgap
  1      27      27  12.8   9.6  -3.2
  2      40      36  12.8  12.8   0.0  <-- DIVERGES
```

The page 1 host paragraph (`pi=2`) does not have pre-narrowed wrap line
segments; every line reports full column width:

```text
TYPESET_DRIFT_LINE: pi=2 li=19 ... vpos=29440 cs=0 sw=38124
...
TYPESET_DRIFT_LINE: pi=2 li=34 ... vpos=48960 cs=0 sw=38124
MC_LINE_PART: pi=2 col=1 lines=19..35 cur_before=0.0 ... charged=279.5 saved_band=279.5
```

Rejected probe: cross-column `Square` next-column obstruction

- Hypothesis: `pi=2` has a non-TAC `Square`, `flowWithText`, `allowOverlap=false`
  picture with `horzRelTo=COLUMN`, `horzOffset=39522`, `width=14389`,
  crossing into column 1 while all host line segments remain full-width. Treat
  its bottom as a next-column obstruction.
- Result: page 1 column 1 `used` increased from `279.5px` to `597.5px`, but
  page count stayed 7 and the same lines still fit on page 1:

```text
문서 로드: /diff/wild_02_paper_fig_10MB/source.hwpx (7페이지)
단 1 (items=2, used=597.5px, hwp_used≈279.5px, diff=+318.1px)
  PartialParagraph  pi=2  lines=19..35
  Shape             pi=2 ci=0
```

- Reverted the behavior probe. This says the missing rule is not simply "reserve
  the cross-column Square object height"; the fit decision must change which
  `pi=2` lines are allowed into page 1, or a render/text extraction mismatch is
  making those extra lines appear despite Hancom pushing them.

Diagnostics kept:

- `RHWP_MC_LINE_PART_DRIFT` logs emitted paragraph fragments with charged height
  vs saved VPOS band height.
- `RHWP_TYPESET_DRIFT_LINES` now includes line segment `cs` and `sw`.

Rejected probe: skip first inline `ColumnDef` as section initial layout

- Hypothesis: first paragraph order is `SectionDef -> non-TAC TopAndBottom
  Picture -> ColumnDef(2) -> title text`; promoting that `ColumnDef` to the
  section's initial layout starts RHWP in two columns too early.
- Probe: made `DocumentCore::find_initial_column_def` return default layout when
  a non-TAC `TopAndBottom` flow object preceded the first `ColumnDef`.
- Result: the title/body became one-column, but the whole document stayed
  one-column and page count overshot Hancom:

```text
/tmp/diff/_review_wild_02_initial_col_skip_2026-06-06/index.html
Hancom=9 RHWP=11
python3 harness/audit_review_gallery.py /tmp/diff/_review_wild_02_initial_col_skip_2026-06-06
FAIL: page-10.png/page-11.png suspicious-short
```

- Visual result: page 1 no longer had the two-column separator, but RHWP placed
  the picture/title too high and page 2 became too narrow/long. Reverted the
  behavior and test.
- Updated diagnosis: the fix is not "ignore inline ColumnDef globally". The
  sharper class is same-paragraph non-TAC `TopAndBottom` object reservation: the
  figure must reserve vertical space before/around the paragraph text while the
  later multi-column section semantics remain available.

Rejected probe: pre-reserve top-of-column body-wide TopAndBottom object

- Hypothesis: keep the initial 2-column section layout, but when column 0 starts
  with a body-wide non-TAC `TopAndBottom` picture/shape in the same paragraph,
  charge that object before laying out the paragraph text and suppress the later
  pushdown for the same control.
- Result: compile and focused test passed, but `wild_02` remained 7 pages and
  the page-1 visual was effectively unchanged:

```text
docker compose --env-file .env.docker run --rm dev cargo test --lib page_relative_scan_group_breaks_before_following_flow -j 1 -- --nocapture
test renderer::typeset::tests::page_relative_scan_group_breaks_before_following_flow ... ok

/tmp/diff/_review_wild_02_topbottom_prereserve_2026-06-06/index.html
Hancom=9 RHWP=7
python3 harness/audit_review_gallery.py /tmp/diff/_review_wild_02_topbottom_prereserve_2026-06-06
PASS: no gallery truncation/aspect issues across 1 doc(s)
```

- Reverted the behavior. This says the issue is not just a missing pagination
  height charge for the first TopAndBottom object. The renderer/layout side is
  also placing the first page from the wrong cached vertical origin/column zone:
  Hancom keeps a large top blank and low title, while RHWP paints at the top of
  the first two-column zone.

Accepted partial: top-aligned narrow TopAndBottom objects reserve a column band

- Structural class: non-TAC `TopAndBottom` means text flows above/below the
  object, not beside it. The old multi-column reserve only applied when object
  width was at least 80% of the body. In `wild_02`, the top figure is narrower
  but top-aligned, so RHWP let the first two-column text start too high.
- Change: keep the existing wide-object rule; additionally allow narrower
  `TopAndBottom` objects only when their top aligns with the body/column top.
  Lower narrow objects are still excluded so normal in-body floats do not start
  reserving full column bands.
- Validation:

```text
docker compose --env-file .env.docker run --rm dev cargo test --lib top_aligned_narrow_topbottom_float_reserves_column_band -j 1 -- --nocapture
test renderer::typeset::tests::top_aligned_narrow_topbottom_float_reserves_column_band ... ok

docker compose --env-file .env.docker run --rm dev cargo test --lib body_wide_reserved_accepts_top_aligned_narrow_topbottom_float -j 1 -- --nocapture
test renderer::layout::tests::body_wide_reserved_accepts_top_aligned_narrow_topbottom_float ... ok

bash harness/gate.sh --no-build
[gate] docs=151 improved=6 regressed=0 new_overflow=0

python3 scripts/check_renderer_overfit.py
renderer overfit check passed with 8 known baseline finding(s).
```

- Focus artifact:
  `/tmp/diff/_review_wild_02_topaligned_topbottom_band_2026-06-06/index.html`
  passed gallery audit and visually moved RHWP page-1 content lower, closer to
  Hancom's large top blank.
- Remaining gap: `wild_02` is still `Hancom=9 / RHWP=7`, and right-column text
  still overlaps the figure. The next target is the line-fit/page-break decision
  for `pi=2` column 1: RHWP still allows lines `19..35` on page 1, while Hancom
  pushes the tail starting `연조직부터...` to page 2.

Rejected probe: engine-side top reserve port

- Hypothesis: the default dump/page-count path might be missing the
  `pending_body_wide_top_reserve` logic that already exists in `TypesetEngine`.
- Probe: temporarily added the same pending reserve state to
  `pagination/engine.rs` / `pagination/state.rs`.
- Result: no focused change. `wild_02` stayed `Hancom=9 / RHWP=7`, and page 1
  still had `PartialParagraph pi=2 lines=19..35` in column 1.
- Reverted. The default production path is `TypesetEngine`; legacy
  `pagination/engine.rs` is only used behind `RHWP_USE_PAGINATOR=1`.

Rejected probe: force multicolumn continuation before a narrow Square picture

- Hypothesis: when a paragraph continuation enters column 1 and the same
  paragraph owns a later narrow non-TAC `Square` picture, the continuation
  should be moved to the next page if cached line segments are still full-width.
- Probe: temporarily added a structural guard in `typeset_paragraph` using only
  control type, wrap mode, rel-to, object geometry, and full-width line segment
  geometry.
- Result: no focused change. `wild_02` stayed `Hancom=9 / RHWP=7`, with the same
  page-1 `pi=2 lines=19..35` continuation.
- Reverted. The remaining issue is probably deeper in Square picture anchor
  routing / same-paragraph wrap-zone geometry, not a simple continuation
  page-break guard.

Rejected probe: full-width remaining-line overlap with same-para Square picture

- Corrected diagnostic command:
  `docker compose --env-file .env.docker run --rm -e RHWP_MC_LINE_PART_DRIFT=1 ...`
  is required; prefixing the Compose command with the env var did not pass it
  into the container.
- Evidence from the real `TypesetEngine` split:

```text
MC_LINE_PART: pi=2 col=0 lines=0..19 cur_before=364.7 page_avail=330.5 charged=330.7
MC_LINE_PART: pi=2 col=1 lines=19..35 cur_before=318.1 page_avail=695.2 charged=279.5
```

- Hypothesis: page-1 leak happens because `cursor_line>0` receives full
  fresh-column height while later remaining full-width lines overlap the same
  paragraph's narrow `Square` picture.
- Probe: move such continuation to the next page when any remaining full-width
  cached line overlaps the same paragraph's non-TAC Square picture span.
- Focused result: page 1 no longer contained `pi=2 lines=19..35`; that tail
  moved to page 2. But the document still reported 7 RHWP pages and the page 2
  visual became overpacked/clipped.
- Gate result:

```text
bash harness/gate.sh --no-build
[gate] docs=151 improved=6 regressed=0 new_overflow=1
  +OVERFLOW wild_02_paper_fig_10MB: 2->4
```

- Reverted. This proves the simple "break before same-para Square overlap" rule
  fixes one wrong-page symptom but creates a render overflow. The next fix must
  model same-paragraph Square wrapping/shape placement and split budget
  together, not just move the continuation wholesale.

Accepted partial: reset-starting multi-column segment charges saved band

- Evidence after the top-aligned `TopAndBottom` reserve: page 4 column 0
  undercharged `pi=5 lines=11..41` by 163.1px:

```text
MC_LINE_PART: pi=5 col=0 lines=11..41 line_h=522.4 charged=522.4 saved_band=685.5 diff=-163.1 first_vpos=0.0 items=0
```

- Patch owner: the generic line-split path in `src/renderer/typeset.rs`, not
  `typeset_multicolumn_paragraph`. A first probe in the latter was a no-op and
  was reverted.
- Structural rule: in a multi-column layout, when a partial segment starts a
  fresh column/page (`items=0`), its first saved line `vpos` is reset to zero,
  and the serialized line-segment band exceeds the composed line advance by
  more than 24px, charge the saved band. This uses line-segment geometry only.
- Focused result:

```text
MC_LINE_PART: pi=5 col=0 lines=11..41 line_h=522.4 charged=685.5 saved_band=685.5 diff=+0.0 first_vpos=0.0 items=0 saved_charge=true
```

- Focus artifact:
  `/tmp/diff/_review_wild_02_generic_saved_band_patch_2026-06-06/index.html`
- Validation:

```text
python3 harness/audit_review_gallery.py /tmp/diff/_review_wild_02_generic_saved_band_patch_2026-06-06
PASS: no gallery truncation/aspect issues across 1 doc(s)

python3 scripts/check_renderer_overfit.py
renderer overfit check passed with 8 known baseline finding(s).

bash harness/gate.sh --no-build
[gate] docs=151 improved=6 regressed=0 new_overflow=0
```

- Limitation: `wild_02` remains `Hancom=9 / RHWP=7`. This is a safe sub-fix
  for one measurable undercharge, not the final page-count fix. Remaining
  prominent underfills include page 4 column 1 (`diff=-288.0px`) and page 5
  column 1 (`diff=-342.1px`), likely due to cross-paragraph saved-vpos gaps
  and later same-paragraph float placement rather than this segment-height
  class.

Accepted partial: multi-column inter-paragraph saved-vpos gap

- Evidence after the saved-band patch: `wild_02` still had large same-column
  gaps missing between adjacent visible paragraphs:

```text
page 4 col1 before: used=486.0px, hwp_used≈774.0px, diff=-288.0px
page 5 col1 before: used=332.0px, hwp_used≈674.1px, diff=-342.1px
```

- Patch owner: `src/renderer/typeset.rs` main paragraph loop, before the
  paragraph is split. Existing vpos-reset logic only handled rewinds
  (`current first vpos < previous last vpos`); this case is the opposite:
  Hancom's saved first-line vpos starts lower than RHWP's accumulated column
  height.
- Structural rule: in multi-column layout only, with no active wrap-around,
  when a visible paragraph without controls enters a non-empty column and its
  saved first-line vpos is materially below the current flow cursor, advance
  the cursor to that saved vpos if it is still inside the column body.
- Focused diagnostic:

```text
MC_VPOS_GAP: pi=6 col=1 cur_h=381.5 first_vpos=572.1 gap=190.7 avail=699.2 charge=true
MC_VPOS_GAP: pi=7 col=1 cur_h=242.4 first_vpos=584.5 gap=342.1 avail=699.2 charge=true
```

- Focused result:

```text
page 4 col1 after: used=676.7px, hwp_used≈774.0px, diff=-97.3px
page 5 col1 after: used=674.1px, hwp_used≈674.1px, diff=+0.0px
```

- Focus artifact:
  `/tmp/diff/_review_wild_02_mc_vpos_gap_patch_2026-06-06/index.html`
- Validation:

```text
python3 harness/audit_review_gallery.py /tmp/diff/_review_wild_02_mc_vpos_gap_patch_2026-06-06
PASS: no gallery truncation/aspect issues across 1 doc(s)

python3 scripts/check_renderer_overfit.py
renderer overfit check passed with 8 known baseline finding(s).

bash harness/gate.sh --no-build
[gate] docs=151 improved=6 regressed=0 new_overflow=0
```

- Limitation: `wild_02` remains `Hancom=9 / RHWP=7`. The remaining large
  front-half mismatch is page 1/2 same-paragraph `Square` picture routing:
  crude break-before-overlap removed page-1 leakage but created page-2
  overflow, so the next pass needs a coupled wrap-zone/split-budget model.

Accepted partial: render-local column-base fallback for off-body Square picture

- Evidence after the saved-vpos gap patch: the page-1 `pi=2 ci=0` non-TAC
  `Square` picture was anchored relative to `Column`, but the current column
  base put its render box outside the body (`x≈1103..1295`) while Hancom keeps
  the figure inside the page body near the right side.
- Patch owner: `src/renderer/layout.rs` `layout_shape_item`, immediately before
  the picture render call. This is render-local placement, not a pagination
  split fix.
- Structural rule: for a non-TAC `Square` picture with `VertRelTo::Para` and
  `HorzRelTo::Column`, if the current column-base x would place the picture
  outside the body and the same horizontal offset from the body-left base keeps
  it inside the body, use the body-left base for this picture's effective
  column area.
- Focused diagnostic:

```text
FLOAT_RENDER: page=0 col_x=576.4 pi=2 ci=0 wrap=Square horz=Column vert=Para y_in=598.8 para_anchor=598.8 pic_y=598.8 result_y=1191.6 x=564.8..756.6 pic_h=170.1 prior_h=0.0 stack=false vpos_accounted=false col_base_fallback=true
```

- Focused result: the first-page Square picture now renders inside the body
  (`x=564.8..756.6`) instead of off-page. Page count remains 7.
- Focus artifact:
  `/tmp/diff/_review_wild_02_col_base_fallback_2026-06-06/index.html`
- Validation:

```text
python3 harness/audit_review_gallery.py /tmp/diff/_review_wild_02_col_base_fallback_2026-06-06
PASS: no gallery truncation/aspect issues across 1 doc(s)

python3 scripts/check_renderer_overfit.py
renderer overfit check passed with 8 known baseline finding(s).

bash harness/gate.sh --no-build
[gate] docs=151 improved=6 regressed=0 new_overflow=0
```

- Limitation: this fixes a visible image-position fidelity gap but does not
  change the pagination owner. `wild_02` is still `Hancom=9 / RHWP=7`; the
  remaining page-count gap still points at same-paragraph Square wrap/split
  budgeting in page 1/2 and a smaller page-4 column-1 undercharge.

Unaccepted probe: route non-TAC para-relative float by saved line band

- Hypothesis: after a paragraph splits, a non-TAC paragraph-relative picture
  control can be emitted into the final paragraph fragment instead of the page
  fragment whose saved `lineSegArray` band owns the picture's vertical offset.
  This would explain small figures drifting one page late and clipping at the
  page edge.
- Probe implemented briefly:
  - `src/renderer/pagination.rs`: helper to find the page/column fragment whose
    paragraph line range contains the float `vertical_offset`.
  - `src/renderer/typeset.rs`: use that helper for non-TAC `Square` /
    `TopAndBottom` paragraph-relative picture floats.
- Compile evidence: focused Rust test compiled and passed:

```text
docker compose --env-file .env.docker run --rm dev cargo test --lib top_aligned_narrow_topbottom_float_reserves_column_band -j 1 -- --nocapture
test renderer::typeset::tests::top_aligned_narrow_topbottom_float_reserves_column_band ... ok
```

- Rejected/unaccepted because the current `/tmp/diff/wild_02_paper_fig_10MB/`
  directory no longer contains `source.hwpx` / `source.hwp`, so focused render
  and gallery validation could not run:

```text
오류: 파일을 읽을 수 없습니다 - /diff/wild_02_paper_fig_10MB/source.hwpx: No such file or directory
no source.hwpx/source.hwp in /tmp/diff/wild_02_paper_fig_10MB
```

- Probe was reverted. Do not accept or reintroduce this until the source fixture
  is restored and the focused render plus full overfit/gate pass.
