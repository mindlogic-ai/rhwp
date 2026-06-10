# RHWP Production Gate Audit -- 2026-06-09

This is the current category-by-category gate audit for the production-readiness loop. It does not replace the detailed board in `work/PRODUCTION_READINESS_BOARD_2026-06-08.md`; it is the short checklist of what is accepted, what is only a guard, and what is blocked.

Latest broad human-review board:

- `/tmp/diff/_review_all_nonlandscape_latest_goal_2026-06-09/index.html`
- Generated from current dirty working tree on 2026-06-09 09:12 KST with
  `review_gallery.py --all --export-current --skip-landscape`.
- 22 non-landscape entries rendered; `accountability_eval*` landscape variants
  skipped by policy.
- `python3 harness/audit_review_gallery.py /tmp/diff/_review_all_nonlandscape_latest_goal_2026-06-09`
  passes: no gallery truncation/aspect issues across 22 docs.
- Companion machine-classification snapshot:
  `work/FIDELITY_CATEGORY_STATUS_2026-06-09_GOAL_REFRESH.md`.

Previous broad human-review boards:

- `/tmp/diff/_review_all_nonlandscape_latest_2026-06-09b/index.html`
- Generated from dirty git HEAD `29e7146e`.
- 22 non-landscape entries rendered; `accountability_eval*` landscape variants skipped by policy.
- 21/22 entries page-match. The only mismatch is `meeting_summary_font_fallback`, a stale duplicate artifact whose `rhwp_svg_cur` symlink points to an empty fallback directory; the real `meeting_summary` entry is `3/3`.

## Current Gate State

| category | status | current evidence | production meaning |
|---|---|---|---|
| Semantic render | mostly accepted | Cover/body, form-tail, civil-defense/photo-grid semantic anchors, natural-sci late tail/picture pairing, and K-STAR recommendation anchor all have focused boards/status entries. | Semantic page pairing is good enough to guard; continue watching page counts and wrong-page anchors. |
| Major visual layout | partial / mostly guard-only | `photo_form24`, `photo_w31`, `accountability_eval`, and `15_3740450...` all have focused current boards and probes. | Remaining drift is mostly table/text/raster density or local visual composition, not missing images or straightforward table split bugs. |
| Text/raster appearance | blocked / probe | Current corpus audit after Gyeonggi, KoPub, Nanum Light, and EBS resource patches: bundled `161910` runs, CDN `54658`, missing/platform fallback `53458`, missing office faces `1643`, missing HY faces `227`. | Production-level visual fidelity still needs font/resource decisions and likely text-paint backend work; do not solve with global font-size/stroke knobs. |
| Export roundtrip | accepted-HWPX / probe-HWP-adapter | Current mutated export probe: 5/6 representative docs `HWPX_AND_HWP_RELOAD`; `45_form_grad_research_plan.hwpx` is confirmed binary HWP despite the `.hwpx` extension. | True-HWPX export/reload is acceptable for the tested structural fixes; binary-HWP-origin HWPX generation remains separate. |
| Regression safety | accepted-scope gated / broad tree still dirty | Accepted-scope gate rerun on 2026-06-09: font audit compile/probe, corpus font summary, `rhwp-studio` build, Rust fmt check, 6 focused Rust unit tests, overfit scan, `git diff --check`, and mutation export probe all passed or reproduced known probe-only status. | Safe to stage only the accepted patch scope; do not sweep in unrelated dirty renderer/harness experiments. |

Current all non-landscape review board after cached picture-anchor vpos patch:
`/tmp/diff/_review_all_nonlandscape_latest_2026-06-09c/index.html`.
Page counts are 21/22 matched; the only mismatch is the stale
`meeting_summary_font_fallback` duplicate (`Hancom=3`, `RHWP=0`), while the real
`meeting_summary` entry is 3/3.

Current font-aware all non-landscape review board after the review harness font
injection patch:
`/tmp/diff/_review_all_nonlandscape_fontaware_latest_2026-06-09/index.html`.
The board renders 22 docs and passes
`python3 harness/audit_review_gallery.py /tmp/diff/_review_all_nonlandscape_fontaware_latest_2026-06-09`.
Page counts remain 21/22 matched with the same stale
`meeting_summary_font_fallback` duplicate as the only mismatch. Landscape
`accountability_eval*` variants are intentionally skipped.

## Category Decisions

