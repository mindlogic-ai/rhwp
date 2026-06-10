# Text/Table Raster Density Probe

Date: 2026-06-09 KST
Status: probe / rejected-broad-tweak
Category: text/raster fidelity

## Representatives

- `photo_w31:24`
  - Clean table-only representative.
  - Page count holds: Hancom=30, RHWP=30.
  - No image geometry owner.
  - Font audit: `Noto Sans KR` 1923 runs, `바탕` 4 runs; no missing resource.
- `photo_form24:7`
  - Mixed diagram-table plus body text.
  - Page count holds: Hancom=89, RHWP=89.
  - No image geometry owner.
  - Font audit: mostly bundled/CDN fonts; only `휴먼둥근헤드라인` 2 missing runs, too small to explain page-level drift.
- `overseas_training:1`
  - Dense text/table representative after Gyeonggi font resources were bundled.
  - Page count holds: Hancom=4, RHWP=4.
  - No image geometry owner; SVG geometry reports `image: 0`.
  - Remaining drift is text/rule raster density and antialiasing, not a table pagination bug.
- `meeting_summary:1`
  - Non-landscape table/text representative after the font-fallback board refresh.
  - Page count holds: Hancom=3, RHWP=3.
  - No image geometry owner; SVG geometry reports `image: 0`.
  - Table band spans the same page region, but text/rule darkness, wrapping, and
    border weight differ visibly.

## Evidence

Current board:

- `/tmp/diff/_review_all_nonlandscape_latest_2026-06-09c/index.html`

Focused probes:

- `python3 harness/svg_geometry_probe.py photo_form24:7 photo_form24:50 photo_w31:24`
- `python3 harness/svg_font_resource_audit.py photo_form24:7 photo_form24:50 photo_w31:24 report_form:2`
- `python3 harness/svg_component_probe.py --keep --out-dir /tmp/diff/_probe_next_drift_components_2026-06-09 photo_form24:7 photo_w31:24`
- `python3 harness/table_boundary_probe.py photo_w31:24`
- `python3 harness/table_boundary_probe.py photo_form24:7`
- `python3 harness/svg_line_region_probe.py photo_w31:24 --y-min 128 --y-max 1006 --keep --out-dir /tmp/diff/_probe_photo_w31_p24_line_region_2026-06-09`
- `python3 harness/hwpx_table_source_probe.py /tmp/diff/photo_w31 --list`
- `python3 harness/hwpx_table_source_probe.py /tmp/diff/photo_form24 --list`
- `python3 harness/svg_geometry_probe.py overseas_training:1`
- `python3 harness/svg_component_probe.py overseas_training:1`
- `python3 harness/raster_backend_probe.py overseas_training:1 --native --threshold-sweep --out-dir /tmp/diff/_raster_backend_probe_overseas_training_p1_2026-06-09`
- `python3 harness/review_pages.py --export-current --pages 1 /tmp/diff/_review_meeting_summary_p1_current_2026-06-09 meeting_summary`
- `python3 harness/svg_geometry_probe.py meeting_summary:1`
- `python3 harness/svg_component_probe.py meeting_summary:1`
- `docker compose --env-file .env.docker run --rm dev cargo build --release --features native-skia -j 1`
- `python3 harness/raster_backend_probe.py meeting_summary:1 --native --threshold-sweep --out-dir /tmp/diff/_raster_backend_probe_meeting_summary_p1_native_2026-06-09`
- `python3 harness/raster_backend_probe.py overseas_training:1 --native --threshold-sweep --out-dir /tmp/diff/_raster_backend_probe_overseas_training_p1_native_2026-06-09`
- `python3 harness/raster_backend_probe.py photo_w31:24 --native --threshold-sweep --out-dir /tmp/diff/_raster_backend_probe_photo_w31_p24_native_2026-06-09`
- repeated native probes with explicit bundled WOFF/WOFF2 font paths and
  user-local Noto/Nanum TTF paths:
  `/tmp/diff/_raster_backend_probe_meeting_summary_p1_native_fonts_2026-06-09`,
  `/tmp/diff/_raster_backend_probe_meeting_summary_p1_native_user_ttf_2026-06-09`,
  `/tmp/diff/_raster_backend_probe_photo_w31_p24_native_user_ttf_2026-06-09`,
  `/tmp/diff/_raster_backend_probe_overseas_training_p1_native_user_ttf_2026-06-09`
