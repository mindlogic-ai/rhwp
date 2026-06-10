# P3 Accountability Eval Wide-Table Diagnosis -- 2026-06-05

## Target

- Doc: `accountability_eval`
- Family: over-wide top-level table fit plus partial-table height/flow
- Current staged source: `/tmp/diff/accountability_eval/source.hwpx`
- Original visual report:
  - `/tmp/diff/accountability_eval/look/page-01.png`
  - `/tmp/diff/accountability_eval/look/page-04.png`
  - `/tmp/diff/accountability_eval/look/page-05.png`
  - `/tmp/diff/accountability_eval/look/page-06.png`
- Fitted-source visual report:
  - `/tmp/diff/accountability_eval_fitted/look/page-01.png`
  - `/tmp/diff/accountability_eval_fitted/look/page-05.png`
- Fitted-source Hancom-oracle report:
  - `/tmp/diff/accountability_eval_fitted_oracle/look/page-01.png`
  - `/tmp/diff/accountability_eval_fitted_oracle/look/page-05.png`
  - `/tmp/diff/accountability_eval_fitted_oracle/look/page-06.png`
  - `/tmp/diff/accountability_eval_fitted_oracle/look/page-11.png`

## Current Truth

The old focus manifest says `11/4`, but the currently staged HWPX does not
match that oracle.

- Fresh Hancom render of staged source: 6 pages.
- Current rhwp render of staged source: 4 pages.
- Therefore current staged truth is `6/4`, not `11/4`.
- Fresh baseline after P1a commit `d8592723`: still Hancom 6 / RHWP 4 for
  `/tmp/diff/accountability_eval/source.hwpx`; P1a did not change this target.

Do not chase an 11-page target unless the exact original source/oracle pair is
restored.

## Structural Signature

- One dominant top-level table.
- Table shape: `38x9`.
- First row cell width sum: wider than the page text area.
- Wrap/anchor family: `TOP_AND_BOTTOM`, paragraph-relative, non-TAC,
  `flowWithText=1`, `allowOverlap=0`, `repeatHeader=1`.
- Current dump-pages symptom: early `PartialTable` pages report too little
  consumed height, including several pages with `used=0.0px`.

This is not just a page-count typo. It combines:

1. Hancom-style fit-to-print width behavior.
2. Text reflow after width shrinkage.
3. Partial table row/page height accounting.

## Preprocessor Probe

FactChat already has a safer upload-time preprocessor:

- `/Users/jaehoshin/Desktop/mindlogic/factchat/worktree-hwpx-final/server/factchat/utils/hwpx_layout_fitter.py`

Probe result on `/tmp/diff/accountability_eval/source.hwpx`:

- changed: `True`
- sections scanned: `1`
- tables total: `1`
- tables scaled: `1`
- smallest scale: `0.6870160847991632`
- original size: `186607`
- fitted size: `171649`
- fitted output: `/tmp/diff/accountability_eval/source_fitted.hwpx`

After fitting:

- rhwp page count improved from 4 to 5.
- Visual width fit improved: the table no longer clips as severely off the
  right page edge.
- The document is still not production-faithful:
  - Hancom staged oracle has 6 pages.
  - rhwp fitted output has 5 pages.
  - table text/row height remains visually poor.
  - overlapping/dense cell text remains visible in the fitted gallery.

## Hancom-Rerender Gate

The fitted HWPX was sent through Hancom on 2026-06-05.

- Input: `/tmp/diff/accountability_eval/source_fitted.hwpx`
- Hancom output:
  `/tmp/diff/accountability_eval_fitted/hancom_fitted.pdf`
- Hancom reported page count: 11 pages.
- Rebuilt comparison directory:
  `/tmp/diff/accountability_eval_fitted_oracle/`
- Tripwire: Hancom 11 pages, rhwp 5 pages.

Visual read:

- page 1: width fit is closer than the original RHWP output, but RHWP text is
  too large/dense and overlaps horizontally inside cells.
- page 5: RHWP is already showing content from later logical rows while Hancom
  is still in the middle of the table.
- pages 6-11: Hancom has real table content; RHWP has no corresponding pages.

This rejects "fitter alone solves `accountability_eval`". The fitter changes
Hancom's own pagination from the staged original 6 pages to 11 pages and RHWP
still under-paginates the fitted source.

