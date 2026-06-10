# RHWP Production Readiness Board -- 2026-06-08

Purpose: turn the long fidelity loop into finite production gates. This board
is the decision surface; detailed probes remain in the category-specific notes.

Short current gate audit: `work/PRODUCTION_GATE_AUDIT_2026-06-09.md`.

## Goal

Ship when semantic rendering is stable on the focus corpus, major visual
failures are classified, and export roundtrip has a passing gate. Do not chase
pixel-perfect Hancom parity as the first production target.

## Gates

| gate | pass condition | current status | next action |
|---|---|---|---|
| Semantic render | page counts match and no wrong-page headings/content on focus docs | mostly passing | freeze accepted fixes, keep guard counts current |
| Major visual layout | no obvious missing/shifted images, clipped tables, or table-body drift in representative boards | partial | work category-by-category; do not use global font/stroke knobs |
| Text/raster appearance | table text/rules are readable and within agreed region thresholds | open | treat as backend/cell-text project, not pagination |
| Export roundtrip | exported HWPX/HWP reopens in Hancom/RHWP with stable pages and no structural loss | accepted-HWPX/probe-HWP-adapter | true-HWPX reload drift fixed for `75` stale paragraph-source and `15` shape-position flags; HWP adapter parity and source-HWP-to-HWPX remain separate probes/blockers |
| Regression safety | focused tests, overfit check, guard page counts, refreshed board | partial | run before any commit |

## Latest Broad Review

Generated from current local code:

```bash
docker compose --env-file .env.docker run --rm dev cargo build --release --bin rhwp -j 1
python3 harness/review_gallery.py /tmp/diff/_review_all_latest_nonlandscape_2026-06-08 \
  --all --skip-landscape --export-current
python3 harness/audit_review_gallery.py /tmp/diff/_review_all_latest_nonlandscape_2026-06-08
python3 harness/fidelity_category_status.py \
  --out work/FIDELITY_PAGECOUNT_STATUS_ALL_LATEST_NONLANDSCAPE_2026-06-08.md \
  03_3781727_staff_evaluation_table 04_3781571_car_2bu_je_notice \
  05_3781559_medschool_car_2bu_je_plan \
  09_3766093_natural_sci_planning_committee_260527 \
  13_3763367_k_star_visa_track_plan \
  15_3740450_research_admin_innovation_meeting_template \
  18_3728528_research_fund_repayment_request 20_3727659_resume_2605_ai \
  form_01_교수법_과제양식_코다이_49KB form_07_______________41KB \
  form_11_응시원서_자기소개서_48KB form_17_융합전공신청서_운영계획서_81KB \
  internship_plan meeting_summary multicultural_plan overseas_training \
  photo_122p_civil_defense photo_form24 photo_w31 report_form research_form
```

- Broad review HTML: `/tmp/diff/_review_all_latest_nonlandscape_2026-06-08/index.html`.
- Gallery audit: pass, no truncation/aspect issues across 22 docs.
- Landscape/wide accountability variants were skipped by policy.
- `meeting_summary_font_fallback` is an experiment symlink folder and is not
  counted as a real corpus failure; the real `meeting_summary` row is 3/3.
- Real portrait corpus page-count status: 20/21 clean. The only current
  real page-count gap is `photo_form24`, Hancom `89` / RHWP `88`.

Refresh after `b3986582` and `4c9f82d4`:

```bash
python3 harness/review_gallery.py /tmp/diff/_review_all_nonlandscape_latest_2026-06-08 \
  --all --skip-landscape --export-current
python3 harness/audit_review_gallery.py /tmp/diff/_review_all_nonlandscape_latest_2026-06-08
```

- Fresh review HTML: `/tmp/diff/_review_all_nonlandscape_latest_2026-06-08/index.html`.
- Gallery audit: pass, no truncation/aspect issues across 22 docs.
- Current non-landscape rendered set is page-count clean: 21/21 real docs match
  Hancom page counts. `meeting_summary_font_fallback` remains a derived
  experiment directory with `RHWP=0` and is excluded from real corpus status.
- Remaining blockers are now visual/semantic-anchor drift rather than simple
  total page-count drift.
- Board-derived visual-drift ranking flags:
  - `09_3766093_natural_sci_planning_committee_260527` pages 49-50: same
    total page count but wrong internal page pairing around the NEXT Lab report.
  - `photo_form24` pages 50-52 and 66-69: mostly same-page picture/table scale
    and vertical geometry drift.
  - `13_3763367_k_star_visa_track_plan` page 4: flowchart/table geometry and
    overlapping text drift.
  - `overseas_training` page 1: table/font/rule density drift with stable
    semantics.

Refresh after `29e7146e` plus the current dirty `photo_form24` probe:

```bash
docker compose --env-file .env.docker run --rm dev cargo build --release
python3 harness/review_gallery.py /tmp/diff/_review_goal_nonlandscape_latest_2026-06-08 \
  --all --export-current --skip-landscape --max-pages 12
python3 scripts/check_renderer_overfit.py
```

- Broad review HTML: `/tmp/diff/_review_goal_nonlandscape_latest_2026-06-08/index.html`.
- Generated from git HEAD `29e7146e`; dirty worktree `yes`.
- 22 non-landscape docs rendered; `accountability_eval`,
  `accountability_eval_fitted`, and `accountability_eval_fitted_oracle` were
  skipped by landscape policy.
- Real docs in the capped broad board are page-count clean except the derived
  `meeting_summary_font_fallback` experiment row, which shows `RHWP=0` and is
  not a real corpus source.
- `photo_form24` page count is `89/89` in this dirty probe, but the focused
  pages 61-66 board shows a failed visual pairing: Hancom page 65 has finished
  the large policy table and starts the contact table, while RHWP page 65 is
  still rendering the prior row/diagram fragment and pushes the contact table
  to page 66. Treat current `photo_form24` Rust changes as `probe`, not
  accepted.
- A nested-placeholder host probe was also tested against this target:
  `/tmp/diff/_review_photo_form24_nested_visible_empty_2026-06-08/index.html`.
  The focused regression passed, but real `photo_form24` anchors stayed late
  (`성과관리` Hancom 66 / RHWP 67, `규제특례` Hancom 67 / RHWP 68), so the code
  probe was removed and is not part of the candidate.
- Current rowspan-startcut candidate board:
  `/tmp/diff/_review_photo_form24_rowspan_startcut_2026-06-08/index.html`.
  The structural regression
  `rowspan_touched_continuation_uses_per_row_start_cut_height` passes, overfit
  scan passes, and selected guard page counts stayed clean. It improves
  `pi1107` page-65 continuation accounting (`817.6px -> 582.7px`) but does not
  yet promote the category: `성과관리` and `규제특례` remain +1 page late.

Stable refresh after rejecting the 2026-06-09 late-tail probe:

```bash
CARGO_BUILD_JOBS=1 docker compose --env-file .env.docker run --rm \
  -e CARGO_BUILD_JOBS=1 dev cargo build --release --bin rhwp
python3 scripts/check_renderer_overfit.py
python3 harness/review_gallery.py \
  /tmp/diff/_review_all_nonlandscape_stable_goal_2026-06-09 \
  --all --export-current --skip-landscape --max-pages 12
python3 harness/fidelity_category_status.py \
  03_3781727_staff_evaluation_table 04_3781571_car_2bu_je_notice \
  05_3781559_medschool_car_2bu_je_plan \
  09_3766093_natural_sci_planning_committee_260527 \
  13_3763367_k_star_visa_track_plan \
  15_3740450_research_admin_innovation_meeting_template \
  18_3728528_research_fund_repayment_request 20_3727659_resume_2605_ai \
  form_01_교수법_과제양식_코다이_49KB form_07_______________41KB \
  form_11_응시원서_자기소개서_48KB form_17_융합전공신청서_운영계획서_81KB \
  internship_plan meeting_summary multicultural_plan overseas_training \
  photo_122p_civil_defense photo_form24 photo_w31 report_form research_form \
  --out /tmp/diff/FIDELITY_STATUS_ALL_NONLANDSCAPE_STABLE_GOAL_2026-06-09.md
```

