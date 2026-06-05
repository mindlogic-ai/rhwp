# RHWP Fidelity Gap Focus — 2026-06-05

This is the concrete work map for a multi-hour fidelity run. It names the
failure families, the exact documents/pages/images to inspect, the structural
discriminators that make a fix general, and the validation gates that prevent
monkeypatching.

## Rule Of Engagement

Fix families, not files.

Allowed engine discriminators:
- control type: picture, shape, table, paragraph, partial table
- wrap mode: Square, TopAndBottom, BehindText, InFrontOfText
- anchor mode: page, paper, paragraph, column, cell
- treat-as-character and flow-with-text flags
- declared object/table size vs body/column available area
- line-segment vpos reset, spacer, cached height, and next visible block fit
- table repeat-header, row split, nested table, and cell text measurement

Forbidden engine discriminators:
- filename, page slug, title text, body-text sentinel
- a bare page number
- hand-picked paragraph index except inside tests/probes

Every patch needs:
- target visual improvement
- no unrelated page-count regression
- no new overflow
- `python3 scripts/check_renderer_overfit.py`
- visual inspection of every changed document

## P0 — Validation Surface Cleanup

Why first:
- `focus_gate.sh quick` was previously hiding failures behind missing fixtures.
- After staging seven fixtures, the gate is more honest but not yet clean.

Concrete work:
- Find or regenerate the missing `meeting` fixture.
- Replace `05_3781559_medschool_car_2bu_je_plan` with the correct HWPX
  generated from the original HWP through Hancom conversion. The currently
  staged licensed `_doc.hwpx` renders 3 pages while the focus target expects 4.
- Re-run the quick gate on a clean baseline branch with the same staged sources
  before treating restored-doc overflow markers as renderer regressions.

Documents:
- `/tmp/diff/meeting/source.hwpx` is missing.
- `/tmp/diff/05_3781559_medschool_car_2bu_je_plan/source.hwpx` is suspect.
- Fixture manifest: `work/focus_fixture_sources_2026-06-05.tsv`
- Staging helper: `work/stage_focus_fixtures.sh`

Validation:

```bash
bash work/stage_focus_fixtures.sh
bash harness/focus_gate.sh quick --build
```

## P1 — Image / Float Content Loss And Overlap

Why this matters:
- This is the clearest production blocker. Users see hidden content, image/text
  overlap, and missing tables.

### P1a: `med_02____2_4MB`

Status:
- A structural patch exists in `src/renderer/typeset.rs`.
- It groups consecutive page-relative, paper-anchored, full-page scanned-photo
  paragraphs and forces the next visible flow content to the following page.
- Native evidence shows page 3 now contains `실험결과` and the measurement table.
- Fresh 2026-06-05 decision: LAND candidate for this scanned-photo content-loss
  family. Do not deploy yet. `wild_02` and `wc31` remain separate unsolved
  families.

Structural discriminator:
- non-TAC picture/shape
- `textWrap=SQUARE`
- `flowWithText=1`
- `vertRelTo=PAPER`
- `horzRelTo=PAPER|PAGE`
- object covers most of the body area
- following visible flow content exists

Visual artifacts:
- `/tmp/diff/_gallery3/med_02____2_4MB/index.html`
- `/tmp/diff/_gallery3/med_02____2_4MB/page-03.png`
- patched SVG evidence: `/tmp/diff/med_02____2_4MB/rhwp_svg_patch/source_003.svg`

Validation already run:
- native build passed
- targeted unit test passed
- `scripts/check_renderer_overfit.py` passed
- full gate before fixture staging passed with `docs=142 improved=1 regressed=0 new_overflow=0`
- clean split validation passed after removing unfinished `wild_02`/P3 source
  experiments: native release build passed, target look stayed Hancom=6/rhwp=6,
  overfit passed, and broad gate reported
  `docs=151 improved=1 regressed=0 new_overflow=0`

Next decision:
- Keep as LAND candidate for the narrow scanned-photo family. Do not call rhwp
  broadly production-ready; continue with `wild_02` multi-column float diagnosis
  and P2 stale-vpos/table interaction work.

### P1b: `wild_02_paper_fig_10MB`

Why next:
- It tests whether image/float logic generalizes beyond scanned full-page
  photos. It is broader and riskier than `med_02`.

