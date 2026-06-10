# Nanum Gothic Light Resource Status -- 2026-06-09

Status: accepted-resource / text-raster category remains probe.

Representative: `form_17_융합전공신청서_운영계획서_81KB:4`.

Guard: `report_form:2`.

## Classification

- Category: text/raster fidelity.
- Cause: exact document font `나눔고딕 Light` was not bundled or mapped to the existing `NanumGothic Light` metrics entry.
- Non-cause: page count. `form_17` and `report_form` remain page-count clean.

## Patch

Added `web/fonts/NanumGothic-Light.woff2` and registered exact aliases:

- `나눔고딕 Light`
- `NanumGothic Light`
- `NanumGothicLight`

Also mapped those aliases to the existing Rust `NanumGothic Light` metrics data so text measurement and browser paint use the same weight class.

## Evidence

Focused font-resource audit after patch:

- `form_17:1`: `나눔고딕 Light` 69 runs -> bundled `fonts/NanumGothic-Light.woff2`.
- `form_17:4`: `나눔고딕 Light` 434 runs -> bundled `fonts/NanumGothic-Light.woff2`.
- `form_17:6`: `나눔고딕 Light` 19 runs -> bundled `fonts/NanumGothic-Light.woff2`.
- `form_17:7`: `나눔고딕 Light` 28 runs -> bundled `fonts/NanumGothic-Light.woff2`.
- Guard `report_form:2`: unchanged bundled `Noto Sans KR` / `HY헤드라인M` resources.

Full corpus font-resource movement:

- Before Nanum Light patch: bundled `161155` runs, missing/platform fallback `54213` runs.
- After Nanum Light patch: bundled `161705` runs, missing/platform fallback `53663` runs.

Validation:

- `python3 harness/svg_font_resource_audit.py form_17_융합전공신청서_운영계획서_81KB:1 form_17_융합전공신청서_운영계획서_81KB:4 form_17_융합전공신청서_운영계획서_81KB:6 form_17_융합전공신청서_운영계획서_81KB:7 report_form:2`
- `cd rhwp-studio && npm run build`
- `docker compose --env-file .env.docker run --rm dev /usr/local/cargo/bin/cargo test --lib renderer::font_metrics_data::tests::nanum_weight_aliases_map_to_bundled_metrics -j 1`
- `python3 scripts/check_renderer_overfit.py`
- `python3 harness/svg_font_resource_audit.py --all --summary > /tmp/diff/FONT_RESOURCE_AUDIT_ALL_AFTER_NANUM_LIGHT_2026-06-09.tsv`
- `python3 harness/review_pages.py /tmp/diff/_review_nanum_light_resource_form17_2026-06-09 form_17_융합전공신청서_운영계획서_81KB --pages 4 --export-current`
- `python3 harness/audit_review_gallery.py /tmp/diff/_review_nanum_light_resource_form17_2026-06-09`
- `python3 harness/fidelity_category_status.py form_17_융합전공신청서_운영계획서_81KB report_form --out /tmp/diff/FIDELITY_STATUS_NANUM_LIGHT_GUARDS_2026-06-09.md`

Focused review:

- `/tmp/diff/_review_nanum_light_resource_form17_2026-06-09/index.html`

## Remaining Limitation

This accepts one exact public font resource. It does not solve the remaining Yoon, Garamond, Hancom, Human, Soonchunhyang, EBS, or HY resource gaps.