- Broad review HTML:
  `/tmp/diff/_review_all_nonlandscape_stable_goal_2026-06-09/index.html`.
- Overfit scanner passed with the existing 8 baseline findings.
- The board intentionally caps long docs at 12 pages; `audit_review_gallery.py`
  reports only expected truncation for `09`, `13`, `photo_122p_civil_defense`,
  `photo_form24`, and `photo_w31`.
- The 21 real non-landscape docs are page-count clean. The derived
  `meeting_summary_font_fallback` symlink experiment was removed from the board
  index/status because its absolute `/tmp/diff/...` source symlink is not valid
  inside the Docker `/diff` mount.
- Visual ranking on the capped board now puts `photo_form24` pages 4/7/8/9,
  `photo_w31` pages 1/2/4/6, `13_3763367...` page 1, and `overseas_training`
  page 1 near the top. These are visual categories, not page-count failures.

Current goal refresh:

```bash
python3 harness/review_gallery.py --all --export-current --skip-landscape \
  --max-pages 12 /tmp/diff/_review_all_current_skip_landscape_latest_2026-06-08
python3 harness/review_pages.py \
  /tmp/diff/_review_09_semantic_drift_pages_46_51_latest_2026-06-08 \
  09_3766093_natural_sci_planning_committee_260527 \
  --pages 46,47,48,49,50,51 --export-current
```

- Broad review HTML:
  `/tmp/diff/_review_all_current_skip_landscape_latest_2026-06-08/index.html`.
  It includes 22 docs and skips the landscape accountability variants by policy.
- Focused `09` board:
  `/tmp/diff/_review_09_semantic_drift_pages_46_51_latest_2026-06-08/index.html`.
- Current real-doc page counts in the broad set are clean. The derived
  `meeting_summary_font_fallback` experiment row is not a real corpus source.
- `09` remains a same-count semantic drift, not an accepted fix target: fresh
  anchors show `붙임 11` and `[참고]` are +1 page late around pages 46-48, then
  the later NEXST section catches up.
- Table/text/raster representative board:
  `/tmp/diff/_review_overseas_training_page1_current_2026-06-08/index.html`.
  `overseas_training` page 1 is classified as text/raster fidelity with minor
  vertical compression, not pagination. Geometry bands are close
  (`Hancom main band 875.5px`, `RHWP main band 865.6px`), while dark-pixel
  density is low at normal thresholds (`threshold=96` ratio `0.864`). Font
  mutation probes were rejected: best `serif_nanum_regular` improved mean diff
  only `22.14 -> 21.60` and made hard ink lighter; stroke/font-size/advance
  probes were worse. Do not land broad font/stroke knobs from this page alone.

Fresh full non-landscape goal render:

```bash
docker compose --env-file .env.docker run --rm dev cargo build --release --bin rhwp -j 1
python3 harness/review_gallery.py \
  /tmp/diff/_review_all_nonlandscape_fresh_goal_2026-06-08 \
  --all --export-current --skip-landscape
python3 harness/audit_review_gallery.py \
  /tmp/diff/_review_all_nonlandscape_fresh_goal_2026-06-08
python3 harness/fidelity_category_status.py \
  --out /tmp/diff/FIDELITY_STATUS_ALL_NONLANDSCAPE_FRESH_GOAL_2026-06-08.md \
  03_3781727_staff_evaluation_table 04_3781571_car_2bu_je_notice \
  05_3781559_medschool_car_2bu_je_plan \
  09_3766093_natural_sci_planning_committee_260527 \
  13_3763367_k_star_visa_track_plan \
  15_3740450_research_admin_innovation_meeting_template \
  18_3728528_research_fund_repayment_request 20_3727659_resume_2605_ai \
  form_01_교수법_과제양식_코다이_49KB form_07_______________41KB \
  form_11_응시원서_자기소개서_48KB form_17_융합전공신청서_운영계획서_81KB \
  internship_plan meeting_summary multicultural_plan overseas_training \
  photo_122p_civil_defense photo_form24 photo_w31 report_form research_form
python3 scripts/check_renderer_overfit.py
```

- Fresh broad review HTML:
  `/tmp/diff/_review_all_nonlandscape_fresh_goal_2026-06-08/index.html`.
- Gallery audit: pass, no truncation/aspect issues across 22 docs.
- Landscape accountability variants were skipped by policy.
- Real non-landscape page counts are clean for the 21-doc status set,
  including `photo_122p_civil_defense` `129/129`, `photo_form24` `89/89`,
  and `photo_w31` `30/30`.
- Overfit scanner passed with the existing 8 known baseline findings.
- Current visual-drift ranking from the fresh board starts with:
  `09` page 50 (`58.43` mean diff), `09` page 49 (`37.82`),
  `photo_form24` pages 51/50, `photo_w31` page 24, and
  `13_3763367_k_star_visa_track_plan` page 4 (`23.14`).

Current goal refresh, 2026-06-09:

```bash
docker compose --env-file .env.docker run --rm dev cargo build --release --bin rhwp -j 1
python3 harness/review_gallery.py \
  /tmp/diff/_review_all_nonlandscape_current_goal_2026-06-09 \
  --all --export-current --skip-landscape
python3 harness/audit_review_gallery.py \
  /tmp/diff/_review_all_nonlandscape_current_goal_2026-06-09
python3 harness/fidelity_category_status.py \
  --out /tmp/diff/FIDELITY_STATUS_ALL_NONLANDSCAPE_CURRENT_GOAL_2026-06-09.md \
  03_3781727_staff_evaluation_table 04_3781571_car_2bu_je_notice \
  05_3781559_medschool_car_2bu_je_plan \
  09_3766093_natural_sci_planning_committee_260527 \
  13_3763367_k_star_visa_track_plan \
  15_3740450_research_admin_innovation_meeting_template \
  18_3728528_research_fund_repayment_request 20_3727659_resume_2605_ai \
  form_01_교수법_과제양식_코다이_49KB form_07_______________41KB \
  form_11_응시원서_자기소개서_48KB form_17_융합전공신청서_운영계획서_81KB \
  internship_plan meeting_summary multicultural_plan overseas_training \
  photo_122p_civil_defense photo_form24 photo_w31 report_form research_form
```

- Fresh current review HTML:
  `/tmp/diff/_review_all_nonlandscape_current_goal_2026-06-09/index.html`.
- Gallery audit: pass, no truncation/aspect issues across 22 docs.
- Real non-landscape page counts are clean for the 21-doc status set, including
  `09` `51/51`, `photo_122p_civil_defense` `129/129`, `photo_form24` `89/89`,
  and `photo_w31` `30/30`.
- Landscape accountability variants remain skipped by policy.
- Derived `meeting_summary_font_fallback` may appear in the gallery index, but
  is excluded from corpus decisions.
- Worst fresh visual-drift pages from the generated side-by-side strips:
  `09` page 50 (`58.43` mean diff), `photo_form24` page 51 (`32.60`),
  `photo_w31` page 24 (`28.59`), `13_3763367_k_star_visa_track_plan` page 1
  (`24.53`), `overseas_training` page 1 (`21.99`), and
  `15_3740450_research_admin_innovation_meeting_template` page 2 (`21.17`).
- Focused follow-up boards from the same current code:
  - `/tmp/diff/_review_09_pages48_51_current_goal_2026-06-09/index.html`
  - `/tmp/diff/_review_overseas_page1_current_goal_2026-06-09/index.html`
  - `/tmp/diff/_review_research_admin_pages1_5_current_goal_2026-06-09/index.html`
  - `/tmp/diff/_review_meeting_summary_pages1_3_current_goal_2026-06-09/index.html`
  All four focused boards pass `harness/audit_review_gallery.py`.

