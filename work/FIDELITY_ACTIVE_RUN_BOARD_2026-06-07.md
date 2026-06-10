# RHWP Fidelity Active Run Board -- 2026-06-07

This board records the current evidence-backed fastest path for a long fidelity
run. It is intentionally category based: fix one structural family, prove it on
one target, then gate the corpus before moving on.

## Current Verified State

Current focus gate:

```text
bash harness/gate.sh --no-build
[gate] docs=9 improved=0 regressed=0 new_overflow=0
```

Generated status artifacts:

- `work/FIDELITY_CATEGORY_STATUS_2026-06-07.md`
  - source/oracle availability and current RHWP page-count status.
- `work/FIDELITY_VISUAL_STATUS_2026-06-07.md`
  - focused no-crop gallery status for the currently renderable visual targets.
  - includes worst visual page and mean pixel diff for each focused document.

Freshly checked focused galleries:

- `/tmp/diff/_review_overseas_font_weight/index.html`
  - `overseas_training`: 4 RHWP pages, no review truncation.
  - Structural fix is good: page 4 now includes the trailing checklist title
    before the checklist table.
  - Remaining drift: font fallback/weight and table stroke darkness.
- `/tmp/diff/_review_accountability_current_2026-06-07/index.html`
  - `accountability_eval`: 6 RHWP pages, matching the staged Hancom oracle.
  - Remaining drift: table scale/font metrics, not a current page-count block.
- `/tmp/diff/_review_15_current_2026-06-07/index.html`
  - `15_3740450_research_admin_innovation_meeting_template`: 5 RHWP pages,
    matching Hancom.
  - Remaining drift: embedded image/table scale and some vertical spacing.

Current visual metric ranking from `work/FIDELITY_VISUAL_STATUS_2026-06-07.md`:

```text
15_3740450_research_admin_innovation_meeting_template  page 3  mean diff 56.65
overseas_training                                      page 1  mean diff 30.46
accountability_eval                                    page 4  mean diff 21.04
```

Interpretation: after page-count blockers, the highest-value renderable visual
target is doc 15 page 3, where picture/table-cell geometry differs materially
from Hancom. This is not a gallery truncation issue.

Freshly checked tests/gates from the active patch set:

```text
docker compose --env-file .env.docker run --rm dev cargo fmt --check
docker compose --env-file .env.docker run --rm dev cargo test --lib test_medium_weight_face -j 1
docker compose --env-file .env.docker run --rm dev cargo test --lib renderer::typeset::tests -j 1
python3 scripts/check_renderer_overfit.py
bash harness/gate.sh --no-build
```

Results: formatting passed, targeted font test passed, typeset tests passed
`23 passed`, overfit passed with 8 known baseline findings, and gate passed.

## Fastest Loop

0. Refresh the category map from current local evidence:

   ```bash
   python3 harness/fidelity_category_status.py \
     --out work/FIDELITY_CATEGORY_STATUS_2026-06-07.md
   ```

   For visual targets:

   ```bash
   python3 harness/fidelity_category_status.py --with-gallery \
     --out work/FIDELITY_VISUAL_STATUS_2026-06-07.md \
     overseas_training accountability_eval 15_3740450_research_admin_innovation_meeting_template
   ```

1. Pick one category and one first-divergent page from the refreshed status,
   not from stale `_hancom_pages.json` rows.
2. Regenerate a no-crop focused board if the status did not already do it:

   ```bash
   python3 harness/review_gallery.py /tmp/diff/_review_<name> <doc> --export-current
   python3 harness/audit_review_gallery.py /tmp/diff/_review_<name>
   ```

3. Dump the current render tree or page split:

   ```bash
   docker compose --env-file .env.docker run --rm -v /tmp/diff:/diff dev \
     /app/target/release/rhwp dump-pages /diff/<doc>/source.hwpx
   ```

4. Patch only a structural renderer rule: control type, wrap mode, anchor mode,
   table geometry, line segment geometry, font face/weight class, or measured
   layout relationships.
5. Add a focused regression for the structural invariant.
6. Accept only after focused visual review, focused test, overfit check, and
   `harness/gate.sh --no-build`.

Forbidden renderer discriminators:

- document filename
- title/body text sentinel
- page number alone
- fixture-specific paragraph/control index outside tests or diagnostics

## Category Queue

### P1: Multi-column floating figure under-pagination

Target:

- `wild_02_paper_fig_10MB`
- Oracle/current from cached evidence: Hancom 9 / RHWP 7.
- First known divergence: Hancom pushes the final page-1 intro tail to page 2,
  while RHWP keeps that tail on page 1.

Current blocker:

- `/tmp/diff/wild_02_paper_fig_10MB/source.hwpx` is missing in the current
  `/tmp/diff` staging area. Cached artifacts exist, but the source must be
  restored before another trustworthy rerender/probe cycle.

Next action:

1. Restore the exact `wild_02_paper_fig_10MB` source into
   `/tmp/diff/wild_02_paper_fig_10MB/source.hwpx`.
2. Regenerate:

   ```bash
   python3 harness/review_gallery.py /tmp/diff/_review_wild_02_current_2026-06-07 \
     wild_02_paper_fig_10MB --export-current
   ```

3. Continue from the known first divergence in `work/P1_WILD02_FLOAT_DIAGNOSIS_2026-06-05.md`.

Patch only if the discriminator is structural:

- non-TAC picture/shape
- `TopAndBottom` or `Square`
- `flowWithText=1`
- `allowOverlap=0`
- paragraph-relative vertical anchor
- column-relative horizontal anchor
- multi-column page/paragraph
- horizontal range crosses or obstructs another column near the top of flow

Reject broad fixes that globally page-break `TopAndBottom` objects or reserve
all floating object height twice.

### P2: Table split and trailing host text

Targets:

- `overseas_training`
- `meeting_summary`
- related large TAC table documents

Current state:

- `overseas_training`: structurally improved. The split itinerary table no
  longer loses the following host paragraph title; page 4 now begins with the
  checklist title and table.
- `meeting_summary`: current gate has no new overflow/regression.

Remaining work:

- font fallback/metrics for missing Korean fonts
- table border stroke fidelity
- avoid changing pagination unless a fresh visual shows wrong-page content

Fast validation:

```bash
python3 harness/review_gallery.py /tmp/diff/_review_overseas_current overseas_training --export-current
python3 harness/audit_review_gallery.py /tmp/diff/_review_overseas_current
docker compose --env-file .env.docker run --rm dev cargo test --lib renderer::typeset::tests -j 1
```

### P3: Wide table fit and row/page height

Target:

- `accountability_eval`

Current state:

- Current staged source renders 6 RHWP pages, matching staged Hancom.
- No-crop review passes.
- The old 11-page target belongs to the fitted-source Hancom-rerender lane, not
  the current staged source.

Remaining work:

- visual scale/row text metrics
- fitted-source export/reopen validation
- avoid treating the upload-time fitter as a renderer fix unless Hancom-rerender
  and RHWP both converge on the same source

Fast validation:

```bash
docker compose --env-file .env.docker run --rm -v /tmp/diff:/diff dev \
  /app/target/release/rhwp dump-pages /diff/accountability_eval/source.hwpx
python3 harness/review_gallery.py /tmp/diff/_review_accountability_current accountability_eval --export-current
```

### P4: Embedded image/table scale and vertical spacing

Target:

- `15_3740450_research_admin_innovation_meeting_template`

Current state:

- Fresh dump-pages reports 5 RHWP pages, matching Hancom.
- No-crop review passes.
- Page 4 is structurally close, but embedded images/tables are scaled and
  vertically positioned differently from Hancom.
- Visual metric identifies page 3 as the worst current focused visual drift
  (`mean diff 56.65`): image grids inside tables have large blank bands,
  different image cropping/placement, and lower table content appears in a
  different grid position than Hancom.

Likely owners:

- image sizing/cropping in SVG renderer
- table/image cell content scale
- font fallback/metrics

This is visual-polish work, not the next page-count blocker. The next concrete
patch attempt should inspect image controls inside table cells on page 3 and
prove a geometry invariant such as image top/bottom staying within the owning
cell without introducing blank vertical bands.

Fresh page-3 geometry probe:

- SVG: `/tmp/diff/15_3740450_research_admin_innovation_meeting_template/rhwp_svg_cur/source_003.svg`
- Worst obvious anomaly: `image 3` is emitted at `y=-29.3` while the lower
  image-table cells begin around `y=422.4`.
- Dump evidence around page-3 source controls:
  - paragraph `0.21` contains a `4x2` table with cell pictures.
  - several pictures are non-TAC `TopAndBottom` inside cells.
  - some vertical offsets are wrapped unsigned negatives, e.g.
    `vert=Para(off=4294950285)` and `vert=Para(off=4294967240)`.

Hypothesis for next patch: table-cell picture placement is treating wrapped
negative paragraph-relative offsets as absolute page/paragraph placement in a
way that lets a cell-owned image escape above its owning cell. The structural
rule should normalize/clamp signed offsets for non-TAC cell pictures relative
to the cell content box, and the regression should assert image bounds stay
within the owning cell/table area. Do not branch on this document name or the
meeting/photo text.

Probe result:

- Patched the full-table non-inline picture path in
  `src/renderer/layout/table_layout.rs` to route through
  `layout_picture_full(..., clamp_to_container_top=true)` instead of
  precomputing an already-offset position and then calling `layout_picture`.
- The escaped image moved from `y=-29.3` to `y=424.3`, so the lower photo grid
  is now populated instead of leaving the first lower image clipped off page.
- Page count remains clean: 5/5 for doc 15, and `harness/gate.sh --no-build`
  reports no regressions or new overflow.
- The aggregate page-3 metric is still high (`56.78`, previous `56.65`)
  because remaining drift is dominated by table/image scale and crop placement,
  especially the top photo table. Treat this as a partial structural image
  bounds fix, not a completed P4 visual-fidelity fix.

### P5: Export/reopen fidelity

Required before production claims:

1. Export edited HWPX from the active path.
2. Reopen through Hancom/licensed lane.
3. Reopen through RHWP.
4. Compare:
   - page count
   - table row/cell count
   - image count and bounding boxes
   - text extraction around edited regions
   - visible page screenshots

This is separate from renderer-only fidelity. Renderer improvements can pass
while export/reopen still corrupts geometry or unsupported XML.

## Current Production Readiness Read

Not production-ready as a full Hancom replacement.

Reasonable for controlled preview/editor workflows only if we keep the licensed
Hancom/oracle lane available for high-fidelity preview/export verification.
The renderer has made structural progress on page counts, table continuation,
and missing text, but the remaining failures are real: multi-column floats,
font metrics, stroke fidelity, embedded image scale, and export/reopen proof.
