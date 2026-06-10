# RHWP Fidelity Status -- Natural Science Agenda Cover Probe -- 2026-06-09

## Status

- Category: semantic/layout drift, agenda cover shape/table geometry.
- Row status: probe / partial TextBox improvement / blocked-layout.
- Representative: `09_3766093_natural_sci_planning_committee_260527:1`.
- Related high-drift pages sampled: `09...:17`, `09...:22`, `09...:49`.
- Current clean focused board:
  `/tmp/diff/_review_09_current_probe_clean_2026-06-09/index.html`.

## Current Result

The current export is page-count clean:

- Hancom: `51`
- RHWP current: `51`
- Focused board audit passes:
  `python3 harness/audit_review_gallery.py /tmp/diff/_review_09_current_probe_clean_2026-06-09`

Page 1 is still visually wrong. Hancom shows a clean agenda cover with separated
agenda boxes and the school footer. RHWP overlaps the agenda rows and label
bands; the `논의사항`/`보고사항` sections drift upward and collide with the
preceding agenda content.

One narrow TextBox vertical-centering candidate is retained as a probe
improvement: when a `drawText` box has `vertAlign=CENTER` but its nested
paragraphs have no saved lineSegs, RHWP now falls back to composed line metrics
for the content height instead of treating the content height as zero. This
improves the title/date region, but does not promote the category because the
agenda body still overlaps.

## Evidence

`svg_geometry_probe.py` on page 1 shows no image owner. The issue is shape/table
and text-band placement:

- Hancom raster continues with separated bands through `y=966.6..989.0`.
- RHWP raster has the agenda/title content compressed and overlapping through
  `y=717.4..752.5`.
- The focused visual board confirms the overlap is visible to a human reviewer.

`dump_pages_current.txt` for page 1 contains the agenda cover material plus the
agenda table objects:

- `Shape pi=4/5/6/7` with `wrap=InFrontOfText`
- `Table pi=9 ci=1 1x1 wrap=TopAndBottom tac=true`
- `PartialTable pi=10 ci=0 rows=0..8 cont=false 8x2`

The active render path is the `typeset.rs` paginator plus the render-tree layout
passes, not the legacy `pagination/engine.rs` path. Rejected candidates:

- An engine-only candidate was rejected because it had no effect on the SVG
  export path.
- A no-lineSeg `InFrontOfText` TextBox flow-reservation candidate compiled and
  rendered, but produced the same page-1 overlap; it was removed.
- A no-lineSeg full-width TAC stack candidate was rejected because the spill is
  not owned by the empty-runs TAC branch; the active failure is in the
  non-empty inline TAC/text run path where top-level parser text and TAC
  background boxes share a line.

## Related Probe Notes

- Page 17 is mainly dense table/text raster: `휴먼명조`/table lines, no image
  owner.
- Page 49 has one image aligned closely with Hancom; remaining drift is text and
  label/table geometry rather than missing raster content.
- Page 22 includes off-page table geometry and missing-office-face
  `휴먼둥근헤드라인`, so it belongs partly to the residual Office/HY/Hancom font
  resource bucket.

## Next Patch Shape

Do not patch this with global y-shifts, font scaling, or broad table spacing.
The likely target is the inline TAC/text run geometry path for agenda cover
paragraphs whose source HWPX has no lineSegs and embeds full-width TAC rectangle
backgrounds plus `InFrontOfText` label rectangles:

- preserve paragraph-origin anchors for `InFrontOfText` label rectangles;
- keep agenda label boxes aligned to the saved paragraph starts;
- avoid advancing full-width TAC rectangle backgrounds horizontally into the
  next agenda row when the following text belongs inside the next row;
- guard with page 1 absence/position of overlapping agenda body text and page
  count `51/51`.

This needs a render-tree/SVG geometry invariant before promotion.

## Validation

- `git diff --check -- src/renderer/layout/shape_layout.rs src/renderer/typeset.rs`
- `docker compose --env-file .env.docker run --rm dev cargo build --release --bin rhwp -j 1`
- `python3 harness/review_gallery.py --export-current /tmp/diff/_review_09_current_probe_clean_2026-06-09 09_3766093_natural_sci_planning_committee_260527 report_form form_01_교수법_과제양식_코다이_49KB`
- `python3 harness/audit_review_gallery.py /tmp/diff/_review_09_current_probe_clean_2026-06-09`
- `python3 harness/svg_geometry_probe.py 09_3766093_natural_sci_planning_committee_260527:1`
