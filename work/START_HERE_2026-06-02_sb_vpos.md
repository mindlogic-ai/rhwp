# START HERE — 2026-06-02 (visual fidelity: sb / vpos-snap)

Branch `mindlogic/feat/trust-lineseg-cache`. Working tree CLEAN (reverted my probes/hack;
saved as `work/SESSION_sb_vpos_probes_2026-06-02.patch`). LOCAL only — nothing pushed.

## What this session established (all evidence-backed, not theory)

1. **LOOKED at meeting_summary** (the handoff's "obviously cramped" flagship): it actually
   renders FAITHFULLY now — drift.py gaps match Hancom ±0.5pt. It's a trust-cache hit. The
   "cramped" claim was overstated vs the current binary. Not a real defect.

2. **The line-height-fallback root-cause theory is DEAD.** Probe `RHWP_LH_DIAG` in
   `corrected_line_height` (mod.rs:574): report_form + meeting_summary emit ONLY
   `LH_PASSTHRU` — the PERCENT branch `max_fs*ls_val/100` (mod.rs:576) NEVER fires. These
   docs use cached `raw_lh`. **Do not "fix the PERCENT fallback"** — it's dead code for
   these docs. Corrected [[dont-defer-fix-one-by-one]] + [[report-form-sb-zeroing]] memories.

3. **The real defect = trust-cache zeroes `spacing_before`.** drift.py: report_form p3-5
   gaps 33.6→29.5 (0.88), overseas p1 9.4→8.4 (0.89) — a consistent ~12% tightening that is
   the dropped sb (NOT line-height). meeting_summary (cache hit) is exempt.

4. **A controls-guarded pagination sb-rule PASSES the gate but ORPHANS.** Bumping
   `formatted.{spacing_after,total_height,height_for_fit}` by the cache-reserved deficit
   `(next.first_vpos − this.last_bottom)px − sa` (3<def<60, both paras `controls.is_empty()`)
   → gate GREEN: report_form 5→6, **form_24 holds 84**, 0 regressions on 22 staged docs.
   The controls guard is what beats the form_24 counterexample (doc13 19→21 without it).
   BUT render still draws sb=0 → report_form p6 is a 2-line orphan, breaks misaligned. A
   HALF-FIX. Reverted. (form_24's "absolute counterexample" status is downgraded — the
   guard separates them on the pagination side.)

## THE fix to pursue next (the right layer)

The shared `HeightCursor::vpos_adjust` drives BOTH pagination (typeset vpos_snap) AND render
(layout.rs:2605). If it APPLIED for report_form's body paras, both passes would snap to the
cached airy positions → count + spacing + breaks fixed together (and ZERO sb-rule needed).
It's REJECTED on the **lazy-base path**: height_cursor.rs:150-164 returns `(prev_vpos_end,
false)` when `lazy_base < 0` → `applied=false` → tight fallback. The 8px backward clamp in
`vpos_corrected_end_y` (layout.rs:267/274) does NOT block forward/airy corrections, so the
blocker is the lazy_base derivation, not the clamp.

NEXT: `RHWP_VPOS_DEBUG=1` (probe already at height_cursor.rs:203) on report_form → find WHY
lazy_base goes invalid for its body paras → fix the derivation so the snap applies → gate +
**~60-doc visual pass** (this fn touches every multi-paragraph doc; page-count gate is
visually blind here, so this is supervised work, not a blind unattended land).

## Boot

```
cd /Users/jaehoshin/Desktop/mindlogic/factchat/worktree-rhwp-poc/rhwp
# binary rebuilt clean from HEAD this session.
python3 harness/drift.py /tmp/diff/report_form      # objective gap table
python3 harness/look.py  /tmp/diff/report_form --export  # then READ look/page-0N.png
bash harness/gate.sh --no-build                     # 19 staged docs, page-count+overflow
```
Recover this session's probes (LH_DIAG + SBSA_GAP classifier + the pagination hack):
`git apply work/SESSION_sb_vpos_probes_2026-06-02.patch`
