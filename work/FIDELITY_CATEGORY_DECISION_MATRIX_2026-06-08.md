# RHWP Fidelity Category Decision Matrix -- 2026-06-08

Purpose: keep the long renderer-fidelity loop concrete. This is the current
decision layer on top of the detailed runbook in
`work/FIDELITY_NEXT_CATEGORY_PLAN_2026-06-08.md`.

## Current Board

Source:

```bash
python3 harness/fidelity_category_status.py --with-gallery \
  --out work/FIDELITY_VISUAL_STATUS_CURRENT_CONTINUE_2026-06-08.md \
  form_07_______________41KB accountability_eval overseas_training \
  meeting_summary 15_3740450_research_admin_innovation_meeting_template report_form
```

| doc | pages | worst | mean | decision |
|---|---:|---:|---:|---|
| `overseas_training` | 4/4 | p1 | 21.35 | guard-only until a new table-text invariant appears |
| `15_3740450_research_admin_innovation_meeting_template` | 5/5 | p3 | 20.64 | `probe`: independent photo-grid guards now staged; visual/oracle guard still needed before Rust |
| `meeting_summary` | 3/3 | p1 | 17.86 | guard-only table/text raster page |
| `accountability_eval` | 6/6 | p4 | 15.49 | queued only if another CellBreak-rowspan guard doc appears |
| `form_07_______________41KB` | 11/11 | p5 | 15.19 | guard-only table/text/fill raster page |
| `report_form` | 6/6 | p2 | 12.15 | clean guard |

## Accepted Renderer Classes In This Run

1. Single-character SVG clusters no longer force `textLength`.
   - File: `src/renderer/svg.rs`.
   - Structural reason: per-character SVG clusters should not ask static
     rasterizers to squeeze one glyph with `lengthAdjust`.
   - Guard status: page counts stable; board improved weakly without regressions.

2. Mixed TAC/non-TAC repeated photo-grid rows share the same derived picture
   y-offset.
   - Files: `src/renderer/layout/table_layout.rs`,
     `src/renderer/layout/table_partial.rs`.
   - Structural reason: one repeated photo-grid row can mix cropped TAC and
     non-TAC picture cells; sibling pictures should align to the same row
     origin.
   - Guard status: focused test, overfit scan, fmt, release build, and
     `harness/gate.sh --no-build` passed.

## Rejected Candidate Families

Do not retry these without a new structural discriminator and fresh regional
evidence:

- Global stroke-width inflation or minimum stroke width.
  - Worsens `overseas_training`, `meeting_summary`, and `form_07`.
- Text stroke paint-order thickening.
  - Worsens target and guard docs.
- Broad font size or weight changes.
  - Whole-page scores can move, but regional dark-ink evidence usually worsens.
- Broad font-face alias policy for Malgun/Gyeonggi families.
  - Open Korean aliases worsened `overseas_training`.
  - Malgun-to-Nanum/Pretendard weakly improves some means by reducing dark ink,
    which is the wrong direction for the oracle.
- Lower-page y-shifts and generic image y/height/filter shifts.
  - Worsen photo pages and table/text pages.
- Simple CellBreak carried-rowspan top-slice on `accountability_eval`.
  - It increased page fill but made the visual board worse.
- Pale fill color changes on `form_07` page 5.
  - Current `#fff7cc` is closer than white/lighter/darker/desaturated variants.

## Fast Validation Order

Use this order for every new category:

0. Build the current queue from local evidence:

```bash
python3 harness/fidelity_queue_builder.py \
  --out work/FIDELITY_QUEUE_CURRENT_2026-06-08.md
```

Treat `patchable` or `probe` rows as candidates. Treat `guard-only` and
`needs-more-guards` rows as stop signs unless new documents or new structural
evidence have been added.

1. Refresh one-page evidence:

```bash
python3 harness/svg_geometry_probe.py DOC:PAGE
python3 harness/svg_region_probe.py DOC:PAGE --region NAME:X0,Y0,X1,Y1
python3 harness/svg_text_region_probe.py DOC:PAGE --region NAME:X0,Y0,X1,Y1
```

