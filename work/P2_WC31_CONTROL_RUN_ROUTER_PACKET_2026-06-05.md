# P2 wc31 Control-Run Router Packet -- 2026-06-05

Target: `wc31_17pg`

Fresh evidence:

- review: `/tmp/diff/_review_wc31_fresh_nocrop/index.html`
- dump: `/tmp/diff/wc31_17pg/dump_pages_wc31_fresh.txt`
- drift: `/tmp/diff/wc31_17pg/drift_wc31_fresh.txt`
- detector: `python3 harness/embedded_scan_title_diag.py /tmp/diff/wc31_17pg/source.hwpx`
- corpus detector: `python3 harness/embedded_scan_title_diag.py --corpus /tmp/diff --limit 50`
- route packet:
  `python3 harness/embedded_scan_title_diag.py /tmp/diff/wc31_17pg/source.hwpx --json`

Current result:

- Hancom: 17 pages
- RHWP: 13 pages
- detector corpus match: 1/151, only `wc31_17pg`

Structural class:

- page/paper-relative full-page scan pictures:
  - non-TAC picture/shape-picture
  - `text_wrap=Square`
  - `vertRelTo=Paper`
  - `horzRelTo=Paper/Page`
  - width near body/page width
  - height covers most of body
- nearby body-wide 1x3 evidence/title tables:
  - one row, three columns
  - width near body width
  - height <= 7000 HU
  - often TAC `TopAndBottom`, but `pi=64 ci=2` is non-TAC `Square`

Observed bad ownership:

- page 5:
  - Hancom: prior scanned/body page only.
  - RHWP: leaks `pi=61 ci=1` title at top over prior body.
  - dump: `FullParagraph pi=60`, `Shape pi=61 ci=0`, `Table pi=61 ci=1`.
- page 6:
  - Hancom: `증빙 1` title + report body.
  - RHWP: already at `증빙 2` over later education-plan body.
  - dump: `Table pi=63`, `Shape pi=64 ci=0`, `Shape pi=64 ci=1`,
    `Table pi=64 ci=2`, `PartialParagraph pi=64`.

Expanded structural sequence from the diagnostic:

```text
p61 scan  bin=image4 wrap=SQUARE vert=PAPER horz=PAPER size=47941x60910
p61 title tac=True  wrap=TOP_AND_BOTTOM size=47767x5574
p63 title tac=True  wrap=TOP_AND_BOTTOM size=47767x5574
p64 scan  bin=image5 wrap=SQUARE vert=PAPER horz=PAPER size=47766x66205
p64 media bin=image6 tac=True wrap=SQUARE vert=PARA horz=PARA size=47590x66387
p64 title tac=False wrap=SQUARE size=47767x5574
p65 title tac=True  wrap=TOP_AND_BOTTOM size=47767x5291
p66 media_table rows=3 cols=2 tac=False wrap=SQUARE size=47624x62402
```

This is why page breaks alone fail: the correct visual ownership binds a title
to a later scan/media control in the run, not necessarily to the title's host
paragraph.

The detector now emits a `route_sequence` in JSON. Current first candidate:

```text
p61 scan image4
p61 title -> next_body scan p64 image5
p63 title -> next_body scan p64 image5
p64 scan image5
p64 media image6
p64 title -> next_body media_table p66
p65 title -> next_body media_table p66
p66 media_table
```

The duplicate `title -> image5` and `title -> p66 media_table` ownership hints
are the main warning against a naive "each title keeps with next body" patch.
Any renderer behavior probe must decide title/body pairing without using title
text or document names.

Embedded image proof:

- `/tmp/diff/wc31_17pg/bindata_extract/image4.JPG` is exactly the Hancom page 5
  body scan (`향후 계획 및 개선 제언`) and contains no evidence title band.
- `/tmp/diff/wc31_17pg/bindata_extract/image5.JPG` is the Hancom page 6 body
  scan and contains no evidence title band.
- `/tmp/diff/wc31_17pg/bindata_extract/image6.JPG` is the Hancom page 9 body
  scan and contains no evidence title band.

Therefore the separate 1x3 title tables are real overlays/page bands, not text
inside the images. Fresh visual order:

```text
Hancom page 5: image4 only
Hancom page 6: p61 title + image5
Hancom page 7: p63 title only
Hancom page 8: p64 title only
Hancom page 9: image6/body scan
```

Current RHWP order:

```text
RHWP page 5: image4 + p61 title
RHWP page 6: p63 title + image5 + p64 title
RHWP page 7: p65 title + p66 media table
RHWP page 8: p69 media table
```

