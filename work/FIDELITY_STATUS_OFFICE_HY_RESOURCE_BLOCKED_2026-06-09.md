# Office/HY/Hancom Residual Resource Status -- 2026-06-09

Status: blocked-font-resource / rejected-broad-substitution.

Representatives:

- `photo_w31:2/6/12`
- `09_3766093_natural_sci_planning_committee_260527:4/12/28/37`
- `internship_plan:1`
- `wb17_library_report_13pg:2/3`
- `photo_form24:62/63`
- `overseas_training:4`

## Classification

- Category: text/raster fidelity.
- Cause: requested Office/HY/Hancom-family fonts are not bundled and are not verified as redistributable web resources.
- Non-cause: page-count or image/table ownership. These representatives are text/raster-density misses first; broad geometry changes would not explain the requested font faces.

## Current Corpus Evidence

From `/tmp/diff/FONT_RESOURCE_AUDIT_ALL_OFFICE_NEXT_2026-06-09.tsv`:

- `한컴 고딕`: 1329 missing office-face runs.
- `휴먼둥근헤드라인`: 304 missing office-face runs.
- `HY울릉도M`: 201 missing HY-face runs.
- `한컴산뜻돋움`: 182 missing/platform fallback runs.
- `HY수평선B`: 22 missing HY-face runs.
- `한컴 윤고딕 250`: 10 missing office-face runs.
- `HY옛글B`: 4 missing HY-face runs.

Highest-count pages:

- `한컴 고딕`: `photo_w31:6` 355 runs, `photo_w31:2` 317 runs, `photo_w31:4` 286 runs.
- `휴먼둥근헤드라인`: `09_3766093...:37` 39 runs, `:28` 37 runs, `:12` 36 runs, `:15` 35 runs.
- `HY울릉도M`: `photo_w31:12` 29 runs, `:10` 25 runs, `:19` 23 runs, `:21` 22 runs.
- `한컴산뜻돋움`: `photo_form24:62` 87 runs, `photo_form24:63` 87 runs.
- `HY수평선B`: `internship_plan:1` 22 runs.
- `HY옛글B`: `wb17_library_report_13pg:2` 2 runs and `:3` 2 runs.
- `한컴 윤고딕 250`: `overseas_training:4` 10 runs.

## Source/License Check

No matching local resources exist under `web/fonts/` or `rhwp-studio/dist/fonts/`.

Public lookup did not find clean upstream redistributable resources for this production renderer:

- `한컴산뜻돋움` appears in third-party font indexes with personal-trial/commercial-license warnings, not as a redistributable webfont.
- `휴먼둥근헤드라인` appears in third-party font indexes with purchase/license flows.
- HY faces such as `HY울릉도M`, `HY수평선B`, and `HY옛글B` appear as legacy/proprietary office fonts or unknown-license downloads.

## Decision

Do not map these families to Noto, Pretendard, KoPub, Nanum, AppleGothic, or other bundled fonts as a renderer rule. That would be a broad visual substitution, not an exact-resource fix, and would alter glyph identity/metrics across unrelated documents.

Promotion requires one of:

- verified redistributable/licensed exact font resources; or
- an explicit product fallback policy that names acceptable substitutes and is validated against guard pages.

Until then this bucket is closed as blocked for renderer work. The next renderer effort should move to structural text/raster backend issues or a different category, not more global font guessing.