| category | row status | representative evidence |
|---|---|---|
| Cover/body title-band semantic split | accepted-semantic | `/tmp/diff/_review_fresh_comparable_post_cover_fix_2026-06-08/05_3781559_medschool_car_2bu_je_plan/index.html` |
| Form tail before explicit form page | accepted-semantic | `/tmp/diff/_review_fresh_comparable_tail_overflow_debug_2026-06-08/form_11_응시원서_자기소개서_48KB/index.html` |
| Photo/table page-count drift | guard-only/probe | `/tmp/diff/_review_photo_form24_pages61_66_current_2026-06-09/photo_form24/index.html` |
| Same-count semantic-anchor drift | accepted-semantic/probe-visual | `/tmp/diff/_review_09_tail_picture_pair_final_2026-06-09/09_3766093_natural_sci_planning_committee_260527/index.html` |
| Diagram/table geometry drift | accepted-semantic/probe-visual | `/tmp/diff/_review_kstar_pages1_4_current_2026-06-09/index.html` |
| K-STAR flowchart cell text | probe/rejected-broad-tweak | `work/FIDELITY_STATUS_KSTAR_FLOWCHART_CELL_TEXT_PROBE_2026-06-09.md`; representative `13_3763367_k_star_visa_track_plan:4` |
| Page-count / semantic drift | accepted-semantic | `photo_122p_civil_defense` now matches Hancom page count on the checked current board; visual drift remains. |
| Photo-grid / pre-grid | guard-only/probe-no-patch | `work/FIDELITY_STATUS_RESEARCH_ADMIN_PHOTO_GRID_P2_PROBE_2026-06-09.md`; refreshed board `/tmp/diff/_review_research_admin_photo_grid_p2_refresh_2026-06-09/index.html` |
| Dense financial table geometry/raster | guard-only/probe | `/tmp/diff/_review_photo_w31_page24_current_2026-06-09/index.html` |
| Cached picture anchor vpos | accepted-image-geometry | `work/FIDELITY_VISUAL_STATUS_PHOTO_FORM24_CACHED_PICTURE_VPOS_2026-06-09.md`; focused board `/tmp/diff/_review_photo_form24_p51_cached_vpos_candidate3_2026-06-09/index.html` |
| Text/table raster density | probe/rejected-broad-tweak/blocked-backend | `work/FIDELITY_STATUS_TEXT_TABLE_RASTER_DENSITY_PROBE_2026-06-09.md`; representatives `photo_w31:24`, `photo_form24:7`, `overseas_training:1`, `meeting_summary:1`; native-Skia backend probe built but rejected because Korean text replay is incomplete. |
| Review harness SVG font parity | accepted-harness | `harness/review_gallery.py` now injects temporary data-URI `@font-face` rules from `rhwp-studio/src/core/font-loader.ts` into SVG copies before Playwright rasterization. |
| Civil-defense grouped cell image geometry | probe/rejected-candidate | `work/FIDELITY_STATUS_CIVIL_DEFENSE_GROUPED_CELL_IMAGE_PROBE_2026-06-09.md`; current board `/tmp/diff/_review_civil_defense_p76_grouped_container_probe_current_2026-06-09/index.html` |
| CellBreak carried rowspan / table raster | guard-only/rejected-patch | `work/FIDELITY_STATUS_ACCOUNTABILITY_CELLBREAK_ROWSPAN_GUARD_2026-06-09.md`; refreshed board `/tmp/diff/_review_accountability_p4_refresh_2026-06-09/index.html` |
| Table-text-raster | blocked-font-resource/probe | `/tmp/diff/FONT_RESOURCE_AUDIT_ALL_CURRENT_2026-06-09.tsv` |
| Garamond text/raster resource | blocked-font-resource/rejected-broad-substitution | `/tmp/diff/FIDELITY_STATUS_GARAMOND_RESOURCE_BLOCKED_2026-06-09.md` |
| Hancom Gothic text/raster resource | blocked-font-resource/rejected-broad-substitution | `/tmp/diff/FIDELITY_STATUS_HANCOM_GOTHIC_RESOURCE_BLOCKED_2026-06-09.md` |
| Gyeonggi text/raster resource | accepted-resource/probe-visual | `work/FIDELITY_STATUS_GYEONGGI_RESOURCE_ACCEPTED_2026-06-09.md` |
| KoPub text/raster resource | accepted-resource/probe-visual | `work/FIDELITY_STATUS_KOPUB_RESOURCE_ACCEPTED_2026-06-09.md` |
| Nanum Gothic Light text/raster resource | accepted-resource/probe-visual | `work/FIDELITY_STATUS_NANUM_LIGHT_RESOURCE_ACCEPTED_2026-06-09.md` |
| EBS text/raster resource | accepted-resource/probe-source-missing | `work/FIDELITY_STATUS_EBS_RESOURCE_ACCEPTED_SOURCE_MISSING_2026-06-09.md` |
| Yoon text/raster resource | blocked-font-resource/rejected-broad-substitution | `work/FIDELITY_STATUS_YOON_RESOURCE_BLOCKED_2026-06-09.md` |
| Soonchunhyang text/raster resource | blocked-font-resource/source-missing/rejected-broad-substitution | `work/FIDELITY_STATUS_SOONCHUNHYANG_RESOURCE_BLOCKED_2026-06-09.md` |
| Office/HY/Hancom residual text/raster resources | blocked-font-resource/rejected-broad-substitution | `work/FIDELITY_STATUS_OFFICE_HY_RESOURCE_BLOCKED_2026-06-09.md` |
| GulimChe fallback text/raster | probe/blocked-font-resource/rejected-broad-substitution | `work/FIDELITY_STATUS_GULIMCHE_FALLBACK_PROBE_2026-06-09.md`; representative `04_3781571_car_2bu_je_notice:2` |
| SNU notice footer template | guard-only/probe-no-patch | `work/FIDELITY_STATUS_SNU_NOTICE_FOOTER_TEMPLATE_PROBE_2026-06-09.md`; representative `18_3728528_research_fund_repayment_request:1` |
| CellBreak final-row table tail | accepted/structural-patch | `work/FIDELITY_STATUS_FORM01_CELLBREAK_FINAL_ROW_PROBE_2026-06-09.md`; representative `form_01_교수법_과제양식_코다이_49KB:1-2` |
| Natural-sci agenda cover overlap | probe/partial-textbox-improvement/blocked-layout | `work/FIDELITY_STATUS_NATURAL_SCI_AGENDA_COVER_PROBE_2026-06-09.md`; current clean board `/tmp/diff/_review_09_current_probe_clean_2026-06-09/index.html`; representative `09_3766093_natural_sci_planning_committee_260527:1` |
| Clean guard | guard | `report_form` remains page-count clean and low-risk guard. |
| Export roundtrip | accepted-HWPX/probe-HWP-adapter | `/tmp/hwp-export-roundtrip-probe-mutated-current-2026-06-09/summary.txt`; `work/FIDELITY_STATUS_EXPORT_MISNAMED_HWP_TO_HWPX_PROBE_2026-06-09.md` |

