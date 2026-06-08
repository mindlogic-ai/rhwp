# RHWP Fidelity Queue -- 2026-06-08 05:35:07

Board: `/Users/jaehoshin/Desktop/mindlogic/factchat/worktree-rhwp-poc/rhwp/work/FIDELITY_VISUAL_STATUS_CURRENT_CONTINUE_2026-06-08.md`

| rank | category | doc | page | status | reason | next command |
|---:|---|---|---:|---|---|---|
| 1 | `cover/body-title semantic split` | `05_3781559_medschool_car_2bu_je_plan` | 1-2 | `accepted-semantic` | Hancom keeps the cover-only page 1 and starts the colored body title band plus `□ 추진 배경` on page 2. RHWP previously leaked the non-TAC `TopAndBottom` `pageBreak=CELL` title-band table (`pi=17`) onto page 1 and collapsed the document to 3 pages. The structural fix defers shallow full-width CELL title-band tables after cover media/visible cover text when blank spacers and visible body text follow. Fresh current board shows Hancom 4 / RHWP 4. Remaining differences are cover/table geometry, font, and stroke weight, not semantic page split. | `open /tmp/diff/_review_fresh_comparable_post_cover_fix_2026-06-08/05_3781559_medschool_car_2bu_je_plan/index.html` |
| 2 | `table-text-raster` | `overseas_training` | 1 | `guard-only` | current evidence rejects broad SVG font/stroke/fill/y-shift knobs; use as guard until a backend or cell-composition invariant appears | `python3 harness/raster_backend_probe.py overseas_training:1 --native --region focus:X0,Y0,X1,Y1` |
| 3 | `photo-grid/pre-grid` | `photo_122p_civil_defense` | 79 | `accepted-129` | structural candidates now align the page-count and checked heading anchors: HWPX `pageBreak=TABLE` non-TAC TopAndBottom photo tables keep raw row height; late one-line tails before explicit page breaks move to sparse tail pages; previous-material-page detection defers a large `pageBreak=CELL` TAC table after a continued table+spacer+heading boundary; late heading + following `pageBreak=TABLE` TAC table now defers the table; text after a near-full `pageBreak=CELL` TAC form table starts on the next page when another CELL TAC form table follows; and the final visible tail group before an explicit blank break moves together. Fresh dump is 129 pages vs Hancom 129; remaining misses are sizing/glyph/rule-weight fidelity, not semantic page drift. | `python3 harness/heading_drift_scan.py photo_122p_civil_defense --dump /tmp/diff/photo_122p_civil_defense/dump_pages_tail_group_candidate3.txt && open /tmp/diff/_review_civil_defense_tail_group_candidate_2026-06-08/index.html` |
| 4 | `table-text-raster` | `meeting_summary` | 1 | `guard-only` | current evidence rejects broad SVG font/stroke/fill/y-shift knobs; use as guard until a backend or cell-composition invariant appears | `python3 harness/raster_backend_probe.py meeting_summary:1 --native --region focus:X0,Y0,X1,Y1` |
| 5 | `cellbreak-rowspan` | `accountability_eval` | 4 | `probe-no-patch-yet` | page count matches Hancom 6/6, but page 4 misses Hancom's clipped lower continuation strip: RHWP stops around y=626.8 while Hancom has main table to y=658.5 plus a lower band y=688.9..735.3. The owner is the `rowspan_touched` CellBreak path: one-line rows crossed by carried rowspans are treated as unsplittable and deferred wholesale. A shallow top-slice candidate aimed at the normal row-overflow path was a no-op and removed. | `python3 harness/svg_geometry_probe.py accountability_eval:4 && python3 harness/cellbreak_rowspan_scan.py --min-slack 0.0` |
| 6 | `table-text-raster` | `form_07_______________41KB` | 5 | `guard-only` | current evidence rejects broad SVG font/stroke/fill/y-shift knobs; use as guard until a backend or cell-composition invariant appears | `python3 harness/raster_backend_probe.py form_07_______________41KB:5 --native --region focus:X0,Y0,X1,Y1` |
| 7 | `guard` | `report_form` | 2 | `guard` | page count and visual score are currently below drift threshold | `python3 harness/fidelity_category_status.py --with-gallery report_form` |

## Structural Scanner Summary

