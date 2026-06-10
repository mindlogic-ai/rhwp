# RHWP Fidelity Fast Loop Plan — 2026-06-05

Purpose: drive a multi-hour renderer-fidelity run without random cycling.
Use this when the goal is to improve visible rhwp render fidelity against
Hancom oracle output while avoiding fixture monkeypatches and regressions.

Current state:
- Old gallery: `/tmp/diff/_gallery3` is stale and can make bottom content look
  truncated. Do not use it as current visual authority.
- Current visual authority: regenerate a two-column non-cropping board with
  `harness/review_gallery.py`; it records git HEAD/dirty state and links raw
  full-height PNG strips.
- Existing gate state: `harness/gate.sh` and `harness/baseline_pc.tsv`.
- Latest handoff: `work/START_HERE_2026-06-04_NEXT.md`.
- Concrete queue: `work/fidelity_target_queue_2026-06-05.tsv`.
- Do not deploy or push unless explicitly told.

## Fastest Loop

Use native Rust validation first. Do not rebuild WASM/studio per hypothesis.

1. Pick one failure family and one target page.
2. Inspect the fresh Hancom/RHWP review-gallery image and current dump output.
3. Instrument only enough to identify the structural class.
4. Patch the shared renderer rule, not a document name/text.
5. Native build:
   `CARGO_BUILD_JOBS=1 docker compose --env-file .env.docker run --rm dev cargo build --release --bin rhwp`
6. Rerender/hash gate:
   `bash harness/gate.sh --no-build`
7. Anti-overfit:
   `python3 scripts/check_renderer_overfit.py`
8. Visual check every changed doc, not only the target. If a preview looks
   bottom-clipped, inspect the raw PNG dimensions before changing renderer code.
9. Commit only if: target improves, no new page-count regression, no new overflow,
   changed-doc visual sweep is acceptable.

If a hypothesis needs more than 3 build/probe cycles without a clean
structural discriminator, bank the diagnosis and move to the next family.

## Anti-Monkeypatch Rules

Allowed renderer conditions:
- control type, text-wrap mode, treat-as-character flag
- line segment shape, vpos reset, paragraph/cell geometry
- table row/cell dimensions, repeated-header flags
- object anchor mode, relative-to page/paragraph/cell
- measured-vs-declared object extents
- page/body/column available geometry

Forbidden renderer conditions:
- document filename
- body text sentinels
- exact title strings
- page number only without a structural geometry condition
- hardcoded fixture-specific paragraph indices unless confined to tests/probes

Tests may assert text/page invariants. Engine code may not branch on them.

## Priority 1 — Image / Float Pagination And Overlap

Why first: this is the most visible production blocker. Users immediately see
image/text overlap, hidden content, or clipped figures. The latest handoff also
names one remaining content-loss bug in this family.

Targets:
- `wild_02_paper_fig_10MB/page-01.png`
  - Symptom: large figure/text overlap and wrong page flow.
  - Page count: Hancom 9, ours 7.
  - Product impact: hard no for visible production.
- `med_02____2_4MB/page-03`
  - Symptom from handoff: "실험결과" table invisible behind full-page scanned
    photo floats; Hancom paginates one photo/page plus table on p3.
  - Product impact: content loss.
- Guard docs:
  - `wc47_6pg` (full-width Square reserve family)
  - `wc51_4pg`
  - `wc69_9pg`
  - `wc04_4pg`
  - `wb03_physics_lab_2pg`

Likely code:
- `src/renderer/typeset.rs`
- `src/renderer/layout/picture_footnote.rs`
- `src/renderer/layout/shape_layout.rs`
- `src/renderer/height_measurer.rs`
- `src/renderer/float_placement.rs`

Probe questions:
- Is the object non-inline or TAC?
- Is it `Square`, `TopAndBottom`, `BehindText`, or `InFrontOfText`?
- Is it page-relative, paragraph-relative, or cell-relative?
- Does pagination reserve the same visual extent that render paints?
- For near-full-page floats, does Hancom effectively force one object per page?

Candidate structural fix shape:
- If a non-inline or TAC picture/shape has visual extent near body/page height
  and would cover the following flow content, page-reserve/defer it as a block
  rather than allowing following table/text to render behind it.

Reject if:
- A broad reserve rule over-paginates currently-correct image docs.
- The fix changes text-only docs.
- The only discriminator is a filename/page/text.

Acceptance:
- Target content no longer overlaps/disappears.
- Page count moves toward Hancom without hurting guard docs.
- Byte/hash diff is limited to float-heavy docs or visually verified.

## Priority 2 — Stale Cache / VPOS / Empty Spacer Forward-Pack

Why second: this causes cumulative page drift, but it is high-blast because
many correct docs depend on cached line segments.

Targets:
- `form_07_______________41KB/pages 9-12`
  - Known diagnosis: rhwp trusts empty spacer para vpos near page bottom and
    wastes p10; Hancom packs the next table onto p10.
- `wc15_7pg`
- `wc16_6pg`
- `wc17_6pg`
- `wc31_17pg`
- `wc14_13pg`
- `wc35_15pg residual`

Likely code:
- `src/renderer/typeset.rs`
- `src/renderer/layout/paragraph_layout.rs`
- `src/renderer/height_cursor.rs`

