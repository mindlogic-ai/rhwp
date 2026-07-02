// 중첩 표 구조 변경 ByPath API (insert/delete row/column) 검증.
// form_19: 본문 표 셀 안에 중첩 표가 있는 정부 서식.
use rhwp::model::control::Control;
use rhwp::wasm_api::HwpDocument;

fn load_form19() -> HwpDocument {
    let bytes = std::fs::read("samples/form_19_empty_para.hwpx").expect("read form_19 fixture");
    HwpDocument::from_bytes(&bytes).expect("parse form_19")
}

/// (parent_para, outer_ctrl, cell_idx, cell_para, nested_ctrl, nested_rows, nested_cols)
fn find_nested_table(doc: &HwpDocument) -> (usize, usize, usize, usize, usize, u16, u16) {
    let document = doc.document();
    for (pi, para) in document.sections[0].paragraphs.iter().enumerate() {
        for (ci, ctrl) in para.controls.iter().enumerate() {
            if let Control::Table(outer) = ctrl {
                for (cell_idx, cell) in outer.cells.iter().enumerate() {
                    for (cp, cpara) in cell.paragraphs.iter().enumerate() {
                        for (nci, nctrl) in cpara.controls.iter().enumerate() {
                            if let Control::Table(nested) = nctrl {
                                return (
                                    pi,
                                    ci,
                                    cell_idx,
                                    cp,
                                    nci,
                                    nested.row_count,
                                    nested.col_count,
                                );
                            }
                        }
                    }
                }
            }
        }
    }
    panic!("form_19 fixture is expected to contain a nested table");
}

fn hops_json(outer_ctrl: usize, cell_idx: usize, cell_para: usize, nested_ctrl: usize) -> String {
    format!(
        "[{{\"controlIndex\":{outer_ctrl},\"cellIndex\":{cell_idx},\"cellParaIndex\":{cell_para}}},\
         {{\"controlIndex\":{nested_ctrl},\"cellIndex\":0,\"cellParaIndex\":0}}]"
    )
}

#[test]
fn nested_insert_then_delete_row_by_path() {
    let mut doc = load_form19();
    let (pi, ci, cell_idx, cp, nci, rows, cols) = find_nested_table(&doc);
    let path = hops_json(ci, cell_idx, cp, nci);

    let dims_before: String = doc
        .get_table_dimensions_by_path(0, pi as u32, &path)
        .expect("dims before");
    assert!(dims_before.contains(&format!("\"rowCount\":{rows}")), "{dims_before}");

    let r = doc
        .insert_table_row_by_path(0, pi as u32, &path, 0, true)
        .expect("insert row by path");
    assert!(r.contains(&format!("\"rowCount\":{}", rows + 1)), "{r}");

    // 바깥 표는 그대로여야 한다 (중첩 표만 변해야 guardrail census 가 안정).
    {
        let document = doc.document();
        let Control::Table(outer) = &document.sections[0].paragraphs[pi].controls[ci] else {
            panic!("outer table moved");
        };
        let Control::Table(nested) = &outer.cells[cell_idx].paragraphs[cp].controls[nci] else {
            panic!("nested table moved");
        };
        assert_eq!(nested.row_count, rows + 1);
        assert_eq!(nested.col_count, cols);
    }

    let r = doc
        .delete_table_row_by_path(0, pi as u32, &path, 0)
        .expect("delete row by path");
    assert!(r.contains(&format!("\"rowCount\":{rows}")), "{r}");
}

#[test]
fn nested_insert_then_delete_column_by_path() {
    let mut doc = load_form19();
    let (pi, ci, cell_idx, cp, nci, _rows, cols) = find_nested_table(&doc);
    let path = hops_json(ci, cell_idx, cp, nci);

    let r = doc
        .insert_table_column_by_path(0, pi as u32, &path, 0, true)
        .expect("insert column by path");
    assert!(r.contains(&format!("\"colCount\":{}", cols + 1)), "{r}");

    let r = doc
        .delete_table_column_by_path(0, pi as u32, &path, 0)
        .expect("delete column by path");
    assert!(r.contains(&format!("\"colCount\":{cols}")), "{r}");
}

#[test]
fn body_level_single_hop_also_works() {
    let mut doc = load_form19();
    let (pi, ci, ..) = find_nested_table(&doc);
    let (rows, cols) = {
        let document = doc.document();
        let Control::Table(outer) = &document.sections[0].paragraphs[pi].controls[ci] else {
            panic!("not a table");
        };
        (outer.row_count, outer.col_count)
    };
    let path = format!(
        "[{{\"controlIndex\":{ci},\"cellIndex\":0,\"cellParaIndex\":0}}]"
    );
    let r = doc
        .insert_table_row_by_path(0, pi as u32, &path, 0, true)
        .expect("insert row single hop");
    assert!(r.contains(&format!("\"rowCount\":{}", rows + 1)), "{r}");
    assert!(r.contains(&format!("\"colCount\":{cols}")), "{r}");
}

#[test]
fn bad_path_is_clean_error_not_panic() {
    // 오류 경로는 JsValue 변환(비 wasm32 에서 panic) 를 피해 native API 로 검증.
    let mut doc = load_form19();
    let (pi, ci, cell_idx, cp, _nci, ..) = find_nested_table(&doc);
    // 존재하지 않는 컨트롤을 가리키는 hop → Err 로 떨어져야 한다.
    let path = hops_json(ci, cell_idx, cp, 99);
    assert!(doc
        .insert_table_row_by_path_native(0, pi, &path, 0, true)
        .is_err());
    // 빈 경로도 Err.
    assert!(doc
        .insert_table_row_by_path_native(0, pi, "[]", 0, true)
        .is_err());
    // 표가 아닌 컨트롤(셀 문단의 범위 밖 셀)도 Err.
    let path = format!(
        "[{{\"controlIndex\":{ci},\"cellIndex\":99999,\"cellParaIndex\":0}},\
         {{\"controlIndex\":0,\"cellIndex\":0,\"cellParaIndex\":0}}]"
    );
    assert!(doc
        .insert_table_row_by_path_native(0, pi, &path, 0, true)
        .is_err());
}
