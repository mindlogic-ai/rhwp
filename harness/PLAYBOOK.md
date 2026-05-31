# rhwp fidelity ralph — agent playbook (the anti-hardcode contract)

You are one iteration of an autonomous loop fixing rhwp page-count/layout drift.
Your job is NOT to make every number move. Your job is to land **general, structural**
fixes and to **correctly classify** docs that can't be generally fixed. A loop that
"fixes" 11/11 by memorizing is a FAILURE. A loop that fixes 3 and classifies 8 with
honest reasons is a SUCCESS.

## The one rule that matters
**Fix on STRUCTURE, never on document CONTENT.** Allowed discriminators: lineseg
presence, vpos resets, item type (TAC/TopAndBottom/Square), numbering id/level, table
geometry, overflow magnitude, page_break kind — properties *any* document has. FORBIDDEN:
`text.contains("<literal>")`, fixture-named fns (`is_sampleNN`, `_hwp`), doc ids.
`fingerprint_lint.py` blocks these mechanically; if it fires, your fix is wrong — redo
it structurally, don't add to the baseline.

## Per-iteration steps
1. `bash harness/ralph.sh next` → target doc + objective drift table.
2. Read the drift table. The `first_divergent_page` localizes the bug. Confirm the
   real cause with an **env-gated `eprintln!` probe** (e.g. `RHWP_*_DIAG`) — never guess.
   Build (`CARGO_BUILD_JOBS=1`, ~80s), read the numbers, find the ONE wrong value.
3. **If no general structural cause in ~3 probes → STOP this doc.** Set its queue status
   to `blocked` with a one-line reason (metric-only / needs-feature / cumulative-no-single-cause).
   This is a valid outcome. Move on. Strip all probes (`grep -rn _DIAG src/` must be clean).
4. Patch the engine (structural only, `// === [Mindlogic patch — <name>] ===` markers).
5. `bash harness/ralph.sh verify` → runs fingerprint_lint + corpus gate + held-out check.
   Must print `ALL-GREEN`. Any RED → `git checkout -- src/`, mark doc blocked, move on.
6. ALL-GREEN → re-render the target, eyeball drift.py again (target improved, gaps now
   match Hancom ±2pt). Then `gate.sh --update-baseline` + `git commit` LOCAL. Update queue
   status to `done` with before/after page count.
7. NEVER deploy (no WASM build, no rsync, no Vercel). Local commits only.

## Gotchas (learned, don't relearn)
- Binary is **Linux ELF — docker only**. Native exec fails. `_sweep.sh` is bogus.
- `dump-pages` metric **LIES** on TopAndBottom docs (phantom -300..-500px). Use `drift.py`
  (objective Hancom-bbox vs SVG) as the truth signal. dump-pages is fine for per-ITEM probing.
- The cell trust-lineseg-cache is **already implemented** (height_measurer.rs Bucket A).
  Don't re-add it. form_07's para=64 table is **not** over-tall (Hancom renders it equally
  tall — verified by bbox). See rhwp-dead-leads memory. Don't re-chase either.
- Held-out docs (corpus.tsv `set=held`): do NOT read their oracle or name them in code.
  If a fix helps dev but not held, it memorized → reject.
- Build OOMs on multi-job → always `CARGO_BUILD_JOBS=1`.
- 2 pre-existing stashes exist (not loop's) — ignore them.

## Queue
`harness/queue.tsv` — `pending` → work it; `blocked`/`done` → skip. Categories:
cumulative-drift (hard, likely blocked), metric-lie (fix drift signal first), image-pagination,
under-paginate, needs-feature (blocked — requires new capability like wide-table reflow).
