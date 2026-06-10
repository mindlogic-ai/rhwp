# Current RHWP Fidelity Board -- 2026-06-05

This board records fresh current-source checks from the native release binary.
It supersedes stale `_gallery3` counts for choosing the next implementation
cycle. Hancom images remain the oracle.

## Verified Current State

Fresh non-cropping review gallery:

- `/tmp/diff/_review_active_2026-06-06/index.html`
- served locally at `http://localhost:8799/_review_active_2026-06-06/index.html`
- generated from current git HEAD `25d42bfd` with dirty worktree marker;
  left column is Hancom oracle, right column is current RHWP.

Do not use `/tmp/diff/_gallery3` as a bottom-edge visual authority. Its old
three-column strips can appear vertically truncated or distorted; for example
`wild_02_paper_fig_10MB/page-01.png` is `2304x1103` there while the tracked
review-gallery output is `1812x1304`. Regenerate with
`harness/review_gallery.py` and click the raw full-height strip before deciding
that the renderer clipped content. `harness/look.py` now uses the same
non-cropping screenshot pattern: decode the SVG image, measure scroll size,
resize the viewport, and screenshot with `fullPage: true`.
`harness/audit_review_gallery.py` now fails stale/cropped galleries; it reports
389 evidence issues on old `/tmp/diff/_gallery3` and passes on the current
active board.

| Family | Document | Fresh result | Decision |
|---|---:|---:|---|
| page-relative scanned image | `med_02____2_4MB` | Hancom 6 / RHWP 6 | P1a verified. Page 3 now shows the `실험결과` table instead of hiding it behind the scan. Keep as landed rule and guard with `page_relative_scan_group_breaks_before_following_flow`. |
| stale VPOS/table forward-pack | `form_07_______________41KB` | Hancom 11 / RHWP 11 | Page-count clean in current source; fresh review gallery shows all 11/11 pages. Do not chase old `_gallery3` 12-page artifacts. |
| stale/cache sibling | `wc15_7pg` | Hancom 7 / RHWP 7 | Page-count clean in current source; fresh review gallery shows all 7/7 pages. |
| stale/cache sibling | `wc16_6pg` | Hancom 6 / RHWP 6 | Page-count clean in current source; fresh review gallery shows all 6/6 pages. |
| stale/cache sibling | `wc17_6pg` | Hancom 6 / RHWP 6 | Page-count clean in current source; fresh review gallery shows all 6/6 pages. |
| fitted wide-table oracle | `accountability_eval_fitted_oracle` | Hancom 11 / RHWP 11 | Page-count clean; keep as visual/table/export guard, not active page-count target. |
| multi-column float | `wild_02_paper_fig_10MB` | Hancom 9 / RHWP 7 | Still active. Render diagnostics proved pagination charges the PI0 image while render rewinds the cursor, but simple render-cursor and host-text fixes caused overflow regressions in DNA/wc26 guards and were reverted. |
| scanned/evidence page ownership | `wc31_17pg` | Hancom 17 / RHWP 17 | Page-count clean in current source. Accepted a structural evidence-title/body-fragment orphan router: when a 1x3 evidence title plus blank spacer and first `PartialTable` fragment sits at a page tail, and the next page starts the continuation of that same table, move the title/spacer/first fragment to a new page unless the source page itself starts with a continued table. Full gate: `docs=151 improved=6 regressed=0 new_overflow=0`. Residual visual drift remains in evidence pages, so keep it as visual QA target, not page-count target. |
| square formula-table packing | `wc35_15pg` | Hancom 15 / RHWP 15 | Page-count clean in current source; residual visual drift remains around formula/table boxes on pages 7-8, so treat as visual fidelity target, not page-count target. |
| wild business plan | `wild_01_business_plan_31pg` | Hancom 31 / RHWP 32 | Active +1 residual; triage after `wc35` unless visual severity outranks it. |

## `wc35_15pg` Current Diagnosis

Fresh artifacts:

- `/tmp/diff/wc35_15pg/look/page-07.png`
- `/tmp/diff/wc35_15pg/look/page-08.png`
- `/tmp/diff/_review_improved_2026-06-05/wc35_15pg/page-07.png`
- `/tmp/diff/_review_improved_2026-06-05/wc35_15pg/page-08.png`

