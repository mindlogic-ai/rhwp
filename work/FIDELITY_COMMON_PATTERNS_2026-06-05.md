# RHWP Fidelity Common Patterns -- 2026-06-05

This is the concrete category map for a long renderer-fidelity run. It answers:
what to focus on, which docs/pages/images prove the issue, where the code
likely lives, how to validate quickly, and when to land/bank/revert.

## Operating Rule

Fastest route:

1. Fix one failure family at a time.
2. Use Hancom PDF/SVG gallery as oracle.
3. Use native `rhwp dump-pages` and gates before any WASM/studio rebuild.
4. Patch structural renderer rules only.
5. Visually inspect every changed document before keeping a patch.

Do not branch engine behavior on filename, title text, body-text sentinel, or a
bare page number.

## Pattern 1 -- Page-Relative Full-Page Scanned Images

Product symptom:

- following text/table is hidden behind a full-page scan,
- page count can still match, so dump-pages alone may look clean.

Primary target:

- `med_02____2_4MB`
- page: `page-03`
- visual: `/tmp/diff/_gallery3/med_02____2_4MB/page-03.png`
- patched SVG evidence: `/tmp/diff/med_02____2_4MB/rhwp_svg_patch/source_003.svg`

Current state:

- LAND candidate for this narrow scanned-photo content-loss family.
- Fresh validation on 2026-06-05: targeted Rust test passed, overfit check
  passed, broad gate reported `docs=149 improved=1 regressed=0
  new_overflow=0`, and refreshed med_02 visual reported Hancom=6/rhwp=6.
- Clean split validation after removing unfinished `wild_02`/P3 source
  experiments: only `src/renderer/typeset.rs` remains modified for this patch;
  native release build passed; broad gate reported
  `docs=151 improved=1 regressed=0 new_overflow=0`; refreshed `wild_02`
  remained Hancom=9/rhwp=7 and is not part of this fix.
- Residual: table scale/spacing is not pixel-perfect and this does not solve
  multi-column float failures.

Structural discriminator:

- non-TAC picture or picture-shaped shape,
- `textWrap=SQUARE`,
- `flowWithText=1`,
- `vertRelTo=PAPER`,
- `horzRelTo=PAPER|PAGE`,
- object overlaps most of the body/page area,
- later visible flow content exists.

Likely code:

- `src/renderer/typeset.rs`

Validation:

```bash
CARGO_BUILD_JOBS=1 docker compose --env-file .env.docker run --rm dev \
  cargo test --lib page_relative_scan_group_breaks_before_following_flow -j 1
bash harness/gate.sh --no-build
python3 scripts/check_renderer_overfit.py
```

Land bar:

- target page content visible,
- page count remains correct,
- no new overflow,
- visual sweep on changed float docs.

## Pattern 2 -- Multi-Column Floating Figures

Product symptom:

- top-of-page figure should reserve a visual band,
- rhwp starts text too high,
- figure overlaps the right column,
- late document content disappears because flow is under-paginated.

Primary target:

- `wild_02_paper_fig_10MB`
- page: `page-01`, late-content check `page-09`
- visuals:
  - `/tmp/diff/wild_02_paper_fig_10MB/look/page-01.png`
  - `/tmp/diff/wild_02_paper_fig_10MB/look/page-09.png`
  - `/tmp/diff/_gallery3/wild_02_paper_fig_10MB/index.html`

Structural discriminator to search for:

- non-TAC picture/shape,
- `flowWithText=1`, `allowOverlap=0`,
- `textWrap=TOP_AND_BOTTOM` or `SQUARE`,
- `vertRelTo=PARA`,
- `horzRelTo=COLUMN`,
- horizontal visual span crosses the current column boundary or body edge,
- object starts near the top of a multi-column page/paragraph.

Likely code:

- `src/renderer/typeset.rs`
- `src/renderer/float_placement.rs`
- `src/renderer/layout/paragraph_layout.rs`

Validation:

```bash
docker compose --env-file .env.docker run --rm -v /tmp/diff:/diff dev \
  /app/target/release/rhwp dump-pages /diff/wild_02_paper_fig_10MB/source.hwpx
bash harness/gate.sh --no-build
python3 scripts/check_renderer_overfit.py
python3 harness/look.py /tmp/diff/wild_02_paper_fig_10MB --export
```

Bank rule:

