//! `<hp:tbl>` 표 직렬화.
//!
//! Stage 3 (#182): `Control::Table` IR → `<hp:tbl>` + `<hp:tr>` + `<hp:tc>` + `<hp:subList>` + 문단 재귀.
//!
//! 속성·자식 순서는 한컴 OWPML 공식 (hancom-io/hwpx-owpml-model, Apache 2.0)
//! `Class/Para/TableType.cpp` 의 `WriteElement()`, `InitMap()` 기준:
//!
//! ### `<hp:tbl>` 속성 순서 (부모 AbstractShapeObjectType + 자신)
//! id, zOrder, numberingType, textWrap, textFlow, lock, dropcapstyle,
//! pageBreak, repeatHeader, rowCnt, colCnt, cellSpacing, borderFillIDRef, noAdjust
//!
//! ### `<hp:tbl>` 자식 순서
//! sz, pos, outMargin, (caption, shapeComment, parameterset, metaTag — 옵셔널),
//! inMargin, (cellzoneList — 옵셔널), tr (루프), (label — 옵셔널)
//!
//! ### `<hp:tc>` 속성 순서
//! name, header, hasMargin, protect, editable, dirty, borderFillIDRef
//!
//! ### `<hp:tc>` 자식 순서
//! subList, cellAddr, cellSpan, cellSz, cellMargin
//!
//! ## 중요: table.attr 비트 연산 금지
//!
//! HWPX에서 `table.attr` 는 0인 경우가 많으므로 비트 연산으로 `textWrap/textFlow/pageBreak` 등을
//! 추출하면 안 된다. 반드시 `table.common.text_wrap`, `table.page_break` 등 파싱된 IR 필드를 사용.

use std::io::Write;

use quick_xml::Writer;

use crate::model::shape::{
    Caption, CaptionDirection, CommonObjAttr, HorzAlign, HorzRelTo, TextWrap, VertAlign, VertRelTo,
};
use crate::model::table::{Cell, HwpxTablePageBreak, Table, TablePageBreak, VerticalAlign};
use crate::model::HwpUnit;

use super::context::SerializeContext;
use super::section;
use super::utils::{empty_tag, end_tag, start_tag, start_tag_attrs};
use super::SerializeError;

/// `<hp:tbl>` 직렬화.
pub fn write_table<W: Write>(
    w: &mut Writer<W>,
    table: &Table,
    ctx: &mut SerializeContext,
) -> Result<(), SerializeError> {
    // borderFillIDRef 참조 등록 (assert_all_refs_resolved 검증 대상)
    ctx.border_fill_ids.reference(table.border_fill_id);
    for zone in &table.zones {
        ctx.border_fill_ids.reference(zone.border_fill_id);
    }
    for cell in &table.cells {
        ctx.border_fill_ids.reference(cell.border_fill_id);
    }

    // --- <hp:tbl> 시작 태그 + 속성 ---
    let id_str = table.common.instance_id.to_string();
    let z_order = table.common.z_order.to_string();
    let text_wrap = text_wrap_str(table.common.text_wrap);
    let text_flow = text_flow_str(table.common.text_wrap);
    let lock = bool01(false);
    let page_break = table
        .hwpx_page_break
        .map(hwpx_table_page_break_str)
        .unwrap_or_else(|| table_page_break_str(table.page_break));
    let repeat_header = bool01(table.repeat_header);
    let row_cnt = table.row_count.to_string();
    let col_cnt = table.col_count.to_string();
    let cell_spacing = table.cell_spacing.to_string();
    let border_fill_id_ref = table.border_fill_id.to_string();
    let no_adjust = bool01((table.attr | table.raw_table_record_attr) & 0x08 != 0);

    start_tag_attrs(
        w,
        "hp:tbl",
        &[
            ("id", &id_str),
            ("zOrder", &z_order),
            ("numberingType", "TABLE"),
            ("textWrap", text_wrap),
            ("textFlow", text_flow),
            ("lock", lock),
            ("dropcapstyle", "None"),
            ("pageBreak", page_break),
            ("repeatHeader", repeat_header),
            ("rowCnt", &row_cnt),
            ("colCnt", &col_cnt),
            ("cellSpacing", &cell_spacing),
            ("borderFillIDRef", &border_fill_id_ref),
            ("noAdjust", no_adjust),
        ],
    )?;

    // --- 자식: sz, pos, outMargin, inMargin, tr[] ---
    write_sz(w, &table.common)?;
    write_pos(w, &table.common)?;
    write_out_margin(w, table)?;
    if let Some(caption) = &table.caption {
        write_caption(w, caption, ctx)?;
    }
    write_in_margin(w, table)?;

    // tr[]: 행 단위 반복. 각 행에 속한 셀 (cell.row == r) 을 col 오름차순으로 출력.
    // cellSz height 는 Table::serialized_cell_height 로 방어한다 — u32 언더플로우로
    // 오염된 wrapped-negative 높이를 그대로 내보내면 재열람 시 표가 붕괴한다.
    for row_idx in 0..table.row_count {
        start_tag(w, "hp:tr")?;
        let mut row_cells: Vec<&Cell> = table.cells.iter().filter(|c| c.row == row_idx).collect();
        row_cells.sort_by_key(|c| c.col);
        for cell in row_cells {
            write_cell(w, cell, table.serialized_cell_height(cell), ctx)?;
        }
        end_tag(w, "hp:tr")?;
    }

    end_tag(w, "hp:tbl")?;
    Ok(())
}

