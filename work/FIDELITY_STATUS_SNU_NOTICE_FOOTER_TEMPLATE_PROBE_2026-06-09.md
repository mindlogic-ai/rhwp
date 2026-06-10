# SNU Notice Footer Template Probe -- 2026-06-09

Category: `Text/raster fidelity + footer/template geometry`
Status: `guard-only/probe-no-patch`
Representative: `18_3728528_research_fund_repayment_request:1`
Related representative: `04_3781571_car_2bu_je_notice:2`
Metric guard: `report_form:2`

## Evidence

- Current broad board:
  `/tmp/diff/_review_all_nonlandscape_latest_goal_2026-06-09/index.html`
- Focused board:
  `/tmp/diff/_review_research_fund_footer_goal_2026-06-09/index.html`
- Representative page artifact:
  `/tmp/diff/_review_research_fund_footer_goal_2026-06-09/18_3728528_research_fund_repayment_request/page-001.png`
- Narrow component probe:
  `/tmp/diff/_probe_research_fund_footer_narrow_goal_2026-06-09/`
- Geometry probe:
  `python3 harness/svg_geometry_probe.py 18_3728528_research_fund_repayment_request:1 report_form:2`
- Font audit:
  `python3 harness/svg_font_resource_audit.py 18_3728528_research_fund_repayment_request:1 report_form:2`
- Source table probe:
  `python3 harness/hwpx_table_source_probe.py /tmp/diff/18_3728528_research_fund_repayment_request --list`

## Classification

The document is page-count clean (`1/1`), the SNU logo is present, and the main
body/table is semantically correct. The remaining visible mismatch is a mixed
SNU notice-template issue:

- text/raster density is heavier in RHWP;
- the gray footer bar and contact block appear slightly high relative to
  Hancom;
- the document uses the same footer/contact table pattern as
  `04_3781571_car_2bu_je_notice`;
- the page also uses `굴림체` fallback (`99` runs -> D2Coding) and `굴림`
  (`258` runs -> Noto Sans KR).

Source table shape:

- table `2`: `14x32`, `textWrap=TOP_AND_BOTTOM`, likely footer/contact table;
- table `3`: `14x32`, `textWrap=IN_FRONT_OF_TEXT`, likely overlay/footer
  companion table;
- table `4`: `BEHIND_TEXT`, likely watermark/logo/footer support.

This is not a missing-image or page-count bug, and current evidence does not
isolate a reusable footer-placement invariant independent of font fallback.

## Probe Results

Representative `18_3728528_research_fund_repayment_request:1`:

- `base=9.89`
- `hide_text=5.40`
- `hide_lines=5.29`
- `font_AppleGothic=9.30`
- `font_Nanum_Gothic=9.32`
- `font_Pretendard=9.52`
- `font_Noto_Sans_KR=9.87`
- `font_size_x0.90=9.06`
- `shift_y_after_430_p12=9.06`
- `shift_y_after_430_m12=10.01`

Guard `report_form:2`:

- `base=12.63`
- `font_size_x0.90=12.25`
- `shift_y_after_430_p12=12.89` (regresses)
- `shift_y_after_430_m12=12.09`
- common font substitutions also move guard metrics.

The only apparent footer-position improvement is a broad page-region y-shift
after `430px`, and that regresses the guard. It is not a renderer rule.

## Decision

Do not patch the renderer from this probe.

Future promotion needs a narrow structural invariant for this SNU notice/footer
template class, such as a proved relationship between `TOP_AND_BOTTOM` footer
table, `IN_FRONT_OF_TEXT` overlay table, and page-bottom anchoring. Without that
invariant, the observed deltas are covered by the broader `굴림체` fallback and
text/raster categories.

Rejected for now:

- broad page-region y-shift;
- global font-size reduction;
- global font-family substitution;
- footer-specific tweaks without identifying the structural owner.
