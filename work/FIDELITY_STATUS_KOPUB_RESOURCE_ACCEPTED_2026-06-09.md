# KoPub Resource Status -- 2026-06-09

Status: accepted-resource / text-raster category remains probe.

Representatives:

- `photo_122p_civil_defense:110` for `KoPub바탕체 Light`.
- `photo_122p_civil_defense:124` for `KoPub바탕체 Bold`.
- `form_17_융합전공신청서_운영계획서_81KB:4` for a non-large guard page using `KoPub돋움체 Light`.

The largest `KoPub돋움체 Light` concentration is in `wild_02_paper_fig_10MB`, but that fixture is intentionally not the human-review representative because it is a super-large paper-style file.

## Classification

- Category: text/raster fidelity.
- Cause: exact KoPub document fonts were not bundled, so browser rendering used platform/fallback fonts.
- Non-cause: page count. Guards remain page-count clean.

## Patch

Added original KoPubWorld TTF resources under `web/fonts/` and registered exact emitted document aliases:

- `KoPub돋움체 Light`
- `KoPub돋움체 Medium`
- `KoPub돋움체 Bold`
- `KoPub바탕체 Light`
- `KoPub바탕체 Bold`

The files are original TTFs from the KOPUS distribution, not WOFF2 conversions. KoPub's license treats format conversion as a modified version and restricts use of protected KoPub/KoPubWorld names for modified versions, so this patch accepts the larger original files instead of shipping converted webfonts.

## Evidence

Focused font-resource audit after patch:

- `wild_02_paper_fig_10MB:1`: `KoPub돋움체 Light` 1248 runs -> bundled `fonts/KoPubWorld Dotum Light.ttf`.
- `wild_02_paper_fig_10MB:3`: `KoPub돋움체 Light` 2494 runs -> bundled `fonts/KoPubWorld Dotum Light.ttf`.
- `photo_122p_civil_defense:110`: `KoPub바탕체 Light` 945 runs -> bundled `fonts/KoPubWorld Batang Light.ttf`.
- `photo_122p_civil_defense:124`: `KoPub바탕체 Bold` 104 runs -> bundled `fonts/KoPubWorld Batang Bold.ttf`.
- `form_17_융합전공신청서_운영계획서_81KB:4`: `KoPub돋움체 Light` 124 runs -> bundled `fonts/KoPubWorld Dotum Light.ttf`.
- Guard `report_form:2`: unchanged bundled `Noto Sans KR` / `HY헤드라인M` resources.

Full corpus font-resource movement:

- Before KoPub patch: bundled `143966` runs, missing/platform fallback `71402` runs.
- After KoPub patch: bundled `161155` runs, missing/platform fallback `54213` runs.

Validation:

- `python3 harness/svg_font_resource_audit.py wild_02_paper_fig_10MB:1 wild_02_paper_fig_10MB:3 photo_122p_civil_defense:110 photo_122p_civil_defense:124 form_17_융합전공신청서_운영계획서_81KB:4 report_form:2`
- `cd rhwp-studio && npm run build`
- `python3 scripts/check_renderer_overfit.py`
- `python3 harness/svg_font_resource_audit.py --all --summary > /tmp/diff/FONT_RESOURCE_AUDIT_ALL_AFTER_KOPUB_2026-06-09.tsv`
- `python3 harness/review_pages.py /tmp/diff/_review_kopub_resource_photo122_2026-06-09 photo_122p_civil_defense --pages 110,124 --export-current`
- `python3 harness/review_pages.py /tmp/diff/_review_kopub_resource_form17_2026-06-09 form_17_융합전공신청서_운영계획서_81KB --pages 4 --export-current`
- `python3 harness/audit_review_gallery.py /tmp/diff/_review_kopub_resource_photo122_2026-06-09`
- `python3 harness/audit_review_gallery.py /tmp/diff/_review_kopub_resource_form17_2026-06-09`
- `python3 harness/fidelity_category_status.py photo_122p_civil_defense form_17_융합전공신청서_운영계획서_81KB report_form --out /tmp/diff/FIDELITY_STATUS_KOPUB_GUARDS_2026-06-09.md`

Focused reviews:

- `/tmp/diff/_review_kopub_resource_photo122_2026-06-09/index.html`
- `/tmp/diff/_review_kopub_resource_form17_2026-06-09/index.html`

## Remaining Limitation

This accepts a resource fix, not full text/raster completion. Remaining high-impact resource gaps include Yoon families, Garamond, Hancom Gothic, Human Rounded Headline, Nanum Gothic Light, and HY office faces. The static SVG gallery is still weaker than browser-studio validation for proving actual webfont paint parity.