fn write_sz<W: Write>(w: &mut Writer<W>, c: &CommonObjAttr) -> Result<(), SerializeError> {
    let width = c.width.to_string();
    let height = c.height.to_string();
    empty_tag(
        w,
        "hp:sz",
        &[
            ("width", &width),
            ("widthRelTo", "ABSOLUTE"),
            ("height", &height),
            ("heightRelTo", "ABSOLUTE"),
            ("protect", "0"),
        ],
    )
}

fn write_pos<W: Write>(w: &mut Writer<W>, c: &CommonObjAttr) -> Result<(), SerializeError> {
    let treat = bool01(c.treat_as_char);
    let flow = bool01(c.flow_with_text);
    let overlap = bool01(c.allow_overlap);
    let vert_offset = c.vertical_offset.to_string();
    let horz_offset = c.horizontal_offset.to_string();
    empty_tag(
        w,
        "hp:pos",
        &[
            ("treatAsChar", treat),
            ("affectLSpacing", "0"),
            ("flowWithText", flow),
            ("allowOverlap", overlap),
            ("holdAnchorAndSO", "0"),
            ("vertRelTo", vert_rel_to_str(c.vert_rel_to)),
            ("horzRelTo", horz_rel_to_str(c.horz_rel_to)),
            ("vertAlign", vert_align_str(c.vert_align)),
            ("horzAlign", horz_align_str(c.horz_align)),
            ("vertOffset", &vert_offset),
            ("horzOffset", &horz_offset),
        ],
    )
}

fn write_out_margin<W: Write>(w: &mut Writer<W>, t: &Table) -> Result<(), SerializeError> {
    let left = t.outer_margin_left.to_string();
    let right = t.outer_margin_right.to_string();
    let top = t.outer_margin_top.to_string();
    let bottom = t.outer_margin_bottom.to_string();
    empty_tag(
        w,
        "hp:outMargin",
        &[
            ("left", &left),
            ("right", &right),
            ("top", &top),
            ("bottom", &bottom),
        ],
    )
}

fn write_in_margin<W: Write>(w: &mut Writer<W>, t: &Table) -> Result<(), SerializeError> {
    let left = t.padding.left.to_string();
    let right = t.padding.right.to_string();
    let top = t.padding.top.to_string();
    let bottom = t.padding.bottom.to_string();
    empty_tag(
        w,
        "hp:inMargin",
        &[
            ("left", &left),
            ("right", &right),
            ("top", &top),
            ("bottom", &bottom),
        ],
    )
}