Post-export-fix visual refresh:

```bash
docker compose --env-file .env.docker run --rm dev cargo build --release --bin rhwp -j 1
python3 harness/review_gallery.py \
  /tmp/diff/_review_all_nonlandscape_post_export_fixes_2026-06-09 \
  --all --export-current --skip-landscape --max-pages 12
python3 harness/fidelity_category_status.py \
  03_3781727_staff_evaluation_table 04_3781571_car_2bu_je_notice \
  05_3781559_medschool_car_2bu_je_plan \
  09_3766093_natural_sci_planning_committee_260527 \
  13_3763367_k_star_visa_track_plan \
  15_3740450_research_admin_innovation_meeting_template \
  18_3728528_research_fund_repayment_request 20_3727659_resume_2605_ai \
  form_01_교수법_과제양식_코다이_49KB form_07_______________41KB \
  form_11_응시원서_자기소개서_48KB form_17_융합전공신청서_운영계획서_81KB \
  internship_plan meeting_summary multicultural_plan overseas_training \
  photo_122p_civil_defense photo_form24 photo_w31 report_form research_form \
  --out /tmp/diff/FIDELITY_STATUS_POST_EXPORT_FIXES_NONLANDSCAPE_2026-06-09.md
```

- Broad review HTML:
  `/tmp/diff/_review_all_nonlandscape_post_export_fixes_2026-06-09/index.html`.
- The 21 real non-landscape docs are page-count clean after export serializer
  fixes. `meeting_summary_font_fallback` is still a derived experiment row,
  not a corpus source.
- `harness/audit_review_gallery.py` reports only expected capped-board
  truncation for long docs (`09`, `13`, `photo_122p_civil_defense`,
  `photo_form24`, `photo_w31`).
- Quick split-strip pixel ranking on the capped board now starts with:
  `photo_form24` pages 7/4/9/8, `photo_w31` pages 2/4/6,
  `13_3763367_k_star_visa_track_plan` page 1, and `09` page 1.
  `photo_form24` page 7 is an image/table geometry probe: page count and
  semantic content are stable, but the top diagram/table group is visibly
  smaller/lighter and shifted relative to Hancom. Do not patch it with global
  font/table scale knobs; next useful action is a focused geometry probe of
  that TAC diagram/table group and a guard against the already accepted
  `photo_form24` page-count anchors.
- Focused current probes completed for the first two ranked non-landscape
  visual pages:
  - `photo_form24:7` remains rejected/guard-only. `svg_geometry_probe.py`
    confirms no missing content and stable page semantics, but the main
    diagram/table band differs in raster/text/line density (`Hancom`
    `252.6..611.6`, RHWP `239.3..592.4`). `svg_component_probe.py` reports
    base `28.33`, `hide_text=19.61`, `hide_lines=21.74`,
    `font_size_x0.90=26.85`, and best y-shift experiment
    `shift_y_after_430_m12=24.63`; the useful movements are broad visual knobs,
    not structural renderer rules.
  - `photo_w31:2` is text/raster fidelity probe, not a table geometry patch.
    `svg_geometry_probe.py` shows the content/page pairing is intact but body
    text bands start roughly 15px higher than Hancom and then stay compact.
    `svg_component_probe.py` reports base `25.83`, `hide_text=13.21`,
    `hide_lines=13.37`, `font_size_x0.90=23.41`, `text_y_p4=24.85`, and
    `shift_y_after_430_p12=24.43`; again the best levers are font/paint/shift
    knobs with broad blast radius.
  - `13_3763367_k_star_visa_track_plan:1` stays semantic-accepted /
    visual-probe-only. `svg_geometry_probe.py` shows one non-TAC image/shape
    extending below the page body (`y=1047.5..1300.0`) and compact body text
    bands; `svg_component_probe.py` reports base `24.39`, `hide_text=15.63`,
    `hide_lines=14.56`, `font_size_x0.90=22.72`, and
    `shift_y_after_430_p12=23.14`. The page is too coupled to the accepted
    `21/21` pagination to patch with broad title-band spacing or line-height
    changes.
- Added `harness/svg_font_resource_audit.py` as a repeatable text/raster
  category gate. It scans rendered SVG font-family usage and classifies each
  primary face as bundled, CDN-backed, system, or missing office face. `bundled`
  now requires the referenced local font file to exist under the static font
  roots; the audit prints both `resource_status` and `resource_detail`. Current
  representative output:
  - `overseas_training:1`: `경기천년바탕 Bold` 724 runs,
    `경기천년제목 Medium` 248, and `경기천년제목V Bold` 21 are
    `missing-office-face`. `나눔고딕 ExtraBold` was initially system-dependent,
    then accepted as a bundled-alias subfix below.
  - `photo_w31:2`: `함초롬바탕/돋움` are CDN-backed, but `한컴 고딕`
    317 runs is `missing-office-face`.
  - `13_3763367_k_star_visa_track_plan:1`: `휴먼명조` 448 and
    `휴먼고딕` 36 are `missing-office-face`; `HY헤드라인M` / `HY중고딕`
    are bundled aliases.
  - `report_form:2` is the clean guard: `Noto Sans KR` and `HY헤드라인M`
    are both bundled, matching its low visual-risk status.
  Validation: `python3 -m py_compile harness/svg_font_resource_audit.py` and
  `python3 harness/svg_font_resource_audit.py overseas_training:1
  meeting_summary:1 photo_w31:2 13_3763367_k_star_visa_track_plan:1
  report_form:2` passed; `python3 scripts/check_renderer_overfit.py` passed.
- Accepted a narrow bundled-font alias subfix for Nanum weight faces:
  `나눔고딕 Bold/ExtraBold`, `NanumGothic Bold/ExtraBold`,
  `NanumGothicExtraBold`, and matching Nanum Myeongjo weight aliases now map to
  existing bundled WOFF2 files in `rhwp-studio/src/core/font-loader.ts` and
  `web/editor.html`; legacy `web/font_substitution.js` treats them as
  registered faces; Rust embedded metrics map the ExtraBold aliases to
  `NanumGothicExtraBold` / `NanumMyeongjoExtraBold`. This removes the local-Mac
  dependency for `overseas_training:1`'s 36 `나눔고딕 ExtraBold` runs without
  changing proprietary `경기천년*` fallback policy. Validation:
  `docker compose --env-file .env.docker run --rm dev cargo test --lib
  renderer::font_metrics_data::tests::nanum_weight_aliases_map_to_bundled_metrics
  -j 1`, `docker compose --env-file .env.docker run --rm dev cargo fmt --check
  -- src/renderer/font_metrics_data.rs`, `cd rhwp-studio && npm run build`,
  stricter font-resource audit showing `나눔고딕 ExtraBold` as
  `bundled fonts/NanumGothic-ExtraBold.woff2`,
  focused boards
  `/tmp/diff/_review_font_alias_resource_probe_2026-06-09/index.html` and
  `/tmp/diff/_review_font_alias_resource_guard_2026-06-09/index.html`,
  gallery audit pass, and page counts `overseas_training 4/4`,
  `report_form 6/6`.

Post-`09` semantic acceptance refresh:

```bash
python3 harness/review_gallery.py \
  /tmp/diff/_review_goal_nonlandscape_post09_2026-06-09 \
  --all --export-current --skip-landscape --max-pages 12
python3 harness/fidelity_category_status.py \
  09_3766093_natural_sci_planning_committee_260527 \
  13_3763367_k_star_visa_track_plan photo_form24 photo_w31 \
  photo_122p_civil_defense 05_3781559_medschool_car_2bu_je_plan \
  form_11_응시원서_자기소개서_48KB meeting_summary overseas_training \
  report_form \
  --out /tmp/diff/FIDELITY_STATUS_POST09_BROAD_GUARDS_2026-06-09.md
```