- CellBreak carried-rowspan rows: 12.
- Photo-grid rows: 16.

Interpretation:

- `patchable`: safe enough to start a structural probe now.
- `probe`: run targeted probes before Rust.
- `needs-more-guards`: do not patch until another independent doc appears.
- `guard-only`: useful for preventing regressions, not current patch source.

Current photo-grid patch target:

- Avoid local image-placement tweaks first. The paired-page review shows RHWP
  can render the table body close to Hancom once semantically aligned.
- Current accepted candidate in `src/renderer/height_measurer.rs`: non-TAC
  `TopAndBottom` picture tables whose original HWPX `pageBreak` is `TABLE`
  keep raw row height instead of shrinking to declared `<hp:sz height>`.
- Current candidate in `src/renderer/typeset.rs`: a one-line visible paragraph
  that barely fits at the body bottom moves to its own tail page when the next
  paragraph has an explicit page/section break. The same rule allows a wider
  remaining strip only when the next paragraph is itself an explicit-break
  small TAC `TopAndBottom` title table. This fires at `pi=611`, `pi=716`, and
  two other explicit-break tails, producing Hancom-like sparse pages.
- Current accepted candidate in `src/renderer/typeset.rs`: after a flushed
  material page ends with a continued HWPX `pageBreak=TABLE` partial table plus
  a high-vpos blank spacer paragraph, a following explicit page-break heading is
  allowed to stay as a sparse page when the next paragraph is a single large
  `pageBreak=CELL` TAC `TopAndBottom` table. The important implementation detail
  is to inspect the previous flushed material page, not `pages.last()` blindly,
  because the current empty page shell can already exist while the heading is
  still in `current_items`.
- Guard results for the tail candidate: `photo_w31` stays 30, meeting template
  stays 5, natural-sci stays 57, K-STAR stays 21, internship stays 11. `form_07`
  is 11 under the current patched binary but had no `BOTTOM_TAIL_BREAK`, so that
  delta is from existing uncommitted renderer changes, not this tail rule.
- Latest guard results for the corrected previous-material-page rule:
  `photo_122p_civil_defense` improves `127 -> 128` pages vs Hancom `129`.
  `photo_w31` stays 30, meeting template stays 5, natural-sci stays 57,
  K-STAR stays 21, internship stays 11, and `form_07` stays 11 under the current
  worktree.
- Latest accepted page-79 boundary candidate:
  a late single-line heading followed by a medium-height HWPX
  `pageBreak=TABLE` TAC `TopAndBottom` table now defers the table when the
  heading is already in the lower half of a single-column page. A guard excludes
  footer notes after TAC form tables when the next paragraph is an explicit
  full-page TAC form/table, preventing the `pi=871` orphan page regression.
  Fresh current-source dump:
  `/tmp/diff/photo_122p_civil_defense/dump_pages_current_accepted_2026-06-08.txt`.
  Fresh selected visual review:
  `/tmp/diff/_review_civil_defense_accepted_2026-06-08/index.html`.
- Latest accepted page-96/97 boundary candidate:
  text after a near-full TAC `TopAndBottom` form table with HWPX
  `pageBreak=CELL` now starts the next page when the following paragraph is
  another CELL-split TAC form table. This fixes the `pi=893` leak: RHWP page 96
  no longer shows `□ 서식 5호(과태료 부과 안내문)`, and RHWP page 97 starts with
  that heading like Hancom. The narrowed guard was necessary because a broader
  version moved `photo_w31` `pi=380` and regressed that doc to 31 pages.
  Narrowed guard counts held: `photo_w31` 30, meeting template 5, natural-sci
  57, K-STAR 21, internship 11, `form_07` 11, `meeting_summary` 3, and
  civil-defense 128. Visual review:
  `/tmp/diff/_review_civil_defense_pi893_narrow_manual_2026-06-08/index.html`.
- Remaining work: civil-defense still trails Hancom by 1 page overall
  (`128` vs `129`). Heading drift is now 0 for the checked page-74, page-79,
  page-87, page-90, page-92, and page-96/97 boundaries. The current concrete
  remaining anchors are early `pi=114`, `pi=132`, `pi=158` (`RHWP 15/16/18`
  vs Hancom 16/17/19) and the local `pi=852` mismatch (`RHWP 84`, Hancom 85).
  Visual review still shows sizing, table-rule weight, and glyph differences
  even where page alignment is now correct.
