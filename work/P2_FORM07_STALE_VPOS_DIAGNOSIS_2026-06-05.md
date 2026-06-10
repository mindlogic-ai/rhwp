# P2 Form07 Stale VPOS / Table Packing Diagnosis -- 2026-06-05

Target: `form_07_______________41KB`

Current decision: BANK for this turn. The defect is real, but the safe patch
point is not a generic empty-paragraph collapse. It is a multi-table
TopAndBottom paragraph/anchor packing problem.

## Visual Evidence

Artifacts:

- `/tmp/diff/form_07_______________41KB/look/page-10.png`
- `/tmp/diff/form_07_______________41KB/look/page-11.png`
- `/tmp/diff/_gallery3/form_07_______________41KB/index.html`

Fresh visual refresh:

```text
python3 harness/look.py /tmp/diff/form_07_______________41KB --export
Hancom=11 rhwp=12
```

Observed:

- Hancom page 10 contains the tail of the "진단에 따른 목표/기대결과" table and
  also starts the next section/table, "3. 간호수행과 수행의 이론적 근거".
- rhwp page 10 contains only the previous table content and leaves a large
  lower blank region.
- Hancom page 11 is the final/reference section.
- rhwp page 11 is Hancom's lower page-10 table content, so rhwp is one page
  behind by this point.

## Dump Evidence

Command:

```bash
docker compose --env-file .env.docker run --rm -v /tmp/diff:/diff dev \
  /app/target/release/rhwp dump-pages /diff/form_07_______________41KB/source.hwpx
```

Relevant output:

```text
page 9:
  pi=87 table 3x3
  pi=88 empty paragraph
  pi=89 PartialParagraph lines=0..1
  pi=89 ci=0 table 4x3
  used=876.0px, hwp_used~827.9px, diff=+48.1px

page 10:
  pi=89 ci=1 table 4x3
  pi=90 empty paragraph at vpos=64000
  used=865.3px, hwp_used~882.7px, diff=-17.4px

page 11:
  pi=91 empty paragraph at vpos=30957
  pi=92 empty paragraph at vpos=33157
  pi=93 PartialParagraph lines=0..1
  pi=93 ci=0 table 2x3
  used=492.4px, hwp_used~433.7px, diff=+58.7px

page 12:
  pi=94 ci=0 table 2x3
  final/reference content
```

Important correction:

- The bad area is not simply "one partial table continuation followed by empty
  paragraphs".
- Dump shows `pi=89 ci=0` and `pi=89 ci=1`: multiple TopAndBottom tables share
  the same paragraph/anchor neighborhood.
- A patch that only says "after PartialTable, ignore next empty paragraphs" is
  therefore the wrong abstraction.

## Built-In Diagnostics

Command:

```bash
docker compose --env-file .env.docker run --rm -v /tmp/diff:/diff \
  -e RHWP_TABLE_DRIFT=1 dev \
  /app/target/release/rhwp dump-pages /diff/form_07_______________41KB/source.hwpx
```

Key rows:

```text
TABLE_DRIFT pi=89 eff_h=397.2 host_sp=14.7 table_total=411.9 mt_sum=397.2
TABLE_DRIFT pi=89 eff_h=409.0 host_sp=14.7 table_total=423.7 mt_sum=409.0
TABLE_CUT_DRIFT pi=89 cut_sum=409.0 mt_sum=409.0 diff=+0.0
TABLE_DRIFT pi=93 eff_h=375.0 host_sp=14.7 table_total=389.7 mt_sum=375.0
TABLE_DRIFT pi=94 eff_h=375.0 host_sp=14.7 table_total=389.7 mt_sum=375.0
```

Interpretation:

- Row/cut measurement is not the obvious problem here; cut sums match measured
  row sums.
- The issue is paragraph/table anchor packing and vpos/current-height state
  around same-paragraph `TOP_AND_BOTTOM` table controls.

Additional type-set drift evidence:

```text
TYPESET_DRIFT_PI pi=90 cur_h=835.9 first_vpos=64000
TYPESET_DRIFT_PI pi=91 cur_h=865.3 first_vpos=30957
TYPESET_DRIFT_PI pi=92 cur_h=44.0  first_vpos=33157
```

