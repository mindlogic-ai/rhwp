# Photo-grid source guard scan -- 2026-06-08

Candidates:
      61 /tmp/rhwp_guard_hwpx_candidates.txt

Matches:
15_3740450_research_admin_innovation_meeting_template	3	6x2	TOP_AND_BOTTOM	CELL	1	4	3	1	1		r2c0N,r2c1T,r5c0T,r5c1T
15_3740450_research_admin_innovation_meeting_template	4	4x2	TOP_AND_BOTTOM	CELL	1	4	0	4	0	r2c0:v-226.8;r3c0:v-0.7	r2c0N,r2c1N,r3c0N,r3c1N
15_3740450_research_admin_innovation_meeting_template	6	3x2	TOP_AND_BOTTOM	CELL	1	4	0	4	0	r1c0:v-62.0	r1c0N,r1c1N,r2c0N,r2c1N
# matches=3

## CellBreak Rowspan Guard Scan

Goal: find independent guard documents before retrying the
`accountability_eval` carried-rowspan / blank-separator patch family.

Candidate set:

```text
61 /tmp/rhwp_guard_hwpx_candidates.txt
```

Source-only prefilter:

```bash
python3 harness/cellbreak_source_scan.py $(cat /tmp/rhwp_guard_hwpx_candidates.txt)
```

Source-level matches found:

```text
03_3781727_staff_evaluation_table
04_3781571_car_2bu_je_notice
09_3766093_natural_sci_planning_committee_260527
13_3763367_k_star_visa_track_plan
18_3728528_research_fund_repayment_request
20_3727659_resume_2605_ai
accountability_eval
internship_plan
meeting_summary
multicultural_plan
report_form
research_form
form_01_교수법_과제양식_코다이_49KB
form_11_응시원서_자기소개서_48KB
form_17_융합전공신청서_운영계획서_81KB
```

Interpretation: several local docs contain `pageBreak="CELL"` tables with
rowspans, blank rows, and plausible split rows. This is only a prefilter; it
does not prove those docs exercise the runtime continuation class.

Runtime dump shortlist staged:

```text
/tmp/diff/03_3781727_staff_evaluation_table
/tmp/diff/04_3781571_car_2bu_je_notice
/tmp/diff/09_3766093_natural_sci_planning_committee_260527
/tmp/diff/13_3763367_k_star_visa_track_plan
/tmp/diff/18_3728528_research_fund_repayment_request
/tmp/diff/20_3727659_resume_2605_ai
/tmp/diff/internship_plan
/tmp/diff/multicultural_plan
/tmp/diff/research_form
/tmp/diff/form_01_교수법_과제양식_코다이_49KB
/tmp/diff/form_11_응시원서_자기소개서_48KB
/tmp/diff/form_17_융합전공신청서_운영계획서_81KB
```

Dump command shape:

```bash
docker compose --env-file .env.docker run --rm -v /tmp/diff:/diff \
  dev /app/target/release/rhwp dump-pages /diff/DOC/source.hwpx \
  > /tmp/diff/DOC/dump_pages_current.txt
```

Runtime continuation scan:

```bash
python3 harness/cellbreak_rowspan_scan.py --min-slack 0.0 \
  /tmp/diff/03_3781727_staff_evaluation_table \
  /tmp/diff/04_3781571_car_2bu_je_notice \
  /tmp/diff/09_3766093_natural_sci_planning_committee_260527 \
  /tmp/diff/13_3763367_k_star_visa_track_plan \
  /tmp/diff/18_3728528_research_fund_repayment_request \
  /tmp/diff/20_3727659_resume_2605_ai \
  /tmp/diff/internship_plan \
  /tmp/diff/multicultural_plan \
  /tmp/diff/research_form \
  /tmp/diff/form_01_교수법_과제양식_코다이_49KB \
  /tmp/diff/form_11_응시원서_자기소개서_48KB \
  /tmp/diff/form_17_융합전공신청서_운영계획서_81KB
```

Result:

```text
# matches=0
```