## Remaining Work

1. Commit-readiness is proven only for the accepted patch scope. The dirty worktree still includes many unrelated pre-existing changes; a commit should stage only the accepted font/audit/serializer/export files plus this gate documentation.
2. Text/raster fidelity remains the largest production visual blocker. Required next input is resource/backend strategy, not another layout tweak: Yoon, Garamond, residual Office/HY/Hancom faces, and source-missing fixtures are still blocked; Gyeonggi, KoPub, Nanum Gothic Light, and EBS Jushigyeong Light are accepted resource patches.
3. `wild_02_paper_fig_10MB` cannot be current-validated because `/tmp/diff/wild_02_paper_fig_10MB/source.hwpx` / `source.hwp` is missing.
4. Visual guard rows should stay as guards unless a new structural discriminator appears. Current probes rejected broad image shifts, font-size scaling, stroke thickening, and table-height knobs.

## Current No-Patch Conclusions

- `accountability_eval:4`: lower continuation fragment is present on current code (`RHWP raster band y=56.7..733.0`, bottom line `735.7`). Remaining drift is wide landscape table row-height distribution plus light/small text/rule raster; broad font-size/font-family/stroke/y-shift tweaks are rejected, and landscape pages are deprioritized.
- `photo_w31:24`: dense table drift is text/rule raster density; no images, no missing font resource, no safe table-height patch.
- `15_3740450...:2`: all images are present and the document remains page-count clean. Fresh component probing rejects broad image shifts, font-size changes, stroke tweaks, and crop/height changes; remaining drift is mixed text/rule density plus local table-cell picture composition, not a safe structural patch target.
- `09_3766093...:30`: Garamond resource missing; broad font substitutions are not acceptable renderer rules.
- `09_3766093...:30-33`: Garamond is the highest-impact available-source missing Latin serif resource. Page 30 has 1870 Garamond runs; component probe is text-owned (`base=19.47`, `hide_text=7.28`, `hide_lines=7.28`) and line/stroke/image variants are no-ops. Do not map `Garamond` to an unrelated bundled face; future promotion requires a licensed Garamond-compatible web resource or explicit product fallback policy with guard pages.
- `photo_w31:2/6`: `한컴 고딕` is a repeated missing office face (`317` and `355` runs). Page count is clean (`photo_w31` 30/30, `report_form` 6/6), geometry has no image/page-split owner, and component probe is text-owned (`base=25.83`, `hide_text=13.21`, `hide_lines=13.37`). Do not map `한컴 고딕` to Noto/Pretendard/AppleGothic without an explicit licensed resource or product fallback policy.
- `overseas_training:1-3`: `경기천년*` is no longer a blocked resource. Official Gyeonggi webfont WOFFs are bundled and exact emitted family names resolve in the resource audit. Keep the broader text/raster row in `probe` because static SVG review artifacts still do not fully prove browser webfont paint parity.
- `photo_122p_civil_defense:110/124` and `form_17:4`: `KoPub*` is no longer a blocked resource. Original KOPUS TTFs are bundled with the license file, exact emitted aliases resolve in the resource audit, and guard page counts hold. Keep the broader text/raster row in `probe` because this intentionally does not solve Yoon/Garamond/Hancom/Nanum-Light resource gaps.
- `form_17:1/4/6/7`: `나눔고딕 Light` is no longer a blocked resource. The WOFF2 resource is bundled, exact emitted aliases resolve in the audit, Rust metrics map to `NanumGothic Light`, and guard page counts hold.
- `wc35_15pg:1/2/3/7/8/9`: `EBS전용서체-L` is no longer a blocked resource. Official EBS Jushigyeong Light TTF is bundled and exact emitted aliases resolve in the audit. Category promotion remains blocked by missing `wc35_15pg` source artifact.
- `photo_122p_civil_defense`: Yoon families remain blocked. The current audit shows `-윤명조320` 16269 runs and `-윤고딕320` 14705 runs, with no local resources and no acceptable broad substitute. Future progress needs licensed Yoon resources or an explicit product fallback policy.
- `wc15_7pg/wc16_6pg/wc17_6pg`: `순천향체` remains blocked. Historical public references exist, but no current official redistributable artifact/license was verified, and the source files for these representatives are missing from `/tmp/diff`, so focused side-by-side promotion cannot run.
- `photo_w31`, `09_3766093...`, `photo_form24`, `internship_plan`, `wb17_library_report_13pg`, and `overseas_training:4`: residual Office/HY/Hancom faces remain blocked. The current audit shows `한컴 고딕` 1329 runs, `휴먼둥근헤드라인` 304, `HY울릉도M` 201, `한컴산뜻돋움` 182, and smaller HY/Hancom misses. No exact local resources or clean redistributable sources were verified; broad aliases are rejected.
- `photo_form24:51`: cached picture-anchor vpos is accepted. The large non-TAC `TopAndBottom` picture now aligns to Hancom (`RHWP image y=141.3..697.1`; Hancom raster band `140.7..697.2`) by suppressing stale spacer/host-line vpos only for the structural `TAC table -> tiny empty spacers -> picture-only paragraph` class. Neighboring pages still have pre-existing text/table density drift.
- `photo_w31:24` and `photo_form24:7`: text/table raster density remains probe-only. Component probes show text/rule ownership, but broad stroke, font-size, font-family, image, and regional y-shift variants are rejected because gains are modest or non-structural and would risk guard pages. See `work/FIDELITY_STATUS_TEXT_TABLE_RASTER_DENSITY_PROBE_2026-06-09.md`.
- `overseas_training:1`: Gyeonggi fonts are now available, but the remaining mismatch is still text/rule raster density. SVG geometry has no images; component probes reject stroke/font-size/font-family/y-shift knobs; browser raster has fewer dark pixels than Hancom at low thresholds and more light-gray antialiasing at high thresholds. Native-Skia now builds, but its current Korean text replay is too incomplete to promote.
- `meeting_summary:1`: page count is clean and table band geometry is broadly aligned, but text/rule raster density remains visibly off. Component probes reject the same broad fixes (`font_size_x0.90` only `19.34 -> 18.60`; common font substitutions only `18.83..18.99`; strokes/y-shifts do not solve it).
- Native-Skia backend probe: release build with `--features native-skia` succeeds, but the backend is not promotable. It under-renders Korean text heavily even with explicit bundled WOFF/WOFF2 and user-local Noto/Nanum TTF font paths. `meeting_summary:1` scalar diff improves (`19.34 -> 15.60`) only because most text disappears/lightens; `photo_w31:24` worsens (`28.04 -> 28.43`). Treat this as a native text/font replay blocker, not a production rendering fix.
- Text advance probe: browser SVG emits one `<text>` per visible character with explicit x positions. `meeting_summary:1` shows expanded line steps, but the clean guard `report_form:2` shows the same `1.32` median step/font-size pattern, so broad Korean/Noto advance scaling is rejected. Future work needs a narrower justification/cell-context invariant, not a global metrics knob.
- Line-advance normalization artifact probe: forcing expanded one-character SVG lines toward fixed step/font ratios gives only tiny target improvement (`meeting_summary:1` best `19.34 -> 19.28`) and visibly breaks text flow. It also affects guards (`report_form:2` changes `12.63 -> 12.56`), so this is rejected as a broad coordinate tweak rather than a renderer rule.
- Review harness font parity is accepted as a harness fix, not a renderer fix.
  Static SVGs are screenshot as `<img src=file://...>`, so outer-page CSS cannot
  affect internal SVG font resolution. The board now injects a temporary
  data-URI `@font-face` block for registered local web fonts before rasterizing;
  this better matches the live `rhwp-studio` iframe font-loading path and avoids
  chasing false font drift.