## RHWP Dump Evidence

Dump file:

- `/tmp/diff/accountability_eval_fitted_oracle/dump_pages.txt`
- fresh post-P1a staged-source dump:
  `/tmp/diff/accountability_eval/dump_pages_after_p1a.txt`
- fresh post-P1a staged-source diagnostics:
  `/tmp/diff/accountability_eval/drift_after_p1a.txt`

Before the partial-height accounting patch, RHWP loaded the fitted source as 5
pages and reported zero used height on intermediate split-table pages:

- page 1: `PartialTable pi=0 ci=2 rows=0..4`, `used=0.0px`
- page 2: `PartialTable pi=0 ci=2 rows=4..15`, `used=0.0px`
- page 3: `PartialTable pi=0 ci=2 rows=7..28`, `used=0.0px`
- page 4: `PartialTable pi=0 ci=2 rows=16..35`, `used=0.0px`
- page 5: `PartialTable pi=0 ci=2 rows=29..38`, `used=508.0px`

Patch result:

- `/tmp/diff/accountability_eval_fitted_oracle/dump_pages_after_used_height_patch.txt`
- page 1: `used=603.9px`
- page 2: `used=494.0px`
- page 3: `used=200.7px`
- page 4: `used=251.9px`
- page 5: `used=508.0px`
- page count remains rhwp 5 vs Hancom 11.

The used-height accounting bug is fixed for the validator, but it is not the
full rendering fix. The remaining structural issue is that split/cut logic
advances through too much table content per page compared with Hancom.

Fresh post-P1a staged-source baseline shows the same class on the unfitted
source:

- page 1: `PartialTable pi=0 ci=2 rows=0..15`, `used=0.0px`
- page 2: `PartialTable pi=0 ci=2 rows=7..28`, `used=0.0px`
- page 3: `PartialTable pi=0 ci=2 rows=16..35`, `used=0.0px`
- page 4: `PartialTable pi=0 ci=2 rows=29..38`, `used=297.3px`
- diagnostics report `TABLE_CUT_DRIFT diff=+0.0`, so the row-height model is
  internally consistent while continuation fragments still advance through too
  much logical table content per visual page.

## P3 Subfix Result -- 2026-06-05

Implemented two structural changes:

1. Non-final `PartialTable` fragments now add their measured `partial_height`
   to `current_height` before flushing the column/page. This fixes
   `dump-pages`/validator truth where continuation pages previously showed
   `used=0.0px` while advancing rows.
2. RowBreak/CELL rowspan block cuts are limited to small rowspan blocks
   (`2..=BLOCK_UNIT_MAX_ROWS`). Large RowBreak rowspan groups now advance
   row-wise instead of consuming many future cell-unit cuts inside one visual
   fragment.

Additional scoped visual correction:

- Trusted table-cell `LineSeg.segment_width` can constrain rendered line width
  inside table cells when the saved line is narrower than the cell area. This is
  gated to trusted cache + table-cell context and does not apply to ordinary
  paragraphs.

Fresh validation:

```text
CARGO_BUILD_JOBS=1 docker compose --env-file .env.docker run --rm dev \
  cargo test --lib rowbreak_block_cut_is_limited_to_small_rowspan_blocks -j 1
result: passed

CARGO_BUILD_JOBS=1 docker compose --env-file .env.docker run --rm dev \
  cargo test --lib test_table_split_50rows_multi_page -j 1
result: passed

CARGO_BUILD_JOBS=1 docker compose --env-file .env.docker run --rm dev \
  cargo test --lib saved_cell_line_width_only_applies_to_trusted_narrow_cell_lines -j 1
result: passed

CARGO_BUILD_JOBS=1 docker compose --env-file .env.docker run --rm dev \
  cargo build --release --bin rhwp -j 1
result: passed

python3 scripts/check_renderer_overfit.py
result: renderer overfit check passed with 8 known baseline finding(s).

python3 harness/look.py /tmp/diff/accountability_eval --export
result: Hancom=6 rhwp=6

python3 harness/look.py /tmp/diff/accountability_eval_fitted_oracle --export
result: Hancom=11 rhwp=13, still unresolved

bash harness/gate.sh --no-build
result: docs=151 improved=1 regressed=0 new_overflow=0
  IMPROVE wc31_17pg: 12->13 (oracle 17)
```

Current decision:

- LAND as a partial P3 subfix for staged-source `accountability_eval` and table
  split accounting.
- Do not call P3 complete. The fitted Hancom-rerender remains over-paginated
  and visually poor at Hancom 11 / RHWP 13. The next P3 work must target
  fitted-source row/text composition, not more broad page-count tuning.

## Split/Cut Diagnostic

Diagnostic files:

- `/tmp/diff/accountability_eval_fitted_oracle/table_drift_stderr.txt`
- `/tmp/diff/accountability_eval_fitted_oracle/table_drift_stdout.txt`

Important rows:

- `TABLE_DRIFT`: effective table height `7147.7px`; 38 rows; `pageBreak=CELL`;
  `cellSpacing=0`.
- `TABLE_CUT_DRIFT`: cut row sum equals measured row sum (`diff=+0.0`), so the
  total row-height model is internally consistent.
- The problem is fragment progression:
  - page 1: `cursor_row=0 end_row=4 consumed=603.9`
  - page 2: `cursor_row=4 end_row=15 consumed=494.0 split_end_limit=113.1`
  - page 3: `cursor_row=7 end_row=28 consumed=200.7 split_end_limit=96.0`
  - page 4: `cursor_row=16 end_row=35 consumed=251.9 split_end_limit=113.1`
  - page 5: `cursor_row=29 end_row=38 consumed=508.0`

That means continuation fragments are operating over large rowspan blocks: the
row range overlaps by design, but the consumed height per continuation is far
too small for Hancom's 11-page output.

Additional split probe after instrumenting the active path:

- Trace:
  `/tmp/diff/accountability_eval_fitted_oracle/table_drift_stderr_split_probe.txt`
- The bad 5-page path was not the generic protected-block branch. It was the
  `rowbreak_rowspan_block` branch, triggered by internal hard-break units inside
  large RowBreak/CELL rowspan blocks:
  - row 7 block `7..15`, size 8, `res_consumed=113.1`, `end_cut_len=59`
  - row 16 block `16..28`, size 12, `res_consumed=96.0`, `end_cut_len=90`
  - row 29 block `29..35`, size 6, `res_consumed=113.1`, `end_cut_len=47`
- This consumed future rows' cell-unit cuts inside the same visual block and
  made RHWP jump from page 5 to the end while Hancom still had real content on
  pages 6-11.

Candidate structural patch:

- Limit the RowBreak/CELL rowspan block-cut path to small rowspan blocks only
  (`2..=BLOCK_UNIT_MAX_ROWS`, currently 3).
- Large rowspan blocks now paginate row-wise, matching the existing
  `snap_to_block_boundary` policy that large rowspan blocks should not be
  protected as one block.
- Result on fitted oracle:
  - before: Hancom 11 / RHWP 5
  - after: Hancom 11 / RHWP 13
  - trace:
    `/tmp/diff/accountability_eval_fitted_oracle/table_drift_stderr_large_rowspan_rowwise.txt`
  - visual:
    `/tmp/diff/accountability_eval_fitted_oracle/look/page-01.png`
    through `page-13.png`

Interpretation:

- The candidate fixes the missing-pages direction and proves that large
  rowspan block-cut advancement was a real under-pagination bug.
- It is not a complete P3 fix: RHWP now over-paginates by 2 pages and table
  text still wraps too wide/dense inside cells, causing horizontal overlap.
- Next P3 work should shift to cell text-flow/width composition after fitted
  width scaling, not more pagination block-cut tuning.

Cell text-width probe after the row-wise candidate:

- Patch:
  `src/renderer/layout/paragraph_layout.rs` now lets trusted table-cell lines
  use Hancom's saved `LineSeg.segment_width` as the alignment/distribution
  width when that saved width is narrower than the cell inner width.
- Rerender:
  `/tmp/diff/accountability_eval_fitted_oracle/rhwp_svg_cur/source_001.svg`
- Dump:
  `/tmp/diff/accountability_eval_fitted_oracle/table_drift_stdout_saved_cell_width.txt`
  and
  `/tmp/diff/accountability_eval_fitted_oracle/table_drift_stderr_saved_cell_width.txt`
- Result:
  - page count remains Hancom 11 / RHWP 13.
  - page 1 target cell geometry improved: the first cell's saved-line text now
    stops around `x=273.9`, while the next cell starts around `x=279.0`.
    Before this probe, the same line visibly spilled into the next cell.
  - This is a useful visual correction, not the remaining row/page-count fix.