2. Run SVG-only candidate probes before Rust:

```bash
python3 harness/svg_component_probe.py --variant base --variant CANDIDATE \
  --out-dir /tmp/diff/_probe_NAME DOC:PAGE GUARD:PAGE
```

3. Accept a candidate only if it passes all three checks:
   - target region improves for the visually relevant reason;
   - guard pages do not regress;
   - the rule can be described using renderer structure, not fixture identity.

4. Only then patch Rust and run the full gate:

```bash
docker compose --env-file .env.docker run --rm dev cargo test --lib <focused_test> -j 1
python3 scripts/check_renderer_overfit.py
docker compose --env-file .env.docker run --rm dev cargo fmt --check
docker compose --env-file .env.docker run --rm dev cargo build --release --bin rhwp -j 1
bash harness/gate.sh --no-build
python3 harness/fidelity_category_status.py --with-gallery \
  --out work/FIDELITY_VISUAL_STATUS_NEXT_2026-06-08.md \
  form_07_______________41KB accountability_eval overseas_training \
  meeting_summary 15_3740450_research_admin_innovation_meeting_template report_form
```

## Next Best Work

1. Search for another independent CellBreak carried-rowspan/blank-separator doc.
   - If found, revisit `accountability_eval` with that as a guard.
   - If not found, do not patch that class yet.

2. Probe the photo-grid class.
   - Independent source/runtime guard candidates are now staged:
     `photo_form24`, `photo_122p_civil_defense`, and `photo_w31`.
   - `photo_w31` now has a real WebHWP/Hancom PDF oracle and a focused
     side-by-side gallery with the target.
   - Inspect row/cell picture geometry and rendered image placement across
     those guards before touching Rust.
   - The next best oracle is `photo_122p_civil_defense` because it carries 94
     emitted image boxes on the mapped guard pages.

3. Treat table/text raster drift as a separate backend fidelity project.
   - Current evidence says SVG-level global knobs are unsafe.
   - Next useful evidence is glyph/raster backend parity or a cell-composition
     invariant that improves dark ink without shrinking text away.
   - Use `harness/raster_backend_probe.py` to compare Hancom vs browser-SVG
     and optional native-Skia before touching renderer code.

## Guard Searches

CellBreak carried-rowspan scan:

```bash
python3 harness/cellbreak_rowspan_scan.py --min-slack 0.0
```

Current result:

- Matches are limited to `accountability_eval` and
  `accountability_eval_fitted_oracle` variants.
- This is not enough independent coverage for another rowspan compression
  renderer patch.
- A 61-file curated source scan found several source-level lookalikes
  (`pageBreak="CELL"` + rowspans + blank rows), but after staging the strongest
  candidates and generating `dump_pages_current.txt`, none produced the runtime
  continued-rowspan signature. See
  `work/FIDELITY_GUARD_EXPANSION_2026-06-08.md`.

Photo-grid source scan:

```bash
python3 harness/photo_grid_scan.py /tmp/diff
python3 harness/photo_grid_scan.py /tmp/diff --only-mixed
```

Current result:

- `15_3740450_research_admin_innovation_meeting_template` source table 3 is a
  mixed TAC/non-TAC picture row:
  `6x2`, `TOP_AND_BOTTOM`, `pageBreak=CELL`, `repeatHeader=1`,
  `r2c0N,r2c1T,r5c0T,r5c1T`.
- Source table 4 and 6 are all non-TAC photo tables with negative offsets, but
  they still have no independent visual/oracle guard.
- A 1,615-file broad local scan found independent mixed TAC/non-TAC photo-grid
  source matches. Three docs were staged and rendered with `dump-pages`:
  `photo_form24`, `photo_122p_civil_defense`, and `photo_w31`.
- Current `/tmp/diff` mixed scan finds 10 mixed-row source matches across the
  target plus those staged guards. Therefore, photo-grid has moved from
  `needs-more-guards` to `probe`; further Rust work should be visual/oracle
  guarded, not blocked on source-only coverage.
