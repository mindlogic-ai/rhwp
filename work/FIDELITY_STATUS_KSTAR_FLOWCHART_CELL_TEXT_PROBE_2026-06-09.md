# K-STAR Flowchart Cell Text Probe -- 2026-06-09

Category: `Diagram/table geometry drift`
Status: `probe/rejected-broad-tweak`
Representative: `13_3763367_k_star_visa_track_plan:4`
Guard: `report_form:2`

## Evidence

- Current broad board:
  `/tmp/diff/_review_all_nonlandscape_latest_goal_2026-06-09/index.html`
- Representative page:
  `/tmp/diff/_review_all_nonlandscape_latest_goal_2026-06-09/13_3763367_k_star_visa_track_plan/page-04.png`
- Component probe:
  `/tmp/diff/_probe_kstar_p4_components_goal_2026-06-09/`
- Geometry probe:
  `python3 harness/svg_geometry_probe.py 13_3763367_k_star_visa_track_plan:4`
- Font audit:
  `python3 harness/svg_font_resource_audit.py 13_3763367_k_star_visa_track_plan:4 report_form:2`
- Source probe:
  `python3 harness/hwpx_table_source_probe.py /tmp/diff/13_3763367_k_star_visa_track_plan --table-index 8`

## Classification

This page remains page-count clean and has no images. The visible mismatch is in
the K-STAR flowchart table: RHWP keeps the diagram structure, but table-cell
text and arrow columns are cramped/overlapping compared with Hancom.

Source table `8` is a nested flowchart-like table:

- `rows=3`, `cols=13`, `textWrap=TOP_AND_BOTTOM`, `pageBreak=CELL`,
  `repeatHeader=1`
- narrow spacer/arrow columns contain `▶`
- content columns have explicit widths and in-cell margins
- lineSeg arrays are absent for the relevant cells, so cell text is recomposed

This makes the issue a `diagram/table geometry + table-cell text wrapping`
probe, not a missing-image or page-count bug.

## Probe Results

Component probe results on the representative:

- `base=21.87`
- `hide_text=14.75`
- `hide_lines=15.65`
- `font_size_x0.90=20.44`
- common font substitutions did not solve it (`21.93..22.86` range for tested
  substitutions)
- stroke variants did not solve it and mostly regressed
- image variants are no-ops because the page has no images
- line-advance normalization is effectively neutral (`21.80..21.84`)

Guard page `report_form:2` is affected by the same broad text/font levers:

- `base=12.63`
- `font_size_x0.90=12.25`
- `thin_stroke_x0.50=11.92`
- `text_y_m4=12.12`

Those guard movements are not proof of correctness; they show the proposed
levers are broad renderer-wide visual tuning, not a narrow K-STAR flowchart
rule.

Font-resource audit is not the blocker for this page. Major fonts resolve to
bundled resources:

- `휴먼명조` -> `NanumMyeongjo-Regular.woff2`
- `HY중고딕` -> `NotoSansKR-Regular.woff2`
- `Noto Sans KR` -> `NotoSansKR-Regular.woff2`

## Decision

Do not patch the renderer from this probe. A safe future patch would need a
structural invariant for nested flowchart tables, probably around cell text
composition/clipping/wrapping inside narrow arrow-separated table columns, plus
at least one guard table proving unrelated dense tables do not regress.

Rejected for now:

- global font-size reduction;
- global stroke/rule thinning or thickening;
- global font substitution;
- broad y-shifts or line-advance normalization.