Status:
- Detailed diagnosis: `work/P1_WILD02_FLOAT_DIAGNOSIS_2026-06-05.md`
- Current decision is DIAGNOSE / BANK unless a narrow cross-column
  float-reserve discriminator appears.
- Do not merge this into the `med_02` page-relative scanned-photo rule.

Current dump-pages:
- Hancom: 9 pages
- rhwp: 7 pages
- page 1 has `used=695.4px`, `hwp_used≈435.2px`, `diff=+260.2px`
- later columns show negative drift as content is packed differently

Structural XML:
- Paragraph-relative, column-relative pictures.
- `treatAsChar=0`, `flowWithText=1`, `allowOverlap=0`
- mix of `textWrap=TOP_AND_BOTTOM` and `textWrap=SQUARE`
- pictures are inside flowing text paragraphs rather than standalone
  full-page scanned-image paragraphs.

Visual artifacts:
- `/tmp/diff/_gallery3/wild_02_paper_fig_10MB/index.html`
- `/tmp/diff/_gallery3/wild_02_paper_fig_10MB/page-01.png`
- `/tmp/diff/_gallery3/wild_02_paper_fig_10MB/page-09.png`

Likely fix family:
- float reservation across multi-column text flow
- TopAndBottom object height and paragraph split interaction
- Square wrap zone should affect the column line composer consistently with
  render-time object placement
- specifically investigate column-relative horizontal ranges that cross a
  column boundary or body edge near the top of a multi-column page.

Reject broad fixes that:
- force all TopAndBottom pictures to a new page
- reserve object height twice
- change text-only documents
- improve page count while making multi-column layout visually worse

Validation:

```bash
docker compose --env-file .env.docker run --rm -v /tmp/diff:/diff dev \
  /app/target/release/rhwp dump-pages /diff/wild_02_paper_fig_10MB/source.hwpx
bash harness/focus_gate.sh quick --build
bash harness/gate.sh --no-build
python3 scripts/check_renderer_overfit.py
```

Guard docs:
- `wc47_6pg`
- `wc51_4pg`
- `wc69_9pg`
- `wc04_4pg`
- `wb03_physics_lab_2pg`

## P2 — Stale VPOS / Empty Spacer / Table Forward-Pack

Why this matters:
- These bugs produce page-count drift and misplaced logical content. They are
  high blast-radius because many documents rely on cached line-segment metrics.

### P2a: `form_07_______________41KB`

Current state:
- Hancom: 11 pages
- rhwp: 12 pages
- pages 9-12 contain the visible drift.
- Detailed diagnosis: `work/P2_FORM07_STALE_VPOS_DIAGNOSIS_2026-06-05.md`
- Current decision: BANK for this turn. The defect is real, but the safe patch
  point is same-paragraph/adjacent `TOP_AND_BOTTOM` table anchor packing, not a
  generic empty-paragraph collapse.

Current dump-pages:
- page 9: table `pi=89`, `4x3`, starts at `vpos=31981`
- page 10: continuation table plus empty paragraph `pi=90` at `vpos=64000`
- page 11: two empty paragraphs at `vpos=30957` and `33157`, then table
  `pi=93` starts at `vpos=35357`
- page 12: continuation table starts at page top

Structural XML:
- repeated-header `TOP_AND_BOTTOM` tables
- `treatAsChar=0`, `flowWithText=1`, `allowOverlap=0`
- several table offsets are normal paragraph-relative offsets
- one nearby table has wrapped u32 negative offset (`vertOffset=4294967256`)

Visual artifacts:
- `/tmp/diff/_gallery3/form_07_______________41KB/index.html`
- `/tmp/diff/_gallery3/form_07_______________41KB/page-09.png`
- `/tmp/diff/_gallery3/form_07_______________41KB/page-10.png`
- `/tmp/diff/_gallery3/form_07_______________41KB/page-11.png`
- `/tmp/diff/_gallery3/form_07_______________41KB/page-12.png`

Likely fix family:
- same-paragraph or adjacent `TOP_AND_BOTTOM` table controls with stale/high
  vpos anchors should not manufacture a mostly empty page tail when Hancom
  visually forward-packs the next table under the previous table tail.
