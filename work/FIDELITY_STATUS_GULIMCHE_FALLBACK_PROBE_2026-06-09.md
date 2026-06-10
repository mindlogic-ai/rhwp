# GulimChe Fallback Probe -- 2026-06-09

Category: `Text/raster fidelity`
Status: `probe/blocked-font-resource/rejected-broad-substitution`
Representative: `04_3781571_car_2bu_je_notice:2`
Visual guard: `03_3781727_staff_evaluation_table:1`
Metric guard: `report_form:2`

## Evidence

- Current broad board:
  `/tmp/diff/_review_all_nonlandscape_latest_goal_2026-06-09/index.html`
- Representative pages:
  - `/tmp/diff/_review_all_nonlandscape_latest_goal_2026-06-09/04_3781571_car_2bu_je_notice/page-01.png`
  - `/tmp/diff/_review_all_nonlandscape_latest_goal_2026-06-09/04_3781571_car_2bu_je_notice/page-02.png`
- Component probe:
  `/tmp/diff/_probe_car_notice_p2_components_goal_2026-06-09/`
- Geometry probe:
  `python3 harness/svg_geometry_probe.py 04_3781571_car_2bu_je_notice:1 04_3781571_car_2bu_je_notice:2`
- Source table probe:
  `python3 harness/hwpx_table_source_probe.py /tmp/diff/04_3781571_car_2bu_je_notice --list`
- Font audit:
  `python3 harness/svg_font_resource_audit.py 04_3781571_car_2bu_je_notice:1 04_3781571_car_2bu_je_notice:2 report_form:2`

## Classification

This document is page-count clean (`2/2`) and images/logos are present. The
main visible mismatch is text/raster density and fallback identity: most body
text is emitted as `굴림체`, which the current web font registration maps to
`fonts/D2Coding-Regular.woff2`.

Current corpus audit shows `굴림체` is not widespread but is concentrated:

- `04_3781571_car_2bu_je_notice:1`: 586 runs -> D2Coding
- `04_3781571_car_2bu_je_notice:2`: 400 runs -> D2Coding
- `05_3781559_medschool_car_2bu_je_plan:1`: 98 runs -> D2Coding
- `09_3766093_natural_sci_planning_committee_260527:2`: 374 runs -> D2Coding
- corpus summary: `굴림체` 1458 runs across 4 pages

The representative page also has a gray notice table/box where RHWP follows the
stored SVG/table height more heavily than the Hancom raster appears to. This is
not enough for a structural table-height patch because the page remains
semantically correct and the probe is dominated by text/font appearance.

## Probe Results

Representative `04_3781571_car_2bu_je_notice:2`:

- `base=8.91`
- `hide_text=5.11`
- `hide_lines=6.13`
- `font_AppleGothic=8.41`
- `font_Pretendard=8.49`
- `font_Nanum_Gothic=8.64`
- `font_Noto_Sans_KR=8.84`
- `font_size_x0.90=8.24`
- stroke variants are neutral or worse
- page-region y-shift after 430px (`shift_y_after_430_p12=7.92`) is a broad
  coordinate tweak and not a renderer rule

Guard `report_form:2` reacts to the same broad knobs:

- `base=12.63`
- `font_AppleGothic=12.34`
- `font_Pretendard=12.45`
- `font_size_x0.90=12.25`
- `thin_stroke_x0.50=11.92`

These broad movements do not prove Hancom parity and would alter unrelated
documents.

## Decision

Do not change the renderer or global `굴림체` mapping from this probe.

Future promotion would need one of:

- an exact redistributable Gulim/GulimChe-compatible web resource and license;
- an explicit product fallback policy that accepts a non-exact substitute,
  validated against the concentrated `굴림체` pages and clean guards;
- a narrow structural invariant showing the gray notice table/box height itself
  is wrong independent of font fallback.

Rejected for now:

- mapping `굴림체` globally to AppleGothic/Pretendard/Nanum/Noto;
- global font-size reduction;
- broad y-shifts;
- stroke/rule tweaks.