Current all-staged runtime scan still only matches `accountability_eval` and
`accountability_eval_fitted_oracle` variants. Therefore the CellBreak-rowspan
patch family still lacks an independent runtime guard, even though source-level
lookalikes exist.

Decision:

- Do not retry the simple `accountability_eval` top-slice/rowspan compression
  renderer patch yet.
- The next useful CellBreak work is to broaden beyond this 61-file curated set
  or generate/render more wild docs until `cellbreak_rowspan_scan.py` finds at
  least one non-`accountability_eval` runtime match.
- Source-level candidates should not be treated as visual guards until their
  `dump_pages_current.txt` shows a continued `PartialTable` with carried
  rowspan.

## Broad Photo-Grid Guard Expansion

Goal: find independent documents with the same structural class as the
`meeting_template` page-3 photo-grid bug before making any more renderer
changes.

Broad local candidate inventory:

```bash
find /Users/jaehoshin/Desktop/mindlogic -name '*.hwpx' \
  > /tmp/rhwp_hwpx_candidates.txt
wc -l /tmp/rhwp_hwpx_candidates.txt
```

Result:

```text
1615 /tmp/rhwp_hwpx_candidates.txt
```

Broad source scan:

```bash
python3 harness/photo_grid_scan.py \
  --paths-file /tmp/rhwp_hwpx_candidates.txt \
  --max-bytes 10000000 \
  > /tmp/photo_grid_broad_scan.tsv
```

High-signal independent mixed TAC/non-TAC picture-grid hits:

```text
/Users/jaehoshin/Desktop/mindlogic/factchat/mindlogic_factchat_server/hwpx_prod_samples/form_24_계획서_4MB.hwpx
/Users/jaehoshin/Desktop/mindlogic/factchat/mindlogic_factchat_server/scripts/upstage-test/files/hwpx/122p_민방위교육.hwpx
/Users/jaehoshin/Desktop/mindlogic/mindlogic-document-parser/samples/wild/w31.hwpx
```

Staged as:

```text
/tmp/diff/photo_form24/source.hwpx
/tmp/diff/photo_122p_civil_defense/source.hwpx
/tmp/diff/photo_w31/source.hwpx
```

The scanner was fixed so a direct doc directory such as
`/tmp/diff/photo_form24` resolves its own `source.hwpx` instead of falling back
to scanning all of `/tmp/diff`.

Focused staged source scans:

```bash
python3 harness/photo_grid_scan.py /tmp/diff/photo_form24
python3 harness/photo_grid_scan.py /tmp/diff/photo_122p_civil_defense
python3 harness/photo_grid_scan.py /tmp/diff/photo_w31
```

Results:

```text
photo_form24: 1 match, mixed_row=1
photo_122p_civil_defense: 6 matches, 4 mixed rows
photo_w31: 6 matches, 4 mixed rows
```

Runtime dump generation:

```bash
for d in photo_form24 photo_122p_civil_defense photo_w31; do
  docker compose --env-file .env.docker run --rm -v /tmp/diff:/diff \
    dev /app/target/release/rhwp dump-pages /diff/$d/source.hwpx \
    > /tmp/diff/$d/dump_pages_current.txt
done
```

Result:

```text
photo_form24: dump generated, 1673 lines
photo_122p_civil_defense: dump generated, 1542 lines
photo_w31: dump generated, 514 lines
```

Cheap current-render SVG export:

```bash
for d in photo_form24 photo_122p_civil_defense photo_w31; do
  docker compose --env-file .env.docker run --rm -v /tmp/diff:/diff \
    dev /app/target/release/rhwp export-svg /diff/$d/source.hwpx \
    -o /diff/$d/rhwp_svg_cur
done
```

Result:

```text
photo_form24: 84 RHWP SVG pages
photo_122p_civil_defense: 121 RHWP SVG pages
photo_w31: 30 RHWP SVG pages
```

Rendered page mapping for the strongest photo-grid guards:

```text
photo_form24
- page 9: Table pi=139, 3x2, TopAndBottom, tac=true, vpos=35280

photo_122p_civil_defense
- page 67: Table pi=764, 6x3, TopAndBottom, tac=true, vpos=4866
- page 68: Table pi=766, 12x8, TopAndBottom, tac=false, vpos=1954
- page 69: Table pi=769, 10x5, TopAndBottom, tac=true, vpos=1954
- page 70: Table pi=771, 10x5, TopAndBottom, tac=true, vpos=1954
- page 71: Table pi=773, 8x5, TopAndBottom, tac=true, vpos=1954
- page 72: Table pi=775, 8x5, TopAndBottom, tac=true, vpos=1954..0

photo_w31
- page 26: Table pi=353, 13x3, TopAndBottom, tac=true, vpos=2252
- page 27: Table pi=354, 6x3, TopAndBottom, tac=true, vpos=0
- page 28: nearby alternating TAC/non-TAC 2x1/1x1 picture-table cluster
```

Current limitation:

- These staged guards do not yet have `hancom.pdf` / `hancom_p-*.png`.
- They prove independent source/runtime coverage, not visual correctness.
- Next oracle request should prioritize:
  `photo_form24` page 9, `photo_122p_civil_defense` pages 67-72, and
  `photo_w31` pages 26-28.

Image-box probe without Hancom oracle:

```bash
python3 harness/svg_image_ink_probe.py \
  15_3740450_research_admin_innovation_meeting_template:3 \
  photo_form24:9 \
  photo_122p_civil_defense:67 photo_122p_civil_defense:68 \
  photo_122p_civil_defense:69 photo_122p_civil_defense:70 \
  photo_122p_civil_defense:71 photo_122p_civil_defense:72 \
  photo_w31:26 photo_w31:27 photo_w31:28 \
  > /tmp/photo_grid_image_ink_probe.tsv
```

Result:

```text
115 emitted image boxes:
- target meeting_template page 3: 6
- photo_122p_civil_defense pages 67-72: 94
- photo_w31 pages 26-28: 15
- photo_form24 page 9: 0 decoded SVG image tags
```

Interpretation:

- `photo_122p_civil_defense` and `photo_w31` are the strongest visual-geometry
  guard candidates because RHWP emits actual `<image>` boxes on the mapped
  pages.
- `photo_form24` remains useful as a source/runtime structural match, but is
  weaker for image-placement visual guarding until we understand why its mapped
  page has no decoded SVG image tags.
- The probe output is saved at `/tmp/photo_grid_image_ink_probe.tsv`.

## WebHWP Oracle Automation

Goal: remove manual clicking from the Hancom oracle lane for staged guard docs.

New harness:

```bash
python3 harness/webhwp_oracle_pdf.py /tmp/diff/photo_w31
```

Mechanism:

- Copies the staged `source.hwpx` to the licensed `webhwp` host's Tomcat test
  samples directory as a temporary `codex-oracle-*.hwpx`.
- Opens it through the deployed WebHWP test iframe:
  `https://webhwp.mindlogic.ai/test/resources/hwpctrlframe.html`.
- Uses the existing `saveAs` postMessage path with `format=PDF` and
  `download:true`.
- Saves the downloaded bytes locally as `/tmp/diff/<doc>/hancom.pdf`.
- Removes the temporary remote sample file after the run.

First successful guard oracle:

```text
photo_w31
- Hancom/WebHWP PDF: /tmp/diff/photo_w31/hancom.pdf
- PDF size: 5,083,856 bytes
- Hancom pages: 30
- RHWP pages: 30
- Export elapsed: 12.6s
- Key guard pages: 26-28
```

Rasterization:

```bash
pdftoppm -r 120 -png /tmp/diff/photo_w31/hancom.pdf /tmp/diff/photo_w31/hancom_p
```

Result:

```text
30 Hancom PNG pages
```

Focused review gallery:

```bash
python3 harness/review_gallery.py \
  /tmp/diff/_review_photo_grid_guards_2026-06-08 \
  photo_w31 15_3740450_research_admin_innovation_meeting_template \
  --export-current --max-pages 0
```

Result:

```text
/tmp/diff/_review_photo_grid_guards_2026-06-08/index.html
```

Decision:

- The photo-grid lane now has one real independent visual guard
  (`photo_w31`) in addition to source/runtime coverage.
- The next highest-value oracle is `photo_122p_civil_defense`, because it has
  many more emitted image boxes on pages 67-72.
- Do not patch Rust yet until the `photo_w31` key pages are inspected against
  the target and the candidate rule is expressed as a table/picture geometry
  invariant.

Second successful guard oracle:

```text
photo_122p_civil_defense
- Hancom/WebHWP PDF: /tmp/diff/photo_122p_civil_defense/hancom.pdf
- PDF size: 7,250,907 bytes
- Hancom pages: 129
- RHWP pages: 121
- Export elapsed: 25.3s
- Key RHWP guard pages: 67-72
```

Rasterization:

```bash
pdftoppm -r 120 -png \
  /tmp/diff/photo_122p_civil_defense/hancom.pdf \
  /tmp/diff/photo_122p_civil_defense/hancom_p
```

Result:

```text
129 Hancom PNG pages
```

Interpretation:

- This guard is now stronger than expected: it has both the repeated
  photo-grid image-box class and an 8-page Hancom/RHWP page-count gap.
- Direct page-number comparison needs alignment, because the RHWP key pages
  67-72 may correspond to later Hancom pages after accumulated drift.
- Use this as the next page-count/photo-grid diagnostic, not as a simple
  one-page image-placement guard.

Selected-page review helper:

```bash
python3 harness/review_pages.py \
  /tmp/diff/_review_photo_grid_civil_defense_pages_2026-06-08 \
  photo_122p_civil_defense --pages 67-72 --export-current
```

Result:

```text
/tmp/diff/_review_photo_grid_civil_defense_pages_2026-06-08/index.html
```

Reason for the helper:

- Full or large capped galleries are too slow for 100+ page guard docs.
- `harness/review_pages.py` builds only selected page strips, using the same
  Hancom/RHWP raster model as `review_gallery.py`.

Current `/tmp/diff` mixed photo-grid scan:

```bash
python3 harness/photo_grid_scan.py /tmp/diff --only-mixed
```

Result:

```text
10 mixed-row source matches:
- 15_3740450_research_admin_innovation_meeting_template: 1
- photo_form24: 1
- photo_122p_civil_defense: 4
- photo_w31: 4
```

Decision:

- Photo-grid is no longer blocked on independent guard coverage.
- It is still not automatically patchable: the new docs need page-level visual
  oracle evidence before a new renderer change is accepted.
- The next safe work is a targeted photo-grid probe: compare row/cell picture
  geometry and rendered image placement for `meeting_template:3` against the
  staged guards, then patch only if the rule is structural across those docs.

## Photo-Grid Semantic Page Drift

The selected-page gallery showed that `photo_122p_civil_defense` is not only a
local image-placement bug. RHWP is already semantically ahead of Hancom before
the big photo-grid section, then the gap widens through the repeated
training-center photo tables.

Reusable diagnostic added:

```bash
python3 harness/page_heading_map.py \
  photo_122p_civil_defense \
  --needles-file /tmp/photo_122_heading_needles.txt \
  > /tmp/photo_122_heading_map.tsv
```

Current heading map:

```text
needle	hancom_pages	rhwp_pages	first_delta
(4) 강사 관리	68	64	-4
(5) 강사 수당	69	65	-4
(6) 강사별 교육만족도 조사	69	65	-4
8        민방위 실전체험교육장	70		
(3) 교육장 구성	71	67	-4
가. 경보통신 교육장	71	67	-4
나. 대피통제 교육장	72	68	-4
다. 화생방 교육장	74	69	-5
라. 인명구조 교육장	76	70	-6
마. 소수방 교육장	77	71	-6
바. 응급복구 교육장	78	72	-6
(1) 과태료 부과 개요	79	73	-6
```

Interpretation:

- The pre-grid prose/table area is already about 4 pages compressed in RHWP.
- The large `TopAndBottom` training-center photo tables add another roughly
  2 pages of compression.