- Capped broad review HTML:
  `/tmp/diff/_review_goal_nonlandscape_post09_2026-06-09/index.html`.
- Representative guard page counts are clean: `09` `51/51`, `13` `21/21`,
  `photo_form24` `89/89`, `photo_w31` `30/30`,
  `photo_122p_civil_defense` `129/129`, `05` `4/4`, `form_11` `3/3`,
  `meeting_summary` `3/3`, `overseas_training` `4/4`, `report_form` `6/6`.
- `harness/audit_review_gallery.py` is intentionally not claimed for this
  capped broad board: it reports capped long docs as `TRUNCATED` because the
  HTML embeds only the first 12 strips while declaring full page counts. Use
  focused uncapped boards for category acceptance evidence.

## Current Category Decisions

| category | representative docs | status | before/after | remaining risk | ship/block | next command |
|---|---|---|---|---|---|---|
| Cover/body title-band semantic split | `05_3781559_medschool_car_2bu_je_plan` | accepted-semantic | RHWP `3 -> 4` pages vs Hancom `4`; page 1 no longer leaks body title band, page 2 starts with title band + `□ 추진 배경` | cover geometry/font/table-stroke drift remains; this is not a text/raster or cover-position fix | not a semantic blocker; keep as guard for cover/body page split | open `/tmp/diff/_review_fresh_comparable_post_cover_fix_2026-06-08/05_3781559_medschool_car_2bu_je_plan/index.html` |
| Form tail before explicit form page | `form_11_응시원서_자기소개서_48KB` | accepted-semantic | RHWP `2 -> 3` pages vs Hancom `3`; final note moves to sparse page 2 and `자기소개서` starts page 3 | table/rule/font density still differs; this is not a raster appearance fix | not a semantic blocker; keep as guard for HWPX form tail/page-break split | open `/tmp/diff/_review_fresh_comparable_tail_overflow_debug_2026-06-08/form_11_응시원서_자기소개서_48KB/index.html` |
| Photo/table page-count drift | `photo_form24` | guard-only/probe | Tail-guard combo and later accepted contact-table fixes moved the corpus toward Hancom page count. The current dirty probe adds positive-offset title/intro ordering and a wide-contact deferral; it reaches Hancom `89` / RHWP `89` and aligns earlier AI-section anchors. Fresh focused pages 61-66 board still fails: page 64 RHWP under-fills the bottom social-economy diagram region and page 65 lacks Hancom's contact table. `RHWP_TABLE_DRIFT` shows `pi1107` page-64 split budget leaves row 9 only `195.5px`; row 9 cell units are 12 text units before the nested diagram rows, and RHWP currently fits only 8 (`end_cut=[3,8]`). The nested diagram units start at indices 12-15, so a small split-slack tweak cannot reach the diagram. | page count alone is not a safe acceptance signal. Source scan confirms rows 6-8 have declared/content slack, but text-row and nested-row floor probes either overpacked earlier rows or did not move the diagram/contact pairing. This is not patchable today without a stronger saved-layout or row-block structural owner. | keep as a visual guard; do not commit/promote another contact/table-height tweak from this evidence | open `/tmp/diff/_review_photo_form24_pages61_66_current_2026-06-09/photo_form24/index.html`; diagnostics in `/tmp/diff/photo_form24/dump_pages_table_drift_current_2026-06-09.txt` and `/tmp/diff/photo_form24/dump_pages_unit_debug2_2026-06-09.txt` |
| Same-count semantic-anchor drift | `09_3766093_natural_sci_planning_committee_260527` | accepted-semantic/probe-visual | Cached cell-vpos reset policy already restored Hancom page count (`57 -> 51`). The accepted follow-up is a coupled structural rule: allow a source-XML lineSeg-less one-line tail before an explicit page break to use a small bottom overflow only when it can also split the following repeated same-sized large TAC Square picture/caption pair. Focused anchors now match Hancom on pages 46-50: `[참고]`, `[붙임 11]`, BSL3, `4. 현안`, NEXST title/`그림 1`, `5) 지반조사`, `그림 2`, and `다. 거버넌스` all have delta `0`; RHWP remains `51/51`. | visual/raster drift is not solved; this only fixes semantic page pairing around the late reference and NEXST picture pair. The earlier tail-only half-fix was rejected because it collapsed the doc to 50 pages. | accepted as semantic anchor fix; keep this doc as a guard and continue visual drift separately | open `/tmp/diff/_review_09_tail_picture_pair_final_2026-06-09/09_3766093_natural_sci_planning_committee_260527/index.html`; dump `/tmp/diff/09_3766093_natural_sci_planning_committee_260527/dump_pages_tail_plus_picture_pair_final_2026-06-09.txt`; guard status `/tmp/diff/FIDELITY_STATUS_09_TAIL_PICTURE_PAIR_FINAL_GUARDS_2026-06-09.md` |
| Diagram/table geometry drift | `13_3763367_k_star_visa_track_plan` | accepted-semantic/probe-visual | Page count is stable at 21/21. A narrow keep-with-next rule moves the late `2. 추천 절차` heading from RHWP page 3 to page 4 when it is followed by a 3-6 item procedure list and a wide multi-cell HWPX CELL TAC table. Fresh current board flags page 1 before page 4, and focused probes confirm two different visual classes: page 1 body starts too high/compact after the title band, while page 4 flowchart/table remains off. Page 1 current component probe reports `24.39` base, `hide_text=15.63`, `hide_lines=14.56`, `font_size_x0.90=22.72`, and `shift_y_after_430_p12=23.14`; these are broad font/shift levers, not structural owners. | page 1 looks structural but is not patch-ready: dump/page SVG shows overfull layout and a non-TAC image/shape extending below the page body (`y=1047.5..1300.0`), so title-band spacing changes could destabilize the accepted 21/21 pagination. Page 4 is a lineSeg-less nested flowchart/table-cell composition problem, not a page-count issue. Regional probes show procedure text is too compact (`+16.8%` dark pixels), flowchart/confirmation regions are too light (`-36%` and `-38.4%` dark pixels), and `svg_cell_text_probe` flags x-overflow in narrow flowchart cells. Component probes reject broad knobs because font substitutions are marginal and global scaling changes glyph policy for the wrong reason. | promote semantic anchor only; keep page 1/page 4 visual geometry `probe/open`; no Rust patch accepted from current evidence | open `/tmp/diff/_review_kstar_pages1_4_current_2026-06-09/index.html`; probes: `python3 harness/svg_geometry_probe.py 13_3763367_k_star_visa_track_plan:1`, `python3 harness/svg_component_probe.py 13_3763367_k_star_visa_track_plan:1`; dump `/tmp/diff/13_3763367_k_star_visa_track_plan/dump_pages_table_drift_current_2026-06-09.txt` |
| Page-count / semantic drift | `photo_122p_civil_defense`, `form_07`, `photo_w31`, `internship_plan` | accepted-semantic | civil-defense now 129/129 vs Hancom | visual drift remains on some pages | not a blocker if human review accepts semantic layout | `python3 harness/heading_drift_scan.py photo_122p_civil_defense --dump /tmp/diff/photo_122p_civil_defense/dump_pages_tail_group_candidate3.txt` |
| Photo-grid / pre-grid | `photo_122p_civil_defense`, `photo_w31`, `15_3740450_research_admin_innovation_meeting_template` | accepted for semantic anchors, guard-only/probe for visual | page anchors aligned on civil-defense. Fresh current representative `15_3740450...` page 2 is page-count clean (`5/5`) and all three images are present. Geometry probe reports image boxes at `y=497.9..649.9`, `660.3..1024.3`, and `748.1..1024.7`; visual review shows the lower photo table/content is vertically mismatched but not missing. Font audit is all bundled/CDN (`Noto Sans KR`, `휴먼명조`, `HY중고딕`, `HY헤드라인M`, `바탕`). Component probe does not reveal a structural owner: `base=21.29`, `hide_text=17.65`, `hide_lines=40.55`; broad text/font/size variants only marginally help (`font_size_x0.90=20.58`, `font_AppleGothic=20.90`), image height/brightness variants regress, and `image_y_p6=20.60` is a local visual shift rather than a reusable rule. | sizing, spacing, glyph/rule weight, and local image/table vertical composition remain; not a page-count, missing-image, or safe image-placement patch target | guard; do not patch with global image shift/scale or font knobs unless another structural owner appears | focused board `/tmp/diff/_review_research_admin_photo_grid_p2_current_2026-06-09/index.html`; status `/tmp/diff/FIDELITY_STATUS_RESEARCH_ADMIN_PHOTO_GRID_P2_2026-06-09.md`; probes: `python3 harness/svg_geometry_probe.py 15_3740450_research_admin_innovation_meeting_template:2`, `python3 harness/svg_image_ink_probe.py 15_3740450_research_admin_innovation_meeting_template:2`, `python3 harness/svg_component_probe.py 15_3740450_research_admin_innovation_meeting_template:2` |
| Dense financial table geometry/raster | `photo_w31` | guard-only/probe | fresh current focused page-24 board is page-count clean (`30/30`) and human-reviewable. Page 24 has no images; it is dense tables/text. SVG geometry shows the first table line band is close to Hancom (`443.3px` vs Hancom dark band `462.9px`), while the lower table remains visibly denser/taller in Hancom (`RHWP line band 293.1px`, Hancom lower raster band `388.6px`). Font audit shows only bundled fonts on this page (`Noto Sans KR`, `바탕`), so it is not a missing-resource case. Component probe remains text/rule-raster dominated: `base=28.65`, `hide_text=24.03`, `hide_lines=25.70`; image variants are no-ops, stroke thickening regresses, and only broad font-size/family reductions marginally help (`font_size_x0.90=27.74`, `font_AppleGothic=27.68`). Page 2 remains the companion dense-table guard with the same pattern (`base=25.83`, `hide_text=13.21`, `hide_lines=13.37`). | table rule/text raster density plus line-height/ink differences; not a safe page-break, image-grid, missing-font, or table-height patch target from current evidence | do not patch with broad scale/font/table-height/stroke knobs; keep as a visual guard for backend/text-raster work | focused board `/tmp/diff/_review_photo_w31_page24_current_2026-06-09/index.html`; status `/tmp/diff/FIDELITY_STATUS_PHOTO_W31_PAGE24_CURRENT_2026-06-09.md`; probes: `python3 harness/svg_geometry_probe.py photo_w31:24`, `python3 harness/svg_font_resource_audit.py photo_w31:24`, `python3 harness/svg_component_probe.py photo_w31:24`, plus existing page-2 probe |
| CellBreak carried rowspan / table raster | `accountability_eval` | guard-only/probe-no-patch | page count is clean at 6/6. Fresh focused page-4 board shows the lower continuation row is present in RHWP, but it is much lighter/smaller than Hancom; the previous "missing lower band" hypothesis is stale. `svg_geometry_probe.py` still reports SVG text/lines down to the page bottom (`text y=635.4..730.9`, lines to `736.2`), while raster dark-band detection sees Hancom main band plus lower band (`688.9..735.3`) and RHWP dark ink only to `626.8`, which is a threshold/ink-density symptom rather than absent table geometry. Font audit shows all page-4 text uses bundled `Noto Sans KR`; component probe is text/raster dominated (`base=17.58`, `hide_text=12.88`, `hide_lines=12.65`) and broad font/size substitutions only marginally improve (`font_size_x0.90=16.67`, `font_AppleGothic=16.97`) while heavier weights/strokes regress. | no structural CellBreak/rowspan patch accepted; prior top-slice prototypes were no-op and current visual evidence does not justify table-split changes. Keep as guard for future text/raster backend work. | not a current semantic ship blocker if human review accepts light table text; reject layout patching from this evidence | focused board `/tmp/diff/_review_accountability_page4_current_2026-06-09/index.html`; status `/tmp/diff/FIDELITY_STATUS_ACCOUNTABILITY_PAGE4_CURRENT_2026-06-09.md`; probes: `python3 harness/svg_geometry_probe.py accountability_eval:4`, `python3 harness/svg_font_resource_audit.py accountability_eval:4`, `python3 harness/svg_component_probe.py accountability_eval:4` |
| Table-text-raster | `overseas_training`, `meeting_summary`, `form_07`, `09_3766093_natural_sci_planning_committee_260527`, `photo_w31`, `wild_02_paper_fig_10MB` | blocked-font-resource/probe, accepted bundled-alias subfix | `overseas_training` page 1 and `meeting_summary` page 1 both show stable geometry/content with lighter RHWP ink, weaker table rules, and wider Korean letter spacing. `overseas_training` geometry bands are close (`Hancom main band 875.5px`, `RHWP main band 865.6px`), but the visual weight is wrong. Fresh probes confirm the representative fonts are absent/resource-backed rather than pagination-owned: `overseas_training` uses `경기천년제목 Medium`, `경기천년바탕 Bold`, `경기천년제목V Bold`, and `나눔고딕 ExtraBold`; `meeting_summary` title uses `HY헤드라인M` and body uses fallback `Noto Sans KR`. New `harness/svg_font_resource_audit.py` makes this repeatable: `overseas_training:1` is dominated by missing `경기천년*` office faces. The Hancom Gothic representative is `photo_w31:2`: page count is clean (`photo_w31` 30/30, `report_form` 6/6), font audit reports `한컴 고딕` 317 runs on page 2 and 355 runs on page 6, and `photo_w31:24` remains a bundled-font dense-table guard (`Noto Sans KR`, `바탕`) rather than justification for a `한컴 고딕` alias. Component probe for page 2 is text-owned (`base=25.83`, `hide_text=13.21`, `hide_lines=13.37`); line/stroke/image variants are no-ops, while broad visual knobs such as `font_size_x0.90=23.41`, `shift_y_after_430_p12=24.43`, `text_y_p4=24.85`, `weight_500=25.05`, and `font_AppleGothic=25.12` are rejected as non-structural. Resource search found no exact `한컴 고딕`, Hancom Gothic, HCR, or Malgun font file in the checked production bundle or local macOS font folders, so no `한컴 고딕 -> Noto/Pretendard/AppleGothic` patch is accepted. Accepted subfixes: `나눔고딕 ExtraBold` now resolves as bundled instead of system-dependent by registering existing Nanum weight WOFF2 aliases and embedded metrics; `13_3763367_k_star_visa_track_plan:1` no longer falls through for `휴먼명조`/`휴먼고딕` because the browser loader now registers those exact family names against existing bundled Nanum Myeongjo/Gothic resources while Rust keeps the existing `휴먼*` metrics. Corpus-wide current SVG audit now ranks remaining resource exposure across 577 pages: bundled `140436` text runs, CDN `54658`, missing/platform fallback `71402`, missing office faces `5173`, and missing HY faces `227`. The largest unbundled families are Yoon/KoPub/Garamond-style resources (`-윤명조320`, `-윤고딕320`, `KoPub돋움체 Light`, `Garamond`), while the office-face blockers remain `경기천년바탕 Bold` (`2804` runs), `한컴 고딕` (`1329`), `경기천년제목 Medium` (`445`), `휴먼둥근헤드라인` (`304`), and `경기천년제목 Light` (`213`). `wild_02_paper_fig_10MB` pages 1-7 are the largest KoPub Dodum Light exposure, but `/tmp/diff/wild_02_paper_fig_10MB/source.hwpx` / `source.hwp` is missing, so it is blocked for current-regeneration and patch validation despite stale SVG/PNG artifacts. The top available-source missing-resource representative remains `09_3766093...` page 30: current focused board is page-count clean at `51/51`, font audit reports `Garamond` 1870 runs with no local/repo font resource, and adjacent pages confirm the same class (`p31=1575`, `p32=1654`). Current component probe shows the mismatch is text-owned (`base=19.47`, `hide_text=7.28`, `hide_lines=7.28`) while line/image/stroke variants are no-op and only broad font/size substitutes move the score (`font_size_x0.90=17.31`, `font_Apple_SD_Gothic_Neo=17.23`, `font_Nanum_Gothic=17.89`, `font_AppleGothic=17.86`). Local macOS and repo search found no Garamond/Yoon/Gyeonggi/Hancom files; local KoPub Batang TTFs exist but are not production web resources and do not address Garamond or KoPub Dodum. No `Garamond -> Noto/Nanum/Apple` alias patch is accepted because that would be a broad glyph-identity substitution, not an exact resource fix. The clean guard `report_form:2` uses only bundled `Noto Sans KR` and `HY헤드라인M`. Font-family/stroke/font-size/advance probes were rejected because target improvement was marginal, negative, or broad visual scaling (`font_size_x0.90` improves screenshots but is not a structural renderer rule). Native-Skia built and ran on 2026-06-09, but it did not solve the category: mean diff only moved `22.14 -> 21.69`, Korean glyphs dropped out in the native PNG, and dark-pixel ratio at threshold 96 collapsed to `0.135`. | dark ink/text/rule density remains off; native Skia is currently not a usable oracle/backend replacement for Korean text in this environment. This still needs licensed/proper `경기천년` / `한컴 고딕` plus Yoon/KoPub/Garamond resource decisions or a real text-paint backend parity plan, not pagination or table geometry tweaks. | production quality blocker for high-fidelity raster, but narrow bundled-alias gaps are accepted and guarded; `wild_02` is blocked-source for current validation; `09` Garamond and `photo_w31` Hancom Gothic are resource-blocked/probe-no-patch | commands: `python3 harness/svg_font_resource_audit.py overseas_training:1 meeting_summary:1 photo_w31:2 13_3763367_k_star_visa_track_plan:1 report_form:2`, `python3 harness/svg_font_resource_audit.py 13_3763367_k_star_visa_track_plan:1 photo_w31:2 overseas_training:1 report_form:2`, `python3 harness/svg_font_resource_audit.py photo_w31:2 photo_w31:6 photo_w31:24 report_form:2`, `python3 harness/svg_geometry_probe.py photo_w31:2`, `python3 harness/svg_component_probe.py photo_w31:2`, `python3 harness/svg_font_resource_audit.py --all --summary > /tmp/diff/FONT_RESOURCE_AUDIT_ALL_CURRENT_2026-06-09.tsv`, `python3 harness/review_pages.py /tmp/diff/_review_09_garamond_resource_probe_2026-06-09 09_3766093_natural_sci_planning_committee_260527 --pages 30 --export-current`, `python3 harness/svg_component_probe.py 09_3766093_natural_sci_planning_committee_260527:30`, `cd rhwp-studio && npm run build`, `python3 scripts/check_renderer_overfit.py`; focused boards `/tmp/diff/_review_font_alias_resource_probe_2026-06-09/index.html`, `/tmp/diff/_review_font_alias_resource_guard_2026-06-09/index.html`, `/tmp/diff/_review_human_font_alias_probe_2026-06-09/index.html`, `/tmp/diff/_review_human_font_alias_guard_2026-06-09/index.html`, `/tmp/diff/_review_09_garamond_resource_probe_2026-06-09/index.html`, `/tmp/diff/_review_photo_w31_page24_current_2026-06-09/index.html`; status `/tmp/diff/FIDELITY_STATUS_GARAMOND_RESOURCE_BLOCKED_2026-06-09.md`, `/tmp/diff/FIDELITY_STATUS_HANCOM_GOTHIC_RESOURCE_BLOCKED_2026-06-09.md`; page-count guards `/tmp/diff/FIDELITY_STATUS_HUMAN_FONT_ALIAS_2026-06-09.md`, `/tmp/diff/FIDELITY_STATUS_09_GARAMOND_RESOURCE_2026-06-09.md`, `/tmp/diff/FIDELITY_STATUS_WILD02_FONT_RESOURCE_2026-06-09.md`; next action is licensed/proper office/font-resource validation lane, not another layout patch |
| Clean guard | `report_form` | guard | page count and visual score below drift threshold | none currently | pass | `python3 harness/fidelity_category_status.py --with-gallery report_form` |
| Export roundtrip | edited HWPX/HWP exports from representative spike corpus docs | accepted-HWPX/probe-HWP-adapter | Two structural HWPX export fixes are now accepted. First, section serialization preserves raw paragraph XML only when the raw `<hp:lineseg>` values match current IR; this keeps complex raw paragraphs intact but regenerates stale downstream lineSeg caches. It fixes `75_local_internship_plan`: edited HWPX reload changed from `9p -> 10p` to `9p -> 9p`, while unmutated remains `10p -> 10p`. Second, shape/picture/table serializers now emit modeled `flowWithText` and `allowOverlap` instead of hardcoding `1/0`; this fixes `15_007p_active_admin_stress` HWPX reload from `8p -> 7p` to `8p -> 8p`. Fresh current-state mutation probe on 2026-06-09 reports 5/6 representative docs as `HWPX_AND_HWP_RELOAD`: `15`, `61`, `62`, `63_stress_dna_archaeology_33mb`, and `75`. | HWP adapter parity is separate but not currently a failed self-reload gate: `15` HWP export/reload normalizes to `7p` even when source/unmutated HWPX is `8p`, but the live model also becomes `7p` immediately after `exportHwp`, and reload HWP stays `7p`. Source inspection shows `15` has ordinary HWPX `pagePr` bottom margin and is not an HWP3-origin bottom-tolerance case, so there is no narrow adapter patch accepted from current evidence. `45_form_grad_research_plan.hwpx` remains blocked because the source is HWP/CFB mislabeled `.hwpx` (`D0 CF 11 E0`); current mutation probe loads it as source HWP `39p`, HWPX export outline becomes `41p`, HWPX reload drifts to `55p`, while HWP export/reload stays `41p`. One configured stress sample, `63_stress_college_meeting_30mb.hwpx`, is absent locally and is harness-missing/404, not a renderer result. | promote edited true-HWPX reload for these structural classes; treat HWP adapter as self-reload pass / source-parity probe; keep source-HWP-to-HWPX conversion blocked unless product requires it | artifacts: `/tmp/hwp-export-roundtrip-probe-15-75-shape-pos-flags-2026-06-09/summary.txt`, `/tmp/hwp-export-roundtrip-probe-mutated-broad-existing-shape-pos-flags-2026-06-09/summary.txt`, `/tmp/hwp-export-roundtrip-probe-unmutated-15-75-shape-pos-flags-2026-06-09/summary.txt`, `/tmp/hwp-export-roundtrip-probe-mutated-current-2026-06-09/summary.txt`; validation: `HWP_TEST_URL=http://127.0.0.1:8766/ HWP_EXPORT_ONLY='^(15_007p_active_admin_stress|45_form_grad_research_plan|61_stress_science_advice_15mb|62_stress_college_meeting_16mb|63_stress_dna_archaeology_33mb|75_local_internship_plan)' HWP_EXPORT_MUTATE=1 HWP_EXPORT_ALLOW_UNVERIFIED=1 node hwp-agent-spike/tests/export_roundtrip_probe.mjs`, `rustfmt --check src/serializer/hwpx/section.rs src/serializer/hwpx/shape.rs src/serializer/hwpx/picture.rs src/serializer/hwpx/table.rs`, `python3 scripts/check_renderer_overfit.py`, focused tests `write_section_regenerates_following_paragraph_after_dirty_paragraph`, `write_section_preserves_following_raw_paragraph_when_linesegs_match_ir`, `rect_pos_preserves_flow_and_overlap_flags`, `pic_pos_preserves_flow_and_overlap_flags`, `tbl_pos_preserves_flow_and_overlap_flags`; WASM rebuild/sync hash `a554b0e7...` |