- Latest accepted page-84/85 text-tail candidate:
  plain single-line body text near the bottom now defers when it only fits by
  consuming page-tail slack/trailing spacing and visible body text follows. A
  companion keep-with-next rule moves a late one-line paragraph when the
  following one-line heading/body group cannot fit after it. This fixes the
  local `pi=852` drift (`RHWP 84`, Hancom 85 -> `RHWP 85`, Hancom 85) and
  removes the render overflow previously logged for `pi=852`. Structural tests:
  `late_single_line_text_keeps_following_body_off_page_tail` and
  `late_single_line_text_moves_with_following_body_group`. Latest dump:
  `/tmp/diff/photo_122p_civil_defense/dump_pages_late_single_line_group_candidate.txt`.
  Latest visual strip:
  `/tmp/diff/_review_civil_defense_late_single_line_group_candidate_2026-06-08/index.html`.
  Guard counts held: `photo_w31` 30, meeting template 5, natural-sci 57,
  K-STAR 21, internship 11, `form_07` 11, `meeting_summary` 3. Total
  civil-defense page count is still `128` vs Hancom `129`, so the remaining
  missing page is elsewhere, most likely the early `pi=114/132/158` region.
- Latest accepted early-grid/short-note paired candidate:
  a large medium-width HWPX `pageBreak=CELL` TAC `TopAndBottom` grid now starts
  on the next page when it follows a visible lead-in on a mostly-used page and
  would otherwise consume the last few percent of body height. The rule is
  bounded to `5..=8` columns after `internship_plan` exposed false triggers on
  `16x13` and `14x3` tables. Companion narrowing keeps short note paragraphs
  after TAC guide tables before a plain explicit page break, preventing the
  `pi=239` orphan page. Net effect on `photo_122p_civil_defense`: early
  anchors now align (`pi=114/132/158` all delta 0), `pi=239` no longer creates
  its own page, and checked later headings remain delta 0 through `pi=941`.
  Total page count remains `128` vs Hancom `129`, so this fixes semantic drift
  but not the final missing page. Structural tests:
  `large_cell_tac_after_page_tail_lead_in_starts_next_page` and
  `late_one_line_tail_before_explicit_page_break_moves_to_tail_page`. Latest
  dump:
  `/tmp/diff/photo_122p_civil_defense/dump_pages_page_tail_lead_in_plus_note_narrow_candidate.txt`.
  Latest visual strip:
  `/tmp/diff/_review_civil_defense_page_tail_lead_in_plus_note_narrow_2026-06-08/index.html`.
  Guard counts held: `photo_w31` 30, meeting template 5, natural-sci 57,
  K-STAR 21, `internship_plan` 11, `form_07` 11, `meeting_summary` 3.
  `python3 scripts/check_renderer_overfit.py` passed with 8 known baseline
  findings.
- Latest accepted final-tail candidate:
  a late three-paragraph visible tail group immediately before an explicit
  blank page/section break is kept together on the next page when squeezing it
  into the previous page would leave only a tiny tail strip. The explicit blank
  break may carry non-visual metadata controls (`SectionDef`, `ColumnDef`,
  headers/footers/page-number metadata, etc.) but no visible flow controls.
  This moves `pi=994..996` from RHWP page 127 to page 128 and lets the explicit
  blank `pi=997..998` produce page 129, matching Hancom's final pages.
  `photo_122p_civil_defense` now renders 129 pages vs Hancom 129, while the
  heading drift scan remains delta 0 for checked anchors from `pi=63` through
  `pi=941` except the known ambiguous repeated `(4) 참여형 교육 안내` needle.
  Structural test:
  `late_visible_group_before_explicit_blank_break_starts_next_page`. Latest
  dump:
  `/tmp/diff/photo_122p_civil_defense/dump_pages_tail_group_candidate3.txt`.
  Latest visual strip:
  `/tmp/diff/_review_civil_defense_tail_group_candidate_2026-06-08/index.html`.
  Guard counts held: `photo_w31` 30, meeting template 5, natural-sci 57,
  K-STAR 21, `internship_plan` 11, `form_07` 11, `meeting_summary` 3.
  `python3 scripts/check_renderer_overfit.py` passed with 8 known baseline
  findings.

