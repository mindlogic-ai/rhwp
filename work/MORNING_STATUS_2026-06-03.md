# rhwp fidelity — morning status 2026-06-03

Branch: `mindlogic/feat/trust-lineseg-cache` (LOCAL only, nothing deployed).
Corpus: **70/74 at oracle** (was 69/74). 4 OFF remaining.

## What landed this session (1 commit, LOCAL)

**`c8378740` — harness: resolve form_03 oracle + correct form_07 diagnosis**
(harness-only; no engine change — gate untouched.)

### form_03_signup_consent_form — RESOLVED (was a phantom OFF)
- It was OFF only because its oracle was `None` (never in hancom_pages.json).
- Root: the source (`hwpx-lab/samples_wild/form_03_signup_consent_form.hwpx`) is a
  **lineseg-less HWPX** (`grep '<hp:lineseg' = 0` — likely pypandoc/programmatic,
  not Hancom-authored). **Hancom's cloud converter REJECTS it**: doc2pdf status
  oscillates `F`/`I` with `process_page 0/0` forever (tried with *and* without
  `disable_hft`). No Hancom oracle is obtainable for this doc.
- rhwp renders it **cleanly in 2 pages** (export-svg: 0 overflow): a 15-row 서명부
  signature table, ~rows 1–12 + title/consent on p1, rows 13–15 on p2 — an
  obviously-correct natural overflow. **Visually validated both pages.**
- Recorded `oracle=2` in hancom_pages.json with **explicit provenance: rhwp-self-
  validated, Hancom-UNAVAILABLE** (not a Hancom-confirmed number). Cleared the
  phantom OFF. If Hancom ever supports lineseg-less HWPX, re-confirm.

### form_07 (12/11) — PRIOR DIAGNOSIS DISPROVEN (still OFF, but correctly understood)
- The inherited theory — *"pi=89 is one 단기목표 table with two disagreeing heights
  397.2 vs 409.0 (Δ11.8px); reconcile measure-vs-cut"* — was **WRONG**.
- An enhanced `RHWP_TABLE_DRIFT` probe with `ctrl_idx` proved **pi=89 contains TWO
  DISTINCT tables**: `ci=0` rows `[28.9,170.5,28.9,168.9]=397.2` and `ci=1` rows
  `[29.4,173.7,29.4,176.4]=409.0`. Each is measured **consistently** (cut_sum==mt_sum,
  diff=0). There is **no measurement inconsistency** and **no two-pass reflow** —
  `paginate()` is single-pass; the two fires are two tables, not one table re-fired.
- Real bug (look.py-verified p9–12 vs Hancom): rhwp packs too little onto p10.
  Table map: pi=87(우선순위), pi=89ci0/ci1(진단목표 A/B), pi=93/pi=94(간호수행 A/B).
  - Hancom: p10 = `[pi89ci1 + pi93]`, p11 = `[pi94 + 참고문헌]` → 11pp.
  - rhwp: p10 = `[pi89ci1 ONLY]` (bottom half wasted) → pi93→p11 → pi94→p12 → 12pp.
  - Between pi89ci1 and pi93 sit empty spacer paras pi=90 (cached lineseg
    **vpos=64000 = page bottom**), pi91 (30957), pi92 (33157). rhwp trusts pi90's
    vpos-jump → cur_h fills p10 → forced break → pi93 orphaned to p11. The source's
    vpos reset (64000→30957) encodes a page break *before* pi93; **Hancom ignores
    it and re-flows pi93 onto p10.** → classic **cache-staleness**.
- Reclassified `measure-inconsistency` → `cache-divergence` (same family as
  large_01/report_form). Not a clean structural fix; needs a cache-staleness /
  forward-pack detector (high-blast). Memory `rhwp-dead-leads` entry #4 corrected.

## The 4 remaining OFF — all cache-divergence or feature-gap (NOT unattended-safe)

| doc | state | category | why not landed tonight |
|---|---|---|---|
| **form_07** | 12/11 (+1) | cache-divergence | trailing empty-spacer vpos-jump fills p10; Hancom re-flows. Fix = don't honor the jump when a following table would then fit → fights trust-lineseg-cache, high-blast. |
| **large_01** | 37/39 (−2) | cache-divergence | in-cell content UNDER-measured. Source-inspected this session: cells hold NESTED TABLES + PICTURES (no grouped shapes — that framing was wrong). Two code suspects in `height_measurer.rs::measure_table_impl`: (1) 3 cells w/ nested-tbl+pic take the `has_nested_table_in_cell` branch (line 872) that NEVER adds in-cell pic height (only the `else` branch calls `measure_non_inline_controls_height`); (2) 3 SQUARE-wrap pics dropped (non_inline counts only TopAndBottom). Caveat: TopAndBottom pics consume flow → `para_top` may already embody them (instrument before adding, or double-count). Shared cell-height path = high-blast; 16MB (slow). See `large01-cell-undermeasure`. |
| **report_form** | 5/6 (−1) | cache-staleness | the snap-rejection lead (RHWP_VPOS_DEBUG @ height_cursor.rs:203, applied=false on lazy-path body paras) is the only untried angle, but the fix is vpos_adjust/anchor surgery that **needs a human visual pass on ~60 currently-correct docs** (page-count gate is blind to the drift it risks). 8+ prior cycles; sb/gap/column discriminators provably doomed (form_24 counterexample). See `report-form-sb-zeroing`. |
| **accountability_eval** | 4/11 (−7) | needs-feature | Hancom width-fits + re-wraps wide tables; rhwp draws literal. Requires a NEW engine width-fit capability, not a fix. |