## Rejected Probes

- `photo_form24` title-table contact probe after `b3986582`: allowing a long
  blank-tail 2x3 CELL TAC contact table to move when the following explicit
  paragraph contains a 1-row TAC title table fixed the `AI 교육지원센터` section
  and made total page count `89/89`, but it shifted Hancom pages 66-70 one page
  late (`+1`) and the focused page 60-68 board paired unrelated content on page
  66. Rejected; the remaining issue is not safely solved by another broad
  contact-table deferral. Next structural owner is the large table/appendix
  split around `pi1107` through `pi1116`.
- `photo_form24` repeated text-row declared-floor shrink probe: a generic
  `row_cut_content_height` rule that ignored stale-looking declared heights for
  repeated-header TopAndBottom CELL/RowBreak text rows was tested on
  `/tmp/diff/_review_photo_form24_text_row_floor_probe_2026-06-09/index.html`.
  It overpacked earlier rows: RHWP page 64 started too high/too early and page
  65 still did not match Hancom's contact-table page. Rejected and reverted.
  The row-floor signal is real but too common across guard docs to use as a
  broad renderer rule; the next useful direction is a narrower saved-layout /
  row-fragment alignment owner, not blanket declared-height suppression.
- `photo_form24` nested declared-floor shrink probe: after fixing
  `harness/hwpx_row_floor_scan.py` to detect descendant nested tables, row 9 is
  no longer a 284px text-only row; it has about `476.8px` of nested/table
  content and about `91.7px` declared-height slack. A narrower
  `row_cut_content_height` probe that ignored stale declared height only for
  nested-table cells in repeated-header `CellBreak` `TopAndBottom` tables kept
  guard page counts clean, but did not move the page 63/64/65 pairing or bring
  the bottom diagram into RHWP page 64:
  `/tmp/diff/_review_photo_form24_nested_decl_floor_probe_2026-06-09/index.html`.
  Rejected and reverted. The owner is not simply stale declared height on
  nested-table rows; continue with cumulative page-pair alignment or row-block
  split semantics around the carried `행안부` rowspan block.
