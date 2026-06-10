# Soonchunhyang Font Resource Status -- 2026-06-09

Status: blocked-font-resource / blocked-source-artifact / rejected-broad-substitution.

Representatives:

- `wc15_7pg:7`: `순천향체` 430 runs.
- `wc15_7pg:6`: `순천향체` 290 runs.
- `wc16_6pg:6`: `순천향체` 277 runs.
- `wc17_6pg:4`: `순천향체` 250 runs.

Guard: `report_form:2`.

## Classification

- Category: text/raster fidelity.
- Cause: exact `순천향체` font resource is missing.
- Secondary blocker: the `wc15_7pg`, `wc16_6pg`, and `wc17_6pg` source files are missing from `/tmp/diff`, so focused refreshed side-by-side and page-count validation cannot be completed for these representatives.

## Evidence

Current resource audit:

- `wc15_7pg:7`: `순천향체` 430 runs -> `missing-or-platform-fallback`.
- `wc15_7pg:6`: `순천향체` 290 runs -> `missing-or-platform-fallback`.
- `wc16_6pg:6`: `순천향체` 277 runs -> `missing-or-platform-fallback`.
- `wc17_6pg:4`: `순천향체` 250 runs -> `missing-or-platform-fallback`.
- Guard `report_form:2`: unchanged bundled `Noto Sans KR` / `HY헤드라인M`.

Current page-count/source status:

- `wc15_7pg`: `source_missing`, expected Hancom page count `7`.
- `wc16_6pg`: `source_missing`, expected Hancom page count `6`.
- `wc17_6pg`: `source_missing`, expected Hancom page count `6`.
- `report_form`: page-count clean `6/6`.

External lookup:

- Public historical references say Soonchunhyang University developed and distributed `순천향체` for free.
- The old official download link appears dead, and no current official license file / redistributable artifact was verified in this run.

## Decision

Do not map `순천향체` to Noto, Nanum, KoPub, or another bundled Korean sans as a renderer rule. That would be a broad visual substitution without exact resource rights and without source-backed focused review validation.

Promotion requires both:

- a verified current redistributable `순천향체` font artifact with license terms; and
- restored `wc15_7pg`, `wc16_6pg`, or `wc17_6pg` source files so focused side-by-side and page-count guards can run.
