# RHWP Fidelity Next Run Board -- 2026-06-05

Use this as the concrete next-hours board. The goal is not to make one fixture
look better; the goal is to land structural renderer rules that improve a
failure family and do not regress the current corpus.

## Fast Validation Ladder

Run checks in this order. Stop early when a rung fails.

1. Target detail:

```bash
python3 work/fidelity_queue.py --target <doc>
python3 work/fidelity_queue.py --target <doc> --check-artifacts
```

2. Native Rust build only:

```bash
CARGO_BUILD_JOBS=1 docker compose --env-file .env.docker run --rm dev \
  cargo build --release --bin rhwp
```

3. Target rerender / dump:

```bash
python3 harness/review_gallery.py /tmp/diff/_review_<doc>_live <doc> --export-current
python3 harness/look.py /tmp/diff/<doc> --export
docker compose --env-file .env.docker run --rm -v /tmp/diff:/diff dev \
  /app/target/release/rhwp dump-pages /diff/<doc>/source.hwpx
```

4. Anti-monkeypatch check:

```bash
python3 scripts/check_renderer_overfit.py
```

5. Broad corpus page-count/overflow gate:

```bash
bash harness/gate.sh --no-build
```

6. Visual sweep:

- inspect every document whose page count, overflow status, or render hash
  changed;
- numeric improvement is not enough if image/table/text overlap gets worse.

Do not build WASM/studio until native build, overfit, full gate, and visual
sweep are clean.

## Target 1 -- P3 Rowspan CELL Table Splitting

Document:

- `accountability_eval`
- fitted oracle directory:
  `/tmp/diff/accountability_eval_fitted_oracle`
- key pages:
  - `look/page-01.png`
  - `look/page-05.png`
  - `look/page-06.png`
  - `look/page-11.png`

Why first:

- Hancom-fitted output is 11 pages; RHWP-fitted output is now 13 pages after
  the large-rowspan row-wise candidate. Before that candidate it was 5 pages.
- Width fitting alone is not sufficient.
- Current diagnostics show total table height is internally consistent, so the
  first defect was partial-table row/cell-cut advancement across large
  rowspans.
- A saved-cell-line-width patch improves page 1 horizontal spill: trusted
  table-cell lines now use saved `LineSeg.segment_width` for alignment width
  when the saved line is narrower than the cell inner width. This does not move
  the 11-vs-13 page-count residual.
- The remaining defect is row content-height/page split accounting after text
  composition, not generic clipping.

Likely owner code:

- `src/renderer/layout/table_layout.rs`
- `src/renderer/layout/table_partial.rs`
- `src/renderer/layout/paragraph_layout.rs`
- `src/renderer/height_measurer.rs`
- `src/renderer/typeset.rs` only for pagination integration

Structural discriminator to prove before patching:

- `pageBreak=CELL`
- `repeatHeader=1`
- large `rowSpan` groups
- non-TAC table
- carried partial-table cut whose next fragment consumes far too little height
- trusted table-cell `LineSeg.segment_width` preserved during render and
  measurement

Reject:

- global row-height multiplier,
- global table shrink,
- filename/text/page-specific branch,
- claiming the server fitter solved it.

Acceptance:

- fitted RHWP page count moves from 13 toward Hancom 11;
- page 1 keeps the fixed cell-width behavior: first target cell stops before
  the adjacent cell boundary around `x=279`;
- pages after 5 preserve real logical content without horizontal text overlap;
- no regression in table-heavy guard docs from the queue;
- `check_renderer_overfit.py` and `harness/gate.sh --no-build` pass.

## Target 2 -- P1 Multi-Column Float Reserve

Document:

- `wild_02_paper_fig_10MB`
- key pages:
  - `/tmp/diff/wild_02_paper_fig_10MB/look/page-01.png`
  - `/tmp/diff/wild_02_paper_fig_10MB/look/page-09.png`

Why second:

- This is visible content overlap and late-page content loss.
- It is a different class from page-relative scanned images.

Likely owner code:

- `src/renderer/float_placement.rs`
- `src/renderer/typeset.rs`
- `src/renderer/layout/paragraph_layout.rs`

Structural discriminator to prove before patching:

- `flowWithText=1`
- `allowOverlap=0`
- `vertRelTo=PARA`
- `horzRelTo=COLUMN`
- wrap mode `TOP_AND_BOTTOM` or `SQUARE`
- object crosses or effectively reserves more than one column near a page top

Reject:

- broad TopAndBottom reserve,
- page-height tax on all pictures,
- single-column behavior changes.

Acceptance:

- page 1 no longer starts text through the figure band;
- late logical content moves toward the Hancom page count;
- guard docs `wc47_6pg`, `wc51_4pg`, `wc69_9pg`, `wc04_4pg`,
  `wb03_physics_lab_2pg` remain visually acceptable.

## Target 3 -- P2 Embedded Scan / Title Page Ownership

Document:

- `wc31_17pg`
- fresh review:
  `/tmp/diff/_review_wc31_current_after_revert/index.html`
- key pages:
  - `/tmp/diff/_review_wc31_current_after_revert/wc31_17pg/page-05.png`
  - `/tmp/diff/_review_wc31_current_after_revert/wc31_17pg/page-06.png`
  - `/tmp/diff/_review_wc31_current_after_revert/wc31_17pg/page-07.png`
  - `/tmp/diff/_review_wc31_current_after_revert/wc31_17pg/page-08.png`
  - `/tmp/diff/_review_wc31_current_after_revert/wc31_17pg/page-09.png`

Why third:

- This is now understood as embedded full-page scan/image ownership, not a
  generic preview crop and not only page-count drift.
