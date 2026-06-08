# RHWP Production Readiness Board -- 2026-06-08

Purpose: turn the long fidelity loop into finite production gates. This board
is the decision surface; detailed probes remain in the category-specific notes.

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
| Export roundtrip | exported HWPX reopens in Hancom/RHWP with stable pages and no structural loss | not started | build export-oracle lane after render gate stabilizes |
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

## Current Category Decisions

| category | representative docs | status | before/after | remaining risk | ship/block | next command |
|---|---|---|---|---|---|---|
| Cover/body title-band semantic split | `05_3781559_medschool_car_2bu_je_plan` | accepted-semantic | RHWP `3 -> 4` pages vs Hancom `4`; page 1 no longer leaks body title band, page 2 starts with title band + `□ 추진 배경` | cover geometry/font/table-stroke drift remains; this is not a text/raster or cover-position fix | not a semantic blocker; keep as guard for cover/body page split | open `/tmp/diff/_review_fresh_comparable_post_cover_fix_2026-06-08/05_3781559_medschool_car_2bu_je_plan/index.html` |
| Form tail before explicit form page | `form_11_응시원서_자기소개서_48KB` | accepted-semantic | RHWP `2 -> 3` pages vs Hancom `3`; final note moves to sparse page 2 and `자기소개서` starts page 3 | table/rule/font density still differs; this is not a raster appearance fix | not a semantic blocker; keep as guard for HWPX form tail/page-break split | open `/tmp/diff/_review_fresh_comparable_tail_overflow_debug_2026-06-08/form_11_응시원서_자기소개서_48KB/index.html` |
| Photo/table page-count drift | `photo_form24` | accepted-pagecount/visual-probe | Tail-guard combo keeps the one-line tail before the explicit title-table page break and defers the following late heading/spacer/CELL TAC table. The next accepted local fix preserves the Hancom blank page before the `유학생 특화형` explicit top-reset paragraph and applies a narrow near-top heading reset for the following `성과관리` subsection. The later contact-table fix moves the small contact/signoff CELL TAC table after the large performance table spacer tail onto its own page before the next explicit section title. The latest accepted local fix handles the exact two-bottom-spacer variant of the same small 2x3 CELL TAC contact table before an explicit section title, while rejecting one-spacer and long-spacer-without-large-table forms. Fresh all-nonlandscape board now renders Hancom `89` / RHWP `89`. | page count alone is not a safe acceptance signal. Picture/table scale, vertical geometry, contact-table rule/font weight, and possible section-anchor drift remain visible. Previous broader terminal-contact candidates reached `89/89` but inserted pages at the wrong visual location and remain rejected. | no longer a page-count blocker; keep as visual/anchor probe | open `/tmp/diff/_review_all_nonlandscape_latest_2026-06-08/photo_form24/index.html`; inspect pages 50-52 and 66-69 before changing Rust |
| Same-count semantic-anchor drift | `09_3766093_natural_sci_planning_committee_260527` | probe-rejected/no-patch | Cached cell-vpos reset policy collapses the repeated-header minutes table from many tiny fragments; RHWP `57 -> 51` vs Hancom `51`; fresh full board keeps total page count aligned. However page 50 pairs different content: Hancom is still on the prior image/table section while RHWP has already started the NEXT Lab report. A narrow late-reference-before-explicit-title overflow probe around `pi547` was a no-op on the real dump. | this is not solved by page count. The visible `pi547` singleton is probably a symptom, not the structural owner. Needs a deeper owner in cumulative table/image split or title-shape/page-break modeling before Rust changes are justified. | not promoted; keep as semantic drift probe/guard | open `/tmp/diff/_review_all_nonlandscape_latest_2026-06-08/09_3766093_natural_sci_planning_committee_260527/index.html`; use heading maps around pages 46-50 as diagnostic only, then move to a more structural visual target unless a reusable owner appears |
| Diagram/table geometry drift | `13_3763367_k_star_visa_track_plan` | accepted-semantic/probe-visual | Page count is stable at 21/21. A narrow keep-with-next rule moves the late `2. 추천 절차` heading from RHWP page 3 to page 4 when it is followed by a 3-6 item procedure list and a wide multi-cell HWPX CELL TAC table. Anchor map now matches Hancom for `2. 추천 절차` and `3. 추천서 발급 및 관리`. | internal flowchart/table drawing is still visibly wrong: merged-cell text overlaps, table/rule weights differ, and the diagram is compressed. This patch fixes semantic page pairing, not diagram raster fidelity. `photo_form24` remains 89/88 in the current dirty tree, but `RHWP_FLOWCHART_KEEP_DEBUG` showed this new rule does not trigger there. | promote semantic anchor only; keep visual geometry open | open `/tmp/diff/_review_kstar_flowchart_candidate_narrow_2026-06-08/13_3763367_k_star_visa_track_plan/index.html`; inspect pages 4-5 |
| Page-count / semantic drift | `photo_122p_civil_defense`, `form_07`, `photo_w31`, `internship_plan` | accepted-semantic | civil-defense now 129/129 vs Hancom | visual drift remains on some pages | not a blocker if human review accepts semantic layout | `python3 harness/heading_drift_scan.py photo_122p_civil_defense --dump /tmp/diff/photo_122p_civil_defense/dump_pages_tail_group_candidate3.txt` |
| Photo-grid / pre-grid | `photo_122p_civil_defense`, `photo_w31`, `15_3740450_research_admin_innovation_meeting_template` | accepted for semantic anchors, probe for visual | page anchors aligned on civil-defense | sizing, spacing, glyph/rule weight | guard, not active unless new semantic drift appears | open `/tmp/diff/_review_civil_defense_tail_group_candidate_2026-06-08/index.html` |
| CellBreak carried rowspan | `accountability_eval` | probe-no-patch | page count 6/6; page 4 still misses lower band | owner is `rowspan_touched`; naive top-slice prototypes were no-op | not a current ship blocker if acceptable visually; keep as known risk | `python3 harness/svg_geometry_probe.py accountability_eval:4` |
| Table-text-raster | `overseas_training`, `meeting_summary`, `form_07` | guard-only/open | broad SVG/font/stroke/fill knobs rejected | dark ink/text/rule density remains off | potential production quality blocker | `python3 harness/raster_backend_probe.py overseas_training:1 --native --region focus:X0,Y0,X1,Y1` |
| Clean guard | `report_form` | guard | page count and visual score below drift threshold | none currently | pass | `python3 harness/fidelity_category_status.py --with-gallery report_form` |
| Export roundtrip | exported HWPX from edited docs | not-started | no gate yet | exported file may not reopen faithfully | blocker before editor production | define roundtrip harness with Hancom/RHWP reopen |

