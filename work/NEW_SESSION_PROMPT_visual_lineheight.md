# New session — rhwp VISUAL fidelity (line-height), NOT page count

Invoke the `rhwp-fidelity-fix` skill first. Work in
`/Users/jaehoshin/Desktop/mindlogic/factchat/worktree-rhwp-poc/rhwp`,
branch `mindlogic/feat/trust-lineseg-cache`. LOCAL ONLY — do not deploy or push
unless Jaeho explicitly says so.

## Read this first — the honest state (why the last sessions felt like "nothing fixed")

The campaign has been optimizing **page count** (a SAFETY gate). The metric Jaeho
actually flagged is **VISUAL fidelity**. They diverged. Page count is now 70/74,
but **the 24 docs in `harness/focus_set.tsv` were flagged by EYE**, and ~20 of them
are "page-count-OK" yet still render visibly wrong. Page-count parity ≠ visual parity.
The skill says this in bold ("page-count + overflow is NOT a fidelity gate") and it
got ignored. Don't repeat that.

## The systemic bug you can SEE (confirmed by looking, 2026-06-02)

**rhwp renders line spacing TIGHTER than Hancom.** Look at
`/tmp/diff/meeting_summary/look/page-01.png` (run look.py --export to refresh):
Hancom's table-cell text is airy/generously spaced; rhwp crams the same lines tighter.
Page count is 3=3 so every page-count gate calls it "OK" — but the render is obviously
cramped. Same tightness compounds in `report_form` (body under-paginates 5 vs 6) and is
the flagged defect in `meeting_summary`, `overseas_training`, `form_01`, `accountability_eval`.

Root cause (from the [[dont-defer-fix-one-by-one]] memory, NOT yet fixed): rhwp renders
PERCENT line-spacing on the NOMINAL font size (e.g. 10pt × 180% = 18pt) where Hancom uses
the font's NATURAL line metric as the base (≈28pt). The trust-lineseg-cache path is fine
for SNU docs (cache hit), but the wild/samples docs fall through to the PERCENT FALLBACK in
`corrected_line_height` (renderer mod.rs ~568). The discriminator to PROVE first: the cache
fires for SNU (untouched) but these docs hit the fallback → fix the fallback to use natural
font metrics, leaving the cache path alone.

## The loop (per doc — VISUAL, not page count)

1. **LOOK FIRST.** `python3 harness/look.py /tmp/diff/<doc> --export`, READ every
   `look/page-NN.png`. Name the visible defect. (Delegate page-reading to a subagent to keep
   context lean.) The render is the truth; page count is a tripwire only.
2. **MEASURE the drift objectively in pt** (not by eye, not by Gemini, not page count):
   Hancom per-line gap = `pdftotext -bbox /tmp/diff/<doc>/hancom.pdf` → group `<word yMin>`
   into lines → gaps; rhwp gap = parse `<text y=>` in `rhwp_svg_cur/*.svg`, pt = px/1.3333.
   `python3 harness/drift.py /tmp/diff/<doc>` tabulates it. Target: rhwp gap matches Hancom ±2pt.
3. **PROBE the exact fallback value** with an env-gated probe at the line-height site (the live
   path is the RENDERER, `corrected_line_height` / `calc_para_lines_height`; confirm the fallback
   fires for this doc and the cache does NOT). Don't theorize — instrument.
4. **Narrowest STRUCTURAL fix** to the fallback (keys on lineseg/font-metric/percent-flag —
   NEVER doc text; `fingerprint_lint.py` enforces this). Leave the trust-cache path untouched.
5. **Gate:** `python3 harness/fingerprint_lint.py` && `bash harness/gate.sh` must be clean
   (0 page-count regressions, 0 new overflow). Then re-`look.py` and confirm the render visibly
   moved toward Hancom (gaps now match ±2pt). RED → narrow or revert.
6. Commit LOCAL with before/after pt-gaps + which docs improved visually.

## Targets (focus quick tier — short, high-signal, shared fix class)

PRIMARY (the line-height cluster — one fix should move several):
1. `meeting_summary` (3pp, line-height too tight — clearest signal, start here)
2. `overseas_training` (4pp, row/line-height)
3. `report_form` (under-paginates 5/6 — the same tightness compounding)
4. `accountability_eval` (severe table row-height under-measure — may be same family)
5. `form_01` / `form_04` / `form_15` / `tiny_03` (short wild-form visual checks)

GUARD DOCS (must NOT regress visually — the line-height fix must leave these alone):
- `05_3781559_medschool_car_2bu_je_plan` (SNU, cache path — explicit guard in focus set)
- `medschool`, `form_04`, any SNU doc (cache-hit, sb-baked)
- The whole `gate.sh` corpus for page count.

DEFER (giant / known-hard cache-divergence — do NOT start here):
- `large_01` (in-cell diagram height-growth, see [[large01-cell-undermeasure]] — supervised cell-height surgery)
- `form_07` (empty-spacer vpos-jump cache-staleness, see [[rhwp-dead-leads]] #4)
- `huge_01/02`, `med_03`, `09` (giant cumulative — page-count-fixed, visual review only if time)

## Hard rules
- **No fingerprinting** — structural fixes only; `fingerprint_lint.py` blocks doc-text branches.
- **LOOK before and after every change.** "Page count unchanged" is NOT "fixed." Stats lie on
  TopAndBottom/tables; the SVG render + pt-gap table are the truth.
- ~3 builds per doc; if it resists a clean+gated fix, bank a sharp note and move on.
- Commit messages end with: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- NEVER deploy. The 25 local commits are UNPUSHED — ask Jaeho before pushing to back them up.

## State pointers
- `harness/focus_set.tsv` (24 flagged docs; its `rhwp_pages` column is a STALE June-1 snapshot —
  trust the live binary, not that column). `harness/FOCUS_PLAYBOOK.md`, `focus_index.py`
  (regenerates `/tmp/diff/_FOCUS_INDEX.html`), `focus_next.py` (also shows stale counts).
- Page-count fixes that DID land (verified): form_22 38→37, doc13 20→19, + earlier huge_01/02,
  med_03, meeting, 15, 09, form_07 13→12, form_03 resolved. These are real but mostly orthogonal
  to the VISUAL line-height work below.
- Sources for some docs are cleaned from `/tmp/diff/<doc>/`; restore from
  `hwpx-lab/samples_wild/` or `mindlogic_factchat_server/hwpx_prod_samples/`, or regenerate via
  `.claude/skills/rhwp-fidelity-fix/scripts/run_diff.py <file>`.
