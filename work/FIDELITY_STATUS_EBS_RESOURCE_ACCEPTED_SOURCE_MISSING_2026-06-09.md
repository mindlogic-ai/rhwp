# EBS Font Resource Status -- 2026-06-09

Status: accepted-resource / probe-source-missing.

Representative: `wc35_15pg`, especially pages `1`, `2`, `3`, `7`, `8`, `9`.

Guard: `report_form:2`.

## Classification

- Category: text/raster fidelity.
- Cause: exact document font `EBS전용서체-L` was not bundled.
- Promotion blocker: `wc35_15pg` source file is missing from `/tmp/diff`, so refreshed focused side-by-side and page-count validation cannot run for the representative.

## Patch

Added original EBS Jushigyeong Light TTF resource:

- `web/fonts/EBS-Jusigyeong-L.ttf`

Registered aliases:

- `EBS전용서체-L`
- `EBS주시경 Light`
- `EBSJSK Light`

The file is the original TTF from the official EBS Jushigyeong font download. EBS's usage guide permits commercial use across media including web/mobile/print/video, and prohibits arbitrary source modification, reverse engineering, renaming redistribution, and resale. This patch does not modify font source data.

## Evidence

Focused resource audit after patch:

- `wc35_15pg:1`: `EBS전용서체-L` 21 runs -> bundled `fonts/EBS-Jusigyeong-L.ttf`.
- `wc35_15pg:2`: `EBS전용서체-L` 30 runs -> bundled `fonts/EBS-Jusigyeong-L.ttf`.
- `wc35_15pg:3`: `EBS전용서체-L` 75 runs -> bundled `fonts/EBS-Jusigyeong-L.ttf`.
- `wc35_15pg:7`: `EBS전용서체-L` 13 runs -> bundled `fonts/EBS-Jusigyeong-L.ttf`.
- `wc35_15pg:8`: `EBS전용서체-L` 41 runs -> bundled `fonts/EBS-Jusigyeong-L.ttf`.
- `wc35_15pg:9`: `EBS전용서체-L` 25 runs -> bundled `fonts/EBS-Jusigyeong-L.ttf`.
- Guard `report_form:2`: unchanged bundled `Noto Sans KR` / `HY헤드라인M`.

Full corpus font-resource movement:

- Before EBS patch: bundled `161705` runs, missing/platform fallback `53663` runs.
- After EBS patch: bundled `161910` runs, missing/platform fallback `53458` runs.

Validation:

- `python3 harness/svg_font_resource_audit.py wc35_15pg:1 wc35_15pg:2 wc35_15pg:3 wc35_15pg:7 wc35_15pg:8 wc35_15pg:9 report_form:2`
- `python3 harness/fidelity_category_status.py wc35_15pg report_form --out /tmp/diff/FIDELITY_STATUS_EBS_GUARDS_2026-06-09.md`
- `cd rhwp-studio && npm run build`
- `python3 scripts/check_renderer_overfit.py`
- `python3 harness/svg_font_resource_audit.py --all --summary > /tmp/diff/FONT_RESOURCE_AUDIT_ALL_AFTER_EBS_2026-06-09.tsv`

## Remaining Limitation

This is accepted as an exact resource mapping, but not promoted as a full visual category because `wc35_15pg/source.hwpx` or `source.hwp` is missing. Restore the source artifact before generating a focused human-review board or page-count guard.