- bank rather than patch if the only rule found is broad TopAndBottom page
  breaking or global column reserve.

## Pattern 3 -- Stale VPOS / Empty Spacer Forward-Pack

Product symptom:

- page has suspicious empty tail,
- next table/block starts on the following page even though Hancom packed it
  earlier,
- page count drifts by one or more pages.

Primary target:

- `form_07_______________41KB`
- pages: `page-09` to `page-12`
- detailed diagnosis:
  `/Users/jaehoshin/Desktop/mindlogic/factchat/worktree-rhwp-poc/rhwp/work/P2_FORM07_STALE_VPOS_DIAGNOSIS_2026-06-05.md`
- latest probe banked/reverted: empty-spacer VPOS suppression after a
  `TopAndBottom` table fires at `pi=90` and moves the next table start onto
  page 10, but the following 2-row table still splits to a near-empty extra
  page. The remaining defect is table body/row-height composition after
  forward-packing, not just stale empty paragraph VPOS.
- visuals:
  - `/tmp/diff/_gallery3/form_07_______________41KB/page-09.png`
  - `/tmp/diff/_gallery3/form_07_______________41KB/page-10.png`
  - `/tmp/diff/_gallery3/form_07_______________41KB/page-11.png`
  - `/tmp/diff/_gallery3/form_07_______________41KB/page-12.png`

Sibling targets:

- `wc15_7pg`
- `wc16_6pg`
- `wc17_6pg`
- `wc31_17pg`
- `wc35_15pg`

Structural discriminator:

- same-paragraph or adjacent non-TAC `TOP_AND_BOTTOM` table controls,
- `pageBreak=CELL`, `repeatHeader=1`, `flowWithText=1`, `allowOverlap=0`,
- cached high-vpos empty anchors after table controls,
- following visible table/block is visually forward-packed by Hancom,
- row/cut measurement diagnostics do not show a row-height mismatch.

Likely code:

- `src/renderer/typeset.rs`
- `src/renderer/layout/paragraph_layout.rs`
- `src/renderer/height_cursor.rs`
- `src/renderer/layout/table_layout.rs`
- `src/renderer/height_measurer.rs`

Validation:

```bash
bash harness/gate.sh --no-build
python3 scripts/check_renderer_overfit.py
python3 harness/look.py /tmp/diff/form_07_______________41KB --export
```

Guard docs:

- `form_24_____4MB`
- `form_25__________________6MB`
- `huge_01_DNA________33MB`
- `huge_02_DNA_______75MB`

Reject:

- global empty paragraph collapse,
- global ignore of cached vpos,
- changes that under-paginate table-heavy forms.
- row-height tuning when `TABLE_CUT_DRIFT` says measured and cut row sums match.
- widening final-row overflow tolerance after stale spacer recovery without
  proving Hancom measures the following table row shorter.

## Pattern 4 -- Wide Tables And Partial Table Height

Product symptom:

- table is clipped horizontally,
- Hancom fits/reflows table into printable area,
- rhwp under-paginates because partial-table pages report too little consumed
  height.

Primary target:

- `accountability_eval`
- staged-source current truth: Hancom 6 pages, rhwp 4 pages
- detailed diagnosis:
  `/Users/jaehoshin/Desktop/mindlogic/factchat/worktree-rhwp-poc/rhwp/work/P3_ACCOUNTABILITY_TABLE_FIT_DIAGNOSIS_2026-06-05.md`
- visuals:
  - `/tmp/diff/accountability_eval/look/page-01.png`
  - `/tmp/diff/accountability_eval/look/page-04.png`
  - `/tmp/diff/accountability_eval/look/page-05.png`
  - `/tmp/diff/accountability_eval/look/page-06.png`
- fitted-source visuals:
  - `/tmp/diff/accountability_eval_fitted/look/page-01.png`
  - `/tmp/diff/accountability_eval_fitted/look/page-05.png`
- fitted-source Hancom-oracle visuals:
  - `/tmp/diff/accountability_eval_fitted_oracle/look/page-01.png`
  - `/tmp/diff/accountability_eval_fitted_oracle/look/page-05.png`
  - `/tmp/diff/accountability_eval_fitted_oracle/look/page-06.png`
  - `/tmp/diff/accountability_eval_fitted_oracle/look/page-11.png`
  - `/tmp/diff/accountability_eval_fitted_oracle/look/page-13.png`

Important caveat:

- the focus manifest's `11/4` target does not match the currently staged
  source. Resolve the source/oracle mismatch before chasing 11 pages.
- upload-time fitter probe scaled 1/1 table with scale `0.6870160847991632`
  and moved rhwp from 4 to 5 pages toward the staged Hancom 6-page oracle.
- fitted output is not production-faithful. A real Hancom rerender of
  `source_fitted.hwpx` produced 11 pages. RHWP initially produced 5 pages; the
  large-rowspan row-wise candidate moves RHWP to 13 pages, preserving later
  logical content but still showing major row/text overlap.
- used-height accounting for intermediate `PartialTable` pages is now repaired:
  fitted pages 1-4 no longer report `used=0.0px`. This improves the validator
  but does not solve the remaining 11-vs-13 visual/text-flow failure.
- trusted table-cell saved line widths now constrain glyph distribution in the
  render path, improving the page 1 horizontal spill. This is a visual
  correction only; the remaining gap is row content-height/page split
  measurement after text composition.

Likely code:

- `src/renderer/layout/table_layout.rs`
- `src/renderer/layout/table_partial.rs`
- `src/renderer/layout/paragraph_layout.rs`
- `src/renderer/height_measurer.rs`
- safer production preprocessor: `server/factchat/utils/hwpx_layout_fitter.py`

Fastest production route:

- prefer upload-time HWPX table fitting for clearly over-wide top-level tables,
  with Hancom reopen/render as the gate.
- keep upload-time fitting only as a possible first-stage mitigation. The
  remaining work is RHWP cell text-flow/width composition after width fit.

Reject:

- shrink every table globally,
- pixel-tune padding before solving width/height flow,
- trust the stale 11-page oracle without the matching source,
- claim success from width fitting: fitted-Hancom is 11 pages while fitted-rhwp
  is 5 pages.

## Pattern 5 -- Cover / Approval Page Anchors

Product symptom:

- cover-page approval/stamp table is too high/low,
- body starts too early,
- final page content is pulled backward.

Known target:

- `05_3781559_medschool_car_2bu_je_plan`
- current staged-source caveat: clean HEAD and current patch both render 3
  pages while cached Hancom PDF is 4 pages. The focus baseline is stale for the
  staged source.
- visuals:
  - `/tmp/diff/05_3781559_medschool_car_2bu_je_plan/look/page-01.png`
  - `/tmp/diff/05_3781559_medschool_car_2bu_je_plan/look/page-04.png`

Structural family:

- page/paragraph-anchored `TOP_AND_BOTTOM` cover tables,
- approval/stamp frames,
- body content that should begin after a reserved cover band.

Action:

- do not patch until the correct original source is restored or regenerated
  through Hancom HWP->HWPX.

## Pattern 6 -- Export / Reopen Fidelity

Product symptom:

- rendered document looks acceptable, but exported file does not reopen
  correctly or loses structure.

Primary gate:

- `hwp-agent-spike/tests/export_roundtrip_probe.mjs`
- `hwp-agent-spike/tests/CORPUS_VALIDATION.md`

Production rule:

- HWPX export/reopen is the viable near-term gate.
- HWP export is unsafe unless document class has reload proof.
- magic bytes are not proof; reopen the exported file in Hancom.

## Long-Run Order

1. Finish P0 fixture/source cleanup enough that gates are meaningful.
2. Land or bank Pattern 1 (`med_02`) using the existing candidate patch.
3. Diagnose Pattern 2 (`wild_02`) but patch only with a clean cross-column
   float discriminator.
4. Move to Pattern 3 (`form_07`) because it is likely broad but still
   structurally testable.
5. Treat Pattern 4 as a preprocessor-vs-renderer design decision before a Rust
   patch.
6. Add export/reopen checks for any document classes touched by renderer fixes.

## Evidence Commands

Target lookup:

```bash
python3 work/fidelity_queue.py
python3 work/fidelity_queue.py --target wild_02_paper_fig_10MB
```

Native build:

```bash
CARGO_BUILD_JOBS=1 docker compose --env-file .env.docker run --rm dev \
  cargo build --release --bin rhwp
```

Broad gate:

```bash
bash harness/gate.sh --no-build
```

Overfit check:

```bash
python3 scripts/check_renderer_overfit.py
```

Visual refresh:

```bash
python3 harness/look.py /tmp/diff/<target> --export
```