- trailing empty spacer paragraphs may be a symptom, but are not the primary
  patch point here.
- repeated-header partial-table continuation must remain stable.

Reject broad fixes that:
- collapse all empty paragraphs
- ignore cached vpos globally
- change cover/title-page spacing
- under-paginate table-heavy forms

Guard docs:
- `form_24_____4MB`
- `form_25__________________6MB`
- `huge_01_DNA________33MB`
- `huge_02_DNA_______75MB`

## P3 — Wide Table Fit / Partial Table Height

Why this matters:
- Government/forms/university templates often declare tables wider than the
  printable area. Hancom fits/reflows them. rhwp often draws literal geometry or
  splits rows with a different height model.

### P3a: `accountability_eval`

Current state:
- Focus manifest says Hancom: 11 pages, rhwp: 4 pages.
- Fresh Hancom conversion of the currently staged
  `/tmp/diff/accountability_eval/source.hwpx` produced 6 pages.
- rhwp renders the same staged source as 4 pages.
- Therefore this is both a real table-fit bug and a validation-source mismatch.
  Do not use the 11-page oracle until the exact expected source is found.
- one huge table dominates the document.
- Detailed diagnosis:
  `work/P3_ACCOUNTABILITY_TABLE_FIT_DIAGNOSIS_2026-06-05.md`

Structural XML:
- one `38x9` table at paragraph 0
- declared width: `78397` HWP units
- body width from dump-pages: about `1046.9px`
- `textWrap=TOP_AND_BOTTOM`
- `repeatHeader=1`
- `treatAsChar=0`, `flowWithText=1`, `allowOverlap=0`
- anchored paragraph-relative/paragraph-relative

Current dump-pages:
- pages 1-3 are `PartialTable` items with `used=0.0px`
- page 4 is final `PartialTable` with `used=297.3px`
- this is a table split/measurement model gap, not just a page-count typo.
- fitted-source dump:
  `/tmp/diff/accountability_eval_fitted_oracle/dump_pages.txt`
- fitted-source RHWP pages 1-4 still report `PartialTable used=0.0px`; page
  5 is the only nonzero page at `used=508.0px`.
- after the used-height accounting patch:
  `/tmp/diff/accountability_eval_fitted_oracle/dump_pages_after_used_height_patch.txt`
- pages 1-5 now report positive used height (`603.9`, `494.0`, `200.7`,
  `251.9`, `508.0` px), but page count remains rhwp 5 vs Hancom 11.

Visual artifacts:
- Dedicated staged-source gallery now exists:
  `/tmp/diff/accountability_eval/look/page-01.png`
  `/tmp/diff/accountability_eval/look/page-02.png`
  `/tmp/diff/accountability_eval/look/page-03.png`
  `/tmp/diff/accountability_eval/look/page-04.png`
  `/tmp/diff/accountability_eval/look/page-05.png`
  `/tmp/diff/accountability_eval/look/page-06.png`
- Related table guard gallery:
  `/tmp/diff/_gallery3/form_25__________________6MB/index.html`
  `/tmp/diff/_gallery3/form_25__________________6MB/page-01.png`
- Fitted-source probe gallery:
  `/tmp/diff/accountability_eval_fitted/look/page-01.png`
  `/tmp/diff/accountability_eval_fitted/look/page-05.png`
- Fitted-source Hancom-oracle gallery:
  `/tmp/diff/accountability_eval_fitted_oracle/look/page-01.png`
  `/tmp/diff/accountability_eval_fitted_oracle/look/page-05.png`
  `/tmp/diff/accountability_eval_fitted_oracle/look/page-06.png`
  `/tmp/diff/accountability_eval_fitted_oracle/look/page-11.png`

Visual read:
- page 1: rhwp clips the right side of the over-wide table instead of fitting
  it into the page like Hancom.
- page 4: rhwp has already consumed content differently and shows a sparse
  tail/next chunk while Hancom still has a denser table page.
- pages 5-6: Hancom still has table content; rhwp has no corresponding pages.