This explains the blank tail: by the time rhwp reaches the empty anchors after
`pi=89`, the cursor is already near page bottom, so later visible table content
is forced to the next page.

## Structural Class

Likely family:

- same-paragraph or adjacent-paragraph non-TAC `TOP_AND_BOTTOM` tables,
- `pageBreak=CELL`,
- `repeatHeader=1`,
- `flowWithText=1`,
- `allowOverlap=0`,
- paragraph-relative / column-relative anchors,
- empty paragraphs with high cached vpos between table anchors,
- Hancom visually forward-packs the following table under the previous table
  tail.

Likely owner code:

- `src/renderer/typeset.rs`
  - `typeset_table_paragraph`
  - `typeset_block_table`
  - `vpos_snap_current_height`
- `src/renderer/height_cursor.rs`
  - `HeightCursor::vpos_adjust`
- `src/renderer/layout/table_partial.rs`
  - render-side consistency for split/table fragments

## Rejected Broad Fixes

Do not patch with:

- collapse all empty paragraphs,
- ignore all `vpos` after tables,
- ignore `vpos=64000` globally,
- force the next table onto page 10 by paragraph index or text,
- adjust row heights for `pi=89`/`pi=93` when diagnostics show row sums match.

## Next Probe

The next useful probe is not another visual check. It is instrumentation:

1. Log table-control index, `current_height`, vertical offset, and page item type
   for every table control in paragraphs 87-94.
2. Confirm whether `pi=89 ci=0` and `pi=89 ci=1` are treated as separate
   same-paragraph float lanes or as sequential block tables.
3. Compare layout-side y positions for those two controls against typeset
   `current_height`.
4. Only then consider a narrow rule for same-paragraph TopAndBottom table
   packing.

LAND bar for any future fix:

- rhwp page count moves 12 -> 11 for `form_07`,
- page 10 visually includes the following `3. 간호수행...` table like Hancom,
- no regression in `form_24`, `form_25`, `huge_01_DNA`, `huge_02_DNA`,
- full gate reports no new page-count regressions and no new overflow,
- overfit check passes.

## Rejected Probe: Empty Spacer VPOS Suppression

Candidate:

- Suppress a large forward VPOS jump only for an empty, control-free paragraph
  immediately after a non-TAC paragraph-relative `TopAndBottom` table.
- Then optionally allow a short following `TopAndBottom` table to keep a large
  final row after that recovered stale spacer gap.

Evidence:

- Dump:
  `/tmp/diff/form_07_______________41KB/dump_pages_stale_spacer_probe.txt`
- Diagnostics:
  `/tmp/diff/form_07_______________41KB/drift_stale_spacer_probe.txt`
- Tail-pack dump:
  `/tmp/diff/form_07_______________41KB/dump_pages_stale_spacer_tail_probe.txt`
- Tail-pack diagnostics:
  `/tmp/diff/form_07_______________41KB/drift_stale_spacer_tail_probe.txt`
- Refreshed visual:
  `/tmp/diff/form_07_______________41KB/look/page-10.png`
  `/tmp/diff/form_07_______________41KB/look/page-11.png`
  `/tmp/diff/form_07_______________41KB/look/page-12.png`

Result:

- The stale VPOS skip fired exactly once at `pi=90`:
  `TYPESET_STALE_VPOS_SKIP: pi=90 cur_h=423.7 first_vpos_px=853.3 avail=876.8`.
- It moved `pi=91`, `pi=92`, and the start of `pi=93` onto RHWP page 10.
- Page count stayed Hancom 11 / RHWP 12.
- The following 2-row table still split: row 0 stayed on page 10 and row 1
  moved to a near-empty page 11.
- The remaining final-row overflow was about 46px, not a small rounding tail,
  so widening the existing final-row orphan tolerance would be a broad table
  packing change.

Decision:

- Reverted from source. Do not retry stale-empty-spacer suppression alone.
- The next safe probe should explain why Hancom composes/measures the `pi=93`
  table body shorter or places that table as a whole after the preceding table
  stack. This is table content-height / row measurement after TopAndBottom
  forward-packing, not just stale empty paragraph VPOS.
