# P1 Image/Float Diagnosis — 2026-06-05

Current first implementation target: `med_02____2_4MB`.

Reason: `wild_02_paper_fig_10MB` combines at least two problems:
page-relative/float overlap and multi-column flow collapse. `med_02` isolates
a smaller structural failure: full-page scanned photos do not reserve the page,
so later flow content is paginated under the scan.

## Evidence

Visual artifacts:
- `/tmp/diff/_gallery3/med_02____2_4MB/page-02.png`
- `/tmp/diff/_gallery3/med_02____2_4MB/page-03.png`

Observed:
- Hancom page 2: full-page scanned experiment-method photo.
- Hancom page 3: `실험결과` table.
- Current renderer page 2: full-page scanned photo.
- Current renderer page 3: blank.

Dump command:

```bash
docker compose --env-file .env.docker run --rm -v /tmp/diff:/diff dev \
  /app/target/release/rhwp dump-pages /diff/med_02____2_4MB/source.hwpx
```

Relevant dump:
- Page 2 contains `Shape pi=3`, `Shape pi=4`, then `FullParagraph pi=8 "실험결과"` and the table-like measurement paragraphs.
- Page 3 contains only `FullParagraph pi=61 "(빈)"`.
- The metric still says `diff=+0.0px`, so the dump-pages height metric is blind to this class. Visual check is mandatory.

HWPX attributes for the scanned pictures:

```text
PI 3:
pic textWrap=SQUARE
pos treatAsChar=0 flowWithText=1 allowOverlap=1
pos vertRelTo=PAPER horzRelTo=PAPER vertAlign=TOP horzAlign=LEFT
sz width=51011 height=65252
pos vertOffset=16828 horzOffset=4772

PI 4:
pic textWrap=SQUARE
pos treatAsChar=0 flowWithText=1 allowOverlap=1
pos vertRelTo=PAPER horzRelTo=PAPER vertAlign=TOP horzAlign=LEFT
sz width=53727 height=70506
pos vertOffset=12074 horzOffset=2391
```

At 96 DPI, these are near-paper-height scans. They overlap the body area and
leave no meaningful beside-flow region.

## Current Code Gap

`src/renderer/typeset.rs` already handles several related classes:
- multiple terminal full-width Square/TopAndBottom Para floats,
- single large non-TAC Para float that overflows a nearly-full page,
- TopAndBottom Para pushdown,
- full-width Square Para pushdown.

But `med_02` is `VertRelTo::Paper`, not `VertRelTo::Para`. The current
pushdown/reservation branches do not reserve page-relative full-page Square
pictures, even when `flowWithText=1`.

## Candidate General Rule

Structural discriminator:
- non-TAC `Picture` or picture-shaped `Shape`,
- `text_wrap == Square`,
- `flow_with_text == true`,
- `vert_rel_to == Paper`,
- `horz_rel_to == Paper` or `Page`,
- object overlaps the body area,
- object height covers most of the body area, or bottom extends near/past body bottom,
- later visible flow content exists.

Expected behavior:
- register the full-page scan on the current page,
- reserve the page once for a consecutive group of page-relative full-page scans,
- start later visible paragraphs on the next page.

Important nuance:
- `med_02` has two consecutive scanned-photo controls (`pi=3`, `pi=4`) with
  page-relative anchors. They currently render in the same page item set.
  A naive per-control page break could create an extra page. The safer rule is
  group-level reservation: let the page-relative scan group occupy the current
  page, then break before following visible content.

## Guard Docs

Run and visually inspect changed docs:
- `wc47_6pg`
- `wc51_4pg`
- `wild_02_paper_fig_10MB`
- `wc69_9pg`
- `wc04_4pg`
- `wb03_physics_lab_2pg`

Validation:

```bash
bash harness/focus_gate.sh quick --build
bash harness/gate.sh --no-build
python3 scripts/check_renderer_overfit.py
```

Accept only if:
- `med_02` page 3 contains `실험결과` table visually,
- page count stays 6/6,
- no new overflow,
- no unrelated page-count regression,
- changed docs are float/image docs and visually checked.

Reject if:
- the rule depends on the filename or the text `실험결과`,
- two consecutive scans become two new pages without Hancom evidence,
- text-only documents change,
- `wild_02` gets worse while fixing `med_02`.

## Patch Result

Implemented in `src/renderer/typeset.rs`:
- precompute additional `force_break_before` hints for page-relative full-page
  scanned-picture groups,
- only matches non-TAC `Square` pictures/picture-shapes with `flowWithText`,
  `vertRelTo=Paper`, `horzRelTo=Paper|Page`, body overlap, near-full-page
  height, and later visible flow content,
- groups consecutive scan paragraphs so `med_02` pi=3/pi=4 stays on one visual
  scan page and the break happens before following flow content.

Target evidence after patch:
- `med_02` dump page 2 contains only `Shape pi=3` and `Shape pi=4`.
- `med_02` dump page 3 contains `FullParagraph pi=8 "실험결과"` and the
  measurement rows.
- exported SVG `/tmp/diff/med_02____2_4MB/rhwp_svg_patch/source_003.svg`
  contains `실험결과` and table text.

Validation after patch:

```text
CARGO_BUILD_JOBS=1 docker compose --env-file .env.docker run --rm dev cargo build --release --bin rhwp
Finished release build

bash harness/focus_gate.sh quick --build
focus tier=quick: docs=15 improved=0 same=7 regressed=0 missing=8 new_overflow=0
OK med_02____2_4MB: 6/6
DIFF form_07_______________41KB: 12/11

bash harness/gate.sh --no-build
[gate] docs=142 improved=1 regressed=0 new_overflow=0
IMPROVE wc31_17pg: 12->13 (oracle 17)

python3 scripts/check_renderer_overfit.py
renderer overfit check passed with 8 known baseline finding(s).

CARGO_BUILD_JOBS=1 docker compose --env-file .env.docker run --rm dev cargo test --lib page_relative_scan_group_breaks_before_following_flow -j 1
test renderer::typeset::tests::page_relative_scan_group_breaks_before_following_flow ... ok
```