Updated interpretation:

- The remaining P3 blocker is row content-height/page split accounting after
  text composition, not generic horizontal clipping.
- The next probe should compare measured line count and row consumed height
  before/after saved-cell-width composition against Hancom page boundaries.
- Do not broaden this into a global paragraph alignment change; keep the rule
  scoped to trusted table-cell line segments.

Rejected probe: large-rowspan row-internal cuts.

- Candidate:
  allow normal row cuts for splittable rows inside large RowBreak/CELL rowspan
  blocks instead of whole-row-only placement.
- Dump:
  `/tmp/diff/accountability_eval_fitted_oracle/table_drift_stdout_large_rowspan_rowcut.txt`
  and
  `/tmp/diff/accountability_eval_fitted_oracle/table_drift_stderr_large_rowspan_rowcut.txt`
- Result:
  RHWP remained 13 pages. It introduced cut fragments on pages 2/3/8, but did
  not eliminate the extra pages or land the Hancom 11-page target.
- Decision:
  reverted from source. Do not retry this exact rule without a stricter
  discriminator or a page-boundary proof from Hancom row starts.

Source table structure:

- one `38x9` table with `pageBreak=CELL`, `repeatHeader=1`, `noAdjust=1`.
- fitted outer size: width `53860`, height `1108516` HWP units.
- tall rowspan blocks:
  - row 1, col 0 spans 5 rows.
  - row 7, col 0 spans 8 rows; row 7, col 1 spans 6 rows.
  - row 16, col 0 spans 12 rows.
  - row 29, col 0 spans 6 rows.
  - row 36, col 0 spans 2 rows.

Next fix should be scoped to `CELL` page-break tables with large rowspan
blocks, carried block cuts, and row content-height measurement. A global
row-height multiplier or global table shrink is still the wrong lever.

## Previous Gate Gap

The fitted visual report currently reuses the original Hancom PDF as the left
oracle. That is useful to see whether the fitted RHWP output moved toward the
original target, but it is not the final production gate.

Because the preprocessor mutates the HWPX, the real gate is:

1. Generate `source_fitted.hwpx`.
2. Send `source_fitted.hwpx` to Hancom.
3. Render Hancom PDF for the fitted source.
4. Compare rhwp-fitted output against Hancom-fitted output.
5. Reopen the fitted HWPX in Hancom to prove the rewritten file is accepted.

This gap is now closed for this file: the fitted-source Hancom oracle exists,
and it shows the mitigation is insufficient.

## Decision

KEEP as partially improved renderer work, but do not call P3 solved. Do not
treat the current preprocessor, the large-rowspan row-wise pagination candidate,
or the saved-cell-width visual correction as production-solved for this family,
and do not land any broad renderer shrink from this doc.

Use upload-time HWPX fitting for clearly over-wide top-level tables because it
is narrower and lower-risk than a broad Rust renderer rule that shrinks tables
at render time, but only as a first-stage mitigation. The remaining blocker is
partial-table text-flow/width accounting in RHWP.

## Next Probe

1. Investigate why `rows`/`start_cut`/`end_cut` advance too aggressively after
   width fitting:
   - RHWP page 3 spans `rows=7..28`.
   - RHWP page 4 spans `rows=16..35`.
   - Hancom still needs pages 6-11 for the same logical table.
2. Focus specifically on row content-height measurement after saved-cell-width
   composition for rowspan-heavy fitted `pageBreak=CELL` tables. The current
   candidates prove large rowspan blocks should not use the rowbreak block-cut
   path and that saved table-cell line widths must constrain glyph distribution.
   The remaining issue is why row/page split height still totals 13 RHWP pages
   against Hancom's 11.
3. Compare row content-height measurement against Hancom page boundaries with
   table-heavy guard docs:
   - `form_24_____4MB`
   - `form_25__________________6MB`
   - `large_01_____________16MB`
4. Instrument `table_partial` / `height_measurer` for:
   - row consumed height per split page,
   - text line count/line height per cell after width scaling,
   - why RHWP emits no pages 6-11 while Hancom still has table content.
5. Keep upload-time width fitting as a possible pre-step, but do not claim it
   is enough for production.

## Validation

