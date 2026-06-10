# RHWP Fidelity Status -- form_01 CellBreak Final Row Probe -- 2026-06-09

## Status

- Category: image/table geometry, semantic table-tail drift.
- Row status: accepted / structural patch.
- Representative: `form_01_교수법_과제양식_코다이_49KB:1-2`.
- Guard: `report_form:2`.
- Current broad board:
  `/tmp/diff/_review_all_nonlandscape_after_form01_tail_2026-06-09/index.html`.
- Focused probe board:
  `/tmp/diff/_probe_form01_drift_2026-06-09/index.html`.
- Accepted candidate board:
  `/tmp/diff/_review_form01_cellbreak_zeroheight_tail_candidate_2026-06-09/index.html`.

## Visual Finding

Hancom and RHWP both render 2 pages, so this is not page-count drift.
The mismatch is the table tail:

- Hancom page 2 still has a small table continuation above the final evaluation
  paragraph.
- RHWP page 2 has no horizontal table lines and only the final evaluation
  paragraph.
- RHWP page 1 renders the form table down to about `y=975` and then treats the
  table as complete.

## Structural Evidence

`hwpx_table_source_probe.py` reports one table:

- `22x5`
- `textWrap=TOP_AND_BOTTOM`
- `pageBreak=CELL`
- `repeatHeader=1`
- multiple row-spans:
  `r0c0x4,r5c0x6,r11c0x2,r14c0x2,r16c0x4,r20c0x2`

`dump_pages_current.txt` reports:

- page 1: `PartialTable pi=4 ci=0 rows=0..22 cont=false ... end_cut=[1, 1, 2, 2, 1]`
- page 2: only paragraphs `pi=6` and `pi=7`; no continued `PartialTable`.

`cellbreak_source_scan.py` flags candidate split rows:

- `candidate_splits=15,17`

`hwpx_row_floor_scan.py` shows a final-row zero-height cell with real content:

- row 21 cell `c1`: `decl=0.0`, `content=27.6`, `lines=2`
- row 21 cell `c2`: `decl=34.2`, `content=12.0`, `lines=1`

This is a plausible structural bug class: `CELL` page-break tables with
repeated headers, carried row-span blocks, and zero-height final-row cells can
be marked complete on the first page even though Hancom carries the visible
tail to the next page.

## Accepted Patch

`src/renderer/typeset.rs` now preserves the continuation path when the tiny
final-tail drop rule meets this narrow structural shape:

- non-TAC `TopAndBottom` table;
- HWPX `pageBreak=CELL`;
- repeated header table in both source and measurement;
- final row contains a zero declared-height cell;
- that same measured cell has real text content height.

The existing sub-line tiny-tail clipping policy remains enabled for ordinary
declared-height cells and for larger non-final fragments.

## Rejected Broad Tweaks

`svg_component_probe.py` on the representative and guard:

- target page 1: `base=9.18`, `hide_text=6.16`, `hide_lines=5.94`
- target page 1: `font_size_x0.90=8.61`, `font_size_x1.10=9.82`
- target page 2: `base=1.67`, `hide_text=1.04`, `hide_lines=1.04`
- guard `report_form:2`: `base=12.63`, `font_size_x0.90=12.25`,
  `font_size_x1.10=13.03`, `text_y_p4=12.83`

The target is jointly owned by table lines and text placement. Font-size and
text y-shift variants are broad, modest, and touch the guard, so they are not
acceptable renderer rules.

## Validation

- Focused unit: `cargo test --lib --release final_split_table_subline_tail_can_be_clipped_without_continuation_page -j 1`
- Target/guard board:
  `/tmp/diff/_review_form01_cellbreak_zeroheight_tail_candidate_2026-06-09/index.html`
- Focused gallery audit:
  `PASS: no gallery truncation/aspect issues across 3 doc(s)`
- Structural dump after patch:
  page 2 now contains
  `PartialTable pi=4 ci=0 rows=20..22 cont=true start_cut=[1, 1, 2, 2, 1]`
  before the evaluation paragraph.
- Broad non-landscape board:
  `/tmp/diff/_review_all_nonlandscape_after_form01_tail_2026-06-09/index.html`
- Broad gallery audit:
  `PASS: no gallery truncation/aspect issues across 22 doc(s)`
- Page-count guards hold for the comparable board, excluding the known staging
  artifact `meeting_summary_font_fallback` whose `rhwp_svg_cur` symlink has no
  SVG pages.
- `python3 scripts/check_renderer_overfit.py`
- `git diff --check -- src/renderer/typeset.rs`
