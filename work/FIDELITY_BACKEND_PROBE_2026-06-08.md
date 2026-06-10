# RHWP Backend Raster Probe -- 2026-06-08

Goal: determine whether the current table/text visual drift is caused by
browser-rasterized SVG, by layout/paint emission, or by a deeper text backend
issue.

## Native Build

```bash
docker compose --env-file .env.docker run --rm dev \
  cargo build --release --features native-skia --bin rhwp -j 1
```

Result: succeeded in `3m 23s`.

## Probe Commands

```bash
python3 harness/raster_backend_probe.py overseas_training:1 --native \
  --region header:56,164,737,214 \
  --region body_top:56,214,737,503 \
  --region body_mid:56,503,737,831 \
  --region body_bottom:56,831,737,1038

python3 harness/raster_backend_probe.py meeting_summary:1 --native \
  --region top_table:40,180,760,330 \
  --region body_a:40,330,760,620 \
  --region body_b:40,620,760,900

python3 harness/raster_backend_probe.py form_07_______________41KB:5 --native \
  --region mid_a:30,220,760,500 \
  --region mid_b:30,500,760,800 \
  --region bottom:30,800,760,1080
```

Visual board:

```text
/tmp/diff/_raster_backend_probe/index.html
```

## Results

| doc/page | region | browser-svg | native-skia | read |
|---|---:|---:|---:|---|
| `overseas_training` p1 | header | 34.80 | 39.78 | native worsens header |
| `overseas_training` p1 | body_top | 30.09 | 30.54 | native slightly worse |
| `overseas_training` p1 | body_mid | 27.46 | 27.47 | neutral |
| `overseas_training` p1 | body_bottom | 30.23 | 29.61 | slight native improvement |
| `meeting_summary` p1 | top_table | 26.17 | 22.23 | native improves |
| `meeting_summary` p1 | body_a | 20.47 | 16.99 | native improves |
| `meeting_summary` p1 | body_b | 21.22 | 17.97 | native improves |
| `form_07` p5 | mid_a | 16.59 | 10.78 | native strongly improves |
| `form_07` p5 | mid_b | 17.58 | 11.15 | native strongly improves |
| `form_07` p5 | bottom | 15.48 | 10.30 | native strongly improves |

## Decision

- Native-Skia is not a universal fix: it worsens `overseas_training` header and
  is mixed on that page.
- It materially improves `meeting_summary` and `form_07`, so the remaining
  table/text bucket is partly raster-backend sensitive.
- Do not patch SVG font/stroke/fill knobs based on these pages.
- Next backend task: inspect native/browser text antialiasing and font fallback
  behavior visually, then decide whether production should keep browser-SVG,
  add a native raster lane for export/oracle comparison, or fix a shared text
  paint abstraction.

## Threshold Sweep Follow-Up

Command shape:

```bash
python3 harness/raster_backend_probe.py DOC:PAGE --native --threshold-sweep \
  --region name:x0,y0,x1,y1
```

The sweep compares Hancom and candidate dark-pixel counts at luma thresholds
64, 96, 128, 160, 192, 224, and 240.

Findings:

- `meeting_summary` p1: browser-SVG tracks Hancom reasonably across thresholds
  (`0.71-1.03x`, `0.82-1.02x`, `0.81-1.02x` by region). Native-Skia collapses
  to `0.8-13.6%` of Hancom dark pixels even at threshold 240.
- `form_07` p5: browser-SVG is too dark/dense versus Hancom (`1.5-2.4x`
  depending on threshold and region). Native-Skia is far too pale (`0.1-17.9%`
  of Hancom dark pixels even at threshold 240).
- `overseas_training` p1: browser-SVG is closer to Hancom than native-Skia in
  the table body and reaches near parity at high thresholds. Native-Skia stays
  under-inked (`0.09-0.64x` depending on region/threshold) and still has worse
  header mean-diff.

Interpretation:

- The native-Skia mean-diff improvement on `meeting_summary` and `form_07` is
  mostly an antialiasing / missing-dark-ink metric artifact, not production
  fidelity proof.
- Browser-SVG remains the production baseline for now.
- Native-Skia remains useful as a diagnostic/export comparison lane, but should
  not be treated as the immediate production rendering answer without a separate
  text paint/font fallback fix.

## Native Font Path Probe

Why: browser-SVG uses WOFF2 Korean fonts from `web/fonts` /
`rhwp-studio/*/fonts`, while native-Skia only searches system fonts unless
`--font-path` is supplied. The local `ttfs/` directory contains only
`FONTS.md`, not TTF/OTF/TTC assets.

Harness update:

```bash
python3 harness/raster_backend_probe.py DOC:PAGE --native \
  --native-font-path web/fonts \
  --threshold-sweep --region name:x0,y0,x1,y1
```

Result after rebuilding `rhwp --features native-skia`:

- `--native-font-path web/fonts` produced the same metrics as native-Skia
  without that path on `meeting_summary`, `form_07`, and `overseas_training`.
- A temporary renderer candidate that allowed WOFF/WOFF2 files through the
  native font loader also produced unchanged pixels, then was reverted.
- Local `woff2_decompress` was then used to convert `web/fonts/*.woff2` into
  `/tmp/rhwp_native_fonts/*.ttf`.
- `harness/raster_backend_probe.py` now mounts absolute native font paths into
  the Docker container before invoking `export-png`; this prevents false
  negatives when probing host-local temporary font directories.
- With `--native-font-path /tmp/rhwp_native_fonts`, the same three guard pages
  again produced unchanged native-Skia metrics and unchanged threshold-sweep
  ratios.

Decision:

- The existing web WOFF2 font bundle is not a quick native export fix.
- Decompressed WOFF2-to-TTF assets are also not a quick native export fix in
  the current path. Either Skia is not accepting those converted faces as
  intended, or the document styles are resolving to different families.
- Native export fidelity needs a deeper font-resolution/typeface diagnostic
  before more implementation work, not blind font-path packaging.
- Keep browser-SVG as production baseline; keep native-Skia as diagnostic/export
  research only until its font/ink density matches Hancom under threshold sweep.