- `python3 harness/svg_text_advance_probe.py meeting_summary:1 --y-min 120 --y-max 1030 --min-chars 8 --top 30`
- `python3 harness/svg_text_advance_probe.py photo_w31:24 --y-min 0 --y-max 1122 --min-chars 8 --top 25`
- `python3 harness/svg_text_advance_probe.py report_form:2 --min-chars 8 --top 20`
- `python3 harness/svg_component_probe.py --keep --out-dir /tmp/diff/_probe_meeting_summary_line_advance_norm_2026-06-09 --variant base --variant 'normalize_line_advances_*' meeting_summary:1`
- `python3 harness/svg_component_probe.py --keep --out-dir /tmp/diff/_probe_report_form_line_advance_norm_2026-06-09 --variant base --variant 'normalize_line_advances_*' report_form:2`
- `python3 harness/svg_component_probe.py --keep --out-dir /tmp/diff/_probe_photo_w31_line_advance_norm_2026-06-09 --variant base --variant 'normalize_line_advances_*' photo_w31:24`

## Probe Results

`photo_w31:24` component probe:

- base `28.65`
- hide text `24.03`
- hide lines `25.70`
- thin stroke `x0.50` only `28.43`
- thick strokes worsen
- font family substitutions improve only slightly (`AppleGothic` `27.68`, `Nanum Gothic` `28.00`)
- font size `x0.90` improves only to `27.74`
- image variants are no-ops
- region line probe: hide all line/rule geometry only `25.70`; thin strokes only `28.43`

`photo_form24:7` component probe:

- base `28.33`
- hide text `19.61`
- hide lines `21.74`
- stroke variants do not improve
- image variants are no-ops
- font substitutions/size changes give only modest scalar gains and are broad
- `shift_y_after_430_m12` improves scalar diff to `24.63`, but this is a regional post-hoc move, not a structural renderer rule.

`overseas_training:1` component/backend probe:

- base `22.51`
- hide text `18.75`
- hide lines `20.43`
- no images on the page; all image variants are no-ops
- stroke variants are no improvement or worse
- font substitutions and `font_size_x0.90` improve only modestly (`21.73..21.98`
  for common fallback faces, `21.82` for font-size scaling)
- y-shifts worsen or are too broad (`shift_y_after_430_*` worsens)
- browser-SVG raster has fewer dark pixels than Hancom at low thresholds
  (`ratio=0.90..0.95` for luma thresholds `64..160`) but more light-gray
  nonwhite pixels at high thresholds (`ratio=1.34..1.47` at `224..240`),
  matching an antialias/text-density mismatch
- native-Skia comparison could not run in this checkout because the available
  release binary is not built with the native-Skia export path

`meeting_summary:1` component probe:

- base `19.34`
- hide text `15.33`
- hide lines `15.24`
- no images on the page; all image variants are no-ops
- stroke variants do not improve meaningfully
- common font substitutions improve only modestly (`18.83..18.99`)
- `font_size_x0.90` improves only to `18.60`, a broad non-structural change
- regional y-shifts worsen; text y-shifts are negligible

Native-Skia backend probe:

- `native-skia` release build succeeds.
- `meeting_summary:1`: native-Skia scalar diff improves from browser SVG
  `19.34` to `15.60`, but visual output is invalid for production because most
  Korean glyphs are absent/sparse. Dark-pixel ratio at luma threshold `96` is
  only `0.019` vs Hancom.