- `09_3766093` late-reference overflow probe: the drift begins when Hancom keeps
  the `[참고] 붙임 11...` one-line reference at the bottom of page 46 but RHWP
  emits it alone on page 47, shifting following anchors by `+1` until the later
  NEXT Lab section catches up. Synthetic probes that allowed this one-line
  reference to use a bounded bottom-margin allowance before an explicit
  title/shape break were rejected because all real dumps stayed unchanged,
  including `dump_pages_late_reference_title_shape_candidate4_2026-06-08.txt`.
  Debug logs showed the expected following shape was not visible to that
  predicate path, so accepting the rule would be speculative and unguarded.
- `09_3766093` bottom-blank-before-single-line-orphan probe: collapsing the
  immediately preceding control-free blank paragraph before a one-line visible
  orphan moved `pi547` off its singleton page, but over-corrected the document
  to RHWP `49` pages vs Hancom `51` and shifted `붙임 11` / `[참고]` one page
  early. Rejected and removed; do not retry without a stronger structural
  discriminator than "blank before one-line orphan".
- `09_3766093` source-XML missing-lineSeg tail overflow probe: a narrower
  structural version targeted only a control-free one-line paragraph whose HWPX
  source has no `<hp:lineseg>`, preceded by a control-free blank and followed
  by an explicit `pageBreak` paragraph. It fired on the real `pi547` singleton
  and aligned the immediate anchors (`[참고]`, `[붙임 11]`, BL3, `4. 현안`,
  NEXST `그림 1`) to Hancom, but reduced the document to RHWP `50` pages vs
  Hancom `51` and moved `5) (지반조사)` one page early. Rejected and removed.
  Current restored dump:
  `/tmp/diff/09_3766093_natural_sci_planning_committee_260527/dump_pages_restored_after_tail_probe_2026-06-09.txt`.
  Candidate dump kept for evidence:
  `/tmp/diff/09_3766093_natural_sci_planning_committee_260527/dump_pages_source_xml_tail_overflow_probe_2026-06-09.txt`.
  The next structural owner is a paired large TAC picture group after the
  NEXST title: `pi599` picture + `pi600` caption should end the Hancom page,
  while `pi601`/`pi602`/`pi603` should start the next page. Do not accept the
  tail-overflow half without a guarded picture-pair split rule.