This proves the core bug is not only pagination height. The renderer must
support a structural control-run transform/reordering across paragraph order:
`p64 image5` visually pairs with `p61 title`, while the intervening `p63 title`
waits as a standalone title page.

Do not retry:

- split before the same-paragraph TAC title table alone.
- break before the whole scan+title paragraph.
- broad prebreak before all page-relative scan paragraphs.
- standalone title-page rule that ignores later scan/media controls.

Those all moved page count to 14 at best but produced blank pages, title-only
pages, or swapped title/body ownership.

Required invariant:

The visual control run should be:

1. `image4` alone owns the prior page.
2. evidence title `1` keeps with `image5`.
3. evidence title `2` is standalone in the correct order.
4. evidence title `3` is standalone in the correct order.
5. evidence title `4` keeps with the following `pi=66` profile/media table.

Implementation direction:

- Build a structural control-run router around page-relative scan controls and
  nearby 1x3 evidence/title tables.
- Route title controls by the following scan/media ownership, not only by host
  paragraph index.
- Allow the router to reorder page item ownership across paragraph order within
  a detected run. A simple "push title to next page" still leaves `p63 title`
  before `p64 image5`, which contradicts Hancom page 6.
- Treat large TAC media pictures inside the same run as ownership targets too;
  `image6` is not a page-relative scan under the strict predicate, but it is a
  media body that must be separated from title `3`.
- Treat large body/media tables as ownership targets too; `pi=66` is a large
  non-TAC Square `3x2` table that title `4` must own.
- Keep this outside document names and title text. The detector text is only
  for diagnostics.
- If implemented in pagination, make page items capable of representing a
  control routed to a different page than the rest of its host paragraph.
- If implemented in layout, preserve dump/page ownership and prove the rendered
  page no longer leaks title tables over the prior scan.

Fast validation:

```bash
python3 harness/review_gallery.py /tmp/diff/_review_wc31_probe wc31_17pg --export-current
python3 harness/embedded_scan_title_diag.py /tmp/diff/wc31_17pg/source.hwpx
python3 harness/embedded_scan_title_diag.py --corpus /tmp/diff --limit 50
python3 scripts/check_renderer_overfit.py
bash harness/gate.sh --no-build
```

Accept only if:

- page 5 has no evidence title leak.
- page 6 starts evidence title `1` with its report body.
- title/body order for evidence 2, 3, and 4 stays correct.
- RHWP page count moves toward 17 without blank manufactured pages.
- no new overflow and no page-count regression in the 151-doc gate.

## 2026-06-05 Late Probe: Post-Pagination Router + TAC Picture Fallback

Current source contains a structural post-pagination router plus a narrow
layout fallback for large routed TAC pictures whose host paragraph did not emit
a `FullParagraph` item.

Evidence:

- focused review: `/tmp/diff/_review_wc31_tac_picture_fallback/index.html`
- dump: `/tmp/diff/wc31_17pg/dump_pages_wc31_tac_picture_fallback.txt`
- drift: `/tmp/diff/wc31_17pg/drift_wc31_tac_picture_fallback.txt`
- targeted compile/test:
  `docker compose --env-file .env.docker run --rm dev cargo test --lib page_relative_scan_group_breaks_before_following_flow -j 1 -- --nocapture`
- release build:
  `docker compose --env-file .env.docker run --rm dev cargo build --release -j 1`
- overfit guard:
  `python3 scripts/check_renderer_overfit.py`
- full gate:
  `bash harness/gate.sh --no-build`

Result:

- `wc31_17pg` improved from gate baseline `12` pages to `16` pages, oracle
  `17`.
- Page 5 no longer leaks the evidence title over the prior image.
- Page 6 pairs title `1` with the following body scan.
- Page 9 is no longer blank; the routed large TAC picture renders.
- Full gate: `docs=151 improved=6 regressed=0 new_overflow=0`.
- Overfit guard passed with only the 8 known baseline findings.

Still not accepted as complete:

- `wc31_17pg` remains `16/17`, so one content/page split is still missing.
- Page 8 has a small stray glyph above the `증빙` title band.
- The router is still a high-blast-radius behavior probe; keep validating
  visually against adjacent pages before upstreaming or deploying.

## Rejected Late Probe: Move Same-Paragraph Media Title Before Table

Probe:

- Detect a large 2x2/3x2 media table on page `N` and a same-paragraph 1x3
  evidence title table at the start of page `N+1`.
