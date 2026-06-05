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