pub(crate) fn write_caption<W: Write>(
    w: &mut Writer<W>,
    caption: &Caption,
    ctx: &mut SerializeContext,
) -> Result<(), SerializeError> {
    let full_sz = bool01(caption.include_margin);
    let width = caption.width.to_string();
    let gap = caption.spacing.to_string();
    let last_width = caption.max_width.to_string();
    start_tag_attrs(
        w,
        "hp:caption",
        &[
            ("side", caption_direction_str(caption.direction)),
            ("fullSz", full_sz),
            ("width", &width),
            ("gap", &gap),
            ("lastWidth", &last_width),
        ],
    )?;

    start_tag_attrs(
        w,
        "hp:subList",
        &[
            ("id", ""),
            ("textDirection", "HORIZONTAL"),
            ("lineWrap", "BREAK"),
            ("vertAlign", "TOP"),
            ("linkListIDRef", "0"),
            ("linkListNextIDRef", "0"),
            ("textWidth", "0"),
            ("textHeight", "0"),
            ("hasTextRef", "0"),
            ("hasNumRef", "0"),
        ],
    )?;

    let mut vert_cursor = 0u32;
    for (pi, para) in caption.paragraphs.iter().enumerate() {
        ctx.para_shape_ids.reference(para.para_shape_id);
        ctx.style_ids.reference(para.style_id as u16);
        if let Some(cs_ref) = para.char_shapes.first() {
            ctx.char_shape_ids.reference(cs_ref.char_shape_id);
        }
        let (xml, next_vert_cursor) =
            section::render_paragraph_xml_fragment(para, pi as u32, vert_cursor, ctx);
        w.get_mut()
            .write_all(xml.as_bytes())
            .map_err(|e| SerializeError::XmlError(e.to_string()))?;
        vert_cursor = next_vert_cursor;
    }

    end_tag(w, "hp:subList")?;
    end_tag(w, "hp:caption")?;
    Ok(())
}

fn write_cell<W: Write>(
    w: &mut Writer<W>,
    cell: &Cell,
    height: HwpUnit,
    ctx: &mut SerializeContext,
) -> Result<(), SerializeError> {
    let name = cell.field_name.as_deref().unwrap_or("");
    let header = bool01(cell.is_header);
    let has_margin = bool01(cell.apply_inner_margin);
    let border_ref = cell.border_fill_id.to_string();

    start_tag_attrs(
        w,
        "hp:tc",
        &[
            ("name", name),
            ("header", header),
            ("hasMargin", has_margin),
            ("protect", "0"),
            ("editable", "0"),
            ("dirty", "0"),
            ("borderFillIDRef", &border_ref),
        ],
    )?;

    // 자식 순서: subList, cellAddr, cellSpan, cellSz, cellMargin
    write_sub_list(w, cell, ctx)?;
    write_cell_addr(w, cell)?;
    write_cell_span(w, cell)?;
    write_cell_sz(w, cell, height)?;
    write_cell_margin(w, cell)?;

    end_tag(w, "hp:tc")?;
    Ok(())
}

fn write_sub_list<W: Write>(
    w: &mut Writer<W>,
    cell: &Cell,
    ctx: &mut SerializeContext,
) -> Result<(), SerializeError> {
    start_tag_attrs(
        w,
        "hp:subList",
        &[
            ("id", ""),
            (
                "textDirection",
                if cell.text_direction == 1 {
                    "VERTICAL"
                } else {
                    "HORIZONTAL"
                },
            ),
            ("lineWrap", "BREAK"),
            ("vertAlign", cell_vert_align_str(cell.vertical_align)),
            ("linkListIDRef", "0"),
            ("linkListNextIDRef", "0"),
            ("textWidth", "0"),
            ("textHeight", "0"),
            ("hasTextRef", "0"),
            ("hasNumRef", "0"),
        ],
    )?;

    // 셀 내부 문단 재귀. 일반 section 문단과 같은 writer를 사용해야 nested
    // Table/Picture controls and source lineSeg arrays survive edited HWPX export.
    let mut vert_cursor = 0u32;
    for (pi, para) in cell.paragraphs.iter().enumerate() {
        ctx.para_shape_ids.reference(para.para_shape_id);
        ctx.style_ids.reference(para.style_id as u16);
        if let Some(cs_ref) = para.char_shapes.first() {
            ctx.char_shape_ids.reference(cs_ref.char_shape_id);
        }

        let (xml, next_vert_cursor) =
            section::render_paragraph_xml_fragment(para, pi as u32, vert_cursor, ctx);
        w.get_mut()
            .write_all(xml.as_bytes())
            .map_err(|e| SerializeError::XmlError(e.to_string()))?;
        vert_cursor = next_vert_cursor;
    }

    end_tag(w, "hp:subList")?;
    Ok(())
}