**Honest read:** the corpus is at the cache-divergence / feature-gap asymptote.
The easy/surgical wins are done (69→70/74 incl. today's form_22, doc13, form_03).
Each of the 4 remaining needs either a stale-cache detector or a wide-table
width-fit feature — both are supervised, high-blast, multi-build pieces of work
where a green page-count+overflow gate does **not** prove visual safety. None is
appropriate to blind-land unattended, which is precisely why they're the residual.

## Recommended next targets (for a SUPERVISED session, in order of tractability)

1. **large_01 — SUPERVISED ATTEMPT made (2026-06-02); diagnosis now sharp, no safe fix
   landed.** look.py: 2 slip points (p15, p19), both the same class — rhwp packs a tall
   diagram-table + the FOLLOWING table onto one page where Hancom breaks after the diagram.
   Slip 1 = rhwp splits table pi=67 (org-chart flowchart) onto p15+p16 while Hancom keeps
   it whole on p16; the room comes from pi=66 (the L·I·F·E triangle 2x2 table). CELLINV
   probe: pi=66 row1 = 2 nested TAC tables + a **315.7px treat_as_char TopAndBottom triangle
   pic**; content 815.1 < declared 854.7 → row floored at declared 854.7 (rhwp already uses
   the full declared height — NOT a gross under-measure; suspect #1 stays disproven).
   DECISIVE: Hancom renders pi=66 row1 **~78px TALLER** (fills ~the whole 933px page) — that
   slack is exactly what rhwp uses to start pi=67. So it's a HEIGHT-GROWTH divergence, not
   split-policy. Growth SOURCE still ambiguous (3 candidates: pic intrinsic>declared / nested
   tables taller in Hancom / cached element positions under-stating re-flow spacing — do NOT
   assume width-fit, the pic is treat_as_char/inline). NEXT (focused follow-up, free first):
   measure each in-cell element's y-extent in Hancom p15 PDF vs rhwp p15 SVG to see WHICH
   grows, then probe that element's dims. Fix is on the shared cell-height path → high-blast,
   gate + multi-table-doc visual pass. ~2-3 more builds; a focused follow-up, NOT a blind land.
   (Full detail in the `large01-cell-undermeasure` memory.)
2. **report_form vpos-snap rejection.** Instrument `applied=false` cause on its
   lazy-path body paras; if the rejection is a narrow backward-clamp/lazy-base
   under-computation (not the sb route), a targeted vpos_adjust fix may land with a
   form_24 visual guard. Plan a 60-doc visual sweep before committing.
3. **form_07 forward-pack.** Only if a general "collapse trailing empty spacer paras
   when the next block would fit the current page" rule can be made structural and
   gate-clean — likely the same machinery that would help report_form.
4. **accountability_eval** — scope the width-fit feature only if 1–3 are exhausted.

## Gotchas / state for next session
- Working tree CLEAN; binary built from HEAD (incl. the now-reverted probe, which
  only added stderr under RHWP_TABLE_DRIFT=1 — rendering identical to HEAD).
- `/tmp/diff/harness/baseline_pc.tsv` was STALE at session start (had form_22=38,
  doc13=20 pre-today's commits) — re-synced from repo `harness/baseline_pc.tsv`.
  Both hancom_pages.json (repo + /tmp/diff/_hancom_pages.json) now include form_03=2.
- form_03 Hancom GT is permanently unobtainable (lineseg-less; converter rejects).
- The live paginator is **TypesetEngine (src/renderer/typeset.rs)**, NOT
  pagination/engine.rs (only under RHWP_USE_PAGINATOR=1). Built-in `RHWP_TABLE_DRIFT=1`
  prints per-table eff_h/mt_sum/cut_sum/cur_h in typeset_block_table — invaluable;
  add `ctrl_idx` to it again if re-debugging multi-table paragraphs.
- NEVER deploy. LOCAL-first until told otherwise.