- Move the title before the media table and drop the immediate blank spacer.

Local visual result:

- `/tmp/diff/_review_wc31_media_title_probe/wc31_17pg/page-11.png` improved:
  RHWP showed `증빙 5. 방송 보도` above the media table, matching Hancom's
  title ownership better.
- `/tmp/diff/_review_wc31_media_title_probe/wc31_17pg/page-12.png` also
  improved at the top by starting with `증빙 6. 언론 보도` instead of stacked
  `증빙 5/6`.

Rejection reason:

- Full gate failed with new overflow:
  `+OVERFLOW wc31_17pg: 0->1`.
- The missing behavior is not just title reordering. The large media table must
  split/continue with the title consuming top-page height. Moving the title
  without reflowing/splitting the table overfills page 11.

Do not retry as a post-pagination move-only rule. The next viable direction is
to route the title before the table before split calculation, or teach the
post-pagination router to split the table fragment structurally.

## Rejected Late Probe: Pre-Split Media Title Reorder

Probe:

- Inside `typeset_table_paragraph`, detect a large non-TAC media table followed
  later in the same paragraph by a wide short 1x3 evidence title table.
- Typeset the title table before the media table so the normal table split
  calculation sees the title height before splitting the media block.

Local result:

- Focused review: `/tmp/diff/_review_wc31_presplit_title_probe/index.html`.
- Page count reached `wc31_17pg` Hancom 17 / RHWP 17.
- Visual fidelity was still not production-grade: RHWP page 11 was badly
  underfilled, page 12 had the right section but wrong split/density, and pages
  13-15 remained shifted.

Rejection reason:

- Full gate failed with new overflow:
  `+OVERFLOW wc31_17pg: 0->1`.
- Reverted from source and rebuilt release binary.
- Safe post-revert evidence:
  - focused review:
    `/tmp/diff/_review_wc31_safe_after_presplit_revert/index.html`
  - dump:
    `/tmp/diff/wc31_17pg/dump_pages_wc31_safe_after_presplit_revert.txt`
  - full gate:
    `docs=151 improved=6 regressed=0 new_overflow=0`
  - current `wc31_17pg`: Hancom 17 / RHWP 16.

Do not retry as a same-paragraph preordering shortcut. The next viable direction
is structural table-fragment splitting/continuation for the media table after
the evidence title consumes top-of-page height, with an overflow invariant.

## Current Safe Split Diagnosis

Fresh table diagnostics after reverting the pre-split probe:

- table drift:
  `/tmp/diff/wc31_17pg/table_drift_wc31_safe_after_presplit_revert.txt`
- dump with same binary:
  `/tmp/diff/wc31_17pg/dump_pages_wc31_safe_table_drift.txt`

Key current-safe facts:

- Page 11 places `pi=69 ci=0` alone:
  `Table pi=69 ci=0 3x2 635.0x863.3px wrap=Square tac=false`.
- Page 12 then places the delayed same-paragraph title:
  `Table pi=69 ci=1 1x3 636.9x47.9px wrap=TopAndBottom tac=true`.
- `pi=69 ci=0` fits page 11 by a tiny margin only because the title is delayed:
  `avail_for_rows=916.9`, `consumed=913.5`, `fits=true`.
- If the `47.9px` title is placed first, the media table must become a
  `PartialTable`/continuation pair. The rejected pre-split probe proved that
  naive preordering can reach 17 pages but overflows in render/layout.

Next acceptable probe shape:

1. Preserve visual ordering structurally for this class: wide short evidence
   title table and following/associated large media table on the same visual
   page.
2. Split the large media table with the reduced available height, not as a
   post-pagination move.
3. Add/verify an invariant that the resulting `PartialTable` content bottom is
   inside the body box before running the corpus gate.
4. Reuse guards: `wc31_17pg`, `wc69_9pg`, `wc35_15pg`, `wc39_14pg`,
   `wc47_6pg`, `wc51_4pg`, and full `harness/gate.sh --no-build`.

## Accepted Guard: Defer Non-Leading Split Row That Would Render Over Budget

Accepted source change:

- In the generic non-TAC table split walker, after `advance_row_cut` proposes an
  intra-row cut, compare the actual render advance
  `row_cut_content_height(...)` against the remaining fragment budget.
- If this is not the first row of the fragment and the rendered cut would exceed
  the budget by more than the 4px drift tolerance, defer that row to the next
  page instead of accepting a guaranteed overflowing `PartialTable`.
- Page-leading rows still use the existing forced-progress path, so large rows
  cannot loop forever.

