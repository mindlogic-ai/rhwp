# photo_form24 Cached Picture VPOS

Date: 2026-06-09 KST
Status: accepted
Category: image/table geometry

## Target

- Document: `photo_form24`
- Page: 51
- Oracle: Hancom raster band for the large image starts at y=140.7 and ends at y=697.2.
- Before fix: RHWP SVG image box was y=185.3..741.1.
- After fix: RHWP SVG image box is y=141.3..697.1.

## Cause

The page has a large non-TAC `TopAndBottom` picture anchored in a picture-only
paragraph after a TAC title table and two tiny empty spacer paragraphs. The
saved picture paragraph `lineSeg` vpos is cached layout residue:

- `vertical_pos=3511` HU, about 46.8px
- picture `vertRelTo=Para`, `vertOffset=0`
- picture height is unchanged and already matches the oracle

The renderer previously applied the cached spacer/host-line shift to the visual
picture placement, moving the image about 44px too low.

## Patch Shape

Structural guard only:

- picture-only paragraph
- single `Picture` control at control index 0
- non-TAC `TextWrap::TopAndBottom`
- `VertRelTo::Para`
- `vertical_offset == 0`
- cached vpos is small relative to picture height
- immediately preceded by one or more tiny empty spacer paragraphs
- the previous non-spacer paragraph contains a TAC `TopAndBottom` table

The patch suppresses both the inter-item cached vpos adjustment and the
empty-host-line visual shift for this class. No document names or body text are
used.

## Validation

- `docker compose --env-file .env.docker run --rm dev /usr/local/cargo/bin/cargo fmt --check`
- `docker compose --env-file .env.docker run --rm dev /usr/local/cargo/bin/cargo test --lib renderer::layout::tests::cached_picture_anchor_vpos_skips_only_after_tiny_spacer_run_and_tac_table -j 1`
- `docker compose --env-file .env.docker run --rm dev /usr/local/cargo/bin/cargo build --release --bin rhwp -j 1`
- `python3 scripts/check_renderer_overfit.py`
- `git diff --check -- src/renderer/layout.rs src/renderer/layout/tests.rs`

Focused boards:

- `/tmp/diff/_review_photo_form24_p51_cached_vpos_candidate3_2026-06-09/index.html`
- `/tmp/diff/_review_photo_form24_cached_vpos_guard_2026-06-09/index.html`

Guard page counts:

- `photo_form24`: Hancom=89, RHWP=89
- `photo_w31`: Hancom=30, RHWP=30
- `report_form`: Hancom=6, RHWP=6

Guard boards:

- `/tmp/diff/_review_photo_w31_cached_vpos_guard_2026-06-09/index.html`
- `/tmp/diff/_review_report_form_cached_vpos_guard_2026-06-09/index.html`

## Residual

This does not solve the remaining broad text/font/table compression drift on
`photo_form24` pages 50 and 52 or `photo_w31` page 24. Those remain separate
text/table fidelity categories.