fn write_cell_text<W: Write>(w: &mut Writer<W>, text: &str) -> Result<(), SerializeError> {
    use quick_xml::events::{BytesEnd, BytesStart, BytesText, Event};
    // <hp:t>text</hp:t>
    w.write_event(Event::Start(BytesStart::new("hp:t")))
        .map_err(|e| SerializeError::XmlError(e.to_string()))?;
    if !text.is_empty() {
        w.write_event(Event::Text(BytesText::new(text)))
            .map_err(|e| SerializeError::XmlError(e.to_string()))?;
    }
    w.write_event(Event::End(BytesEnd::new("hp:t")))
        .map_err(|e| SerializeError::XmlError(e.to_string()))?;
    Ok(())
}

fn write_cell_addr<W: Write>(w: &mut Writer<W>, cell: &Cell) -> Result<(), SerializeError> {
    let col = cell.col.to_string();
    let row = cell.row.to_string();
    empty_tag(w, "hp:cellAddr", &[("colAddr", &col), ("rowAddr", &row)])
}

fn write_cell_span<W: Write>(w: &mut Writer<W>, cell: &Cell) -> Result<(), SerializeError> {
    let cs = cell.col_span.max(1).to_string();
    let rs = cell.row_span.max(1).to_string();
    empty_tag(w, "hp:cellSpan", &[("colSpan", &cs), ("rowSpan", &rs)])
}

fn write_cell_sz<W: Write>(
    w: &mut Writer<W>,
    cell: &Cell,
    height: HwpUnit,
) -> Result<(), SerializeError> {
    let w_s = cell.width.to_string();
    let h_s = height.to_string();
    empty_tag(w, "hp:cellSz", &[("width", &w_s), ("height", &h_s)])
}

fn write_cell_margin<W: Write>(w: &mut Writer<W>, cell: &Cell) -> Result<(), SerializeError> {
    let l = cell.padding.left.to_string();
    let r = cell.padding.right.to_string();
    let t = cell.padding.top.to_string();
    let b = cell.padding.bottom.to_string();
    empty_tag(
        w,
        "hp:cellMargin",
        &[("left", &l), ("right", &r), ("top", &t), ("bottom", &b)],
    )
}

// ---------- enum 변환 헬퍼 ----------

fn bool01(b: bool) -> &'static str {
    if b {
        "1"
    } else {
        "0"
    }
}

fn text_wrap_str(w: TextWrap) -> &'static str {
    use TextWrap::*;
    match w {
        Square => "SQUARE",
        Tight => "TIGHT",
        Through => "THROUGH",
        TopAndBottom => "TOP_AND_BOTTOM",
        BehindText => "BEHIND_TEXT",
        InFrontOfText => "IN_FRONT_OF_TEXT",
    }
}

/// textFlow: TextWrap 에 따라 결정 (한컴 관찰값 기준).
fn text_flow_str(w: TextWrap) -> &'static str {
    use TextWrap::*;
    match w {
        Square | Tight | Through => "BOTH_SIDES",
        _ => "BOTH_SIDES",
    }
}

fn table_page_break_str(pb: TablePageBreak) -> &'static str {
    use TablePageBreak::*;
    match pb {
        None => "NONE",
        CellBreak => "CELL",
        RowBreak => "TABLE",
    }
}

fn hwpx_table_page_break_str(pb: HwpxTablePageBreak) -> &'static str {
    use HwpxTablePageBreak::*;
    match pb {
        None => "NONE",
        Table => "TABLE",
        Cell => "CELL",
        Row => "ROW",
    }
}

fn vert_rel_to_str(v: VertRelTo) -> &'static str {
    use VertRelTo::*;
    match v {
        Paper => "PAPER",
        Page => "PAGE",
        Para => "PARA",
    }
}

fn horz_rel_to_str(h: HorzRelTo) -> &'static str {
    use HorzRelTo::*;
    match h {
        Paper => "PAPER",
        Page => "PAGE",
        Column => "COLUMN",
        Para => "PARA",
    }
}

fn vert_align_str(v: VertAlign) -> &'static str {
    use VertAlign::*;
    match v {
        Top => "TOP",
        Center => "CENTER",
        Bottom => "BOTTOM",
        Inside => "INSIDE",
        Outside => "OUTSIDE",
    }
}