- `cargo test --lib test_table_split_50rows_multi_page -j 1`: passed.
- `cargo test --lib page_relative_scan_group_breaks_before_following_flow -j 1`:
  passed.
- `cargo test --lib rowbreak_block_cut_is_limited_to_small_rowspan_blocks -j 1`:
  passed.
- `cargo test --lib saved_cell_line_width_only_applies_to_trusted_narrow_cell_lines -j 1`:
  passed.
- `python3 scripts/check_renderer_overfit.py`: passed with 8 known baseline
  findings.
- `bash harness/gate.sh --no-build`: `docs=151 improved=1 regressed=0
  new_overflow=0`; `wc31_17pg` remains only an improvement from 12 to 13 pages
  toward oracle 17, not fixed.

## Reject

- Shrink every table globally.
- Tune cell padding/borders before width and partial-height flow are proven.
- Treat the stale `11/4` manifest as a valid target for this staged source.
- Claim production readiness from the current fitter: Hancom-fitted is 11 pages
  while rhwp-fitted is 5 pages.

## 2026-06-07 Current Recheck

The page-count part of this target has changed in the current accepted renderer
state.

Fresh current dump:

```text
docker compose --env-file .env.docker run --rm -v /tmp/diff:/diff dev \
  /app/target/release/rhwp dump-pages /diff/accountability_eval_fitted_oracle/source.hwpx
문서 로드: /diff/accountability_eval_fitted_oracle/source.hwpx (11페이지)
```

Current split sequence:

```text
rows=0..5
rows=5..9
rows=9..12
rows=12..15
rows=15..19
rows=19..22
rows=22..25
rows=25..28
rows=28..32
rows=32..36
rows=36..38
```

Fresh drift check:

```text
python3 harness/drift.py /tmp/diff/accountability_eval_fitted_oracle
== accountability_eval_fitted_oracle: hancom=11p rhwp=11p first_divergence=p1
```

So the old statement "Hancom-fitted is 11 pages while rhwp-fitted is 5 pages"
is no longer true for the current code. The remaining issue is visual fidelity
inside the table: RHWP still renders denser/smaller cell text than Hancom on
page 1, and line counts differ (`h_lines=44`, `r_lines=33` on page 1). Treat
this as a table-cell typography/composition fidelity class, not as the previous
table split/page-count blocker.

Fresh gallery:

```text
python3 harness/review_gallery.py /tmp/diff/_review_accountability_fitted_oracle_2026-06-07 accountability_eval_fitted_oracle --export-current
python3 harness/audit_review_gallery.py /tmp/diff/_review_accountability_fitted_oracle_2026-06-07
PASS: no gallery truncation/aspect issues across 1 doc(s)
```

The gallery audit was updated to avoid false-positive `suspicious-short`
failures on valid two-column landscape table pages. The old failure class was
very-wide three-column qlmanage strips around `2304x1103`; the refreshed
two-column table strips are landscape by document geometry, not truncated.

Validation caveat:

```text
bash harness/gate.sh --no-build
[gate] docs=9 improved=0 regressed=0 new_overflow=0
```

This is not the earlier 151-doc full corpus gate because the current
`/tmp/diff` staging area only contains 9 source files. Use it only as a local
staged-source safety check until the full fixture corpus is restored.

## 2026-06-07 Continuation-Table Probe

`repeatHeader=1` with row-0 cells serialized as `header=0` looked suspicious
because Hancom continuation pages show a narrow top strip. A structural probe
treated row 0 as an inferred repeated header when no explicit header cells were
present.

Result: **REVERTED / not landable**.

- Page count stayed 11.
- Visual fidelity got worse: RHWP repeated the column-heading text (`분류1`,
  `분류2`, ...) on continuation pages where Hancom's narrow strip is not that
  header row.
- Conclusion: this is not a repeat-header inference bug.

Current structural evidence from the new table-fragment diagnostic:

```bash
python3 harness/table_fragment_diag.py /tmp/diff/accountability_eval_fitted_oracle
```

Key fragments:

- page 05: `rows=15..19`, `carried=0`; row 15 is an intentional blank
  separator row, followed by 조직 운영 / 운영시스템 / 고충처리체계 rows.
- page 11: `rows=36..38`, `carried=0`; the final two source rows render after
  the last blank separator/page group.