Visual read:

- Page count is now clean: 15/15.
- Page 7 is still the first obvious structural visual divergence.
- RHWP places several equation/table boxes too high relative to Hancom while
  x-position is roughly aligned.
- Treat remaining work as visual float/formula-table placement, not as the
  next highest page-count fix.

Structural class:

- repeated non-TAC `Square` one-cell formula tables;
- nearby non-TAC `Square` pictures/groups;
- empty paragraphs with saved split line segments (`cs/sw` left/right zones);
- several `VPOS_CORR applied=false` rows inside the same anchor cluster;
- sparse continuation page starts inside that cluster.

Do not patch yet with:

- global empty paragraph collapse;
- global cached-VPOS ignore;
- broad Square float pushdown;
- page-tail squeeze.

Next useful probe:

1. Add diagnostic-only logging for Square formula-table clusters:
   paragraph index, table `treat_as_char`, wrap, size, `vertical_offset`,
   `horizontal_offset`, first line `cs/sw`, current height, chosen part height,
   and whether a VPOS correction was rejected.
2. Compare `wc35` with guards `wc39_14pg`, `wc47_6pg`, `wc51_4pg`, and
   `wc69_9pg`.
3. Only test a behavior rule if the discriminator is structural and repeats:
   small non-TAC Square formula table, host paragraph with split `cs/sw`, and
   empty spacer cluster immediately after a Square anchor.

## Next Priority

1. `wc31_17pg`: continue from the safe post-revert state, not from the rejected
   17-page overflow probe. Fresh safe review:
   `/tmp/diff/_review_wc31_safe_after_presplit_revert/index.html`. Current
   shape is Hancom 17 / RHWP 16; pages 11-13 show the remaining evidence/media
   split drift and page 17 is the missing RHWP page marker.
2. `wild_02_paper_fig_10MB`: multi-column float reserve/content-overlap target.
3. `wc35_15pg`: visual-only Square formula-table y-placement after page-count
   patch is protected.

### Rejected `wc31` Probe

Probe:

- split before a same-paragraph TAC title table when an earlier control in the
  same paragraph is a page-relative full-page scan picture.

Result:

- page count moved `13 -> 14`;
- no target overflow;
- but `/tmp/diff/_review_wc31_scan_split_probe/wc31_17pg/page-06.png`
  showed RHWP rendering only the `증빙 1` title/header table while Hancom
  renders the header plus the report body below it.

Decision:

- reverted from source and release binary;
- do not land a same-paragraph split unless render ownership is also fixed so
  the scan/report body stays with the title page.
- next `wc31` probe should inspect render/page ownership for the scan picture
  and TAC title table as a unit, not only the page-count split.

### Rejected `wc31` Probe 2

Probe:

- break before the whole same-paragraph page-relative scan + TAC title-table
  paragraph when prior flow content already exists on the current page.

Result:

- page count moved `13 -> 14`;
- `/tmp/diff/_review_wc31_same_para_block_probe/wc31_17pg/page-05.png`
  showed a blank RHWP page 5;
- `/tmp/diff/_review_wc31_same_para_block_probe/wc31_17pg/page-06.png`
  still showed the evidence header over prior page-5 body content, while Hancom
  page 6 should start the scanned report/evidence page.

Decision:

- reverted from source;
- do not land a plain paragraph-entry break. The missing piece is not just
  pagination ownership; render positioning/page anchoring for the paper-relative
  scan picture and same-paragraph title table diverges when the paragraph is
  moved.
- next `wc31` probe should inspect `layout_body_picture` / object positioning
  for paper-relative scans after pagination moves, and compare whether the
  `PageItem::Shape` is present but drawn off the expected page/region.

### Rejected `wc31` Probe 3

Probe:

- treat an empty host paragraph with a single 1x3 TAC `TopAndBottom` title table
  followed by a large picture-heavy `Square` row-break table as a standalone
  title page before the media block.

Result:

- page count moved `13 -> 14`;
- `/tmp/diff/_review_wc31_title_page_probe/wc31_17pg/page-06.png`
  improved one local case (`증빙 2` title/body page appeared);
- but page ownership stayed wrong: page 7 jumped to `증빙 4`, page 8 rendered
  profile content where Hancom expects the `증빙 3` title page.

Decision:

- reverted from source;
- the rule is too local. It handles title-before-next-media paragraphs but does
  not handle the interleaved pattern where a full-page scan image and the next
  title table share a paragraph, or where later paragraph controls visually
  belong before an intervening title.

### Rejected `wc31` Probe 4

Probe:

- insert a break before any top-anchored page-relative full-page scan group when
  earlier flow content exists, while keeping the existing break after the scan
  group.

Result:

- `/tmp/diff/_review_wc31_scan_group_prebreak_probe/wc31_17pg/page-05.png`
  removed the title leak but left RHWP page 5 blank;
- `/tmp/diff/_review_wc31_scan_group_prebreak_probe/wc31_17pg/page-06.png`
  still showed the prior page-5 image under the `증빙 1` title.

Decision:

- reverted from source;
- the page item dump showed page 6 only contained `Shape pi=61 ci=0` and
  `Table pi=61 ci=1`. The apparent prior page body was the embedded
  `BinData/image4.JPG` itself, not stale page text leaking through.
- next direction: model this as embedded full-page image/title ownership. In
  `wc31`, `image4.JPG` is Hancom page 5 body while the same paragraph's title
  table belongs to the next evidence page. A correct fix likely needs
  per-control page routing/keep-with-next for these interleaved scan/title
  controls, not a paragraph-level prebreak.

### Current `wc31` Structural Evidence

Fresh live review:

- `/tmp/diff/_review_wc31_17pg_live/index.html`
- `/tmp/diff/_review_wc31_fresh_nocrop/index.html` (regenerated after fixing
  review-gallery crop risk; all strips are `1812x1304/1305`, so this is not a
  preview truncation artifact)

Current dump:

- `/tmp/diff/wc31_17pg/dump_pages_current.txt`
- `/tmp/diff/wc31_17pg/drift_current.txt`
- `/tmp/diff/wc31_17pg/dump_pages_wc31_fresh.txt`
- `/tmp/diff/wc31_17pg/drift_wc31_fresh.txt`

Structural detector:

- `python3 harness/embedded_scan_title_diag.py /tmp/diff/wc31_17pg/source.hwpx`
- `python3 harness/embedded_scan_title_diag.py --corpus /tmp/diff --limit 30`
- current corpus result: `scanned=151 matches=1`, only
  `/tmp/diff/wc31_17pg/source.hwpx` matches this embedded scan/title
  interleaving class.
- JSON route packet:
  `python3 harness/embedded_scan_title_diag.py /tmp/diff/wc31_17pg/source.hwpx --json`
  now annotates each title with its next structural body target (`scan`,
  `media`, or `media_table`).

The first bad ownership run is:

- `pi=61`: `Picture bin_id=4`, non-TAC, `Square`, `vertRelTo=Paper`,
  page-sized scan image (`169.1mm x 214.9mm`), followed by a TAC 1x3
  `TopAndBottom` title table for evidence `1`.
- `pi=63`: standalone TAC 1x3 `TopAndBottom` title table for evidence `2`.
- `pi=64`: page-relative `image5`, large TAC media `image6`, and non-TAC
  Square 1x3 title table for evidence `3`.
- `pi=65`: TAC 1x3 `TopAndBottom` title table for evidence `4`.
- `pi=66`: large non-TAC Square `3x2` media table (`47624 x 62402 HU`).

Current first route sequence:

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

This is still diagnostic-only, not a renderer fix. It narrows the next safe
behavior attempt: a control router must handle duplicate title-to-body
candidates and large media-table targets without branching on document names or
title text.

Direct BinData inspection refined the invariant:

- `/tmp/diff/wc31_17pg/bindata_extract/image4.JPG` is Hancom page 5 body only.
- `/tmp/diff/wc31_17pg/bindata_extract/image5.JPG` is Hancom page 6 body only.
- `/tmp/diff/wc31_17pg/bindata_extract/image6.JPG` is Hancom page 9 body only.