- `harness/webhwp_oracle_pdf.py` generated a WebHWP/Hancom oracle for
  `photo_w31`: 30 Hancom pages / 30 RHWP pages, key guard pages 26-28.
- Focused gallery:
  `/tmp/diff/_review_photo_grid_guards_2026-06-08/index.html`.

Generated queue:

```bash
python3 harness/fidelity_queue_builder.py \
  --out work/FIDELITY_QUEUE_CURRENT_2026-06-08.md
```

Current interpretation:

- `overseas_training`, `meeting_summary`, and `form_07` are `guard-only`
  table/text-raster pages.
- `meeting_template` photo-grid is `probe`: independent source/runtime guard
  candidates exist, but still need visual/oracle validation.
- `accountability_eval` CellBreak-rowspan remains `needs-more-guards`.
- `report_form` is a clean guard.
- There is no current category that should be patched directly without a
  targeted probe first. The least blocked category is now photo-grid.

## Backend Raster Probe

Command shape:

```bash
python3 harness/raster_backend_probe.py DOC:PAGE --native \
  --region name:x0,y0,x1,y1
```

Current table-text guard result after building native-Skia:

- Native build command succeeded:

```bash
docker compose --env-file .env.docker run --rm dev \
  cargo build --release --features native-skia --bin rhwp -j 1
```

- Backend comparison board:
  `/tmp/diff/_raster_backend_probe/index.html`.
- `overseas_training` p1:
  - browser-SVG: header `34.80`, body_top `30.09`, body_mid `27.46`,
    body_bottom `30.23`.
  - native-Skia: header `39.78`, body_top `30.54`, body_mid `27.47`,
    body_bottom `29.61`.
  - Read: native is not a general fix here; header worsens and body is mixed.
- `meeting_summary` p1:
  - browser-SVG: top_table `26.17`, body_a `20.47`, body_b `21.22`.
  - native-Skia: top_table `22.23`, body_a `16.99`, body_b `17.97`.
  - Threshold-sweep read: browser-SVG tracks Hancom dark-ink density much more
    closely. Native-Skia collapses to roughly `0.8-13.6%` of Hancom dark pixels
    even at threshold 240, so the lower mean diff is mostly a pale-ink metric
    artifact.
- `form_07` p5:
  - browser-SVG: mid_a `16.59`, mid_b `17.58`, bottom `15.48`.
  - native-Skia: mid_a `10.78`, mid_b `11.15`, bottom `10.30`.
  - Threshold-sweep read: browser-SVG is too dark/dense versus Hancom, but
    native-Skia swings too far the other way (`0.1-17.9%` of Hancom dark pixels
    even at threshold 240).
- `overseas_training` p1:
  - Threshold-sweep read: browser-SVG is still closer to Hancom table-body ink
    than native-Skia. Native-Skia stays under-inked across body regions and
    also has worse header mean diff.

Decision:

- Native-Skia is now available locally for experiments.
- It is not an immediate production renderer answer. Its apparent wins on
  `meeting_summary` and `form_07` are dominated by under-inked antialiasing /
  text paint behavior, while `overseas_training` is mixed/worse.
- Browser-SVG remains the production baseline. Native-Skia is useful as a
  diagnostic/export comparison lane until a separate text paint/font fallback
  fix makes its ink density comparable to Hancom.
- `--native-font-path web/fonts` does not improve native-Skia output with the
  current assets. The available web fonts are WOFF2, while the native loader's
  useful path is TTF/OTF/TTC; a temporary WOFF/WOFF2 loader candidate produced
  unchanged pixels and was reverted.
- Converting `web/fonts/*.woff2` to temporary TTF files with
  `woff2_decompress`, mounting that directory into Docker, and passing
  `--native-font-path /tmp/rhwp_native_fonts` also produced unchanged native
  output on `meeting_summary`, `form_07`, and `overseas_training`.
- Next useful task is either a real native typeface-resolution diagnostic
  inside `SkiaTextReplay` / `SkiaLayerRenderer`, or staging more independent
  guard documents for CellBreak-rowspan and photo-grid categories. Do not retry
  broad SVG font/stroke/fill tweaks or simple native font-path packaging.