- `overseas_training:1`: native-Skia is only a small scalar improvement
  (`22.51 -> 21.70`) and still loses Korean text density badly (`96` threshold
  ratio `0.135`).
- `photo_w31:24`: native-Skia worsens scalar diff (`28.04 -> 28.43`) and
  under-renders dark text/rules (`96` threshold ratio `0.196`).
- Passing bundled WOFF/WOFF2 font paths does not change native-Skia output.
- Passing user-local Noto/Nanum TTF paths also does not materially change the
  output. `/System/Library/Fonts/AppleSDGothicNeo.ttc` cannot be mounted by the
  Docker environment due macOS file-sharing restrictions.
- SVG inspection shows the browser path emits one `<text>` element per visible
  character with explicit x positions; there is no CSS `letter-spacing`,
  `textLength`, or `lengthAdjust` attribute on these representative pages.
  Visible spacing comes from composed text advances/justification metrics, not
  a page-level CSS knob.

Per-character advance probe:

- A new read-only harness, `harness/svg_text_advance_probe.py`, groups SVG
  one-character `<text>` runs by line and reports median x-step/font-size ratios.
- `meeting_summary:1` has visible table text lines in the `1.18..1.32`
  median-step/font-size range, with some larger max steps where spaces/columns
  are skipped by SVG output.
- `photo_w31:24` shows both expanded header/title lines (`1.12..1.32`) and
  compressed dense numeric rows (`0.57..0.67`), so the metric path is already
  applying both expansion and compression depending on line shape.
- Clean guard `report_form:2` also has many lines at `1.32`, so a broad
  advance-scale reduction or "disable explicit per-character x" rule would
  likely regress a guard page. This rejects a global Noto/Korean advance tweak
  from the current evidence.
- A temporary `svg_component_probe.py` artifact variant normalized expanded
  one-character line advances to `font_size * {1.00, 1.10, 1.18}`. It does not
  produce a promotable structural patch:
  - `meeting_summary:1`: tiny scalar change only (`19.34 -> 19.28` best) and
    the `1.00` artifact visibly breaks text flow/overlaps the table labels.
  - `report_form:2`: remains a clean guard and also improves slightly
    (`12.63 -> 12.56`), so it does not separate target from guard.
  - `photo_w31:24`: modest scalar gain (`28.04 -> 27.52`) but only as a broad
    SVG coordinate normalization, not a document-structural rule.

## Decision

No code patch.

Rejected broad/global tweaks:

- Global stroke thickening/thinning: negligible or worse; risks table/rule regressions.
- Global font-size scaling: modest scalar gain only; would change unrelated pages and is not a structural HWP/HWPX rule.
- Global font-family substitution: modest scalar gain only; conflicts with resource policy and already-blocked Office/HY/Hancom font decisions.
- Regional y-shifts after a pixel threshold: overfits rendered page coordinates and is not tied to document structure.
- Image shifts/height/crop/filter changes: no-op for these representatives.
- Global Korean/Noto advance scaling: rejected because the same high
  step/font-size ratios appear in the clean `report_form:2` guard.
- Line-level SVG coordinate normalization: rejected because the target gain is
  tiny, the visual artifact is poor, and the same broad variant affects guards.
- Backend-only promotion: rejected/blocked for now. Native-Skia can be built,
  but its current text replay is not production-faithful for Korean table text.
  Future backend work should first fix native text/font replay or compare
  browser metrics directly against Hancom; do not switch the production renderer
  to native-Skia from the current evidence.

Current classification: text/table raster density remains `probe/blocked-backend`.
Next useful work is a real text metrics owner, not another layout shift.
Candidate future probes should compare computed per-character advances,
justification/`extra_char_spacing`, and table cell text layout against Hancom
for `Noto Sans KR` dense-table runs, or pursue licensed/exact resources for
residual Office/HY/Hancom faces.