- SVG row bands confirm RHWP is emitting table geometry for those fragments;
  this is not gallery truncation and not a missing-image issue.

Next hypothesis:

- The remaining defect is table-cell row-band height / line-density fidelity
  under `pageBreak=CELL`, rowspans, and cached `lineSegArray`, not page count,
  repeat header, or missing images.
- The next safe probe should compare Hancom-visible row bands against
  `row_cut_content_height`, `cell_units`, `calc_para_lines_height`, and the
  use of cached line-seg line height/spacing for cell paragraphs.
- Do not patch `repeatHeader` for this fixture.

## 2026-06-07 Font/Ink-Density Evidence

After adding `saved_line_segs`, `svg_text_y`, and `svg_fonts` to
`harness/table_fragment_diag.py`, the line-density hypothesis became weaker:

- In a representative page-5 cell (`row=18 col=8`), HWPX lineSegs are spaced
  at `vertpos=0,1280,2560,3840,5120` HU.
- RHWP SVG emits that same cell at y positions `526.1,543.1,560.2,577.3,594.3`,
  i.e. ~17px pitch, which is exactly `1280 HU @ 96 dpi`.
- SVG body-cell text is `font-size=10.666666666666666` (8pt) and no
  `font-weight`, matching `charPr id=8 height=800 bold=false`.

But the rendered RHWP PNG has much less dark ink than the Hancom PNG:

```text
p1:  hancom_dark=41823 rhwp_dark=20635 ratio=0.49
p5:  hancom_dark=35100 rhwp_dark=12833 ratio=0.37
p11: hancom_dark=21568 rhwp_dark=10788 ratio=0.50
```

`table_fragment_diag.py` now also reports:

```text
font_hint=primary Malgun font not found locally; browser/PDF fallback may be thinner
```

Current conclusion:

- Do not tune row heights just to compensate for faint text; the saved line
  pitch is already respected in sampled cells.
- Do not globally force `맑은 고딕` to `font-weight=500`; the existing
  medium-weight rule intentionally excludes normal Malgun Gothic.
- A safe next test is environmental/font-path validation: render the same SVG
  with a real Malgun Gothic or Hancom-compatible webfont available, then compare
  ink density before changing Rust layout.

## 2026-06-07 Font-Audit Harness

`harness/table_fragment_diag.py` now has a read-only `--font-audit` mode:

```bash
python3 harness/table_fragment_diag.py \
  /tmp/diff/accountability_eval_fitted_oracle \
  --font-audit --pages 1,5,11
```

Latest output from the current artifacts:

```text
p01: hancom_dark=36449 rhwp_dark=16785 ratio=0.46
p05: hancom_dark=30846 rhwp_dark=10276 ratio=0.33
p11: hancom_dark=18913 rhwp_dark=8487  ratio=0.45
```

The page images are essentially the same raster size
(`Hancom=1404x992`, `RHWP=1400x994`), so this is not a gallery scaling artifact.
The SVG still declares primary `맑은 고딕`/`Malgun Gothic`, 8pt body text, and no
normal-cell `font-weight`.

Stop condition for this category:

- P3 `accountability_eval` is **not production-faithful yet**.
- The remaining concrete defect is now best classified as **font/ink-density
  fidelity**, not page-count drift, repeated-header inference, row-split order,
  or missing gallery evidence.
- The next renderer-adjacent experiment should install/provide the intended
  Korean font or render with a Hancom-compatible webfont and compare this same
  audit before making any Rust layout change.

The diagnostic also supports a disposable CSS weight probe:

```bash
python3 harness/table_fragment_diag.py \
  /tmp/diff/accountability_eval_fitted_oracle \
  --weight-probe 500 --pages 1,5,11
python3 harness/table_fragment_diag.py \
  /tmp/diff/accountability_eval_fitted_oracle \
  --weight-probe 600 --pages 1,5,11
```

Results:

```text
weight=500:
  p01 ratio=0.53
  p05 ratio=0.38
  p11 ratio=0.53

weight=600:
  p01 ratio=0.62
  p05 ratio=0.46
  p11 ratio=0.63
```

This improves text darkness but still leaves the worst table page far from
Hancom. That argues against landing a broad `font-weight:500`/`600` renderer
rule as the fix. The safer path is font-face parity first, then only consider a
narrow font policy if real-font rendering still under-shoots Hancom.