## Rejected Probes

- `photo_form24` title-table contact probe after `b3986582`: allowing a long
  blank-tail 2x3 CELL TAC contact table to move when the following explicit
  paragraph contains a 1-row TAC title table fixed the `AI 교육지원센터` section
  and made total page count `89/89`, but it shifted Hancom pages 66-70 one page
  late (`+1`) and the focused page 60-68 board paired unrelated content on page
  66. Rejected; the remaining issue is not safely solved by another broad
  contact-table deferral. Next structural owner is the large table/appendix
  split around `pi1107` through `pi1116`.
- `09_3766093` late-reference overflow probe: the drift begins when Hancom keeps
  the `[참고] 붙임 11...` one-line reference at the bottom of page 46 but RHWP
  emits it alone on page 47, shifting following anchors by `+1` until the later
  NEXT Lab section catches up. Synthetic probes that allowed this one-line
  reference to use a bounded bottom-margin allowance before an explicit
  title/shape break were rejected because all real dumps stayed unchanged,
  including `dump_pages_late_reference_title_shape_candidate4_2026-06-08.txt`.
  Debug logs showed the expected following shape was not visible to that
  predicate path, so accepting the rule would be speculative and unguarded.

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

1. Human-review `/tmp/diff/_review_fresh_comparable_tail_overflow_debug_2026-06-08/index.html`.
2. Treat `05_3781559_medschool_car_2bu_je_plan`, `form_11_응시원서_자기소개서_48KB`,
   and civil-defense as `accepted-semantic, visual-drift-remaining` unless
   human review finds a production-blocking layout issue.
3. For render fidelity, do not chase total page count next; the fresh
   non-landscape board is page-count clean. Continue with either:
   - `09_3766093...` pages 49-50 as same-count semantic-anchor drift; or
   - `13_3763367...` page 4 as structural diagram/table geometry drift.
   Keep `photo_form24`, `photo_w31`, and `overseas_training` as visual guards
   against broad scale/font/stroke tweaks.
4. Start export roundtrip harness if production editing/export is the priority.
5. Otherwise start table-text-raster/backend fidelity, because that is now the
   largest remaining visual quality bucket.
