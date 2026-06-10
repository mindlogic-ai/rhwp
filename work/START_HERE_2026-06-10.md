# START HERE — 2026-06-10 (Claude session wrap)

## State

- Tree: `mindlogic/feat/trust-lineseg-cache` @ `29e7146e`, **62 commits unpushed**, dirty diff intact
  (backup: `/tmp/rhwp_dirty_full_backup_2026-06-10.patch`). Binary = current dirty tree.
- Corpus: 21 docs, **19/21 page-exact** vs Hancom. Gate baseline refreshed (`/tmp/diff/harness/baseline_pc.tsv`).
- Fresh visual board (viewed page-by-page): `/tmp/diff/_review_all_current_2026-06-10/index.html` (serve via :8799).
- 5 deleted corpus sources restored (something wiped source.hwpx from 05/15/meeting_summary/overseas_training/report_form after 06-09; recipe in Claude memory `codex-loop-state-2026-06-10`).

## Findings this session (all measured, not guessed)

1. **05/15 "+1 page" is NOT a code regression** — all 4 revert configs render identically.
   It's a **conversion-variant artifact**: desktop 한글 11-saved hwpx (xmlVersion 1.2) paginates EXACT;
   Hancom cloud-API conversions (Hangul 13 LIN64, xmlVersion 1.5) carry different linesegs → +1 page
   on cover-band (05) / photo-cell (15) patterns. Desktop fixture: `/tmp/diff/05_*/source_desktop_v11.hwpx` (4p = exact).
   **→ open bug: cloud-conversion lineseg +1 drift. Production-relevant (factchat .hwp upload uses the cloud converter).**
2. **Upstream rebase rejected by measurement**: edwardkim devel = v0.7.15, 668 commits ahead.
   Clean upstream sweep = **14/21** (09: 51→59 +57ov, 13: −2 +40ov, civil_defense −7, photo_form24 −3, form_07 +1)
   vs our 19/21. Worktree: `../rhwp-upstream` (GIT_LFS_SKIP_SMUDGE=1). Sweep: `/tmp/diff/harness/_upstream_v0715.tsv`.
   Cherry-pick candidate: upstream `Fix issue 1133 nested table cell height` (our deferred cell-height family).
3. Repo `harness/hancom_pages.json` stale for k_star (19 → truth 21).
4. Fonts: 한컴 faces are FREE incl. commercial (font.hancom.com) → bundle next. Yoon needs paid 2차 임베딩 license
   (윤디자인 B2B / font.co.kr). Garamond → EB Garamond fallback. HY → low run-count, fallback defensible.

## Landed this session

- **Garamond → EB Garamond (OFL) bundled**: `web/fonts/EBGaramond-{Regular,Italic}.ttf` + LICENSE,
  registered in `font-loader.ts` + `font_substitution.js`, documented in `web/fonts/FONTS.md`.
  Audit: doc 09 p30/31 Garamond 3,445 runs now `bundled`. Rust metrics deliberately NOT aliased
  (protects 09's 51-page count; glyph render only). Visual check: serif renders on focused board
  `/tmp/diff/_review_09_garamond_ebg_2026-06-10/`.
- 한컴 고딕/한컴산뜻돋움 confirmed NOT on free font.hancom.com portal (only 6 specialty faces) and NOT
  in 한컴독스 OFL set → stays B2B-only. Remaining downloadable freebies: exhausted.
- webhwp box verified live via ssh: v0.7.13-1 active (May 27!) + v0.7.13-2 rollback sibling, nginx OK.
  Production is 2 weeks behind local fidelity state.

- **한컴 고딕 + HY울릉도M/B bundled from webhwp SDK** (`Shared/TTF/`, listed in Hancom's own
  `UnlicenseFontList.ini` = embedding-unrestricted). Registered in font-loader + substitution; audit:
  photo_w31:2/6 한컴 고딕 672 runs now `bundled`; visual board `/tmp/diff/_review_w31_hancomgothic_2026-06-10/`
  near-parity. Yoon faces on the same box (HANYGO*/HANYoonGothic*) are NOT on the unlicense list — do not copy.
- Font impact quantified (audit TSV): 272,618 corpus runs; remaining missing ≈18%, of which **Yoon ≈84%**
  (윤명조320 16.3k, 윤고딕320 14.7k, …) concentrated in civil_defense + wild_02. For 19/21 docs fonts are done.
  Optional: bundle 함초롬 (HANBatang/HANDotum on box, unlicense-listed) to kill the 54.7k CDN dependency.

## Next actions (priority order)

1. Split the 5.6k-line dirty diff: accepted scope (fonts/serializer/export/harness + accepted patches per
   `work/PRODUCTION_GATE_AUDIT_2026-06-09.md`) → commit; probe leftovers → stash/branch. **Push all 62+ commits.**
2. Bundle 한컴 fonts (free) the same way as KoPub/Gyeonggi; rerun font resource audit.
3. New bug queue item: cloud-conversion lineseg +1 drift (05/15 pattern) — probe lineseg deltas between
   `source_desktop_v11.hwpx` and `source.hwpx` on 05, find the structural discriminator.
4. Yoon font B2B inquiry (Jaeho) — 31k runs in civil_defense, biggest visual lever.
5. Deploy remains blocked on explicit "go" (local fidelity-first directive).