- `photo_122p_civil_defense:76`: grouped table-cell image composition remains
  probe-only. The source cell is a `hp:container` with four child pictures,
  parent/child affine transforms, and child crops. A narrow crop-metadata
  candidate was rejected because it expanded one child image outside the cell.
  Future work needs grouped-picture composition under the table-cell clip, not
  global image shifts or broad crop changes.
- `45_form_grad_research_plan.hwpx`: export-roundtrip failure is
  HWP-adapter-only, not true-HWPX roundtrip. The source is binary HWP by magic
  bytes (`d0 cf 11 e0`) despite the `.hwpx` extension; generated HWPX reloads to
  55 pages while generated HWP reloads to 41 pages. Keep this as a dedicated
  binary-HWP-origin HWPX generation probe.
- `13_3763367_k_star_visa_track_plan:4`: K-STAR flowchart cell text remains
  probe-only. The representative is a nested 3-row x 13-column flowchart table
  with narrow `▶` spacer columns and no cell lineSeg arrays. Component probing
  shows text/table ownership (`base=21.87`, `hide_text=14.75`,
  `hide_lines=15.65`), but broad fixes are rejected: `font_size_x0.90` only
  moves the target to `20.44` and also moves the guard (`report_form:2`
  `12.63 -> 12.25`), while stroke, font-family, y-shift, and line-advance
  variants either regress or are neutral. Future work needs a narrow
  cell-text wrapping/clipping invariant for flowchart tables, not global text
  tuning.