So the separate title tables are page bands. Current correct visual order is:

```text
Hancom page 5: image4 only
Hancom page 6: p61 title + image5
Hancom page 7: p63 title only
Hancom page 8: p64 title only
Hancom page 9: image6/body scan
```

This means the next implementation target is a structural control-run transform
that can reorder page ownership across paragraph order. A simple next-page
title push would still put `p63 title` before `p64 image5`, which is wrong.
- `pi=64`: `Picture bin_id=5`, non-TAC, `Square`, `vertRelTo=Paper`,
  then `Picture bin_id=6`, TAC, then a non-TAC 1x3 `Square` title table for
  evidence `3`.
- `pi=65`: standalone TAC 1x3 `TopAndBottom` title table for evidence `4`.
- `pi=66`: large non-TAC `Square` media/profile table that visually belongs
  after evidence `4`.

Fresh visual confirmation:

- page 5: Hancom still shows the prior `향후 계획 및 개선 제언` scan/body, while
  RHWP leaks the `증빙 1` title table at the page top.
- page 6: Hancom starts `증빙 1` and its report body, while RHWP is already at
  `증빙 2` over the later education-plan body.
- dump page 5 contains only `FullParagraph pi=60`, `Shape pi=61 ci=0`, and
  `Table pi=61 ci=1`; dump page 6 contains `Table pi=63`, `Shape pi=64 ci=0`,
  `Shape pi=64 ci=1`, `Table pi=64 ci=2`, and `PartialParagraph pi=64`.
  This proves the problem is control/page ownership, not missing raster height.

Embedded images verified:

- `/tmp/diff/wc31_17pg/_unz/BinData/image4.JPG` is the Hancom page-5 body.
- `/tmp/diff/wc31_17pg/_unz/BinData/image5.JPG` is the body under evidence
  title `1`.
- `/tmp/diff/wc31_17pg/_unz/BinData/image6.JPG` is the public-report page
  that follows evidence title `3`.

Implication:

- Paragraph order is not enough. The visual order is effectively:
  `image4` -> title `1` + `image5` -> title `2` -> title `3` + `image6`
  -> title `4` + `pi=66` table.
- A safe probe must operate on a structural control run made from
  page-relative scanned pictures and 1x3 evidence/title tables. It should not
  simply break before/after whole paragraphs.
- Next implementation attempt should build a control-run router for this
  structural class:
  1. page-relative full-page scan controls own the current page image;
  2. a same/nearby 1x3 evidence title table can be routed to the following
     scan/media page instead of the paragraph page;
  3. standalone evidence title tables must keep with the next scan/media block;
  4. validation must reject blank manufactured pages and title/body swaps.

## Fast Loop For Next Hours

1. Always refresh target with a non-cropping visual:

```bash
python3 harness/look.py /tmp/diff/<doc> --export
python3 harness/review_gallery.py /tmp/diff/_review_<name> <doc> --export-current
```

If the conversation/browser preview looks bottom-clipped, check the raw strip
dimensions before touching renderer code:

```bash
python3 - <<'PY'
from PIL import Image
from pathlib import Path
for p in sorted(Path('/tmp/diff/_review_<name>/<doc>').glob('page-*.png')):
    print(p.name, Image.open(p).size)
PY
```

2. Dump only after the fresh visual confirms the doc still fails:

```bash
RHWP_TABLE_DRIFT=1 RHWP_VPOS_DEBUG=1 docker compose --env-file .env.docker \
  run --rm -v /tmp/diff:/diff -e RHWP_TABLE_DRIFT=1 -e RHWP_VPOS_DEBUG=1 \
  dev /app/target/release/rhwp dump-pages /diff/<doc>/source.hwpx
```

3. Land only after:

```bash
CARGO_BUILD_JOBS=1 docker compose --env-file .env.docker run --rm dev \
  cargo test --lib <focused_test> -j 1
python3 scripts/check_renderer_overfit.py
bash harness/gate.sh --no-build
```

4. Rebuild WASM/studio only after native gate and visual guards are clean.
