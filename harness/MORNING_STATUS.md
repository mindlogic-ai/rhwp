# rhwp fidelity — morning status (2026-06-01, overnight session)

## TL;DR
You asked: "make this into a ralph/harness that won't hardcode like Codex did."
**Done + committed.** Then "keep going, close the gap" — I probed all 11 DIFF docs
with the new objective metric and **landed 0 engine fixes on purpose**: none has a
safe, structurally-general fix that can be confirmed without your eyes on the page,
and forcing one blind is exactly the Codex/doc-09 failure mode the harness exists to
prevent. The honest gap-closer is a short visual-gated session WITH you — set up below.

## What shipped (committed LOCAL on mindlogic/feat/trust-lineseg-cache, NOT deployed)
- `34c5ab2c` — **the harness**: `harness/`
  - `drift.py` — objective metric: Hancom-PDF-bbox vs rhwp-SVG line gaps (pt). REPLACES
    dump-pages' `used/hwp_used` which LIES on TopAndBottom docs (-300..-500px phantoms).
    PROVEN: on med_03 it cleanly showed p1-14 byte-perfect, divergence isolated to p16.
  - `fingerprint_lint.py` — blocks `text.contains("<hangul>")` / fixture-named fns
    (the Codex hardcode move) mechanically. Exit 1 = no commit.
  - `gate.sh` — build + page-count + overflow regression gate across all 74 docs.
  - `corpus.tsv` — 10-doc held-out split (fix must help held, not just dev = anti-memorize).
  - `ralph.sh` + `PLAYBOOK.md` — the gated loop; **"classify BLOCKED" is a valid outcome.**
- `<next>` — **queue.tsv**: all 11 classified with hard evidence (below).

## The 11 — why each is blocked (evidence, not guesses)
| doc | gap | blocked because |
|---|---|---|
| med_03 | +1 | p16 has only 29.6px room (body 946.7, used 917.1); heading group 42.6px legit doesn't fit. Root = upstream image-region (p15) accumulation, not an orphan. |
| 09 | +2 | metric-lie + cover float overlap; prior wrong-fix already reverted. High risk. |
| form_07 | +2 | cumulative sub-page drift. para=64 table is NOT over-tall (Hancom bbox = 115pt/row, equal). |
| form_22 | +1 | tiny mixed per-page diffs accumulate; "phantom" p18 holds real 117px content. |
| huge_01/02 | +5/+6 | same cumulative-drift family as form_07. |
| report_form | -1 | uniform -13/-31/-24/-32px per-page SHORTFALL = line-height-base family (highest blast). |
| large_01 | -2 | under-paginates + 7 overflow markers (packs too much → clipping). |
| meeting/15 | +1 | image-region pagination (p3/p4 = 4.5/5.5MB image SVGs); same doc. |
| 13 | +1 | complex table-block break (P7 underfills 264px then 14x3 784px table on P8). |
| accountability_eval | -7 | needs a NEW capability (wide-table width-fit + row-height reflow), not a fix. |

## Do this first when you wake (the one thing that unblocks everything)
Open **http://localhost:8799/_MORNING_REVIEW.html** — Hancom vs current rhwp at each
divergence boundary. For each, the only question is: *does Hancom merge/split where rhwp
doesn't?* Your visual call on 2-3 of these tells me which have a real fix vs which are
correct-but-different. Then I run the gated loop (`ralph.sh next` → patch → `ralph.sh
verify` → commit) on the ones you greenlight. With your eyes on the gate, these become
landable; without them, committing is gambling on the 60 OK docs.

## State
Tree CLEAN at the 2 harness commits on `mindlogic/feat/trust-lineseg-cache`. Binary = clean
HEAD. No engine edits. No deploy. 2 old stashes (not mine) still parked — ignore.