- `04_3781571_car_2bu_je_notice:1-2`: `굴림체` fallback remains probe-only.
  The document is page-count clean (`2/2`) with images/logos present, but the
  body text is dominated by `굴림체` currently mapped to
  `D2Coding-Regular.woff2` (`986` runs across the representative). Component
  probing on page 2 is text-owned (`base=8.91`, `hide_text=5.11`), but common
  substitutes are only modest scalar changes (`AppleGothic=8.41`,
  `Pretendard=8.49`, `Noto Sans KR=8.84`) and broad font-size/y-shift knobs
  also move guards. Do not change global `굴림체` mapping without an exact
  redistributable Gulim/GulimChe resource or explicit fallback policy.
- `18_3728528_research_fund_repayment_request:1`: SNU notice footer template is
  guard/probe-only. The page is semantically correct and `1/1`, with the SNU
  logo present. Remaining drift is footer/contact template placement plus
  text/raster density. Source tables include a `14x32` `TOP_AND_BOTTOM` footer
  table, a `14x32` `IN_FRONT_OF_TEXT` overlay-style table, and a `BEHIND_TEXT`
  support table. Narrow probing rejects broad fixes: `shift_y_after_430_p12`
  improves target (`9.89 -> 9.06`) but regresses `report_form:2`
  (`12.63 -> 12.89`), while font-size and font-family substitutions are covered
  by the broader text/fallback categories. Future work needs a structural
  page-bottom/footer anchoring invariant before patching.