Probe questions:
- Is the paragraph empty and control-free?
- Does cached `vpos` jump to/near page bottom?
- Does the next visible block fit if the spacer jump is discounted?
- Does the oracle show the next block forward-packed?
- Is this at page top, page middle, or after a table/float?

Candidate structural fix shape:
- Collapse or discount trailing empty spacer paragraphs only when:
  1. they have no visible text/control,
  2. their cached vpos jump would force a mostly-empty page tail,
  3. the following visible block/table fits the current page body,
  4. there is no page/section/column break control,
  5. visual oracle shows forward packing for this structural class.

Reject if:
- It changes known-correct cached-line docs broadly.
- It fixes over-pagination while creating under-pagination elsewhere.
- It touches report/form table-host-spacing without a narrow discriminator.

Acceptance:
- `form_07` p10 includes the next table as Hancom does.
- No regression in `form_24`, `form_25`, `huge_01`, `huge_02`, and SNU guards.

## Priority 3 — Wide Table Fit / Table Height Model

Why third: important for forms, but some of it is a feature gap better handled
by preprocessing for production.

Targets:
- `accountability_eval`
  - Hancom 11, ours 4. Severe wide-table fit/re-wrap gap.
- `large_01_____________16MB`
  - High-blast cell-height/cache divergence.
- `form_25__________________6MB/page-01.png`
  - Page count matches, but table geometry differs visibly.

Likely code:
- `src/renderer/height_measurer.rs`
- `src/renderer/layout/table_layout.rs`
- `src/renderer/layout/table_partial.rs`
- FactChat preprocessor: `server/factchat/utils/hwpx_layout_fitter.py`

Plan:
- For production, prefer upload-time HWPX fitting for over-wide tables before
  changing core table layout.
- In rhwp, only patch table height when the rule is structural and measured:
  nested table/picture extent, cell padding defense, repeated-header split, or
  declared-vs-actual row floor.

Reject if:
- The patch tries to pixel-tune border weight/spacing before flow bugs.
- It shrinks all tables globally.
- It changes large correct form docs without visual review.

Acceptance:
- Severe under-pagination improves without breaking form_24/form_25/large docs.
- For preprocessor route, Hancom reopen/render must be part of the gate.

## Priority 4 — Export / Reopen Fidelity Gate

This is separate from visible rhwp rendering and is required for the hybrid
architecture.

Known state from `hwp-agent-spike/tests/CORPUS_VALIDATION.md`:
- HWPX export/reload is viable in tested hard/stress cases.
- HWP export/reload is unsafe for large/image-heavy HWPX even when OLE magic is
  valid.

Gate:
1. Original loads in Hancom iframe.
2. Original loads in hidden rhwp.
3. rhwp applies a representative mutation.
4. rhwp exports HWPX.
5. Hancom iframe reopens exported HWPX.
6. Visual/no-corruption check passes.
7. HWP export is enabled only for doc classes where exported HWP reloads.

Do not use magic bytes as proof. Reload the exported file.

## Category Queue

Run in this order:

1. `med_02____2_4MB` p3 or `wild_02_paper_fig_10MB` p1.
   Goal: fix one structural image/float content-loss/overlap class.
2. `form_07_______________41KB` p9-p12.
   Goal: prove or reject narrow stale-empty-spacer forward-pack.
3. `accountability_eval`.
   Goal: decide engine feature vs HWPX preprocessor; do not brute-force in
   table layout without a feature design.
4. Export/reopen probe on the docs affected by 1-3.

Stop conditions per target:
- Land if target improves and full gate is clean.
- Bank if high-blast or no discriminator after 3 cycles.
- Revert if any unrelated green doc regresses visually or by page count.

## Land / Bank / Revert Checklist

Before keeping any renderer patch, fill this in for the target:

```
Target:
Family:
Structural discriminator:
Files changed:

Before:
- oracle pages:
- rhwp pages:
- visible defect:

After:
- rhwp pages:
- visible defect:
- changed-doc list:

Validation:
- native build:
- focus gate:
- full gate:
- overfit check:
- visual checked docs:
- new overflow:
- known residual:

Decision:
- LAND / BANK / REVERT
- reason:
```

Decision rules:

- **LAND** only when the target improves, changed docs are visually checked, the
  full gate has zero regression/new overflow, and `check_renderer_overfit.py`
  passes.
- **BANK** when the mechanism is real but high-blast, or when 3 cycles fail to
  find a safe structural discriminator. Preserve the exact probe evidence in
  `work/`.
- **REVERT** on any unrelated page-count regression, new overflow, content loss,
  or document-specific branch in renderer code.

Fast changed-doc visual check:

1. Run `bash harness/gate.sh --no-build`.
2. Compare `/tmp/diff/harness/_gate_now.tsv` with baseline for page-count moves.
3. If render hash tooling is used, inspect every changed hash document.
4. For every changed doc, open the gallery/diff page and verify:
   - same logical content on same page,
   - no image/text/table overlap,
   - no disappeared table/image/text,
   - page boundary moved in the intended direction.

If a page-count match improves but a visual page becomes worse, it is a
regression. Do not let the numeric gate overrule the visual side-by-side.

## Production Readiness Reading

Visible rhwp-only production is not the near-term target. The gallery proves
readability and major progress, but not Hancom-grade visual fidelity for wild
documents. The production path should remain:

- rhwp hidden for structured agent read/mutate;
- Hancom licensed iframe for visible render/save;
- HWPX export/reopen gate as the product-critical validation.
