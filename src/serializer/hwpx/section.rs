//! Contents/section{N}.xml — Section 본문 직렬화
//!
//! Stage 2 (#182): 기존 템플릿 기반 구조를 유지하되, `<hp:p>` 와 `<hp:run>` 의 속성을
//! IR에서 가져와 동적으로 생성한다. `secPr`/`pagePr`/`grid` 등 섹션 정의는 템플릿 보존
//! (IR에 대응 필드가 더 담길 때까지 점진적으로 동적화 예정).
//!
//! Stage #177 (2026-04-18): `<hp:lineseg>` 직렬화를 IR 기반으로 전환.
//! `Paragraph.line_segs` 의 6개 필드(line_height, text_height, baseline_distance,
//! line_spacing, column_start/segment_width, tag)를 그대로 출력하여 **원본 lineseg 값
//! 보존**. rhwp 는 자신의 문서에서 새로 부정확한 값을 생산하지 않는다.
//!
//! IR 매핑 관행:
//!   - `section.paragraphs` 여러 개 = 하드 문단 경계 (`<hp:p>` 여러 개)
//!   - `paragraph.text` 내 `\n` = 소프트 라인브레이크 (`<hp:lineBreak/>`, 같은 문단 내)
//!   - `paragraph.text` 내 `\t` = 탭 (`<hp:tab width=... leader="0" type="1"/>`)
//!   - `paragraph.para_shape_id` → `<hp:p paraPrIDRef>`
//!   - `paragraph.style_id` → `<hp:p styleIDRef>`
//!   - `paragraph.column_type` → `<hp:p pageBreak/columnBreak>`
//!   - `paragraph.char_shapes[0].char_shape_id` → 첫 `<hp:run charPrIDRef>`
//!   - `paragraph.line_segs[i]` → 각 `<hp:lineseg>` 속성 (6개 필드 그대로 출력)

use quick_xml::Writer;

use crate::model::control::{Control, Equation};
use crate::model::document::{Document, Section};
use crate::model::footnote::{Endnote, Footnote};
use crate::model::header_footer::{Footer, Header, HeaderFooterApply};
use crate::model::paragraph::{ColumnBreakType, LineSeg, Paragraph};
use crate::model::shape::{
    CommonObjAttr, HorzAlign, HorzRelTo, ShapeObject, TextWrap, VertAlign, VertRelTo,
};

use super::context::SerializeContext;
use super::utils::xml_escape;
use super::SerializeError;
use super::{field, picture, table};

const EMPTY_SECTION_XML: &str = include_str!("templates/empty_section0.xml");
const TEXT_SLOT: &str = "<hp:t/>";
const LINESEG_SLOT_OPEN: &str = "<hp:linesegarray>";
const LINESEG_SLOT_CLOSE: &str = "</hp:linesegarray>";
const PARA_CLOSE: &str = "</hp:p></hs:sec>";

// 템플릿 내 첫 <hp:p> 태그의 실제 문자열 (id="3121190098" 랜덤 해시 포함).
// 템플릿은 정적이므로 이 문자열이 고정 위치에 있음이 보장됨.
const TEMPLATE_FIRST_P_TAG: &str = r#"<hp:p id="3121190098" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">"#;
// 템플릿 내 <hp:run charPrIDRef="0"> 직후에 TEXT_SLOT 이 오는 패턴.
const TEMPLATE_RUN_BEFORE_TEXT: &str = r#"<hp:run charPrIDRef="0"><hp:t/>"#;
const TEMPLATE_FIRST_P_CLOSE: &str = "</hp:p>";

/// 레퍼런스 기준 줄 레이아웃 파라미터.
const VERT_STEP: u32 = 1600; // vertsize(1000) + spacing(600)
const LINE_FLAGS: u32 = 393216;
const HORZ_SIZE: u32 = 42520;
/// 탭 기본 폭 (한컴이 열면서 재계산하지만 초기값으로 필요).
const TAB_DEFAULT_WIDTH: u32 = 4000;