- The photo-grid lane should target pagination/fit semantics before local
  picture y/crop tweaks. A useful patch must shrink the heading deltas without
  breaking `photo_w31`'s 30/30 page-count guard or the existing page-count
  board.

Paired-page visual review helper added:

```bash
python3 harness/review_page_pairs.py \
  /tmp/diff/_review_photo_grid_civil_defense_pairs_2026-06-08 \
  photo_122p_civil_defense \
  --pairs '68:64,69:65,71:67,72:68,74:69,76:70,77:71,78:72,79:73' \
  --export-current
```

Extra semantic probes:

```bash
python3 harness/review_page_pairs.py \
  /tmp/diff/_review_photo_grid_civil_defense_pairs_extra_2026-06-08 \
  photo_122p_civil_defense \
  --pairs '72:68,73:68,74:69,75:69,76:70,77:70,78:72,79:73'
```

Visual conclusion:

- `Hancom 75 / RHWP 69` shows the large `다. 화생방 교육장` table body is
  broadly aligned once pages are semantically paired.
- `Hancom 74 / RHWP 69` shows Hancom has a heading-only page before that
  table, while RHWP places the heading and table on the same page.
- Therefore the strongest next hypothesis is a page-break/keep decision around
  section-heading paragraphs followed by near-full-page `TopAndBottom` photo
  tables.
- `photo_w31` prevents a broad version of this rule: it has similar large TAC
  photo tables and currently matches Hancom 30/30 pages, so the discriminator
  cannot be "large TAC photo table follows short heading" alone.

## Implemented Probe: HWPX TABLE-Break Photo-Table Shrink Gate

Patch:

- File: `src/renderer/height_measurer.rs`
- Rule: non-TAC `TopAndBottom` picture tables whose original HWPX
  `pageBreak="TABLE"` is preserved as `hwpx_page_break=Some(Table)` no longer
  shrink their natural row height down to declared `<hp:sz height>`.
- Reason: `photo_122p_civil_defense` table `pi=766` had raw row height
  `1218.3px` but RHWP shrank it to `726.6px`, packing the full `나. 대피통제`
  table on one page. Hancom renders that table across two pages.
- Guard: ordinary `pageBreak="CELL"` photo grids still shrink when they match
  the existing photo-grid shrink geometry.

Focused regression added:

```text
hwpx_table_break_non_tac_photo_table_keeps_raw_height_for_pagination
```

Patched diagnostic:

```text
TABLE_SHRINK_INPUT: hwpx=Some(Table) page_break=CellBreak repeat=true raw=1218.3 common=726.6 floor=false stale=false table_break=true shrink=false
TABLE_SPLIT_RESULT: pi=766 ... cursor_row=0 end_row=8 ... fits=true
TABLE_SPLIT_RESULT: pi=766 ... cursor_row=8 end_row=12 ... fits=true
```

Effect:

```text
photo_122p_civil_defense pages: 121 -> 122
photo_w31 pages: 30 -> 30
meeting_template pages: 5 -> 5
```

Heading drift after the patch:

```text
(3) 교육장 구성: Hancom 71 / RHWP 67 = -4
나. 대피통제 교육장: Hancom 72 / RHWP 68 = -4
다. 화생방 교육장: Hancom 74 / RHWP 70 = -4  (was -5)
라. 인명구조 교육장: Hancom 76 / RHWP 71 = -5  (was -6)
마. 소수방 교육장: Hancom 77 / RHWP 72 = -5  (was -6)
바. 응급복구 교육장: Hancom 78 / RHWP 73 = -5  (was -6)
(1) 과태료 부과 개요: Hancom 79 / RHWP 74 = -5  (was -6)
```

Patched paired review:

```text
/tmp/diff/_review_photo_grid_civil_defense_pairs_patched_2026-06-08/index.html
```

Remaining gap:

- The patch fixes one concrete table overpacking cause (`pi=766`) but does not
  solve the earlier 4-page compression before the photo-grid section.
- Next photo-grid/page-count work should inspect the pre-grid compression
  around `강사 관리` and the earlier large `TopAndBottom` tables before trying
  any more photo-table scaling rules.