Why this is general:

- The rejected `wc31` probe exposed a real typeset/render mismatch:
  `advance_row_cut` reported a possible cut, but the rendered row fragment was
  larger than the available body budget.
- The rule is based on row split geometry only: no document name, title text, or
  fixture fingerprint.

Evidence:

- Diagnostic before guard, with pre-split title probe:
  `pi=71` produced `partial_h=391.9`, `avail_for_rows=275.9`, then
  `LAYOUT_OVERFLOW ... para=71 type=PartialTable overflow=116.0px`.
- Diagnostic after guard, same temporary title probe:
  `pi=71` first fragment changed to `end_row=1`, `partial_h=28.4`,
  `fits=true`; continuation row rendered on the next page, and focused export
  had no `LAYOUT_OVERFLOW`.
- Accepted final gate after removing the temporary title reorder:
  `docs=151 improved=6 regressed=0 new_overflow=0`.
- Overfit guard passed with only the 8 known baseline findings.

## Rejected Combined Probe: Pre-Split Title Reorder + Split Guard

Probe:

- Re-applied the pre-split media-title reorder after adding the generic split
  guard.

Result:

- Focused export no longer overflowed.
- `wc31_17pg` became 18 RHWP pages against the 17-page Hancom oracle.
- Focused review:
  `/tmp/diff/_review_wc31_presplit_guard_probe/index.html`.
- Dump:
  `/tmp/diff/wc31_17pg/dump_pages_wc31_presplit_guard_probe.txt`.

Decision:

- Reverted the title reorder again.
- Keep only the generic split guard.
- Do not retry the title reorder alone; the remaining missing behavior is a
  larger evidence/media grouping and spacer-collapse problem after the split,
  especially around pages 13-18.

## Accepted 2026-06-06 Probe: Evidence Title + Split Body Fragment Orphan Router

Accepted source change:

- Added `rewrite_evidence_title_split_table_orphans` after the embedded
  scan/title router.
- Structural trigger only:
  - current page tail contains a 1-row, 3-column, body-wide evidence/title
    table;
  - optional following items are blank control-free spacer paragraphs;
  - tail then contains the first `PartialTable` fragment for a body table;
  - the next page starts with a continuation fragment of the same table;
  - the current page itself does **not** start with a continued table.
- Action: move the title/spacer/first table fragment to a newly inserted page
  immediately before the continuation page.

Why this is general:

- Hancom keeps the evidence title with the first body-table fragment instead of
  leaving the title at the previous page bottom.
- The discriminator is pure structure: title-table geometry, blank spacer run,
  table fragment identity, and continuation state. No document name, page text,
  or paragraph-number branch.
- The explicit "source page starts with continued table" exclusion prevents the
  same router from over-firing on the next evidence title (`pi=94`/`pi=95`),
  where Hancom intentionally keeps the following title at the bottom of a page
  that begins with the prior table's continuation.

Focused evidence:

- First broad probe over-fired and produced RHWP 18 pages:
  `/tmp/diff/_review_wc31_title_split_probe_2026-06-06/index.html`.
- Narrowed probe produced Hancom 17 / RHWP 17:
  `/tmp/diff/_review_wc31_title_split_probe2_2026-06-06/index.html`.
- Current active board:
  `/tmp/diff/_review_active_2026-06-06/index.html`.
- Current dump:
  `/tmp/diff/wc31_17pg/dump_pages_wc31_title_split_probe2_2026-06-06.txt`.

Validation:

```text
python3 harness/audit_review_gallery.py /tmp/diff/_review_wc31_title_split_probe2_2026-06-06
PASS: no gallery truncation/aspect issues across 1 doc(s)

python3 scripts/check_renderer_overfit.py
renderer overfit check passed with 8 known baseline finding(s).

bash harness/gate.sh --no-build
[gate] docs=151 improved=6 regressed=0 new_overflow=0
  IMPROVE  form_07_______________41KB: 12->11 (oracle 11)
  IMPROVE  wc15_7pg: 6->7 (oracle 7)
  IMPROVE  wc16_6pg: 5->6 (oracle 6)
  IMPROVE  wc17_6pg: 5->6 (oracle 6)
  IMPROVE  wc31_17pg: 12->17 (oracle 17)
  IMPROVE  wc35_15pg: 16->15 (oracle 15)
```

Remaining visual risk:

- Page count is now clean, but `wc31` still has visible density/spacing drift in
  pages 12-15. Treat this as a visual QA target, not as an open page-count
  target.
