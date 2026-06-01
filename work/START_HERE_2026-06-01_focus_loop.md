# rhwp fidelity — focus-loop session status (2026-06-01)

Branch `mindlogic/feat/trust-lineseg-cache` @ 945b3d69. **Tree CLEAN — 0 engine edits, 0 commits this session.** Docker up, binary from 5/31 21:47, http :8799 live.

## What this session did
Ran the focus loop end-to-end (proven operational): `focus_gate.sh quick` (15 docs),
`drift.py`, `dump-pages`, compiled-in `RHWP_TYPESET_DRIFT[_LINES]` probes. Took the #1
quick target **report_form** from "unknown drift" to a fully-traced root cause.

## Quick-tier state (page count)
9 clean. DIFF: report_form 5/6, form_07 13/11, meeting 6/5, 15_… 6/5, accountability_eval 4/11.
Of these: meeting_summary (Δgap −0.5) + overseas_training (Δ−0.6) are **already correct guards**.
accountability_eval needs a **new capability** (wide-table width-fit + row reflow), not a fix.

## report_form — traced to the bottom (NOT landed; here's why)
- drift.py: p3/4/5 gaps −3 to −4.4pt short → under-paginates 5 vs 6.
- Probe DISPROVED the line-height-recompute hypothesis: rhwp reproduces the HWPX cache
  EXACTLY (fmt_ls==seg_ls, diff=+0.0). The ls=11.2 vs 14.9 is IN the cache.
- Cache encodes additive inter-para sb: gap = para_height + next.sb (e.g. pi21→22 = 36.0+13.3=49.3px).
  encoded_sb median 8px, 52/67 pairs. Guards: medschool median 0 (4 big-jump outliers), form_04 median −13.3 (clamped) → both unchanged by an sb fix. Probe data: `/tmp/diff/_probe_*.txt`.
- BUT both typeset AND render already place by cached vpos via `HeightCursor::vpos_adjust`
  (height_cursor.rs:75; anchor/page_base at layout.rs:2186/2216; per-para snap typeset.rs:1531).
  The gap SHOULD reproduce through that and doesn't → root cause is in the vpos anchor /
  `skip_spacing_before_prededuct` path, AND report_form's spacing is owned by the
  **zone-band accumulator** (#866/#874 in layout.rs ~2160-2240) because it's full of
  TopAndBottom tac tables — the most regression-prone, whack-a-mole-historied code in the engine.

## Why no blind commit
Per the standing objective-gated policy + done-means-visually-validated / dont-defer memories:
a change in the #866/#874 zone-band logic cannot be objectively proven non-regressing across
the ~60 currently-correct docs without a human visual pass (page-count gate is blind to
within-zone visual shifts). Landing it blind is the documented doc-09 failure mode.

## Recommended next step (supervised, ~30-60 min)
1. Add `RHWP_ZONE_DIAG` probe in layout.rs zone-leave (2160-2240) + render body loop (3332):
   print per-para placed-y vs cached vpos for report_form → confirm whether render snaps
   per-para or only column-top.
2. Narrowest edit: make render apply the per-para cache-vpos snap typeset does, gated to
   trust-cache paras with encoded_sb in (2px, 2×max_fs].
3. Gate: `fingerprint_lint.py` + `gate.sh` (74-doc page-count+overflow) + `drift.py` sweep
   across ALL staged docs (objective visual gate: report_form →~0/6p, no other doc median Δ>2pt).
4. Human eyeball report_form p2-6 + 3-4 OK docs at :8799 before commit. Land if green.

---
## UPDATE — attempted the fix (8 build cycles), BLOCKED on form_24 (gate RED)
- Root cause CONFIRMED: `height_cursor::vpos_adjust` pre-deducts curr_sb expecting
  render to re-add spacing_before; trust-cache render zeroes it → short gaps.
- Fix that WORKS for report_form (5→6, 0 page-count regressions): skip pre-deduction
  when cache left a real gap. WIP patch: `work/report_form_sb_fix_WIP.patch`.
- BLOCKER: same fix overflows form_24 (NEW page23 +19px VISIBLE, page54 +9.2px,
  page77 +4.2px) + org_diagnosis (+0.7px guard). 3 gap-magnitude discriminators tried
  (loose/tight/cap) — none separate report_form's win from form_24's overflow because
  report_form needs honoring large region gaps that form_24 also has.
- Tree CLEAN at HEAD, binary = clean HEAD. NOT committed (objective-gated policy: RED gate).
- NEXT (supervised, ~1 build): gate the skip on "honoring cache vpos stays within col
  bottom" (use vpos_corrected_end_y `applied`/clamp), so form_24's near-bottom paras
  keep pre-deduction. Then re-gate + eyeball report_form p2-6 + form_24 p23 at :8799.
