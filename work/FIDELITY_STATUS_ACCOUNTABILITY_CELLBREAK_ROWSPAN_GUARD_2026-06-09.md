# Accountability CellBreak Rowspan Guard -- 2026-06-09

Category: `CellBreak carried rowspan / table raster`
Status: `guard-only/rejected-patch`
Representative: `accountability_eval:4`

## Evidence

- Fresh focused board: `/tmp/diff/_review_accountability_p4_refresh_2026-06-09/index.html`
- Page strip: `/tmp/diff/_review_accountability_p4_refresh_2026-06-09/accountability_eval/page-004.png`
- Canonical refreshed board/export: `/tmp/diff/_review_accountability_canonical_refresh_2026-06-09/index.html`
- Dump: `/tmp/diff/accountability_eval/dump_pages_cellbreak_current_2026-06-09.txt`
- Table drift stderr: `/tmp/diff/accountability_eval/table_drift_cellbreak_current_2026-06-09.stderr`

## Current Classification

This is not currently a missing-fragment bug. The older queue note said RHWP
stopped near `y=626.8` while Hancom had a lower continuation strip, but the
current render reaches the same bottom area:

- Hancom raster bands: `58.4..658.5`, then lower strip `688.9..735.3`
- RHWP raster band: `56.7..733.0`
- SVG horizontal table lines include top `56.7` and bottom `735.7`
- `dump-pages` page 4 is `PartialTable rows=21..28`, `used=679.0px`

The remaining mismatch is wide landscape table visual fidelity: row-height
distribution, lighter/smaller text, and table-rule raster density. It is not a
clean semantic drift, missing image, or missing CellBreak fragment.

## Probe Results

Boundary probe:

- Hancom has an internal lower strip split around `657.7`, `688.9`, and `734.5`
- RHWP draws one continuous final table band down to `735.7`
- RHWP line gaps differ from Hancom, but the fragment is present

Component probe:

- base `17.59`
- hide text `12.88`
- hide lines `12.65`
- font-size `x0.90` improves only to `16.68`
- common font substitutions improve only modestly (`16.97..17.04`)
- stroke, image, crop, and regional y-shift variants do not provide a structural fix

## Decision

No renderer patch for this category in the current pass.

Reasons:

- the original structural miss is no longer reproduced on current code;
- the remaining mismatch is visual/raster distribution on a landscape table;
- the user explicitly deprioritized wide landscape pages;
- broad font-size, font-family, stroke, and y-shift tweaks are rejected by the
  production gate.

Keep `accountability_eval:4` as a guard page for future table-fragment changes,
but do not use it as the next patch source unless a new structural invariant
appears in a non-landscape guard set.