/// Stage 2 진입점. `ctx` 는 Stage 3+ 에서 파라미터 검증에 사용.
pub fn write_section(
    section: &Section,
    _doc: &Document,
    _index: usize,
    ctx: &mut SerializeContext,
) -> Result<Vec<u8>, SerializeError> {
    if let Some(raw) = &section.hwpx_section_xml {
        return Ok(raw.clone());
    }

    let mut vert_cursor: u32 = 0;

    let first_para = section.paragraphs.first();
    let reusable_first_raw = first_para
        .filter(|p| !paragraph_has_dirty_table(p))
        .and_then(|p| p.hwpx_para_xml.as_ref());
    let mut out = if let Some(raw) = reusable_first_raw {
        if let Some(p) = first_para {
            vert_cursor = next_vert_cursor_from_ir(&p.line_segs, vert_cursor);
        }
        replace_template_first_paragraph(EMPTY_SECTION_XML, &String::from_utf8_lossy(raw))
    } else {
        let (first_t, first_linesegs, first_advance) = match first_para {
            Some(p) => render_paragraph_parts(p, vert_cursor, ctx),
            None => render_paragraph_parts_for_text("", vert_cursor),
        };
        vert_cursor = first_advance;

        let mut out = EMPTY_SECTION_XML.replacen(TEXT_SLOT, &first_t, 1);
        out = replace_first_linesegs(&out, &first_linesegs);

        // 첫 문단 `<hp:p>` 태그를 IR 기반 속성으로 교체
        if let Some(p) = first_para {
            let new_p_tag = render_hp_p_open(p, 0);
            out = out.replacen(TEMPLATE_FIRST_P_TAG, &new_p_tag, 1);

            // 첫 문단의 텍스트용 <hp:run> 의 charPrIDRef 를 IR 기반으로 교체
            // 템플릿에서 TEXT_SLOT 이 있던 자리 바로 앞의 <hp:run charPrIDRef="0"> 패턴.
            let first_run_cs = first_run_char_shape_id(p);
            let new_run = format!(r#"<hp:run charPrIDRef="{}">"#, first_run_cs);
            let replacement = format!("{}{}", new_run, &first_t);
            // 이미 first_t 는 out 에 들어갔으므로 그 직전의 <hp:run charPrIDRef="0"> 만 변경
            let anchor = format!("{}{}", r#"<hp:run charPrIDRef="0">"#, &first_t);
            if out.contains(&anchor) {
                out = out.replacen(&anchor, &replacement, 1);
            }
        }
        out
    };

    // 추가 문단: `</hp:p></hs:sec>` 직전에 `<hp:p>` 요소를 삽입.
    if section.paragraphs.len() > 1 {
        let mut extra = String::new();
        for (idx, p) in section.paragraphs.iter().enumerate().skip(1) {
            if !paragraph_has_dirty_table(p) {
                if let Some(raw) = &p.hwpx_para_xml {
                    if raw_para_linesegs_match_ir(raw, &p.line_segs) {
                        extra.push_str(&String::from_utf8_lossy(raw));
                        vert_cursor = next_vert_cursor_from_ir(&p.line_segs, vert_cursor);
                        continue;
                    }
                }
            }
            let (t, linesegs, advance) = render_paragraph_parts(p, vert_cursor, ctx);
            vert_cursor = advance;
            let cs = first_run_char_shape_id(p);
            extra.push_str(&render_hp_p_open(p, idx as u32));
            extra.push_str(&format!(r#"<hp:run charPrIDRef="{}">"#, cs));
            extra.push_str(&t);
            extra.push_str(r#"</hp:run><hp:linesegarray>"#);
            extra.push_str(&linesegs);
            extra.push_str(r#"</hp:linesegarray></hp:p>"#);
        }
        out = out.replacen(PARA_CLOSE, &format!("</hp:p>{}</hs:sec>", extra), 1);
    }

    if let Some(sec_pr) = &section.hwpx_sec_pr_xml {
        out = replace_first_sec_pr(&out, &String::from_utf8_lossy(sec_pr));
    }

    Ok(out.into_bytes())
}

fn paragraph_has_dirty_table(p: &Paragraph) -> bool {
    p.controls.iter().any(control_has_dirty_table)
}

fn control_has_dirty_table(control: &Control) -> bool {
    match control {
        Control::Table(table) => {
            table.dirty
                || table.cells.iter().any(|cell| {
                    cell.paragraphs
                        .iter()
                        .any(|para| para.controls.iter().any(control_has_dirty_table))
                })
        }
        _ => false,
    }
}

/// IR의 Paragraph를 기반으로 `<hp:p>` 시작 태그를 생성.
///
/// `id` 는 문단 순서 기반(0, 1, 2, ...)로 할당한다. 한컴 샘플은 랜덤 해시도 쓰지만
/// 파서는 id 를 무시하므로 순차값으로 충분.
fn render_hp_p_open(p: &Paragraph, id: u32) -> String {
    let page_break = if matches!(p.column_type, ColumnBreakType::Page) {
        1
    } else {
        0
    };
    let column_break = if matches!(p.column_type, ColumnBreakType::Column) {
        1
    } else {
        0
    };
    format!(
        r#"<hp:p id="{}" paraPrIDRef="{}" styleIDRef="{}" pageBreak="{}" columnBreak="{}" merged="0">"#,
        id, p.para_shape_id, p.style_id, page_break, column_break,
    )
}

/// Render a full `<hp:p>` fragment for nested paragraph containers such as
/// table-cell subLists. Unlike the section template path, this returns raw XML
/// and preserves the normal paragraph run/control/lineseg serialization.
pub(super) fn render_paragraph_xml_fragment(
    p: &Paragraph,
    id: u32,
    vert_start: u32,
    ctx: &mut SerializeContext,
) -> (String, u32) {
    let (t, linesegs, advance) = render_paragraph_parts(p, vert_start, ctx);
    let cs = first_run_char_shape_id(p);
    let xml = format!(
        r#"{p_open}<hp:run charPrIDRef="{cs}">{t}</hp:run><hp:linesegarray>{linesegs}</hp:linesegarray></hp:p>"#,
        p_open = render_hp_p_open(p, id),
        cs = cs,
        t = t,
        linesegs = linesegs,
    );
    (xml, advance)
}

fn replace_template_first_paragraph(template: &str, replacement: &str) -> String {
    let Some(start) = template.find(TEMPLATE_FIRST_P_TAG) else {
        return template.to_string();
    };
    let Some(close_rel) = template[start..].find(TEMPLATE_FIRST_P_CLOSE) else {
        return template.to_string();
    };
    let end = start + close_rel + TEMPLATE_FIRST_P_CLOSE.len();
    let mut out = String::with_capacity(template.len() + replacement.len());
    out.push_str(&template[..start]);
    out.push_str(replacement);
    out.push_str(&template[end..]);
    out
}

fn replace_first_sec_pr(xml: &str, replacement: &str) -> String {
    let Some(start) = xml.find("<hp:secPr") else {
        return xml.to_string();
    };
    let Some(close_rel) = xml[start..].find("</hp:secPr>") else {
        return xml.to_string();
    };
    let end = start + close_rel + "</hp:secPr>".len();
    let mut out = String::with_capacity(xml.len() + replacement.len());
    out.push_str(&xml[..start]);
    out.push_str(replacement);
    out.push_str(&xml[end..]);
    out
}

fn raw_para_linesegs_match_ir(raw: &[u8], line_segs: &[LineSeg]) -> bool {
    let raw = String::from_utf8_lossy(raw);
    let mut parsed = Vec::new();
    let mut rest = raw.as_ref();
    while let Some(start) = rest.find("<hp:lineseg ") {
        let after_start = &rest[start..];
        let Some(end) = after_start.find('>') else {
            return false;
        };
        let tag = &after_start[..=end];
        let Some(line_seg) = parse_lineseg_tag(tag) else {
            return false;
        };
        parsed.push(line_seg);
        rest = &after_start[end + 1..];
    }
    parsed.len() == line_segs.len()
        && parsed.iter().zip(line_segs).all(|(raw, ir)| {
            raw.text_start == ir.text_start
                && raw.vertical_pos == ir.vertical_pos
                && raw.line_height == ir.line_height
                && raw.text_height == ir.text_height
                && raw.baseline_distance == ir.baseline_distance
                && raw.line_spacing == ir.line_spacing
                && raw.column_start == ir.column_start
                && raw.segment_width == ir.segment_width
                && raw.tag == ir.tag
        })
}

fn parse_lineseg_tag(tag: &str) -> Option<LineSeg> {
    Some(LineSeg {
        text_start: attr_u32(tag, "textpos")?,
        vertical_pos: attr_i32(tag, "vertpos")?,
        line_height: attr_i32(tag, "vertsize")?,
        text_height: attr_i32(tag, "textheight")?,
        baseline_distance: attr_i32(tag, "baseline")?,
        line_spacing: attr_i32(tag, "spacing")?,
        column_start: attr_i32(tag, "horzpos")?,
        segment_width: attr_i32(tag, "horzsize")?,
        tag: attr_u32(tag, "flags")?,
    })
}

fn attr_u32(tag: &str, name: &str) -> Option<u32> {
    attr_str(tag, name)?.parse().ok()
}

fn attr_i32(tag: &str, name: &str) -> Option<i32> {
    attr_str(tag, name)?.parse().ok()
}

fn attr_str<'a>(tag: &'a str, name: &str) -> Option<&'a str> {
    let needle = format!(r#"{name}=""#);
    let start = tag.find(&needle)? + needle.len();
    let tail = &tag[start..];
    let end = tail.find('"')?;
    Some(&tail[..end])
}

/// 문단 첫 run 의 charPrIDRef.
/// 비어있으면 0 (기본 글자모양) 반환.
fn first_run_char_shape_id(p: &Paragraph) -> u32 {
    p.char_shape_id_at(0)
        .or_else(|| p.char_shapes.first().map(|r| r.char_shape_id))
        .unwrap_or(0)
}

/// Paragraph 하나를 (`<hp:t>` XML, lineseg XML, 다음 vert_cursor)로 변환.
///
/// `<hp:lineseg>` 출력 원칙 (#177):
/// - `para.line_segs` 가 비어있지 않으면 **IR 값 그대로 출력**
/// - 비어있을 때만 텍스트 내 `\n` 기반으로 fallback 생성 (빈 문단·`Document::default()` 호환)
fn render_paragraph_parts(
    para: &Paragraph,
    vert_start: u32,
    ctx: &mut SerializeContext,
) -> (String, String, u32) {
    let t_xml = render_run_content(para, ctx);

    if !para.line_segs.is_empty() {
        // IR 기반 출력 — 원본 lineseg 값 보존 (#177)
        let linesegs = render_lineseg_array_from_ir(&para.line_segs);
        let vert_end = next_vert_cursor_from_ir(&para.line_segs, vert_start);
        (t_xml, linesegs, vert_end)
    } else {
        // Fallback — IR에 line_segs 가 없으면 기존 생성 로직 유지
        let (linesegs, vert_end) = render_lineseg_array_fallback(&para.text, vert_start);
        (t_xml, linesegs, vert_end)
    }
}

/// IR 없이 텍스트만 있을 때 `<hp:t>` 와 fallback lineseg 생성.
/// `write_section` 이 `first_para == None` 인 경우를 위해 유지.
fn render_paragraph_parts_for_text(text: &str, vert_start: u32) -> (String, String, u32) {
    let t_xml = render_hp_t_content(text);
    let (linesegs, vert_end) = render_lineseg_array_fallback(text, vert_start);
    (t_xml, linesegs, vert_end)
}

/// `<hp:t>...</hp:t>` 본문 생성 — 탭/소프트브레이크/XML escape 포함.
fn render_hp_t_content(text: &str) -> String {
    let mut t_xml = String::from("<hp:t>");
    let mut buf = String::new();
    for c in text.chars() {
        match c {
            '\t' => {
                flush_buf(&mut t_xml, &mut buf);
                t_xml.push_str(&format!(
                    r#"<hp:tab width="{}" leader="0" type="1"/>"#,
                    TAB_DEFAULT_WIDTH
                ));
            }
            '\n' => {
                flush_buf(&mut t_xml, &mut buf);
                t_xml.push_str("<hp:lineBreak/>");
            }
            c if (c as u32) < 0x20 => { /* 기타 제어문자 무시 */ }
            c => buf.push(c),
        }
    }
    flush_buf(&mut t_xml, &mut buf);
    t_xml.push_str("</hp:t>");
    t_xml
}

/// Paragraph의 본문 run 콘텐츠를 `<hp:t>`와 인라인 컨트롤 XML로 직렬화한다.
fn render_run_content(para: &Paragraph, ctx: &mut SerializeContext) -> String {
    if !para.field_ranges.is_empty() {
        return render_run_content_with_fields(para, ctx);
    }

    if para.controls.is_empty() && para.char_shapes.len() > 1 {
        return render_char_shape_run_content(para);
    }

    let slot_count = inferred_control_slot_count(para);
    let slots: Vec<&Control> = if slot_count == para.controls.len() {
        para.controls.iter().collect()
    } else {
        para.controls
            .iter()
            .filter(|c| is_hwpx_inline_slot(c))
            .collect()
    };

    if slots.is_empty() {
        return render_hp_t_content(&para.text);
    }

    if slot_count != slots.len() {
        let mut out = render_hp_t_content(&para.text);
        for slot in slots {
            render_control_slot(&mut out, slot, ctx);
        }
        return out;
    }

    let mut out = String::new();
    let mut text_buf = String::new();
    let mut slot_idx = 0usize;
    let mut expected_utf16_pos = 0u32;

    for (idx, c) in para.text.chars().enumerate() {
        let char_pos = para
            .char_offsets
            .get(idx)
            .copied()
            .unwrap_or(expected_utf16_pos);
        while slot_idx < slots.len() && char_pos >= expected_utf16_pos.saturating_add(8) {
            flush_text_fragment(&mut out, &mut text_buf);
            render_control_slot(&mut out, slots[slot_idx], ctx);
            slot_idx += 1;
            expected_utf16_pos = expected_utf16_pos.saturating_add(8);
        }

        text_buf.push(c);
        let width = char_utf16_width(c);
        if char_pos >= expected_utf16_pos {
            expected_utf16_pos = char_pos.saturating_add(width);
        } else {
            expected_utf16_pos = expected_utf16_pos.saturating_add(width);
        }
    }

    flush_text_fragment(&mut out, &mut text_buf);
    while slot_idx < slots.len() {
        render_control_slot(&mut out, slots[slot_idx], ctx);
        slot_idx += 1;
    }

    if out.is_empty() {
        render_hp_t_content("")
    } else {
        // 한컴은 컨트롤만 있는 run 에도 빈 <hp:t/>를 둔다 — 없으면 재파싱된
        // run 에 텍스트런이 없어 compose 류 글리프가 렌더되지 않는다
        // (corpus/52 "목차" 드롭).
        if !out.contains("<hp:t") {
            out.push_str("<hp:t></hp:t>");
        }
        out
    }
}

fn render_char_shape_run_content(para: &Paragraph) -> String {
    let mut out = String::new();
    let mut text_buf = String::new();
    let mut current_cs = first_run_char_shape_id(para);

    for (idx, c) in para.text.chars().enumerate() {
        let cs = para.char_shape_id_at(idx).unwrap_or(current_cs);
        if cs != current_cs {
            flush_text_fragment(&mut out, &mut text_buf);
            out.push_str("</hp:run>");
            out.push_str(&format!(r#"<hp:run charPrIDRef="{}">"#, cs));
            current_cs = cs;
        }
        text_buf.push(c);
    }

    flush_text_fragment(&mut out, &mut text_buf);
    if out.is_empty() {
        render_hp_t_content("")
    } else {
        out
    }
}

fn render_run_content_with_fields(para: &Paragraph, ctx: &mut SerializeContext) -> String {
    let mut out = String::new();
    let mut text_buf = String::new();
    let char_len = para.text.chars().count();

    for (idx, c) in para.text.chars().enumerate() {
        for range in para.field_ranges.iter().filter(|r| r.start_char_idx == idx) {
            flush_text_fragment(&mut out, &mut text_buf);
            if let Some(Control::Field(f)) = para.controls.get(range.control_idx) {
                render_field_begin(&mut out, f);
            }
        }

        text_buf.push(c);

        let next_idx = idx + 1;
        for range in para
            .field_ranges
            .iter()
            .filter(|r| r.end_char_idx == next_idx)
        {
            flush_text_fragment(&mut out, &mut text_buf);
            if let Some(Control::Field(f)) = para.controls.get(range.control_idx) {
                render_field_end(&mut out, f.field_id);
            }
        }
    }

    flush_text_fragment(&mut out, &mut text_buf);

    for range in para
        .field_ranges
        .iter()
        .filter(|r| r.start_char_idx >= char_len)
    {
        if let Some(Control::Field(f)) = para.controls.get(range.control_idx) {
            render_field_begin(&mut out, f);
            render_field_end(&mut out, f.field_id);
        }
    }

    for ctrl in para.controls.iter().filter(|c| is_hwpx_inline_slot(c)) {
        render_control_slot(&mut out, ctrl, ctx);
    }

    if out.is_empty() {
        render_hp_t_content("")
    } else {
        // render_run_content 와 동일 — 컨트롤만 있는 run 에도 빈 <hp:t/> 유지.
        if !out.contains("<hp:t") {
            out.push_str("<hp:t></hp:t>");
        }
        out
    }
}

fn render_field_begin(out: &mut String, f: &crate::model::control::Field) {
    match writer_to_string(|w| field::write_field_begin(w, f)) {
        Ok(xml) => {
            out.push_str("<hp:ctrl>");
            out.push_str(&xml);
            out.push_str("</hp:ctrl>");
        }
        Err(e) => eprintln!("[hwpx] FieldBegin 직렬화 실패: {e}"),
    }
}

fn render_field_end(out: &mut String, field_id: u32) {
    match writer_to_string(|w| field::write_field_end(w, field_id)) {
        Ok(xml) => {
            out.push_str("<hp:ctrl>");
            out.push_str(&xml);
            out.push_str("</hp:ctrl>");
        }
        Err(e) => eprintln!("[hwpx] FieldEnd 직렬화 실패: {e}"),
    }
}

fn inferred_control_slot_count(para: &Paragraph) -> usize {
    let text_units: u32 = para.text.chars().map(char_utf16_width).sum();
    let from_char_count = para.char_count.saturating_sub(1).saturating_sub(text_units) / 8;

    let mut from_offsets = 0u32;
    let mut expected = 0u32;
    for (idx, c) in para.text.chars().enumerate() {
        let pos = para.char_offsets.get(idx).copied().unwrap_or(expected);
        if pos > expected {
            from_offsets += (pos - expected) / 8;
        }
        expected = pos.max(expected).saturating_add(char_utf16_width(c));
    }

    from_char_count.max(from_offsets) as usize
}

fn is_hwpx_inline_slot(control: &Control) -> bool {
    matches!(
        control,
        Control::Table(_)
            | Control::Shape(_)
            | Control::Picture(_)
            | Control::CharOverlap(_)
            | Control::Ruby(_)
            | Control::Equation(_)
            | Control::Form(_)
            | Control::Header(_)
            | Control::Footer(_)
            | Control::Footnote(_)
            | Control::Endnote(_)
            | Control::PageNumberPos(_)
            | Control::NewNumber(_)
            | Control::AutoNumber(_)
            | Control::PageHide(_)
    )
}

fn flush_text_fragment(out: &mut String, text_buf: &mut String) {
    if !text_buf.is_empty() {
        out.push_str(&render_hp_t_content(text_buf));
        text_buf.clear();
    }
}

fn render_control_slot(out: &mut String, control: &Control, ctx: &mut SerializeContext) {
    match control {
        Control::Equation(eq) => {
            out.push_str(&render_equation(eq));
        }
        Control::Table(tbl) => match writer_to_string(|w| table::write_table(w, tbl, ctx)) {
            Ok(xml) => out.push_str(&xml),
            Err(e) => eprintln!("[hwpx] Table 직렬화 실패: {e}"),
        },
        Control::Picture(pic) => match writer_to_string(|w| picture::write_picture(w, pic, ctx)) {
            Ok(xml) => out.push_str(&xml),
            Err(e) => eprintln!("[hwpx] Picture 직렬화 실패: {e}"),
        },
        Control::Field(f) => {
            render_field_begin(out, f);
            render_field_end(out, f.field_id);
        }
        Control::Shape(shape) => {
            out.push_str(&render_shape(shape, ctx));
        }
        Control::Footnote(note) => {
            out.push_str(&render_footnote(note, ctx));
        }
        Control::Endnote(note) => {
            out.push_str(&render_endnote(note, ctx));
        }
        Control::Header(header) => {
            out.push_str(&render_header(header, ctx));
        }
        Control::Footer(footer) => {
            out.push_str(&render_footer(footer, ctx));
        }
        // 섹션/번호 인라인 컨트롤 — 편집으로 첫 문단이 IR 재생성될 때
        // 쪽번호/새번호 표시가 통째로 사라지던 가족 (edit-eval reopen_render).
        Control::PageNumberPos(pn) => {
            out.push_str(&format!(
                r#"<hp:ctrl><hp:pageNum pos="{}" formatType="{}" sideChar="{}"/></hp:ctrl>"#,
                page_num_pos_str(pn.position),
                num_format_str(pn.format),
                xml_escape(&pn.dash_char.to_string()),
            ));
        }
        Control::NewNumber(nn) => {
            out.push_str(&format!(
                r#"<hp:ctrl><hp:newNum num="{}" numType="{}"/></hp:ctrl>"#,
                nn.number,
                auto_num_type_str(nn.number_type),
            ));
        }
        Control::AutoNumber(an) => {
            out.push_str(&format!(
                r#"<hp:ctrl><hp:autoNum num="{}" numType="{}"/></hp:ctrl>"#,
                an.number,
                auto_num_type_str(an.number_type),
            ));
        }
        Control::CharOverlap(co) => {
            // <hp:compose> — 글자겹침 (원문자/박스숫자). 드롭 시 편집된 표의
            // 모든 셀에서 ①/□1 류 글자가 사라진다 (corpus/01·52 reopen_render).
            let compose_text: String = co.chars.iter().collect();
            out.push_str(&format!(
                r#"<hp:compose circleType="{}" charSz="{}" composeType="{}" charPrCnt="{}" composeText="{}">"#,
                compose_circle_type_str(co.border_type),
                co.inner_char_size,
                if co.expansion == 1 { "OVERLAP" } else { "SPREAD" },
                co.char_shape_ids.len(),
                xml_escape(&compose_text),
            ));
            for id in &co.char_shape_ids {
                out.push_str(&format!(r#"<hp:charPr prIDRef="{}"/>"#, id));
            }
            out.push_str("</hp:compose>");
        }
        Control::Form(form) => {
            // 양식 개체 (checkBtn 류). 드롭 시 편집된 표의 체크박스가 캡션째
            // 사라진다 (form-002 180개, corpus/21 9개). 모델이 보존한 속성만
            // 복원하고 나머지는 한컴 기본값 — 렌더 내용(캡션/체크 상태)은 유지.
            out.push_str(&render_form_object(form));
        }
        Control::PageHide(ph) => {
            out.push_str(&format!(
                r#"<hp:ctrl><hp:pageHiding hideHeader="{}" hideFooter="{}" hideMasterPage="{}" hideBorder="{}" hideFill="{}" hidePageNum="{}"/></hp:ctrl>"#,
                ph.hide_header as u8,
                ph.hide_footer as u8,
                ph.hide_master_page as u8,
                ph.hide_border as u8,
                ph.hide_fill as u8,
                ph.hide_page_num as u8,
            ));
        }
        _ => {}
    }
}

/// parse_page_num_attrs 의 역매핑 (HWP 스펙 표 150 bit 8~11).
fn page_num_pos_str(pos: u8) -> &'static str {
    match pos {
        0 => "NONE",
        1 => "TOP_LEFT",
        2 => "TOP_CENTER",
        3 => "TOP_RIGHT",
        4 => "BOTTOM_LEFT",
        6 => "BOTTOM_RIGHT",
        7 => "OUTSIDE_TOP",
        8 => "OUTSIDE_BOTTOM",
        9 => "INSIDE_TOP",
        10 => "INSIDE_BOTTOM",
        _ => "BOTTOM_CENTER",
    }
}

/// parse_page_num_attrs formatType 의 역매핑 (표 134).
fn num_format_str(format: u8) -> &'static str {
    match format {
        1 => "CIRCLE_DIGIT",
        2 => "ROMAN_CAPITAL",
        3 => "ROMAN_SMALL",
        4 => "LATIN_CAPITAL",
        5 => "LATIN_SMALL",
        6 => "HANGUL",
        7 => "HANJA",
        _ => "DIGIT",
    }
}

/// parse_compose circleType 의 역매핑 (파서의 SHAPE_REVERSAL_TIRANGLE 오탈자 유지).
fn compose_circle_type_str(border_type: u8) -> &'static str {
    match border_type {
        1 => "SHAPE_CIRCLE",
        2 => "SHAPE_REVERSAL_CIRCLE",
        3 => "SHAPE_RECTANGLE",
        4 => "SHAPE_REVERSAL_RECTANGLE",
        5 => "SHAPE_TRIANGLE",
        6 => "SHAPE_REVERSAL_TIRANGLE",
        _ => "CHAR",
    }
}

/// 0x00BBGGRR → "#RRGGBB" (parse_color_str 의 역매핑).
fn color_ref_str(c: u32) -> String {
    if c == 0xFFFF_FFFF {
        return "none".to_string();
    }
    format!(
        "#{:02X}{:02X}{:02X}",
        c & 0xFF,
        (c >> 8) & 0xFF,
        (c >> 16) & 0xFF
    )
}

/// FormObject → <hp:btn|checkBtn|radioBtn|comboBox|edit> (parse_form_object 의 역매핑).
/// 모델이 보존하지 않는 속성(triState/backStyle/pos 세부)은 한컴 기본값으로 채운다.
fn render_form_object(form: &crate::model::control::FormObject) -> String {
    use crate::model::control::FormType;
    let tag = match form.form_type {
        FormType::PushButton => "hp:btn",
        FormType::CheckBox => "hp:checkBtn",
        FormType::ComboBox => "hp:comboBox",
        FormType::RadioButton => "hp:radioBtn",
        FormType::Edit => "hp:edit",
    };
    let prop = |k: &str, d: &str| -> String {
        form.properties
            .get(k)
            .cloned()
            .unwrap_or_else(|| d.to_string())
    };
    let mut out = format!(
        r#"<{tag} caption="{}" value="{}" radioGroupName="" triState="0" backStyle="OPAQUE" name="{}" foreColor="{}" backColor="{}" groupName="{}" tabStop="{}" editable="{}" tabOrder="{}" enabled="{}" borderTypeIDRef="{}" drawFrame="{}" printable="{}" command="{}""#,
        xml_escape(&form.caption),
        if form.value != 0 { "CHECKED" } else { "UNCHECKED" },
        xml_escape(&form.name),
        color_ref_str(form.fore_color),
        color_ref_str(form.back_color),
        xml_escape(&prop("GroupName", "")),
        prop("TabStop", "1"),
        prop("Editable", "1"),
        prop("TabOrder", "0"),
        if form.enabled { "1" } else { "0" },
        prop("BorderType", "0"),
        prop("DrawFrame", "1"),
        prop("Printable", "1"),
        xml_escape(&prop("Command", "")),
    );
    if matches!(form.form_type, FormType::ComboBox) {
        out.push_str(&format!(r#" selectedValue="{}""#, xml_escape(&form.text)));
        out.push_str(&format!(r#" listBoxRows="{}""#, prop("ListBoxRows", "0")));
        out.push_str(&format!(r#" listBoxWidth="{}""#, prop("ListBoxWidth", "0")));
        out.push_str(&format!(r#" editEnable="{}""#, prop("EditEnable", "0")));
    }
    out.push('>');
    out.push_str(&format!(
        r#"<hp:formCharPr charPrIDRef="{}" followContext="{}" autoSz="{}" wordWrap="{}"/>"#,
        prop("CharShapeID", "0"),
        prop("FollowContext", "0"),
        prop("AutoSize", "0"),
        prop("WordWrap", "0"),
    ));
    out.push_str(&format!(
        r#"<hp:sz width="{}" widthRelTo="ABSOLUTE" height="{}" heightRelTo="ABSOLUTE" protect="0"/>"#,
        form.width, form.height
    ));
    out.push_str(
        r#"<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="1" holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="PARA" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/><hp:outMargin left="0" right="0" top="0" bottom="0"/>"#,
    );
    if matches!(form.form_type, FormType::ComboBox) {
        let mut i = 0;
        while let Some(item) = form.properties.get(&format!("listItem{}", i)) {
            out.push_str(&format!(r#"<hp:listItem value="{}"/>"#, xml_escape(item)));
            i += 1;
        }
    }
    if matches!(form.form_type, FormType::Edit) && !form.text.is_empty() {
        out.push_str(&format!("<hp:text>{}</hp:text>", xml_escape(&form.text)));
    }
    out.push_str(&format!("</{tag}>"));
    out
}

/// parse_num_type 의 역매핑.
fn auto_num_type_str(t: crate::model::control::AutoNumberType) -> &'static str {
    use crate::model::control::AutoNumberType::*;
    match t {
        Page => "PAGE",
        TotalPage => "TOTAL_PAGE",
        Footnote => "FOOTNOTE",
        Endnote => "ENDNOTE",
        Picture => "PICTURE",
        Table => "TABLE",
        Equation => "EQUATION",
    }
}

fn writer_to_string<F>(f: F) -> Result<String, SerializeError>
where
    F: FnOnce(&mut Writer<Vec<u8>>) -> Result<(), SerializeError>,
{
    let mut writer = Writer::new(Vec::new());
    f(&mut writer)?;
    let bytes = writer.into_inner();
    String::from_utf8(bytes)
        .map_err(|e| SerializeError::XmlError(format!("invalid UTF-8 from XML writer: {e}")))
}

fn render_shape(shape: &ShapeObject, ctx: &mut SerializeContext) -> String {
    // Rectangle: Writer-based serializer (drawText 포함)
    if let ShapeObject::Rectangle(r) = shape {
        return match writer_to_string(|w| super::shape::write_rect(w, r)) {
            Ok(xml) => xml,
            Err(e) => {
                eprintln!("[hwpx] Shape::Rectangle 직렬화 실패: {e}");
                String::new()
            }
        };
    }
    // Line: Writer-based serializer
    if let ShapeObject::Line(l) = shape {
        return match writer_to_string(|w| super::shape::write_line(w, l)) {
            Ok(xml) => xml,
            Err(e) => {
                eprintln!("[hwpx] Shape::Line 직렬화 실패: {e}");
                String::new()
            }
        };
    }
    // Group (container): 자식 도형을 재귀 직렬화. 이전에는
    // render_common_shape_xml 로 빈 껍데기만 출력되어 그룹 내부의
    // rect/drawText (글상자 텍스트) 가 편집 후 재직렬화에서 전부
    // 유실됐다 (19_org_diagnosis Ⅳ 배너 등).
    if let ShapeObject::Group(g) = shape {
        let mut out = match writer_to_string(|w| super::shape::write_container_open(w, &g.common))
        {
            Ok(xml) => xml,
            Err(e) => {
                eprintln!("[hwpx] Shape::Group 직렬화 실패: {e}");
                return String::new();
            }
        };
        for child in &g.children {
            out.push_str(&render_shape(child, ctx));
        }
        out.push_str("</hp:container>");
        return out;
    }
    let (tag, c) = match shape {
        ShapeObject::Rectangle(_) | ShapeObject::Line(_) | ShapeObject::Group(_) => unreachable!(),
        ShapeObject::Ellipse(e) => ("ellipse", &e.common),
        ShapeObject::Arc(a) => ("arc", &a.common),
        ShapeObject::Polygon(p) => ("polygon", &p.common),
        ShapeObject::Curve(cv) => ("curve", &cv.common),
        ShapeObject::Picture(pic) => {
            return match writer_to_string(|w| picture::write_picture(w, pic, ctx)) {
                Ok(xml) => xml,
                Err(e) => {
                    eprintln!("[hwpx] Shape::Picture 직렬화 실패: {e}");
                    String::new()
                }
            };
        }
        ShapeObject::Chart(ch) => ("chart", &ch.common),
        ShapeObject::Ole(o) => ("ole", &o.common),
    };
    render_common_shape_xml(tag, c)
}

fn render_common_shape_xml(tag: &str, c: &CommonObjAttr) -> String {
    format!(
        concat!(
            r#"<hp:{tag} id="{id}" zOrder="{zo}" textWrap="{tw}" textFlow="BOTH_SIDES" lock="0">"#,
            r#"<hp:sz width="{w}" height="{h}" widthRelTo="ABSOLUTE" heightRelTo="ABSOLUTE"/>"#,
            r#"<hp:pos treatAsChar="{tac}" vertRelTo="{vr}" vertAlign="{va}" horzRelTo="{hr}" horzAlign="{ha}" vertOffset="{vo}" horzOffset="{ho}"/>"#,
            r#"<hp:outMargin left="{ml}" right="{mr}" top="{mt}" bottom="{mb}"/>"#,
            r#"</hp:{tag}>"#,
        ),
        tag = tag,
        id = c.instance_id,
        zo = c.z_order,
        tw = text_wrap_to_hwpx(c.text_wrap),
        tac = if c.treat_as_char { "1" } else { "0" },
        w = c.width,
        h = c.height,
        vr = vert_rel_to_hwpx(c.vert_rel_to),
        va = vert_align_to_hwpx(c.vert_align),
        hr = horz_rel_to_hwpx(c.horz_rel_to),
        ha = horz_align_to_hwpx(c.horz_align),
        vo = c.vertical_offset,
        ho = c.horizontal_offset,
        ml = c.margin.left,
        mr = c.margin.right,
        mt = c.margin.top,
        mb = c.margin.bottom,
    )
}

fn render_note_sublist(
    tag: &str,
    number: u16,
    paragraphs: &[Paragraph],
    ctx: &mut SerializeContext,
) -> String {
    let mut out = format!(
        r#"<hp:ctrl><hp:{tag} number="{num}"><hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="TOP" linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">"#,
        tag = tag,
        num = number,
    );
    let mut vert_cursor: u32 = 0;
    for (idx, p) in paragraphs.iter().enumerate() {
        let (t, linesegs, advance) = render_paragraph_parts(p, vert_cursor, ctx);
        vert_cursor = advance;
        let cs = first_run_char_shape_id(p);
        out.push_str(&render_hp_p_open(p, idx as u32));
        out.push_str(&format!(r#"<hp:run charPrIDRef="{}">"#, cs));
        out.push_str(&t);
        out.push_str(r#"</hp:run><hp:linesegarray>"#);
        out.push_str(&linesegs);
        out.push_str(r#"</hp:linesegarray></hp:p>"#);
    }
    out.push_str(&format!("</hp:subList></hp:{tag}></hp:ctrl>", tag = tag));
    out
}

fn render_footnote(note: &Footnote, ctx: &mut SerializeContext) -> String {
    render_note_sublist("footNote", note.number, &note.paragraphs, ctx)
}

fn render_endnote(note: &Endnote, ctx: &mut SerializeContext) -> String {
    render_note_sublist("endNote", note.number, &note.paragraphs, ctx)
}

fn header_footer_apply_to_hwpx(apply_to: HeaderFooterApply) -> &'static str {
    match apply_to {
        HeaderFooterApply::Both => "BOTH",
        HeaderFooterApply::Even => "EVEN",
        HeaderFooterApply::Odd => "ODD",
    }
}

fn render_header_footer_sublist(
    tag: &str,
    apply_to: HeaderFooterApply,
    paragraphs: &[Paragraph],
    ctx: &mut SerializeContext,
) -> String {
    let mut out = format!(
        r#"<hp:ctrl><hp:{tag} applyPageType="{apply}"><hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="TOP" linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">"#,
        tag = tag,
        apply = header_footer_apply_to_hwpx(apply_to),
    );
    let mut vert_cursor: u32 = 0;
    for (idx, p) in paragraphs.iter().enumerate() {
        let (t, linesegs, advance) = render_paragraph_parts(p, vert_cursor, ctx);
        vert_cursor = advance;
        let cs = first_run_char_shape_id(p);
        out.push_str(&render_hp_p_open(p, idx as u32));
        out.push_str(&format!(r#"<hp:run charPrIDRef="{}">"#, cs));
        out.push_str(&t);
        out.push_str(r#"</hp:run><hp:linesegarray>"#);
        out.push_str(&linesegs);
        out.push_str(r#"</hp:linesegarray></hp:p>"#);
    }
    out.push_str(&format!("</hp:subList></hp:{tag}></hp:ctrl>", tag = tag));
    out
}

fn render_header(header: &Header, ctx: &mut SerializeContext) -> String {
    render_header_footer_sublist("header", header.apply_to, &header.paragraphs, ctx)
}

fn render_footer(footer: &Footer, ctx: &mut SerializeContext) -> String {
    render_header_footer_sublist("footer", footer.apply_to, &footer.paragraphs, ctx)
}

fn render_equation(eq: &Equation) -> String {
    let c = &eq.common;
    let id = c.instance_id.to_string();
    let z_order = c.z_order.to_string();
    let version = xml_escape(&eq.version_info);
    let baseline = eq.baseline.to_string();
    let text_color = color_ref_to_hwpx(eq.color);
    let base_unit = eq.font_size.to_string();
    let font = xml_escape(&eq.font_name);
    let script = xml_escape(&eq.script);
    let width = c.width.to_string();
    let height = c.height.to_string();
    let treat = if c.treat_as_char { "1" } else { "0" };
    let vert_offset = c.vertical_offset.to_string();
    let horz_offset = c.horizontal_offset.to_string();
    let margin_left = c.margin.left.to_string();
    let margin_right = c.margin.right.to_string();
    let margin_top = c.margin.top.to_string();
    let margin_bottom = c.margin.bottom.to_string();

    format!(
        r#"<hp:equation id="{id}" zOrder="{z_order}" numberingType="EQUATION" textWrap="{}" textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" instid="{id}" version="{version}" baseLine="{baseline}" textColor="{text_color}" baseUnit="{base_unit}" font="{font}"><hp:script>{script}</hp:script><hp:sz width="{width}" widthRelTo="ABSOLUTE" height="{height}" heightRelTo="ABSOLUTE"/><hp:pos treatAsChar="{treat}" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" vertRelTo="{}" horzRelTo="{}" vertAlign="{}" horzAlign="{}" vertOffset="{vert_offset}" horzOffset="{horz_offset}"/><hp:outMargin left="{margin_left}" right="{margin_right}" top="{margin_top}" bottom="{margin_bottom}"/></hp:equation>"#,
        text_wrap_to_hwpx(c.text_wrap),
        vert_rel_to_hwpx(c.vert_rel_to),
        horz_rel_to_hwpx(c.horz_rel_to),
        vert_align_to_hwpx(c.vert_align),
        horz_align_to_hwpx(c.horz_align),
    )
}

fn char_utf16_width(c: char) -> u32 {
    if c == '\t' {
        8
    } else if (c as u32) > 0xFFFF {
        2
    } else {
        1
    }
}

fn color_ref_to_hwpx(color: u32) -> String {
    if color == 0xFFFFFFFF {
        return "none".to_string();
    }

    let a = (color >> 24) & 0xFF;
    let r = color & 0xFF;
    let g = (color >> 8) & 0xFF;
    let b = (color >> 16) & 0xFF;
    if a == 0 {
        format!("#{r:02X}{g:02X}{b:02X}")
    } else {
        format!("#{a:02X}{r:02X}{g:02X}{b:02X}")
    }
}

fn text_wrap_to_hwpx(wrap: TextWrap) -> &'static str {
    match wrap {
        TextWrap::Square => "SQUARE",
        TextWrap::Tight => "TIGHT",
        TextWrap::Through => "THROUGH",
        TextWrap::TopAndBottom => "TOP_AND_BOTTOM",
        TextWrap::BehindText => "BEHIND_TEXT",
        TextWrap::InFrontOfText => "IN_FRONT_OF_TEXT",
    }
}

fn vert_rel_to_hwpx(rel: VertRelTo) -> &'static str {
    match rel {
        VertRelTo::Paper => "PAPER",
        VertRelTo::Page => "PAGE",
        VertRelTo::Para => "PARA",
    }
}

fn horz_rel_to_hwpx(rel: HorzRelTo) -> &'static str {
    match rel {
        HorzRelTo::Paper => "PAPER",
        HorzRelTo::Page => "PAGE",
        HorzRelTo::Column => "COLUMN",
        HorzRelTo::Para => "PARA",
    }
}

fn vert_align_to_hwpx(align: VertAlign) -> &'static str {
    match align {
        VertAlign::Top => "TOP",
        VertAlign::Center => "CENTER",
        VertAlign::Bottom => "BOTTOM",
        VertAlign::Inside => "INSIDE",
        VertAlign::Outside => "OUTSIDE",
    }
}

fn horz_align_to_hwpx(align: HorzAlign) -> &'static str {
    match align {
        HorzAlign::Left => "LEFT",
        HorzAlign::Center => "CENTER",
        HorzAlign::Right => "RIGHT",
        HorzAlign::Inside => "INSIDE",
        HorzAlign::Outside => "OUTSIDE",
    }
}

/// IR의 `line_segs` 를 그대로 XML로 직렬화 (6개 필드 전부 IR 값 사용).
///
/// rhwp 는 자신의 문서에서 비표준 lineseg 를 **새로 생산하지 않는다**.
/// 원본 한컴 파일의 lineseg 값이 파서에 의해 `Paragraph.line_segs` 에 담겼다면,
/// 저장 시 그 값을 훼손 없이 보존한다.
fn render_lineseg_array_from_ir(segs: &[LineSeg]) -> String {
    let mut out = String::new();
    for seg in segs {
        out.push_str(&format!(
            r#"<hp:lineseg textpos="{}" vertpos="{}" vertsize="{}" textheight="{}" baseline="{}" spacing="{}" horzpos="{}" horzsize="{}" flags="{}"/>"#,
            seg.text_start,
            seg.vertical_pos,
            seg.line_height,
            seg.text_height,
            seg.baseline_distance,
            seg.line_spacing,
            seg.column_start,
            seg.segment_width,
            seg.tag,
        ));
    }
    out
}

/// IR 기반 다음 문단의 vert_start 계산 — 마지막 lineseg 의 vpos + lh 사용.
fn next_vert_cursor_from_ir(segs: &[LineSeg], vert_start: u32) -> u32 {
    if let Some(last) = segs.last() {
        // vertical_pos 는 섹션 시작 기준 절대값일 수도, 문단 기준 상대값일 수도 있음.
        // 현재 rhwp 는 섹션 절대값이므로 그대로 + lh 로 다음 커서 산출.
        let next = (last.vertical_pos as i64) + (last.line_height.max(0) as i64);
        if next > vert_start as i64 {
            next as u32
        } else {
            vert_start + VERT_STEP
        }
    } else {
        vert_start + VERT_STEP
    }
}

/// Fallback — IR 에 line_segs 가 없는 경우에만 사용 (예: `Document::default()`).
/// 과거 동작을 보존하기 위해 기존 정적값으로 lineseg 생성.
fn render_lineseg_array_fallback(text: &str, vert_start: u32) -> (String, u32) {
    let mut linesegs = String::new();
    push_lineseg_static(&mut linesegs, 0, vert_start);
    let mut utf16_pos: u32 = 0;
    let mut lines_in_para: u32 = 0;
    for c in text.chars() {
        let u16_len = c.len_utf16() as u32;
        match c {
            '\t' | '\n' => {
                utf16_pos += u16_len;
                if c == '\n' {
                    lines_in_para += 1;
                    push_lineseg_static(
                        &mut linesegs,
                        utf16_pos,
                        vert_start + lines_in_para * VERT_STEP,
                    );
                }
            }
            c if (c as u32) < 0x20 => {}
            _ => utf16_pos += u16_len,
        }
    }
    let vert_end = vert_start + (lines_in_para + 1) * VERT_STEP;
    (linesegs, vert_end)
}

fn flush_buf(t_xml: &mut String, buf: &mut String) {
    if !buf.is_empty() {
        t_xml.push_str(&xml_escape(buf));
        buf.clear();
    }
}

/// Fallback 전용 static lineseg 생성기 — IR에 값이 없을 때만 사용.
/// 주: 이 함수의 출력은 "명세 상 정확한 값" 이 아닌 정적 자리표이므로,
/// 호출 후 문서는 `DocumentCore::from_bytes` 의 `reflow_zero_height_paragraphs`
/// 또는 사용자의 `reflow_linesegs_on_demand` 로 재계산되어야 한다.
fn push_lineseg_static(out: &mut String, textpos: u32, vertpos: u32) {
    out.push_str(&format!(
        r#"<hp:lineseg textpos="{}" vertpos="{}" vertsize="1000" textheight="1000" baseline="850" spacing="600" horzpos="0" horzsize="{}" flags="{}"/>"#,
        textpos, vertpos, HORZ_SIZE, LINE_FLAGS,
    ));
}

fn replace_first_linesegs(xml: &str, new_inner: &str) -> String {
    let open = xml
        .rfind(LINESEG_SLOT_OPEN)
        .expect("template has linesegarray");
    let inner_start = open + LINESEG_SLOT_OPEN.len();
    let close_rel = xml[inner_start..]
        .find(LINESEG_SLOT_CLOSE)
        .expect("template has closing linesegarray");
    let inner_end = inner_start + close_rel;
    let mut out = String::with_capacity(xml.len() + new_inner.len());
    out.push_str(&xml[..inner_start]);
    out.push_str(new_inner);
    out.push_str(&xml[inner_end..]);
    out
}

// `TEMPLATE_RUN_BEFORE_TEXT` 는 패턴 인식용 상수로만 쓰이므로 명시 참조.
#[allow(dead_code)]
fn _template_anchor_hint() {
    let _ = TEMPLATE_RUN_BEFORE_TEXT;
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::paragraph::{CharShapeRef, Paragraph};

    fn make_doc_with_paragraph(para: Paragraph) -> (Document, Section) {
        let mut section = Section::default();
        section.paragraphs.push(para);
        let mut doc = Document::default();
        doc.sections.push(section.clone());
        (doc, section)
    }

    #[test]
    fn write_section_preserves_clean_hwpx_source_xml() {
        let raw = br#"<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"><hp:p id="raw"/></hs:sec>"#.to_vec();
        let mut section = Section::default();
        section.hwpx_section_xml = Some(raw.clone());
        section.paragraphs.push(Paragraph {
            text: "regenerated text must not leak".to_string(),
            ..Default::default()
        });

        let mut doc = Document::default();
        doc.sections.push(section.clone());
        let mut ctx = SerializeContext::collect_from_document(&doc);

        let bytes = write_section(&section, &doc, 0, &mut ctx).unwrap();
        assert_eq!(bytes, raw);
    }

    #[test]
    fn write_section_preserves_clean_paragraph_source_xml() {
        let raw_para = br#"<hp:p id="raw" paraPrIDRef="9" styleIDRef="0"><hp:run charPrIDRef="2"><hp:t>raw paragraph</hp:t></hp:run><hp:linesegarray><hp:lineseg textpos="0" vertpos="0" vertsize="1" textheight="1" baseline="1" spacing="0" horzpos="0" horzsize="1" flags="0"/></hp:linesegarray></hp:p>"#.to_vec();
        let mut section = Section::default();
        section.paragraphs.push(Paragraph {
            text: "regenerated text must not leak".to_string(),
            hwpx_para_xml: Some(raw_para.clone()),
            ..Default::default()
        });

        let mut doc = Document::default();
        doc.sections.push(section.clone());
        let mut ctx = SerializeContext::collect_from_document(&doc);

        let xml = String::from_utf8(write_section(&section, &doc, 0, &mut ctx).unwrap()).unwrap();
        assert!(xml.contains(std::str::from_utf8(&raw_para).unwrap()));
        assert!(!xml.contains("regenerated text must not leak"));
    }

    #[test]
    fn write_section_regenerates_following_paragraph_after_dirty_paragraph() {
        let stale_raw_para = br#"<hp:p id="stale" paraPrIDRef="0" styleIDRef="0"><hp:run charPrIDRef="0"><hp:t>stale raw paragraph</hp:t></hp:run><hp:linesegarray><hp:lineseg textpos="0" vertpos="11428" vertsize="10948" textheight="10948" baseline="9306" spacing="480" horzpos="0" horzsize="48188" flags="393216"/></hp:linesegarray></hp:p>"#.to_vec();
        let mut section = Section::default();
        section.paragraphs.push(Paragraph {
            text: "edited".to_string(),
            line_segs: vec![LineSeg {
                text_start: 0,
                vertical_pos: 0,
                line_height: 900,
                text_height: 900,
                baseline_distance: 765,
                line_spacing: 360,
                column_start: 0,
                segment_width: 42520,
                tag: 393216,
            }],
            ..Default::default()
        });
        section.paragraphs.push(Paragraph {
            text: "current paragraph".to_string(),
            hwpx_para_xml: Some(stale_raw_para),
            line_segs: vec![LineSeg {
                text_start: 0,
                vertical_pos: 1260,
                line_height: 900,
                text_height: 900,
                baseline_distance: 765,
                line_spacing: 360,
                column_start: 0,
                segment_width: 42520,
                tag: 393216,
            }],
            ..Default::default()
        });

        let mut doc = Document::default();
        doc.sections.push(section.clone());
        let mut ctx = SerializeContext::collect_from_document(&doc);

        let xml = String::from_utf8(write_section(&section, &doc, 0, &mut ctx).unwrap()).unwrap();
        assert!(xml.contains("current paragraph"));
        assert!(xml.contains(r#"vertpos="1260""#));
        assert!(!xml.contains("stale raw paragraph"));
        assert!(!xml.contains(r#"vertpos="11428""#));
    }

    #[test]
    fn write_section_preserves_following_raw_paragraph_when_linesegs_match_ir() {
        let raw_para = br#"<hp:p id="raw-complex" paraPrIDRef="0" styleIDRef="0"><hp:run charPrIDRef="0"><hp:t>raw complex paragraph</hp:t></hp:run><hp:linesegarray><hp:lineseg textpos="0" vertpos="1260" vertsize="900" textheight="900" baseline="765" spacing="360" horzpos="0" horzsize="42520" flags="393216"/></hp:linesegarray></hp:p>"#.to_vec();
        let mut section = Section::default();
        section.paragraphs.push(Paragraph {
            text: "edited predecessor".to_string(),
            line_segs: vec![LineSeg {
                text_start: 0,
                vertical_pos: 0,
                line_height: 900,
                text_height: 900,
                baseline_distance: 765,
                line_spacing: 360,
                column_start: 0,
                segment_width: 42520,
                tag: 393216,
            }],
            ..Default::default()
        });
        section.paragraphs.push(Paragraph {
            text: "regenerated text must not leak".to_string(),
            hwpx_para_xml: Some(raw_para.clone()),
            line_segs: vec![LineSeg {
                text_start: 0,
                vertical_pos: 1260,
                line_height: 900,
                text_height: 900,
                baseline_distance: 765,
                line_spacing: 360,
                column_start: 0,
                segment_width: 42520,
                tag: 393216,
            }],
            ..Default::default()
        });

        let mut doc = Document::default();
        doc.sections.push(section.clone());
        let mut ctx = SerializeContext::collect_from_document(&doc);

        let xml = String::from_utf8(write_section(&section, &doc, 0, &mut ctx).unwrap()).unwrap();
        assert!(xml.contains(std::str::from_utf8(&raw_para).unwrap()));
        assert!(!xml.contains("regenerated text must not leak"));
    }

    #[test]
    fn write_section_preserves_raw_sec_pr_when_paragraph_regenerates() {
        let raw_sec_pr = br#"<hp:secPr id="" textDirection="HORIZONTAL" spaceColumns="1134" tabStop="8000" tabStopVal="4000" tabStopUnit="HWPUNIT" outlineShapeIDRef="1" memoShapeIDRef="0" textVerticalWidthHead="0" masterPageCnt="0"><hp:pagePr landscape="WIDELY" width="59528" height="84186" gutterType="LEFT_ONLY"><hp:margin header="2834" footer="2834" gutter="0" left="5669" right="5669" top="4251" bottom="4252"/></hp:pagePr></hp:secPr>"#.to_vec();
        let mut section = Section {
            hwpx_sec_pr_xml: Some(raw_sec_pr.clone()),
            ..Default::default()
        };
        section.paragraphs.push(Paragraph {
            text: "edited".to_string(),
            ..Default::default()
        });

        let mut doc = Document::default();
        doc.sections.push(section.clone());
        let mut ctx = SerializeContext::collect_from_document(&doc);

        let xml = String::from_utf8(write_section(&section, &doc, 0, &mut ctx).unwrap()).unwrap();
        assert!(xml.contains(std::str::from_utf8(&raw_sec_pr).unwrap()));
        assert!(!xml.contains(r#"left="8504""#));
    }

    #[test]
    fn group_shape_serializes_children_with_draw_text() {
        // <hp:container> 가 빈 껍데기로 직렬화되어 그룹 내부 rect/drawText
        // (글상자 텍스트) 가 편집 후 유실되던 회귀 가드 (19_org_diagnosis).
        use crate::model::control::Control;
        use crate::model::shape::{GroupShape, RectangleShape, ShapeObject, TextBox};
        let mut rect = RectangleShape::default();
        let mut tb = TextBox::default();
        tb.paragraphs.push(Paragraph {
            text: "그룹 안 글상자".to_string(),
            ..Default::default()
        });
        rect.drawing.text_box = Some(tb);
        let group = GroupShape {
            children: vec![ShapeObject::Rectangle(rect)],
            ..Default::default()
        };
        let mut para = Paragraph::default();
        para.controls
            .push(Control::Shape(Box::new(ShapeObject::Group(group))));
        let (doc, section) = make_doc_with_paragraph(para);
        let mut ctx = SerializeContext::collect_from_document(&doc);
        let bytes = write_section(&section, &doc, 0, &mut ctx).unwrap();
        let xml = std::str::from_utf8(&bytes).unwrap();
        assert!(xml.contains("<hp:container"), "{}", &xml[..300.min(xml.len())]);
        assert!(xml.contains("</hp:container>"), "container must not be an empty tag");
        assert!(xml.contains("<hp:rect"), "group child rect must serialize");
        assert!(xml.contains("그룹 안 글상자"), "drawText text must survive");
    }

    #[test]
    fn hp_p_attrs_reflect_para_shape_id_and_style_id() {
        let mut para = Paragraph::default();
        para.para_shape_id = 7;
        para.style_id = 3;
        para.text = "hi".to_string();
        let (doc, section) = make_doc_with_paragraph(para);
        let mut ctx = SerializeContext::collect_from_document(&doc);
        let bytes = write_section(&section, &doc, 0, &mut ctx).unwrap();
        let xml = std::str::from_utf8(&bytes).unwrap();
        assert!(
            xml.contains(r#"paraPrIDRef="7""#),
            "<hp:p> must reflect para_shape_id=7: {}",
            &xml[..200.min(xml.len())]
        );
        assert!(
            xml.contains(r#"styleIDRef="3""#),
            "<hp:p> must reflect style_id=3"
        );
    }

    #[test]
    fn hp_run_reflects_first_char_shape_id() {
        let mut para = Paragraph::default();
        para.text = "hello".to_string();
        para.char_shapes.push(CharShapeRef {
            start_pos: 0,
            char_shape_id: 42,
        });
        let (doc, section) = make_doc_with_paragraph(para);
        let mut ctx = SerializeContext::collect_from_document(&doc);
        let bytes = write_section(&section, &doc, 0, &mut ctx).unwrap();
        let xml = std::str::from_utf8(&bytes).unwrap();
        assert!(
            xml.contains(r#"<hp:run charPrIDRef="42"><hp:t>hello</hp:t>"#),
            "first run must use char_shape_id 42, xml excerpt around <hp:t>: {:?}",
            xml.find("<hp:t>")
                .map(|i| &xml[i.saturating_sub(50)..(i + 50).min(xml.len())])
        );
    }

    #[test]
    fn multi_char_shape_paragraph_emits_multiple_runs() {
        let mut para = Paragraph::default();
        para.text = "hello".to_string();
        para.char_offsets = vec![0, 1, 2, 3, 4];
        para.char_shapes.push(CharShapeRef {
            start_pos: 0,
            char_shape_id: 3,
        });
        para.char_shapes.push(CharShapeRef {
            start_pos: 2,
            char_shape_id: 4,
        });

        let (doc, section) = make_doc_with_paragraph(para);
        let mut ctx = SerializeContext::collect_from_document(&doc);
        let bytes = write_section(&section, &doc, 0, &mut ctx).unwrap();
        let xml = std::str::from_utf8(&bytes).unwrap();

        assert!(
            xml.contains(r#"<hp:run charPrIDRef="3"><hp:t>he</hp:t></hp:run><hp:run charPrIDRef="4"><hp:t>llo</hp:t>"#),
            "char shape transition must split runs, got: {}",
            xml
        );
    }

    #[test]
    fn page_break_paragraph_emits_attr() {
        let mut para = Paragraph::default();
        para.text = "p1".to_string();
        para.column_type = crate::model::paragraph::ColumnBreakType::Page;
        let (doc, section) = make_doc_with_paragraph(para);
        let mut ctx = SerializeContext::collect_from_document(&doc);
        let bytes = write_section(&section, &doc, 0, &mut ctx).unwrap();
        let xml = std::str::from_utf8(&bytes).unwrap();
        assert!(
            xml.contains(r#"pageBreak="1""#),
            "pageBreak must be 1 for Page column_type"
        );
        assert!(xml.contains(r#"columnBreak="0""#));
    }

    #[test]
    fn default_paragraph_keeps_zero_attrs() {
        let mut para = Paragraph::default();
        para.text = "x".to_string();
        let (doc, section) = make_doc_with_paragraph(para);
        let mut ctx = SerializeContext::collect_from_document(&doc);
        let bytes = write_section(&section, &doc, 0, &mut ctx).unwrap();
        let xml = std::str::from_utf8(&bytes).unwrap();
        assert!(xml.contains(r#"paraPrIDRef="0""#));
        assert!(xml.contains(r#"styleIDRef="0""#));
        // char_shapes 가 비어있으면 fallback 0
        assert!(xml.contains(r#"<hp:run charPrIDRef="0">"#));
    }

    #[test]
    fn additional_paragraphs_use_their_own_char_shape() {
        let mut p1 = Paragraph::default();
        p1.text = "first".to_string();
        p1.char_shapes.push(CharShapeRef {
            start_pos: 0,
            char_shape_id: 5,
        });
        let mut p2 = Paragraph::default();
        p2.text = "second".to_string();
        p2.para_shape_id = 2;
        p2.char_shapes.push(CharShapeRef {
            start_pos: 0,
            char_shape_id: 6,
        });
        let mut section = Section::default();
        section.paragraphs.push(p1);
        section.paragraphs.push(p2);
        let mut doc = Document::default();
        doc.sections.push(section.clone());
        let mut ctx = SerializeContext::collect_from_document(&doc);
        let xml = String::from_utf8(write_section(&section, &doc, 0, &mut ctx).unwrap()).unwrap();
        // 두 번째 문단: paraPrIDRef=2, charPrIDRef=6
        assert!(xml.contains(r#"paraPrIDRef="2""#));
        assert!(
            xml.matches(r#"charPrIDRef="6""#).count() >= 1,
            "second paragraph must emit charPrIDRef=6"
        );
    }

    // ---------- #177 Stage 2: IR 기반 lineseg 출력 ----------

    use crate::model::paragraph::LineSeg;

    #[test]
    fn task177_lineseg_reflects_ir_values() {
        // IR에 담긴 lineseg 값이 XML 속성에 그대로 반영되는지 확인.
        let mut para = Paragraph::default();
        para.text = "hello".to_string();
        para.line_segs.push(LineSeg {
            text_start: 0,
            vertical_pos: 5000,
            line_height: 1200,
            text_height: 1100,
            baseline_distance: 900,
            line_spacing: 700,
            column_start: 100,
            segment_width: 50000,
            tag: 999,
        });
        let (doc, section) = make_doc_with_paragraph(para);
        let mut ctx = SerializeContext::collect_from_document(&doc);
        let xml = String::from_utf8(write_section(&section, &doc, 0, &mut ctx).unwrap()).unwrap();
        assert!(xml.contains(r#"<hp:lineseg textpos="0" vertpos="5000" vertsize="1200" textheight="1100" baseline="900" spacing="700" horzpos="100" horzsize="50000" flags="999"/>"#),
            "lineseg must reflect IR values exactly, got XML: {}",
            &xml[xml.find("<hp:lineseg").unwrap_or(0)..(xml.find("<hp:lineseg").unwrap_or(0) + 200).min(xml.len())]);
    }

    #[test]
    fn task177_multiple_linesegs_preserved_in_order() {
        let mut para = Paragraph::default();
        para.text = "three\nlines\nhere".to_string();
        for (i, (tp, vp, lh)) in [(0u32, 0i32, 1000), (6, 1500, 1200), (12, 3100, 1100)]
            .iter()
            .enumerate()
        {
            let _ = i;
            para.line_segs.push(LineSeg {
                text_start: *tp,
                vertical_pos: *vp,
                line_height: *lh,
                text_height: *lh,
                baseline_distance: 850,
                line_spacing: 600,
                column_start: 0,
                segment_width: 42520,
                tag: 393216,
            });
        }
        let (doc, section) = make_doc_with_paragraph(para);
        let mut ctx = SerializeContext::collect_from_document(&doc);
        let xml = String::from_utf8(write_section(&section, &doc, 0, &mut ctx).unwrap()).unwrap();
        // 3개 lineseg 모두 출력되고 각각의 vertsize 값이 IR 값과 일치
        assert_eq!(xml.matches("<hp:lineseg ").count(), 3);
        assert!(xml.contains(r#"textpos="0" vertpos="0" vertsize="1000""#));
        assert!(xml.contains(r#"textpos="6" vertpos="1500" vertsize="1200""#));
        assert!(xml.contains(r#"textpos="12" vertpos="3100" vertsize="1100""#));
    }

    #[test]
    fn task177_fallback_used_when_ir_empty() {
        // IR 의 line_segs 가 비어있으면 fallback 경로로 정적 값 출력.
        let mut para = Paragraph::default();
        para.text = "a\nb".to_string(); // 소프트브레이크 1개 → fallback 은 lineseg 2개 생성
        let (doc, section) = make_doc_with_paragraph(para);
        let mut ctx = SerializeContext::collect_from_document(&doc);
        let xml = String::from_utf8(write_section(&section, &doc, 0, &mut ctx).unwrap()).unwrap();
        // 정적 fallback: vertsize=1000, textheight=1000, baseline=850, spacing=600
        assert!(xml.contains(r#"vertsize="1000""#));
        assert!(xml.contains(r#"baseline="850""#));
    }

    #[test]
    fn task177_ir_lineseg_takes_precedence_over_text() {
        // text 의 \n 개수가 2개(lineseg 3개 기대)이지만 IR의 line_segs 는 1개만 있음.
        // IR 기반 출력이 우선 — 1개만 출력돼야 함.
        let mut para = Paragraph::default();
        para.text = "a\nb\nc".to_string(); // 3줄
        para.line_segs.push(LineSeg {
            text_start: 0,
            vertical_pos: 0,
            line_height: 2000, // IR 값
            text_height: 2000,
            baseline_distance: 1700,
            line_spacing: 300,
            column_start: 0,
            segment_width: 40000,
            tag: 0,
        });
        let (doc, section) = make_doc_with_paragraph(para);
        let mut ctx = SerializeContext::collect_from_document(&doc);
        let xml = String::from_utf8(write_section(&section, &doc, 0, &mut ctx).unwrap()).unwrap();
        // IR 에 1개만 있으므로 lineseg 도 1개만 출력 (rhwp 는 원본 보존)
        assert_eq!(xml.matches("<hp:lineseg ").count(), 1);
        assert!(
            xml.contains(r#"vertsize="2000""#),
            "IR value 2000 must be used, not fallback 1000"
        );
    }
}