fn horz_align_str(h: HorzAlign) -> &'static str {
    use HorzAlign::*;
    match h {
        Left => "LEFT",
        Center => "CENTER",
        Right => "RIGHT",
        Inside => "INSIDE",
        Outside => "OUTSIDE",
    }
}

fn caption_direction_str(d: CaptionDirection) -> &'static str {
    use CaptionDirection::*;
    match d {
        Left => "LEFT",
        Right => "RIGHT",
        Top => "TOP",
        Bottom => "BOTTOM",
    }
}

fn cell_vert_align_str(v: VerticalAlign) -> &'static str {
    use VerticalAlign::*;
    match v {
        Top => "TOP",
        Center => "CENTER",
        Bottom => "BOTTOM",
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::document::Document;
    use crate::model::paragraph::Paragraph;
    use crate::model::table::{Cell, Table};
    use crate::serializer::hwpx::context::SerializeContext;

    fn empty_table(rows: u16, cols: u16) -> Table {
        let mut t = Table::default();
        t.row_count = rows;
        t.col_count = cols;
        for r in 0..rows {
            for c in 0..cols {
                let mut cell = Cell::default();
                cell.col = c;
                cell.row = r;
                cell.col_span = 1;
                cell.row_span = 1;
                cell.width = 1000;
                cell.height = 300;
                cell.paragraphs.push(Paragraph::default());
                t.cells.push(cell);
            }
        }
        t.rebuild_grid();
        t
    }

    fn serialize(table: &Table) -> String {
        let doc = Document::default();
        let mut ctx = SerializeContext::collect_from_document(&doc);
        let mut w: Writer<Vec<u8>> = Writer::new(Vec::new());
        write_table(&mut w, table, &mut ctx).expect("write_table");
        String::from_utf8(w.into_inner()).unwrap()
    }

    #[test]
    fn cell_sz_sanitizes_u32_wrapped_negative_height() {
        // Reproduce the med_01 nested-table-host underflow: one cell in a row
        // carries a wrapped-negative height (-1282 as u32). The sibling in the
        // same row holds the real (valid) row height. The serializer must NOT
        // emit the bogus value — it substitutes the row's max valid height.
        let mut t = empty_table(2, 2);
        // row 0: give the real siblings a distinctive valid height…
        for c in t.cells.iter_mut().filter(|c| c.row == 0) {
            c.height = 2697;
        }
        // …then corrupt exactly one cell (col 0) with a u32-wrapped -1282.
        let bogus = (-1282_i32) as u32; // 4294966014
        t.cells.iter_mut().find(|c| c.row == 0 && c.col == 0).unwrap().height = bogus;

        let xml = serialize(&t);
        assert!(
            !xml.contains(&bogus.to_string()),
            "wrapped-negative height must never be serialized: {}",
            xml
        );
        // The corrupted cell should now carry the row's max valid height (2697).
        assert_eq!(
            xml.matches(r#"height="2697""#).count(),
            2,
            "both row-0 cells should serialize height 2697: {}",
            xml
        );
    }

    #[test]
    fn cell_sz_leaves_valid_heights_untouched() {
        let t = empty_table(2, 2); // all heights 300 (valid)
        let xml = serialize(&t);
        assert_eq!(
            xml.matches(r#"height="300""#).count(),
            4,
            "valid heights must pass through unchanged: {}",
            xml
        );
    }

    #[test]
    fn tbl_root_attrs_in_canonical_order() {
        let t = empty_table(2, 3);
        let xml = serialize(&t);
        assert!(xml.contains("<hp:tbl "), "should emit <hp:tbl>: {}", xml);
        // id → zOrder → numberingType → textWrap → textFlow → lock → dropcapstyle →
        // pageBreak → repeatHeader → rowCnt → colCnt → cellSpacing → borderFillIDRef → noAdjust
        let ip = xml.find("id=").unwrap();
        let zp = xml.find("zOrder=").unwrap();
        let nt = xml.find("numberingType=").unwrap();
        let tw = xml.find("textWrap=").unwrap();
        let tf = xml.find("textFlow=").unwrap();
        let rc = xml.find("rowCnt=").unwrap();
        let cc = xml.find("colCnt=").unwrap();
        let bf = xml.find("borderFillIDRef=").unwrap();
        let na = xml.find("noAdjust=").unwrap();
        assert!(
            ip < zp && zp < nt && nt < tw && tw < tf && tf < rc && rc < cc && cc < bf && bf < na
        );
    }

    #[test]
    fn tbl_preserves_original_hwpx_page_break_spelling() {
        let mut t = empty_table(1, 1);
        t.page_break = TablePageBreak::RowBreak;
        t.hwpx_page_break = Some(HwpxTablePageBreak::Cell);

        let xml = serialize(&t);

        assert!(
            xml.contains(r#"pageBreak="CELL""#),
            "HWPX export should preserve original pageBreak spelling: {}",
            xml
        );
    }

    #[test]
    fn tbl_pos_preserves_flow_and_overlap_flags() {
        let mut t = empty_table(1, 1);
        t.common.flow_with_text = false;
        t.common.allow_overlap = true;

        let xml = serialize(&t);

        assert!(xml.contains(r#"flowWithText="0""#), "{}", xml);
        assert!(xml.contains(r#"allowOverlap="1""#), "{}", xml);
    }

    #[test]
    fn tr_count_matches_row_count() {
        let t = empty_table(4, 2);
        let xml = serialize(&t);
        assert_eq!(xml.matches("<hp:tr>").count(), 4);
    }

    #[test]
    fn tc_count_matches_cell_count() {
        let t = empty_table(2, 3);
        let xml = serialize(&t);
        assert_eq!(xml.matches("<hp:tc ").count(), 6);
    }

    #[test]
    fn cells_have_canonical_child_order() {
        let t = empty_table(1, 1);
        let xml = serialize(&t);
        // subList → cellAddr → cellSpan → cellSz → cellMargin
        let sl = xml.find("<hp:subList ").unwrap();
        let ca = xml.find("<hp:cellAddr ").unwrap();
        let cs = xml.find("<hp:cellSpan ").unwrap();
        let cz = xml.find("<hp:cellSz ").unwrap();
        let cm = xml.find("<hp:cellMargin ").unwrap();
        assert!(sl < ca && ca < cs && cs < cz && cz < cm);
    }

    #[test]
    fn caption_paragraphs_are_emitted_before_in_margin() {
        let mut t = empty_table(1, 1);
        let mut p = Paragraph::default();
        p.text = "caption".to_string();
        t.caption = Some(Caption {
            direction: CaptionDirection::Bottom,
            width: 8504,
            spacing: 850,
            max_width: 35914,
            paragraphs: vec![p],
            ..Default::default()
        });

        let xml = serialize(&t);
        assert!(xml.contains("<hp:caption "), "caption missing: {}", xml);
        assert!(
            xml.contains("<hp:t>caption</hp:t>"),
            "caption text missing: {}",
            xml
        );
        let cap = xml.find("<hp:caption ").unwrap();
        let im = xml.find("<hp:inMargin ").unwrap();
        assert!(cap < im, "caption must precede inMargin");
    }

    #[test]
    fn cell_addr_reflects_coordinates() {
        let t = empty_table(2, 2);
        let xml = serialize(&t);
        assert!(xml.contains(r#"<hp:cellAddr colAddr="0" rowAddr="0"/>"#));
        assert!(xml.contains(r#"<hp:cellAddr colAddr="1" rowAddr="0"/>"#));
        assert!(xml.contains(r#"<hp:cellAddr colAddr="0" rowAddr="1"/>"#));
        assert!(xml.contains(r#"<hp:cellAddr colAddr="1" rowAddr="1"/>"#));
    }

    #[test]
    fn cell_span_defaults_to_one() {
        let t = empty_table(1, 1);
        let xml = serialize(&t);
        assert!(xml.contains(r#"<hp:cellSpan colSpan="1" rowSpan="1"/>"#));
    }

    #[test]
    fn border_fill_id_ref_registered_in_ctx() {
        let doc = Document::default();
        let mut ctx = SerializeContext::collect_from_document(&doc);
        let mut t = empty_table(1, 1);
        t.border_fill_id = 99;
        t.cells[0].border_fill_id = 99;
        let mut w: Writer<Vec<u8>> = Writer::new(Vec::new());
        write_table(&mut w, &t, &mut ctx).unwrap();
        // 99 는 등록되지 않은 borderFill → unresolved
        assert!(ctx.border_fill_ids.unresolved().contains(&99u16));
    }
}
