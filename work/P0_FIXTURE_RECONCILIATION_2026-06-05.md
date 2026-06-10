# P0 Fixture Reconciliation — 2026-06-05

Purpose: make the quick fidelity gate trustworthy before landing more renderer
changes.

## Current Quick-Gate Problems

Fresh command:

```bash
bash harness/focus_gate.sh quick --build
```

Current result:

```text
focus tier=quick: docs=15 improved=1 same=12 regressed=1 missing=1 new_overflow=5
IMPROVE report_form: 5->6 oracle=6
DIFF 15_3740450_research_admin_innovation_meeting_template: 6/5
DIFF accountability_eval: 4/11
DIFF form_07_______________41KB: 12/11
REGRESS 05_3781559_medschool_car_2bu_je_plan: 4->3 oracle=4
+OVERFLOW 20_3727659_resume_2605_ai: 0->1
+OVERFLOW accountability_eval: 0->3
+OVERFLOW meeting_summary: 0->2
+OVERFLOW overseas_training: 0->2
+OVERFLOW report_form: 0->1
MISSING meeting
```

Interpretation:
- This is not a clean renderer regression gate yet.
- The restored fixtures made hidden issues visible, but the baseline metadata
  was not calibrated against the exact staged sources.

## `meeting`

Status:
- Still missing.
- Bounded search did not find an exact `meeting.{hwp,hwpx}` source under the
  known `hwpx-lab` and `factchat` trees.
- Do not alias this to `wb12_gangjin_meeting_4pg` or `meeting_summary`; the
  expected page counts and document class differ.

Required next step:
- Locate the original source that corresponds to focus manifest `meeting`
  Hancom 5 / rhwp 6, or remove/exclude it from quick until the exact source is
  available.

## `05_3781559_medschool_car_2bu_je_plan`

Status:
- Staged source:
  `/tmp/diff/05_3781559_medschool_car_2bu_je_plan/source.hwpx`
- Licensed source:
  `/Users/jaehoshin/Desktop/mindlogic/factchat/worktree-hwp-licensed/server/tests/hwp_validation/golden_tables/05_3781559_medschool_car_2bu_je_plan/_doc.hwpx`
- These have the same section size/preview and are effectively the same staged
  HWPX source.
- Cached Hancom PDF:
  `/Users/jaehoshin/Desktop/mindlogic/factchat/worktree-hwp-licensed/server/tests/hwp_validation/synth_text_cache/05_3781559_medschool_car_2bu_je_plan.pdf`
- `pdfinfo` says Hancom PDF has 4 pages.

Clean HEAD comparison:
- Created a temporary clean worktree at `/tmp/rhwp-head-check` on `dcebfaba`.
- Built native `rhwp` there.
- Rendered the same staged source.
- Clean HEAD also produced 3 pages.
- Therefore the current `med_02` page-relative scan patch is not the cause of
  the quick-gate `05_3781559` `4->3` line.

Visual artifacts:
- `/tmp/diff/05_3781559_medschool_car_2bu_je_plan/look/page-01.png`
- `/tmp/diff/05_3781559_medschool_car_2bu_je_plan/look/page-02.png`
- `/tmp/diff/05_3781559_medschool_car_2bu_je_plan/look/page-03.png`
- `/tmp/diff/05_3781559_medschool_car_2bu_je_plan/look/page-04.png`

Visual read:
- page 1: rhwp cover content is lower/overpacked relative to Hancom and visible
  body content begins on page 1 where Hancom leaves more cover space.
- page 3: rhwp contains most of Hancom page 3 plus content that Hancom leaves
  for page 4.
- page 4: Hancom has the final `향후 계획` tail; rhwp has no page 4.

Structural class:
- page-anchored `TOP_AND_BOTTOM` cover table
- paragraph-relative/TAC tables later
- one ordinary paragraph-relative Square picture, not PAPER-relative full-page
  scan

Conclusion:
- Treat `05_3781559` as a separate P2/P3 drift target or recalibrate the quick
  baseline for the staged source.
- Do not count it as a regression from the current P1 scanned-photo patch.

## `accountability_eval`

Status:
- Focus manifest says Hancom 11 / rhwp 4.
- Fresh Hancom conversion of the currently staged
  `/tmp/diff/accountability_eval/source.hwpx` produced Hancom 6 pages.
- Current rhwp produces 4 pages.
- Dedicated look artifacts now exist:
  `/tmp/diff/accountability_eval/look/page-01.png` through `page-06.png`.

Conclusion:
- This is still a real wide-table fit/height bug.
- It is also a source/oracle mismatch. Do not chase the 11-page oracle until
  the exact 11-page source is found.

## Gate Policy Until P0 Is Resolved

For renderer patches:
- Use `harness/gate.sh --no-build` for broad regression detection against the
  original full baseline.
- Use `harness/focus_gate.sh quick --build` as an informative focus surface,
  but annotate:
  - `meeting` missing
  - `05_3781559` baseline stale for staged source
  - `accountability_eval` oracle/source mismatch
  - restored-doc overflow markers need clean-baseline recalibration

Do not run `--update-baseline` until:
- exact fixture sources are resolved, or
- the quick manifest explicitly marks unresolved docs as excluded/stale.
