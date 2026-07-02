// insertFootnote/insertEquation at offset 0 of an empty-text paragraph must
// not panic ('unreachable' WASM trap). form_19 (HWPX) repro: HWPX-parsed
// paragraphs have controls but an EMPTY ctrl_data_records vec, so
// `ctrl_data_records.insert(insert_idx, None)` with insert_idx > 0 violated
// Vec::insert bounds — a panic that aborts the WASM instance and breaks the
// agent bridge's subsequent snapshot restore.
use rhwp::wasm_api::HwpDocument;

fn load_form19() -> HwpDocument {
    let bytes = std::fs::read("samples/form_19_empty_para.hwpx").expect("read form_19 fixture");
    HwpDocument::from_bytes(&bytes).expect("parse form_19")
}

/// form_19 p1: 표를 host 하는 빈 텍스트 문단 (controls=[Table], ctrl_data_records=[]).
const TABLE_HOST_PARA: usize = 1;

#[test]
fn footnote_at_offset0_of_hwpx_table_host_paragraph() {
    let mut doc = load_form19();
    let res = doc
        .insert_footnote_native(0, TABLE_HOST_PARA, 0)
        .expect("insert_footnote_native on HWPX table-host paragraph");
    assert!(res.contains("\"ok\":true"), "unexpected result: {res}");
}

#[test]
fn equation_at_offset0_of_hwpx_table_host_paragraph() {
    let mut doc = load_form19();
    let res = doc
        .insert_equation_native(0, TABLE_HOST_PARA, 0, "a^2+b^2=c^2", 1200, 0)
        .expect("insert_equation_native on HWPX table-host paragraph");
    assert!(res.contains("\"ok\":true"), "unexpected result: {res}");
}

/// probe_guardrail.mjs 의 실제 시퀀스: p0 split → p1 텍스트 → p2(구 p1 표 문단)에
/// 각주 삽입 + 각주 내부 텍스트 입력 + 렌더 + 스냅샷 복원까지 무사해야 한다.
#[test]
fn probe_sequence_footnote_then_render_and_snapshot() {
    let mut doc = load_form19();
    let p0_len = doc.document().sections[0].paragraphs[0]
        .text
        .chars()
        .count() as u32;
    doc.split_paragraph(0, 0, p0_len).expect("split p0");
    doc.insert_text(0, 1, 0, "프로브 텍스트 문단")
        .expect("insert text");

    let res = doc
        .insert_footnote_native(0, 2, 0)
        .expect("insert_footnote_native at p2 offset 0");
    let ctrl_idx: usize = res
        .split("\"controlIdx\":")
        .nth(1)
        .and_then(|s| s.split([',', '}']).next())
        .and_then(|s| s.parse().ok())
        .expect("controlIdx in result");
    doc.insert_text_in_footnote_native(0, 2, ctrl_idx, 0, 0, "프로브 각주")
        .expect("insert_text_in_footnote_native");

    for pg in 0..doc.page_count() {
        doc.render_page_svg(pg).expect("render page");
    }
    let id = doc.save_snapshot();
    doc.restore_snapshot(id).expect("restore snapshot");
}

#[test]
fn footnote_at_offset0_of_freshly_inserted_empty_paragraph() {
    let mut doc = load_form19();
    let para_count = doc.document().sections[0].paragraphs.len();
    doc.insert_paragraph_native(0, para_count)
        .expect("insert empty paragraph");
    let res = doc
        .insert_footnote_native(0, para_count, 0)
        .expect("insert_footnote_native on fresh empty paragraph");
    assert!(res.contains("\"ok\":true"), "unexpected result: {res}");
}

#[test]
fn equation_at_offset0_of_freshly_inserted_empty_paragraph() {
    let mut doc = load_form19();
    let para_count = doc.document().sections[0].paragraphs.len();
    doc.insert_paragraph_native(0, para_count)
        .expect("insert empty paragraph");
    let res = doc
        .insert_equation_native(0, para_count, 0, "a^2+b^2=c^2", 1200, 0)
        .expect("insert_equation_native on fresh empty paragraph");
    assert!(res.contains("\"ok\":true"), "unexpected result: {res}");
}