- `BinData/image4.JPG` is Hancom page 5's body image. RHWP draws the following
  `증빙 1` 1x3 title table over that image, so the defect is per-control page
  ownership inside/crossing a paragraph.
- Rejected probes proved that paragraph-level prebreaks or standalone title
  table breaks can improve the count while creating blank pages or misordering
  `증빙 2/3/4`.
- Run `python3 harness/embedded_scan_title_diag.py /tmp/diff/wc31_17pg/source.hwpx`
  before editing. Current corpus scan is `scanned=151 matches=1`, so the rule
  must be narrow and structural.

Likely owner code:

- `src/renderer/typeset.rs`
- `src/renderer/layout.rs`
- `src/renderer/layout/picture_footnote.rs`
- `src/renderer/layout/table_layout.rs`

Structural discriminator to prove before patching:

- empty or near-empty host paragraph with page-relative/PAPER-relative
  full-page scanned picture;
- adjacent or same-paragraph 1x3 title table, often TAC `TopAndBottom`;
- embedded image itself represents a prior logical page while the title table
  starts the next evidence page;
- saved line segments/top anchors show page ownership but paragraph-level item
  routing is too coarse.

Reject:

- document/title text checks,
- broad prebreak before all page-relative pictures,
- standalone title-page rule that ignores same-paragraph scan/title ordering,
- accepting page-count improvement when title pages are blank or out of order.

Acceptance:

- page 5 keeps only the embedded page-5 body image, with no `증빙 1` overlay;
- page 6 starts `증빙 1` with the report body below it;
- standalone `증빙 2` and `증빙 3` title pages appear in order;
- RHWP page count moves toward 17 without blank-page artifacts;
- guard docs for stale-vpos and picture-float behavior remain stable.

## Target 4 -- P2 Stale VPOS / Empty Spacer Forward-Pack

Document:

- `form_07_______________41KB`
- key pages:
  - `/tmp/diff/_gallery3/form_07_______________41KB/page-09.png`
  - `/tmp/diff/_gallery3/form_07_______________41KB/page-10.png`
  - `/tmp/diff/_gallery3/form_07_______________41KB/page-11.png`
  - `/tmp/diff/_gallery3/form_07_______________41KB/page-12.png`

Why fourth:

- This likely explains several page-count misses, but it has high blast radius
  because many documents depend on cached line segments.
- Fresh probe result: suppressing the stale empty spacer after the preceding
  `TopAndBottom` table moves the next table start onto page 10, but RHWP still
  renders 12 pages because the following 2-row table body splits to a near-empty
  page. That probe is banked/reverted; the next useful work is table body
  measurement/composition after TopAndBottom forward-packing, not broader empty
  paragraph or VPOS suppression.
- Later probe result: collapsing consecutive empty control-free spacers between
  adjacent paragraph-relative non-TAC `TopAndBottom` tables can move `form_07`
  from 12 pages to the Hancom 11-page count, but it is not landable as-is. Page
  10 then paints the following table only down to RHWP's body bottom while the
  Hancom oracle keeps the lower table band/text visible farther down the page.
  Treat this as a render/clip/body-bottom interaction after forward-packing,
  not as proof that generic spacer collapse is solved.

Likely owner code:

- `src/renderer/typeset.rs`
- `src/renderer/layout/paragraph_layout.rs`
- `src/renderer/height_cursor.rs`
- `src/renderer/layout/table_layout.rs`
- `src/renderer/height_measurer.rs`

Structural discriminator to prove before patching:

- empty control-free paragraph,
- cached VPOS jumps near page bottom,
- following visible table/block fits if the spacer jump is discounted,
- no explicit page/section/column break,
- Hancom visually forward-packs the following block.
- after discounting the spacer, the following short `TopAndBottom` table still
  needs a structural row/body-height explanation; do not widen row-overflow
  tolerance unless Hancom row composition proof shows the row itself is measured
  shorter.
- if the patch changes page count by packing the next table onto page 10, also
  prove the table cell text and fills are not clipped at the body bottom. SVG
  clip/body expansion must be inspected before accepting a pagination-only
  improvement.

Reject:

- global empty paragraph collapse,
- global cached VPOS ignore,
- fixes that under-paginate table-heavy forms.
- short-table final-row overflow widening without row-height proof.

Acceptance:

- `form_07` page 10 forward-packs the following table like Hancom;
- the forwarded table body on page 10 remains visibly complete relative to the
  oracle and does not lose lower cell text at the body bottom;
- table-heavy guard docs do not lose content or page-count correctness.

## Target 5 -- P4 Export / Reopen Gate

Run after each landed renderer-category patch, not instead of render validation.

Gate:

```bash
HWP_TEST_URL=http://127.0.0.1:8765/ \
  node hwp-agent-spike/tests/export_roundtrip_probe.mjs
```

Acceptance:

- exported HWPX reopens in Hancom after representative mutation;
- HWP export remains class-gated unless reopen proof exists;
- magic bytes are not accepted as proof.

## Land / Bank / Revert Rules

LAND:

- target defect improves visibly;
- page count moves toward oracle or remains correct;
- no unrelated page-count regression;
- no new overflow;
- overfit checker passes;
- every changed visual document is inspected.

BANK:

- three probe/build cycles fail to find a structural discriminator;
- the mechanism is real but the safe abstraction is unclear;
- evidence is preserved in `work/P<n>_<name>_DIAGNOSIS_*.md`.

REVERT:

- content disappears;
- image/table/text overlap appears in an unrelated doc;
- a green non-target document changes page count without explanation;
- the only working condition is filename, body text, title text, or page index.