Preprocessor probe:
- `server/factchat/utils/hwpx_layout_fitter.py` scaled 1/1 table.
- scale: `0.6870160847991632`
- output: `/tmp/diff/accountability_eval/source_fitted.hwpx`
- rhwp page count moved from 4 to 5 toward staged Hancom 6.
- width clipping improved, but row/text flow remains visibly poor.
- real Hancom rerender of the fitted HWPX produced 11 pages.
- fitted-oracle tripwire: Hancom 11, rhwp 5.
- pages 6-11 exist in Hancom and are missing from rhwp.
- validator metric was repaired so intermediate partial table pages no longer
  appear as `used=0.0`, but this is not a production rendering fix.

Likely fix family:
- table width fit/reflow should be decided explicitly:
  - production preprocessor for over-wide HWPX tables, or
  - renderer-level table width scaling only under structural constraints.
- partial table row/height measurement must report real consumed height.

Safer production route:
- prefer upload-time HWPX fitting for clearly over-wide top-level tables:
  `server/factchat/utils/hwpx_layout_fitter.py`
- keep fitting as a possible first-stage mitigation only. The current fitted
  HWPX fails the Hancom-fitted vs rhwp-fitted gate.
- next real renderer work is row/cell-cut advancement after width fit:
  RHWP currently consumes too many logical rows/cell fragments per page.

Reject broad fixes that:
- shrink every table globally
- tune cell padding/borders before solving flow/measurement
- change already-correct form docs without side-by-side visual review
- claim success from rhwp-fitted page-count improvement alone
- claim the current preprocessor is enough for production on this family

Guard docs:
- `form_24_____4MB`
- `form_25__________________6MB`
- `large_01_____________16MB`

## P4 — Export / Reopen Fidelity

Why this matters:
- Render fidelity and export fidelity are different product risks.
- Magic bytes do not prove an exported file is usable.

Production gate:
1. original loads in Hancom iframe
2. original loads in hidden rhwp
3. rhwp applies a representative mutation
4. rhwp exports HWPX
5. Hancom iframe reopens the exported HWPX
6. no corruption or visible structural loss

Current rule:
- HWPX export/reopen is the near-term viable path.
- HWP export remains unsafe for large/image-heavy HWPX unless reload is proven
  by document class.

Reference:
- `hwp-agent-spike/tests/export_roundtrip_probe.mjs`
- `hwp-agent-spike/tests/CORPUS_VALIDATION.md`

## Fast Loop For Each Target

1. Open target gallery/image.
2. Run `dump-pages` and identify the first page where `used` diverges from
   `hwp_used` or page count shifts.
3. Extract structural XML for controls on that page.
4. Patch only the shared renderer rule.
5. Native build only.
6. Run quick gate, overfit check, then full gate if improved.
7. Visually inspect every changed document.
8. LAND / BANK / REVERT.

Native commands:

```bash
CARGO_BUILD_JOBS=1 docker compose --env-file .env.docker run --rm dev \
  cargo build --release --bin rhwp

bash harness/focus_gate.sh quick --build
bash harness/gate.sh --no-build
python3 scripts/check_renderer_overfit.py
```

## Recommended Next 4-Hour Plan

Hour 0-1:
- Close P0 fixture cleanup enough that quick-gate results are interpretable.
- If exact `meeting`/`05_3781559` sources are unavailable, mark them excluded
  rather than pretending they are proof.

Hour 1-2:
- Finish the `med_02` P1 LAND/BANK decision.
- Run a visual sweep of changed docs from the full gate.

Hour 2-3:
- Probe `wild_02` without editing first.
- Determine whether its failure is a TopAndBottom reservation bug, Square wrap
  zone bug, or multi-column split bug.
- Bank diagnosis if no clean discriminator appears after three cycles.

Hour 3-4:
- Start `form_07` only after P1 is either landed or banked.
- Keep P2 changes isolated from P1; do not combine them in one patch.

## Production Recommendation

Do not make visible rhwp-only rendering the arbitrary-wild-doc production path
yet. The remaining failures are structural, not just pixel drift:
- image/text overlap and hidden content
- multi-column float/page flow mismatch
- stale cached vpos/page packing drift
- wide-table fitting and partial-table measurement gaps

The production path should remain hybrid:
- Hancom licensed iframe for visible rendering
- rhwp hidden for parse/edit/export
- HWPX export/reopen in Hancom as the safety gate
- rhwp visible rendering improves category by category until the gates are
  boring on wild docs
