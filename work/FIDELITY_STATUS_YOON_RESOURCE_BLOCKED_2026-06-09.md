# Yoon Resource Status -- 2026-06-09

Status: blocked-font-resource / rejected-broad-substitution.

Representative: `photo_122p_civil_defense`, especially pages `11`, `28`, `41`, `64`, `87`, `117`, `125-127`.

## Classification

- Category: text/raster fidelity.
- Cause: document requests commercial Yoon family fonts such as `-윤명조320`, `-윤고딕320`, and `Yoon가변 윤고딕 320_TT`.
- Non-cause: page count. `photo_122p_civil_defense` is page-count clean in the current guard status (`129/129`).

## Evidence

Current corpus audit after the KoPub patch:

- `-윤명조320`: 16269 missing/platform-fallback runs.
- `-윤고딕320`: 14705 missing/platform-fallback runs.
- `-윤명조120`: 3968 missing/platform-fallback runs.
- `Yoon가변 윤고딕 320_TT`: 3768 missing/platform-fallback runs.
- `-윤고딕330`: 1969 missing/platform-fallback runs.
- Other Yoon variants total several thousand additional runs.
- No local Yoon resources exist under `web/fonts/` or `rhwp-studio/dist/fonts/`.

Representative pages:

- `photo_122p_civil_defense:11`: `-윤고딕320` 794 runs.
- `photo_122p_civil_defense:126`: `-윤명조320` 670 runs.
- `photo_122p_civil_defense:64`: `Yoon가변 윤고딕 320_TT` 388 runs.
- `photo_122p_civil_defense:87`: `-윤명조120` 539 runs.

## Decision

Do not map Yoon families to Noto, Pretendard, Nanum, or KoPub as a renderer rule. That would be a broad visual substitution, not an exact resource fix, and it would change glyph identity/metrics across many pages without proving Hancom parity.

Promotion requires one of:

- a legitimate Yoon webfont/embedding license and exact font resources; or
- an explicit product fallback policy that accepts a named substitute, with guard pages proving no regression.

Until then this remains blocked, not a renderer layout target.
