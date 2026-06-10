# Gyeonggi Font Resource Status -- 2026-06-09

Status: accepted-resource / text-raster category remains probe.

Representative: `overseas_training:1`.

## Classification

- Category: text/raster fidelity.
- Cause: exact document fonts `경기천년*` were not bundled, so browser rendering fell through generic Korean fallbacks.
- Non-cause: page count, image placement, and table geometry. `overseas_training` remains `4/4`, and the page-1 geometry probe showed the main content bands were already close.

## Patch

Added official Gyeonggi webfont resources under `web/fonts/` and registered exact emitted family names in both render surfaces:

- `경기천년바탕`, `경기천년바탕 Regular`, `경기천년바탕 Bold`
- `경기천년제목`, `경기천년제목 Light`, `경기천년제목 Medium`, `경기천년제목 Bold`
- `경기천년제목V`, `경기천년제목V Bold`

The `rhwp-studio/public/fonts` path is a symlink to `web/fonts`, so the Vite build copies these resources into `rhwp-studio/dist/fonts/`.

## Evidence

Font resource audit after patch:

- `overseas_training:1`: `경기천년바탕 Bold` 724 runs -> bundled `fonts/GyeonggiBatang-Bold.woff`
- `overseas_training:1`: `경기천년제목 Medium` 248 runs -> bundled `fonts/GyeonggiTitle-Medium.woff`
- `overseas_training:1`: `경기천년제목V Bold` 21 runs -> bundled `fonts/GyeonggiTitleV.woff`
- `overseas_training:2` and `:3`: same Gyeonggi families now bundled.
- Guard `report_form:2`: unchanged bundled `Noto Sans KR` / `HY헤드라인M` resources.

Validation:

- `python3 harness/svg_font_resource_audit.py overseas_training:1 overseas_training:2 overseas_training:3 report_form:2`
- `cd rhwp-studio && npm run build`
- `python3 scripts/check_renderer_overfit.py`
- `python3 harness/review_pages.py /tmp/diff/_review_gyeonggi_resource_overseas_training_2026-06-09 overseas_training --pages 1 --export-current`
- `python3 harness/audit_review_gallery.py /tmp/diff/_review_gyeonggi_resource_overseas_training_2026-06-09`

Focused review:

- `/tmp/diff/_review_gyeonggi_resource_overseas_training_2026-06-09/index.html`

## Remaining Limitation

This accepts the exact browser resource fix, not the entire text/raster category. The static SVG gallery path is still weaker than the browser studio path for validating webfont loading, so the category should remain `probe` until we either embed font resources into exported SVG review artifacts or validate the browser canvas path directly.