- `09_3766093` accepted coupled tail + picture-pair split: after the rejected
  half-fix above, the structural owner was narrowed to the page-bottom reference
  tail plus the immediately following repeated large TAC Square picture/caption
  pair. The final candidate keeps Hancom/RHWP at `51/51` and aligns the focused
  anchor map on pages 46-50 with zero deltas. Guards held for `09`, `13`,
  `photo_form24`, `photo_w31`, `photo_122p_civil_defense`, `05`, `form_11`,
  `meeting_summary`, and `overseas_training`; `cargo fmt --check`, focused
  regression `missing_lineseg_tail_gates_repeated_picture_pair_split`,
  release build `cargo build --release --bin rhwp`, and
  `check_renderer_overfit.py` all passed. Review board:
  `/tmp/diff/_review_09_tail_picture_pair_final_2026-06-09/index.html`.
- `photo_form24` nested-placeholder host split probe: broadening the nested-table
  split predicate from string-empty to visibly-empty (`\u{FFFC}`/whitespace) was
  structurally plausible and passed a focused synthetic row-cut regression, but
  the real dump and side-by-side board stayed unchanged. Rejected and reverted.
  The remaining owner is still the `pi1107` repeated-header CELL table row 9
  continuation/cut accounting, not placeholder text detection.
- `photo_form24` row-9 split-slack idea: rejected as a patch target for now.
  Temporary unit diagnostics showed the page-64 row-9 budget is about `195.5px`;
  RHWP fits only the first 8 text units of the rightmost cell, while the nested
  diagram rows start at units 12-15. A small budget/slack allowance would at
  most include one more text unit and would still not move the diagram onto
  page 64. The next reusable owner is earlier row/text height measurement or
  saved-line-seg interpretation, not a local end-cut bump.
- `photo_form24` row-floor / page-64-65 geometry recheck: reran source and
  component probes against table 110 (`pageBreak=CELL`, `repeatHeader=1`,
  `textWrap=TOP_AND_BOTTOM`). `hwpx_row_floor_scan.py` confirms the row-floor
  signal is real but broad inside the same table: rows 2, 3, 4, 6, and 9 all
  have large declared-vs-content slack (`row6 slack=115.0`, `row9 slack=91.7`),
  while previous declared-floor suppression either overpacked earlier pages or
  did not move the nested social-economy diagram. `svg_component_probe.py`
  on pages 64 and 65 rejects an image/table-geometry patch from current
  evidence: image transforms are no-ops, stroke tweaks barely move or worsen,
  and the only visible improvements are broad font substitutions or
  `font_size_x0.90` (`p64 base=18.00 -> 16.83`, `p65 base=19.96 -> 19.38`).
  Rejected as a patch target; keep as guard-only/probe until a saved-layout
  discriminator distinguishes row 9 from earlier slack rows without global
  table-height compression.
