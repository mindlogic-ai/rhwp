# Civil Defense Grouped Cell Image Probe

Status: probe / rejected-candidate

Representative: `photo_122p_civil_defense:76`

Category: image/table geometry

## Finding

The page count is clean (`129/129`) and the table grid is broadly aligned, but
the lower `실습기자재` image row has local composition drift in the first image
cell. The HWPX source stores that cell as a grouped `hp:container`, not as a
plain direct picture:

- parent container `instid=357041651`, `groupLevel=0`
- parent `orgSz=11157x11014`, `curSz=8382x10220`
- parent rendering matrix translates by about `(-1343, -250)` HWP units and
  scales by about `(0.751277, 0.92791)`
- four child `hp:pic` nodes (`groupLevel=1`) use individual `imgClip` and
  `renderingInfo` matrices

Current RHWP renders the child pictures as separate visible image nodes inside
the cell. Hancom renders the grouped composition as one coherent cell image.

## Rejected Candidate

Tried preserving child-picture `crop`, `original_size_hu`, and external path
metadata in `ShapeObject::Picture` group rendering, matching direct picture
paths. The structural unit test passed, but visual regeneration rejected the
patch: one child image expanded outside the table cell (`x=149.4..476.0`,
`y=611.7..1078.9`) because current crop math is not compatible with the group
transform path.

The candidate was removed.

## Evidence

- Current/restored focused board:
  `/tmp/diff/_review_civil_defense_p76_grouped_container_probe_current_2026-06-09/index.html`
- Rejected candidate board:
  `/tmp/diff/_review_civil_defense_p76_grouped_picture_crop_candidate_2026-06-09/index.html`
- Source probe:
  `python3 harness/hwpx_table_source_probe.py /tmp/diff/photo_122p_civil_defense --table-index 75`
- Geometry probes:
  `python3 harness/svg_geometry_probe.py photo_122p_civil_defense:76`
  `python3 harness/svg_image_ink_probe.py photo_122p_civil_defense:76`
- Rejected-candidate validation:
  `docker compose --env-file .env.docker run --rm test cargo test --lib grouped_picture_layout_preserves_crop_metadata -j 1`
- Reverted/current validation:
  `docker compose --env-file .env.docker run --rm test cargo fmt --check`
  `python3 scripts/check_renderer_overfit.py`
  `docker compose --env-file .env.docker run --rm dev cargo build --release --bin rhwp -j 1`
  `python3 harness/audit_review_gallery.py /tmp/diff/_review_civil_defense_p76_grouped_container_probe_current_2026-06-09`

## Next Structural Owner

The likely owner is grouped-shape rendering inside table cells, not row height
or simple image positioning. A future acceptable patch needs to model grouped
picture composition under a table-cell clip:

- apply parent and child affine transforms consistently;
- preserve child crop semantics without expanding page-space image boxes;
- keep children clipped to the group/cell bounds;
- guard with adjacent `photo_122p_civil_defense` pages and photo-grid docs.

Do not patch this with global image shifts, broad crop changes, or document/text
fingerprints.