2026-06-08 continuation notes:

- `cellbreak-rowspan` / `accountability_eval` current truth:
  Hancom and RHWP both render the staged source as 6 pages, so the remaining
  issue is visual table-fragment fidelity rather than page-count drift. Current
  board:
  `/tmp/diff/_review_accountability_current_2026-06-08/index.html`.
- Page 4 geometry:
  `python3 harness/svg_geometry_probe.py accountability_eval:4` reports RHWP
  line/table content ending around `y=626.8`; Hancom has a main band to
  `y=658.5` plus a lower continuation band `y=688.9..735.3`.
- Split diagnostics:
  `/tmp/diff/accountability_eval/dump_pages_table_drift_current.txt` and
  `/tmp/diff/accountability_eval/table_drift_current.stderr` show page 4 as
  `rows=21..27`, `used=635.4px`, with `44.9px` slack. The scanner reports
  carried rowspans `(16,0,12)` and `(19,1,4)` plus nearby blank row `28`.
- Rejected/no-op candidate:
  allowing a bounded shallow `CellBreak` top slice in the normal row-overflow
  path did not affect the target after rebuilding. A temporary
  `RHWP_CELLBREAK_DEBUG` probe showed the normal row-overflow branch never
  fires for this table; the owner is the earlier `rowspan_touched` path.
  A follow-up attempt in `rowspan_touched` was also no-op because the target
  row is one-line-per-cell and `MeasuredTable::is_row_splittable(row)` returns
  false. The speculative hunks and debug marker were removed.
- Next implementation direction:
  investigate a clip-aware fragment model for `CellBreak` repeated-header text
  rows crossed by carried rowspans. Hancom appears to paint/clip the top of a
  following one-line row into the remaining page body, not split a multi-line
  cell. Do not force the existing line-cut path without also proving partial
  row height/render clipping semantics.

- Do not trust the old late-pair board
  `/tmp/diff/_review_photo_grid_late_pairs_tail_patch3_2026-06-08/index.html`
  unless `rhwp_svg_cur` has just been regenerated. That board was observed to
  reuse stale SVG pages and showed RHWP page 74 as `마. 소수방 교육장` while the
  current dump had `다. 화생방 교육장`.
- Fresh board:
  `/tmp/diff/_review_photo_grid_late_pairs_fresh_svg_2026-06-08/index.html`.
  This board confirms the remaining visible miss: Hancom page 74 is a sparse
  `다. 화생방 교육장` heading page; RHWP page 74 packs the full `다` photo table
  under the heading.
- Rejected/no-op candidate: merely disabling the 1% TAC sub-line fit tolerance
  for “continued table + spacer + heading + near-full TAC table” did not change
  the real dump. Debug showed the TAC fit layer still saw `pi=769` as having
  about 17.8px spare (`available≈777.2`, `cur≈26.1`, `h≈733.4`), so the first
  remaining miss is not a simple overflow-tolerance case.
- Rejected/no-op candidate: deferring a single large `pageBreak=CELL`
  treat-as-character `TopAndBottom` table when the previous rendered page ended
  with a `pageBreak=TABLE` partial table plus high-vpos blank spacer passed its
  synthetic unit test but did not change the real dump. `photo_122p_civil_defense`
  stayed at 127 pages, and page 74 still packed `다. 화생방 교육장` plus table
  `pi=769` together. Root cause: it inspected `pages.last()`, which can be the
  current empty page shell. The corrected accepted rule now scans backward to
  the previous flushed material page.
- Fresh accepted-candidate board:
  `/tmp/diff/_review_photo_grid_late_pairs_material_prev_candidate_2026-06-08/index.html`.
  Page 74 now matches Hancom as a sparse `다. 화생방 교육장` page; page 75 now
  contains the moved `pi=769` table.
- New source probe:
  `harness/hwpx_para_source_probe.py /tmp/diff/photo_122p_civil_defense --start 762 --end 775`
  maps renderer paragraph indexes to HWPX source metadata. Key source shape:
  `pi=766` table global 67 is `pageBreak=TABLE`, `pi=767` is a blank spacer with
  lineSeg `vertpos=36875`, `pi=768` is an explicit page-break heading, and
  `pi=769` table global 68 is a single large `pageBreak=CELL` TAC table.