- `form_01_교수법_과제양식_코다이_49KB:1-2`: CellBreak final-row table tail is
  accepted as a narrow structural patch. Hancom and RHWP both render `2/2`.
  Before the patch, Hancom page 2 carried a small table continuation above the
  evaluation paragraph while RHWP page 2 had no table lines. The accepted rule
  keeps the continuation path for non-TAC `TopAndBottom` HWPX `CELL` repeated
  header tables whose final row has a zero declared-height cell with measured
  text content. After the patch, `dump-pages` shows page 2 containing
  `PartialTable pi=4 ci=0 rows=20..22 cont=true start_cut=[1, 1, 2, 2, 1]`
  before the evaluation paragraph. Remaining visual drift is table/text
  geometry, not missing semantic continuation.
- `09_3766093_natural_sci_planning_committee_260527:1`: natural-sci agenda
  cover overlap remains probe-only. The current export is page-count clean
  (`51/51`) and focused gallery audit passes. A TextBox `vertAlign=CENTER`
  fallback using composed line metrics improves the title/date area for
  no-lineSeg nested drawText boxes, but page 1 still overlaps agenda label
  rectangles and agenda body rows, including one full-width row emitted off the
  right edge. Related high-drift pages split into existing buckets: page 17 is
  dense table/text raster, page 22 includes residual office-face and off-page
  table geometry, and page 49 has a closely aligned image with remaining
  text/label drift. Rejected candidates: no-lineSeg `InFrontOfText` flow
  reservation and empty-runs full-width TAC stacking. Do not use global
  y-shifts or font scaling; future work needs a narrow inline TAC/text-run
  geometry invariant.

## Fresh Accepted-Scope Validation