Known remaining validation gap:
- quick gate still reports 8 missing fixtures; restore/regenerate those before
  claiming full quick-corpus coverage.
- visual sweep is still needed on any docs changed by a regenerated gallery,
  especially `wc31_17pg` because the full gate page-count improved there.

## wc31 Side-Effect Check

`bash harness/gate.sh --no-build` reports:

```text
IMPROVE wc31_17pg: 12->13 (oracle 17)
```

This is acceptable as a side effect but not a solved target:
- `dump-pages` now reports 13 pages.
- Page 12 is a single large table with `diff=+3.5px`.
- Page 13 contains following form/table content with `diff=-3.2px`.
- Visual comparison still shows large logical drift versus Hancom around pages
  12-13, so `wc31` remains in the P2 stale/image/table interaction queue.

Do not mark `wc31` fixed from this patch. Treat it as "moved toward oracle,
still failing visually."

## Fresh Decision Check -- 2026-06-05

Decision for this failure family: **LAND candidate for scanned-photo content
loss**, pending normal code review/commit. Do not deploy yet.

Fresh validation:

```text
CARGO_BUILD_JOBS=1 docker compose --env-file .env.docker run --rm dev \
  cargo test --lib page_relative_scan_group_breaks_before_following_flow -j 1

result:
test renderer::typeset::tests::page_relative_scan_group_breaks_before_following_flow ... ok

python3 scripts/check_renderer_overfit.py
result:
renderer overfit check passed with 8 known baseline finding(s).

bash harness/gate.sh --no-build
result:
[gate] docs=149 improved=1 regressed=0 new_overflow=0
  IMPROVE  wc31_17pg: 12->13 (oracle 17)

python3 harness/look.py /tmp/diff/med_02____2_4MB --export
result:
Hancom=6 rhwp=6
look/page-01.png ... look/page-06.png regenerated
```

Fresh `dump-pages` target evidence:

- page 2 contains only the two scan paragraphs/shapes (`pi=3`, `pi=4`) and no
  following `실험결과` flow content.
- page 3 contains `FullParagraph pi=8 "실험결과"` plus the measurement rows.

## Clean Split Validation -- 2026-06-05

Decision: keep only the P1a scanned-photo source change as the land candidate.
Remove/bank unfinished `wild_02` multi-column float and P3 table-splitting
source experiments from this patch.

Current tracked source diff after cleanup:

- `src/renderer/typeset.rs` only.

Fresh validation on the cleaned patch:

```text
CARGO_BUILD_JOBS=1 docker compose --env-file .env.docker run --rm dev \
  cargo test --lib page_relative_scan_group_breaks_before_following_flow -j 1
result: passed

CARGO_BUILD_JOBS=1 docker compose --env-file .env.docker run --rm dev \
  cargo build --release --bin rhwp -j 1
result: passed

python3 scripts/check_renderer_overfit.py
result: renderer overfit check passed with 8 known baseline finding(s).

git diff --check -- src/renderer/typeset.rs
result: passed

python3 harness/look.py /tmp/diff/med_02____2_4MB --export
result: Hancom=6 rhwp=6

bash harness/gate.sh --no-build
result: docs=151 improved=1 regressed=0 new_overflow=0
  IMPROVE wc31_17pg: 12->13 (oracle 17)

python3 harness/look.py /tmp/diff/wild_02_paper_fig_10MB --export
result: Hancom=9 rhwp=7, still unresolved
```

Visual check:

- `/tmp/diff/med_02____2_4MB/look/page-03.png` shows the RHWP side now contains
  the `실험결과` table/content instead of losing it behind the scanned image.
- `wild_02_paper_fig_10MB` remains a separate P1b multi-column float failure and
  must not be described as fixed by this patch.

Fresh visual evidence:

- `/tmp/diff/med_02____2_4MB/look/page-02.png`: rhwp keeps the scanned page as
  a scan page. Minor scale/crop differences remain, but the following result
  table no longer paints under the scan.
- `/tmp/diff/med_02____2_4MB/look/page-03.png`: rhwp now renders the
  `실험결과` section and measurement table on page 3. Table scale/spacing is
  still not pixel-perfect, but the production-blocking content-loss bug is
  fixed for this structural class.

Side-effect review:

- The broad gate's only changed document is `wc31_17pg`, moving from 12 to 13
  pages toward its 17-page Hancom oracle.
- Refreshed visual: `python3 harness/look.py /tmp/diff/wc31_17pg --export`
  reports Hancom=17 and rhwp=13.
- `/tmp/diff/wc31_17pg/look/page-13.png` shows rhwp page 13 is a different
  logical section than Hancom page 13, so `wc31` remains unsolved. Keep it in
  the P2 stale-vpos/image/table interaction queue.

LAND rationale:

- The engine rule is structural, not file-specific.
- The rule is narrow to page-relative PAPER/PAGE Square scanned-picture groups.
- The target content-loss defect is visually fixed.
- Corpus gate reports no regressions and no new overflow.
- Overfit detector passes.

Known residuals:

- This does not solve multi-column float failures such as
  `wild_02_paper_fig_10MB`.
- This does not solve table scale/spacing fidelity on the `med_02` result page.
- This does not solve `wc31_17pg`; it only nudges pagination in the right
  direction.
