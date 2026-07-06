//! Regression: clicking inside a 1x1-wrapper nested table must yield an editable
//! caret. form_21 (정책평가 운영의견서) frames its real 4x4 content table inside a
//! 1x1 wrapper table. The renderer "unwraps" the 1x1 frame (Task #688) but used to
//! address the inner table's cells against the OUTER 1-cell wrapper, so hit_test
//! returned a length-1 cellPath (`{wrapper_ctrl, inner_cell_idx}`) and any edit hit
//! "셀 인덱스 N 범위 초과 (총 1개)" — the whole document felt non-editable.
//!
//! Correct behavior: a hit inside the nested table returns a 2-level cellPath
//! (`[{wrapper_ctrl, cell 0}, {inner_ctrl, inner_cell}]`) that resolves to a real
//! editable paragraph.

use std::path::Path;

use rhwp::wasm_api::HwpDocument;
use serde_json::Value;

fn load() -> HwpDocument {
    let path = Path::new(env!("CARGO_MANIFEST_DIR")).join("samples/form_21_nested_table.hwpx");
    let bytes = std::fs::read(&path).unwrap_or_else(|e| panic!("read {}: {}", path.display(), e));
    HwpDocument::from_bytes(&bytes).expect("parse form_21_nested_table.hwpx")
}

/// A point well inside the nested content table's body text (page 0, document pt).
const HIT_X: f64 = 300.0;
const HIT_Y: f64 = 620.0;

#[test]
fn nested_table_hit_is_editable() {
    let mut doc = load();

    let json = doc
        .hit_test_native(0, HIT_X, HIT_Y)
        .expect("hit_test inside nested table");
    let hit: Value = serde_json::from_str(&json).expect("parse hit json");

    let cell_path = hit
        .get("cellPath")
        .and_then(|p| p.as_array())
        .unwrap_or_else(|| panic!("hit inside nested table must carry a cellPath, hit={hit}"));

    // The nested content lives TWO table levels deep (1x1 wrapper -> 4x4 content),
    // so a correct hit must express both levels.
    assert!(
        cell_path.len() >= 2,
        "nested-table hit must return a 2-level cellPath (got len {}), hit={hit}",
        cell_path.len()
    );

    // Behavioral proof: inserting at the hit location via the returned path must
    // succeed (previously threw "셀 인덱스 N 범위 초과 (총 1개)").
    let sec = hit["sectionIndex"].as_u64().expect("sectionIndex") as u32;
    let parent = hit["parentParaIndex"]
        .as_u64()
        .expect("parentParaIndex (nested hit)") as u32;
    let char_off = hit["charOffset"].as_u64().expect("charOffset") as u32;
    let path_json = serde_json::to_string(cell_path).unwrap();

    let marker = "ZZ";
    doc.insert_text_in_cell_by_path_api(sec, parent, &path_json, char_off, marker)
        .unwrap_or_else(|e| {
            panic!("insert into nested-table cell must succeed, got {e:?} (path={path_json})")
        });

    // The inserted marker must be present at the hit location afterwards.
    let after = doc
        .get_text_in_cell_by_path_api(sec, parent, &path_json, char_off, marker.chars().count() as u32)
        .expect("read back nested cell text");
    assert_eq!(
        after, marker,
        "inserted marker must land at the hit location in the nested cell"
    );
}