- `python3 -m py_compile harness/svg_font_resource_audit.py`
- `python3 harness/svg_font_resource_audit.py 13_3763367_k_star_visa_track_plan:1 photo_w31:2 overseas_training:1 report_form:2`
- `python3 harness/svg_font_resource_audit.py --all --summary > /tmp/diff/FONT_RESOURCE_AUDIT_ALL_CURRENT_2026-06-09.tsv`
- `cd rhwp-studio && npm run build`
- `docker compose --env-file .env.docker run --rm dev cargo fmt --check -- src/renderer/font_metrics_data.rs src/serializer/hwpx/section.rs src/serializer/hwpx/shape.rs src/serializer/hwpx/picture.rs src/serializer/hwpx/table.rs`
- focused Rust tests: `nanum_weight_aliases_map_to_bundled_metrics`, `write_section_regenerates_following_paragraph_after_dirty_paragraph`, `write_section_preserves_following_raw_paragraph_when_linesegs_match_ir`, `rect_pos_preserves_flow_and_overlap_flags`, `pic_pos_preserves_flow_and_overlap_flags`, `tbl_pos_preserves_flow_and_overlap_flags`
- `python3 scripts/check_renderer_overfit.py`
- `git diff --check -- <accepted scope>`
- mutation export probe: `/tmp/hwp-export-roundtrip-probe-mutated-current-2026-06-09/summary.txt` (`5/6 HWPX_AND_HWP_RELOAD`; `45_form_grad_research_plan.hwpx` remains known `HWPX_PAGE_DRIFT` / source-HWP-adapter probe)
- Gyeonggi resource probe: `python3 harness/svg_font_resource_audit.py overseas_training:1 overseas_training:2 overseas_training:3 report_form:2`
- Gyeonggi focused review: `/tmp/diff/_review_gyeonggi_resource_overseas_training_2026-06-09/index.html`
- KoPub resource probe: `python3 harness/svg_font_resource_audit.py wild_02_paper_fig_10MB:1 wild_02_paper_fig_10MB:3 photo_122p_civil_defense:110 photo_122p_civil_defense:124 form_17_융합전공신청서_운영계획서_81KB:4 report_form:2`
- KoPub focused reviews: `/tmp/diff/_review_kopub_resource_photo122_2026-06-09/index.html`, `/tmp/diff/_review_kopub_resource_form17_2026-06-09/index.html`
- Nanum Light resource probe: `python3 harness/svg_font_resource_audit.py form_17_융합전공신청서_운영계획서_81KB:1 form_17_융합전공신청서_운영계획서_81KB:4 form_17_융합전공신청서_운영계획서_81KB:6 form_17_융합전공신청서_운영계획서_81KB:7 report_form:2`
- Nanum Light focused review: `/tmp/diff/_review_nanum_light_resource_form17_2026-06-09/index.html`
- EBS resource probe: `python3 harness/svg_font_resource_audit.py wc35_15pg:1 wc35_15pg:2 wc35_15pg:3 wc35_15pg:7 wc35_15pg:8 wc35_15pg:9 report_form:2`
- EBS source check: `/tmp/diff/FIDELITY_STATUS_EBS_GUARDS_2026-06-09.md`
- Soonchunhyang blocked probe: `python3 harness/svg_font_resource_audit.py wc15_7pg:7 wc15_7pg:6 wc16_6pg:6 wc17_6pg:4 report_form:2`
- Soonchunhyang source check: `/tmp/diff/FIDELITY_STATUS_SOONCHUNHYANG_GUARDS_2026-06-09.md`
- Cached picture-anchor vpos test/build: `cargo fmt --check`, `cargo test --lib renderer::layout::tests::cached_picture_anchor_vpos_skips_only_after_tiny_spacer_run_and_tac_table -j 1`, `cargo build --release --bin rhwp -j 1`
- Cached picture-anchor vpos boards: `/tmp/diff/_review_photo_form24_p51_cached_vpos_candidate3_2026-06-09/index.html`, `/tmp/diff/_review_photo_form24_cached_vpos_guard_2026-06-09/index.html`, `/tmp/diff/_review_photo_w31_cached_vpos_guard_2026-06-09/index.html`, `/tmp/diff/_review_report_form_cached_vpos_guard_2026-06-09/index.html`
- Text/table raster density probes: `svg_geometry_probe.py photo_form24:7 photo_form24:50 photo_w31:24`, `svg_font_resource_audit.py photo_form24:7 photo_form24:50 photo_w31:24 report_form:2`, `svg_component_probe.py --keep ... photo_form24:7 photo_w31:24`, `table_boundary_probe.py photo_w31:24`, `table_boundary_probe.py photo_form24:7`, `svg_line_region_probe.py photo_w31:24 --y-min 128 --y-max 1006 --keep`, `hwpx_table_source_probe.py /tmp/diff/photo_w31 --list`, `hwpx_table_source_probe.py /tmp/diff/photo_form24 --list`
- Font-aware board validation: `python3 -m py_compile harness/review_gallery.py harness/review_pages.py harness/review_page_pairs.py harness/svg_font_face_probe.py`, focused boards `/tmp/diff/_review_font_harness_probe_2026-06-09/index.html` and `/tmp/diff/_review_font_harness_probe_w31_2026-06-09/index.html`, full board `/tmp/diff/_review_all_nonlandscape_fontaware_latest_2026-06-09/index.html`, and gallery audit `PASS: no gallery truncation/aspect issues across 22 doc(s)`.
- form_01 CellBreak zero-height final-tail patch: `cargo test --lib --release final_split_table_subline_tail_can_be_clipped_without_continuation_page -j 1`, `cargo build --release --bin rhwp -j 1`, focused board `/tmp/diff/_review_form01_cellbreak_zeroheight_tail_candidate_2026-06-09/index.html`, focused audit `PASS: no gallery truncation/aspect issues across 3 doc(s)`, broad non-landscape board `/tmp/diff/_review_all_nonlandscape_after_form01_tail_2026-06-09/index.html`, broad audit `PASS: no gallery truncation/aspect issues across 22 doc(s)`, `python3 scripts/check_renderer_overfit.py`, and `git diff --check -- src/renderer/typeset.rs`.
- Natural-sci agenda cover probe cleanup: `git diff --check -- src/renderer/layout/shape_layout.rs src/renderer/typeset.rs`, `docker compose --env-file .env.docker run --rm dev cargo build --release --bin rhwp -j 1`, focused board `/tmp/diff/_review_09_current_probe_clean_2026-06-09/index.html`, focused audit `PASS: no gallery truncation/aspect issues across 3 doc(s)`, and `python3 harness/svg_geometry_probe.py 09_3766093_natural_sci_planning_committee_260527:1`.