- `photo_form24` page-7 diagram/table visual probe: current stable board ranks
  this among the highest full-page diffs (`28.43` mean on the capped broad
  review), but the page is page-count/semantic clean. Dump shows the top diagram
  as a single large `TopAndBottom` `CELL` TAC table (`pi=77`, `1x1`,
  about `635.0x473.9px`) followed by ordinary paragraph/table content.
  `svg_component_probe.py photo_form24:7` did not support a safe patch:
  `hide_text` drops mean diff to `19.61`, `hide_lines` to `21.74`, best font
  substitution is still `26.63`, `font_size_x0.90` is `26.85`, and the best
  positional experiment (`shift_y_after_430_m12`) is only `24.63` and is
  obviously a broad global knob. `svg_geometry_probe.py photo_form24:7` shows
  close but not identical raster bands (`Hancom` main diagram band
  `252.6..611.6`, `RHWP` `239.3..592.4`) plus lighter text/rules. Rejected as
  a renderer patch target; keep as visual guard for table/text-raster backend
  work, not pagination/table-height tuning.
- `table-text-raster` font/paint probes: `overseas_training:1` and
  `meeting_summary:1` are stable-content pages whose main mismatch is text/rule
  raster weight. `svg_geometry_probe.py` shows close geometry bands
  (`overseas_training` Hancom main band `875.5px`, RHWP `865.6px`;
  `meeting_summary` Hancom/RHWP body bands both about `903px`), while
  component probes attribute most diff to text and lines. Font-face variants
  moved scores only marginally (`overseas_training` best open variant
  `22.14 -> 21.60`; `meeting_summary` font-family variants about
  `19.37 -> 18.83`) and broad `font_size_x0.90` is rejected as a visual knob,
  not a document structural rule. Text-region probes show the actual faces are
  missing/public-office/proprietary faces (`경기천년*`, `HY헤드라인M`) falling back
  to bundled/open fonts, and local font scan found no matching Malgun/Batang/
  Dotum/Gulim/HY/Gyeonggi/Hancom fonts. Keep this category blocked on
  font-resource/text-backend parity; do not patch pagination or table geometry
  for this visual class.
- `13_3763367_k_star_visa_track_plan` narrow-cell recomposition safety probe:
  table 8 / page 4 is a 3x13 flowchart-style TAC `TopAndBottom` CELL table with
  no saved cell `lineSegArray`. `svg_cell_text_probe` flags two header cells as
  `x_outside`. A guarded `recompose_for_cell_width` safety factor for missing
  lineSeg cells under 100px wide was tested at `0.92` and then a stronger
  `0.75`; both produced no change in the focused board or probe output:
  `/tmp/diff/_review_kstar_page4_narrow_cell_probe_2026-06-09/index.html` and
  `/tmp/diff/_review_kstar_page4_narrow_cell_probe075_2026-06-09/index.html`.
  Rejected and reverted. The owner is not the split threshold alone; continue
  with SVG/render-time text width/centering or cell-run metric diagnostics.
- `13_3763367_k_star_visa_track_plan` zero-sized lineSeg recomposition probe:
  page-4 table-cell paragraphs parse with a single zero-sized saved lineSeg
  (`line_height/text_height/baseline/spacing/segment_width = 0`), so treating
  those as missing lineSegs is structurally plausible. It fixed the local
  `svg_cell_text_probe` x-overflow in the flowchart cells and produced
  `/tmp/diff/_review_kstar_page4_zero_lineseg_recompose_2026-06-09/index.html`
  plus a narrowed render-only probe at
  `/tmp/diff/_review_kstar_page4_zero_lineseg_renderonly_2026-06-09/index.html`.
  Rejected and reverted because the target document regressed from the accepted
  fresh baseline `21/21` pages to `21/23` pages; guards stayed clean, but the
  target page-count gate failed. Do not retry by broadening
  `recompose_for_cell_width`; the next owner needs a render/SVG-only clipping
  or table-cell text painting path that does not feed pagination/table height.
- `13_3763367_k_star_visa_track_plan` SVG-only clipped-cell x-fit probe:
  a render-time candidate tracked the active clipped table-cell bounds in
  `SvgRenderer` and scaled text x positions only when a text run would exceed
  the cell's right edge. It was intentionally pagination-neutral and kept target
  and guard page counts clean (`13` `21/21`, `report_form` `6/6`, `09`
  `51/51`), with a valid focused board at
  `/tmp/diff/_review_kstar_page4_svg_cell_fit_probe_2026-06-09/index.html`.
  Rejected and reverted because the structural probe still reported the same
  `x_outside` cells (`cell-clip-61`, `cell-clip-82`) and the component score
  stayed in the same class (`base=23.22`; improvements still came from broad
  visual substitutions such as `font_size_x0.90=21.54`, `font_AppleGothic=21.96`,
  not from a defensible cell-geometry rule). The next owner is not a generic
  per-cell SVG x clamp; inspect cell-run measurement/centering or missing-font
  metrics for the narrow flowchart cells.

## Active Diagnostics

- `photo_form24` / `pi1107`: source table 110 is a repeated-header
  `TopAndBottom` CELL table. Row 9 has a carried row-span label from row 7
  (`행안부`) plus row-span-1 cells at cols 1 and 2. The current split sequence is:
  page 64 `cursor_row=6 end_row=10 consumed=921.0 end_cut=[3,8]`, then page 65
  originally charged a full row despite `start_cut=[3,8]`. The candidate fixes
  that accounting, dropping the page-65 continuation from `817.6px` to `582.7px`.
  Because rows 6-8 still consume about `734px`, only about `199px` of row 9 fits
  on page 64; page 65 still spends enough row 9/10 height that contact table
  `pi1110` remains on page 66. Next discriminator is earlier row-height
  distribution for rows 6-9 in this repeated-header CELL table, not another
  contact-table deferral.
- Current 2026-06-09 discriminator: page 64 Hancom includes the bottom nested
  social-economy diagram, but RHWP defers that diagram to page 65. Unit debug
  for row 9 shows col 2 unit heights
  `[20.8, 23.5, 20.8, 20.0, 32.8, 23.5, 20.8, 20.8, 20.8, 23.5, 20.8, 20.8, 18.9, 17.1, 17.1, 190.9]`
  with nested rows at units `12..15`; current page-64 cut is `[3,8]`. This
  makes a local split allowance insufficient and points at cumulative row/text
  height above row 9.

## Run Policy

1. Pick one row above.
2. If status is `accepted-semantic`, only use it as a regression guard unless
   human review finds a production-blocking visual issue.
3. If status is `probe-no-patch`, gather one more structural discriminator
   before changing Rust.
4. If status is `guard-only/open`, run regional/raster probes first; reject
   global knobs unless target and guards both improve for the right reason.
5. Promote a change only after:
   - focused regression passes;
   - `python3 scripts/check_renderer_overfit.py` passes;
   - guard page counts hold;
   - a refreshed side-by-side board is available for human review.

## Recommended Next Track

1. Do not chase total page count next; the fresh non-landscape board is
   page-count clean for the 21 real docs. Keep the landscape/wide-page class
   out of the main production gate unless product requires it.
2. The accepted patch scope is now gate-validated, but the worktree is still
   broadly dirty. If committing, stage only the accepted font/audit,
   serializer/export, and gate-documentation files; do not sweep in probe
   harnesses or unrelated renderer experiments.
3. Treat `photo_form24`, `photo_w31`, `overseas_training`, `meeting_summary`,
   `accountability_eval`, and `15_3740450...` as guards/probes for visual
   classes. Do not use them to justify broad global table-height, font, stroke,
   image-shift, or scale knobs.
4. If render fidelity remains the priority, move to a separate text/raster
   backend lane: font resources first (`경기천년*`, `한컴 고딕`, Yoon, KoPub,
   Garamond), then rule/text paint parity. Keep this separate from pagination.
5. If production editing/export becomes the priority, switch tracks to focused
   export roundtrip for `45_form_grad_research_plan.hwpx` and source-HWP/HWPX
   adapter semantics. The true-HWPX serializer fixes are already accepted for
   the current representative set.
