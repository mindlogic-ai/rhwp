# Research Admin Photo Grid P2 Probe -- 2026-06-09

Category: `Photo-grid / pre-grid`
Status: `guard-only/probe-no-patch`
Representative: `15_3740450_research_admin_innovation_meeting_template:2`

## Evidence

- Fresh focused board: `/tmp/diff/_review_research_admin_photo_grid_p2_refresh_2026-06-09/index.html`
- Page artifact: `/tmp/diff/_review_research_admin_photo_grid_p2_refresh_2026-06-09/15_3740450_research_admin_innovation_meeting_template/page-002.png`
- Component probe: `/tmp/diff/_probe_research_admin_p2_components_2026-06-09/15_3740450_research_admin_innovation_meeting_template_p2/`
- Review audit passed: `python3 harness/audit_review_gallery.py /tmp/diff/_review_research_admin_photo_grid_p2_refresh_2026-06-09`

## Classification

This is not a page-count or missing-image failure. The current render keeps the
representative document at `5/5` pages and all three page-2 images are present.
The remaining mismatch is a mixed visual-fidelity issue:

- table/header rows start slightly high compared with Hancom;
- text/rule density differs;
- lower photo-table composition is locally offset, but not absent or split.

Geometry probes showed the lower table top/header bands are about 14 px earlier
than Hancom while the table bottom remains close. Image ink probes showed all
expected raster regions are present.

## Source Notes

The relevant lower photo table is source table index `4`:

- `rows=4`, `cols=2`, `textWrap=TOP_AND_BOTTOM`, `pageBreak=CELL`,
  `repeatHeader=1`
- row 2 / col 0 picture carries a large para-relative vertical offset
  (`-17011` HU, about `-226.8px`)
- the other lower-table pictures have zero or tiny offsets

That offset explains why this area is risky, but current rendering does not
provide a safe structural rule. A broad "move table images down" or "clamp cell
image top" patch would be visual tuning, not a renderer contract.

## Rejected Tweaks

The component probe did not find an acceptable structural owner:

- `base=20.68`
- `hide_text=17.65`, confirming text contributes, but not a layout fix
- `hide_lines=40.54`, worse; table/rule structure is required
- `clamp_cell_image_top=20.68`, no improvement
- `font_size_x0.90=20.08`, only a broad font-size tweak
- `image_y_p6=19.99`, small scalar improvement but too broad/non-structural
- image height, crop shift, image filters, stroke, and regional y-shifts either
  regressed or did not materially improve

## Decision

Keep this category as a visual guard/probe. Do not patch the renderer from this
page unless a future probe identifies a reusable structural rule for table-cell
picture offsets or table row height distribution with guard coverage.
