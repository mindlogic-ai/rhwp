# rhwp fidelity — session status 2026-06-01/02 (visual-loop session)

Branch `mindlogic/feat/trust-lineseg-cache`. **2 fixes LANDED** (local, not deployed).
HEAD = `48f310ab`. Clean binary, lint clean, gate green (0 regressed across 74 docs).
baseline_pc.tsv updated.

## ✅ LANDED THIS SESSION (2 commits, gated GREEN, visually confirmed)

1. **`8ca24c17` — near-empty vpos-reset spillover orphan.** huge_01 46→41, huge_02 73→67,
   med_03 48→47 (all = oracle). The Task #321 vpos-reset trigger forced a page break for a
   new region even when the current page held only a small tail that overflowed a FULL prior
   page. Suppress when 3 STRUCTURAL conds hold: near_empty(<20%) + prior_full(≥85%, new field
   `prev_flushed_used_height`) + reset-para-has-visible-text. This was the REAL bug behind the
   "line-height/gradual accumulation" symptom on the two biggest over-paginators. See
   [[near-empty-vpos-reset-orphan]]. Magnitude alone can't separate orphans from med_02's legit
   cover/section breaks — needed prior-full + reset-para-text.

2. **`48f310ab` — sub-line last-row absorb.** form_07 13→12. The last-row orphan guard
   (table_layout/typeset row walk) only absorbed tight-fit final rows (≤15%/≥85% of avail). A
   MID-SIZE final row spilling by a pure rounding amount was stranded. Added case (c): absorb
   ANY final row whose overflow ≤3px (sub-line), keyed on overflow magnitude not row size.
   form_25/27 held.

## ENTIRE remaining tail is ROOT-CAUSED (no tractable structural wins left)

**The dominant remaining cluster = in-cell content-height measurement vs declared cell height**
(see [[table-rowheight-drift-cluster]]). DEEP + HIGH-BLAST (touches every table doc). Do NOT
blind-gamble — needs a dedicated session: measure Hancom row pitch via `pdftotext -bbox`, build
a structural discriminator, gate all 74 docs.
- **form_07 (12 vs 11, residual +1):** rhwp honors an INFLATED declared `table.common.height`
  (397 vs content 277) via the "honor the larger of declared/natural" rule (height_measurer.rs
  ~1186). Conversion-inflated declared height = SAME cache-staleness class as report_form.
- **large_01 (37 vs 39, -2):** the SAME bug's under-variant — rhwp UNDER-measures in-cell
  grouped-diagram height so the table stays at declared (~877px) where Hancom grows past it.
  `measure_non_inline_controls_height` misses complex grouped diagram containers.
  See [[large01-cell-undermeasure]].
- **report_form (5 vs 6, -1):** cache-staleness, known-stuck. [[report-form-sb-zeroing]].
- **accountability_eval (4 vs 11, -7):** needs a NEW wide-table width-fit capability (feature).
- **form_22 (38 vs 37, +1):** subtle cumulative ~9px drift + vpos-reset on a stacked multi-
  section page; render matches at the suspected page, location murky. Deep.
- **doc 13 (gate 20 vs oracle 19):** SOURCE-FILE MISMATCH artifact — look.py (source_converted
  or .hwp) renders 19=19; gate counts 20 via a different source file. Not a real bug.

**Overflow tail = all BENIGN (verified this session):** doc 07 (ov=16) = 14 per-page header-
frame sentinels (pi=usize::MAX, artifact) + 2 sub-6px PartialTable bleed. form_20/26/med_01
emit ZERO overflow on current engine (baseline counts were stale). overseas_training 2 markers
benign. No real clipping anywhere.

## The loop (worked well this session)
look.py vision-first → fan out read-only triage to subagents (kept main context lean across a
long session) → env-gated probe for the exact value → narrowest STRUCTURAL fix → find the
discriminator on regression (med_02), reject+narrow → gate BOTH dims 74 docs → re-look → commit
LOCAL + memory. Strip every probe (`grep _DIAG src/` clean). The dump used= metric LIES on
TopAndBottom — confirm fill via SVG max-y, not the metric (burned time twice trusting it).

Tree: committed at 48f310ab, clean binary, lint clean, baseline updated.
