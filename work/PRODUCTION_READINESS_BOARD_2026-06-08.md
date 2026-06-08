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

## Current Category Decisions

| category | representative docs | status | before/after | remaining risk | ship/block | next command |
|---|---|---|---|---|---|---|
| Cover/body title-band semantic split | `05_3781559_medschool_car_2bu_je_plan` | accepted-semantic | RHWP `3 -> 4` pages vs Hancom `4`; page 1 no longer leaks body title band, page 2 starts with title band + `□ 추진 배경` | cover geometry/font/table-stroke drift remains; this is not a text/raster or cover-position fix | not a semantic blocker; keep as guard for cover/body page split | open `/tmp/diff/_review_fresh_comparable_post_cover_fix_2026-06-08/05_3781559_medschool_car_2bu_je_plan/index.html` |
| Form tail before explicit form page | `form_11_응시원서_자기소개서_48KB` | accepted-semantic | RHWP `2 -> 3` pages vs Hancom `3`; final note moves to sparse page 2 and `자기소개서` starts page 3 | table/rule/font density still differs; this is not a raster appearance fix | not a semantic blocker; keep as guard for HWPX form tail/page-break split | open `/tmp/diff/_review_fresh_comparable_tail_overflow_debug_2026-06-08/form_11_응시원서_자기소개서_48KB/index.html` |
| Page-count / semantic drift | `photo_122p_civil_defense`, `form_07`, `photo_w31`, `internship_plan` | accepted-semantic | civil-defense now 129/129 vs Hancom | visual drift remains on some pages | not a blocker if human review accepts semantic layout | `python3 harness/heading_drift_scan.py photo_122p_civil_defense --dump /tmp/diff/photo_122p_civil_defense/dump_pages_tail_group_candidate3.txt` |
| Photo-grid / pre-grid | `photo_122p_civil_defense`, `photo_w31`, `15_3740450_research_admin_innovation_meeting_template` | accepted for semantic anchors, probe for visual | page anchors aligned on civil-defense | sizing, spacing, glyph/rule weight | guard, not active unless new semantic drift appears | open `/tmp/diff/_review_civil_defense_tail_group_candidate_2026-06-08/index.html` |
| CellBreak carried rowspan | `accountability_eval` | probe-no-patch | page count 6/6; page 4 still misses lower band | owner is `rowspan_touched`; naive top-slice prototypes were no-op | not a current ship blocker if acceptable visually; keep as known risk | `python3 harness/svg_geometry_probe.py accountability_eval:4` |
| Table-text-raster | `overseas_training`, `meeting_summary`, `form_07` | guard-only/open | broad SVG/font/stroke/fill knobs rejected | dark ink/text/rule density remains off | potential production quality blocker | `python3 harness/raster_backend_probe.py overseas_training:1 --native --region focus:X0,Y0,X1,Y1` |
| Clean guard | `report_form` | guard | page count and visual score below drift threshold | none currently | pass | `python3 harness/fidelity_category_status.py --with-gallery report_form` |
| Export roundtrip | exported HWPX from edited docs | not-started | no gate yet | exported file may not reopen faithfully | blocker before editor production | define roundtrip harness with Hancom/RHWP reopen |

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
3. For render fidelity, pick the next unresolved non-landscape mismatch:
   `photo_form24` page-count drift (`89/86`) if image/table pagination is
   priority, or `accountability_eval` page-4 lower-band clipping if table
   fragment visual fidelity is priority.
4. Start export roundtrip harness if production editing/export is the priority.
5. Otherwise start table-text-raster/backend fidelity, because that is now the
   largest remaining visual quality bucket.
