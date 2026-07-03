//! 필드 컨트롤 직렬화 — Bookmark, Hyperlink, Field (fieldBegin/End) 뼈대.
//!
//! Stage 5 (#182): 인라인 필드 컨트롤의 `<hp:fieldBegin>` / `<hp:fieldEnd>` 및 `<hp:bookmark>`
//! 의 XML 뼈대를 제공한다. 각주(`<hp:fn>`) / 미주(`<hp:en>`) 는 향후 이슈에서 확장.
//!
//! ## 범위 한정
//!
//! - Stage 5 에서는 **필드 뼈대 출력** 기능만 제공 (section.rs dispatcher 연결은 #186).
//! - 누름틀(ClickHere), 날짜, 메일머지 등 복잡한 필드는 `<hp:fieldBegin type="...">` 의
//!   type 속성만 구분하고 내부 command 직렬화는 #186 에서 확장.

#![allow(dead_code)]

use std::io::Write;

use quick_xml::Writer;

use crate::model::control::{Bookmark, Field, FieldType, Hyperlink};

use super::utils::{empty_tag, end_tag, start_tag, start_tag_attrs};
use super::SerializeError;

// =====================================================================
// <hp:bookmark>
// =====================================================================

pub fn write_bookmark<W: Write>(w: &mut Writer<W>, bm: &Bookmark) -> Result<(), SerializeError> {
    empty_tag(w, "hp:bookmark", &[("name", &bm.name)])
}

// =====================================================================
// <hp:fieldBegin> / <hp:fieldEnd>
// =====================================================================

/// `<hp:fieldBegin>` — 필드 시작 마커.
///
/// HWPX 필드는 텍스트 흐름 안에서 `<hp:fieldBegin>` ~ 텍스트 ~ `<hp:fieldEnd>` 쌍으로 표현된다.
///
/// MEMO 필드는 본문이 아닌 `<hp:subList>` 로 메모 내용 문단을 품는다 — 이전에는
/// 무조건 empty_tag 만 출력해 편집 후 재직렬화에서 메모 전체(파라미터 + 내용)가
/// 유실됐다 (20_overseas_training 메모 4건 −552자, 19_org_diagnosis Ⅳ 배너 메모).
pub fn write_field_begin<W: Write>(w: &mut Writer<W>, field: &Field) -> Result<(), SerializeError> {
    let id_str = field.field_id.to_string();
    let ft = field_type_str(field.field_type);
    let attrs = [
        ("id", id_str.as_str()),
        ("type", ft),
        ("name", field.ctrl_data_name.as_deref().unwrap_or("")),
        ("editable", bool01(field.is_editable_in_form())),
    ];
    let has_command = !field.command.is_empty();
    let has_memo = !field.memo_paragraphs.is_empty();
    if !has_command && !has_memo {
        return empty_tag(w, "hp:fieldBegin", &attrs);
    }
    start_tag_attrs(w, "hp:fieldBegin", &attrs)?;
    // 최소 파라미터 셋 — Command(원본 저장분) + 메모 Number. 원본의 나머지
    // 파라미터(Author/CreateDateTime 등)는 모델이 보존하지 않아 복원 불가.
    let is_memo = matches!(field.field_type, FieldType::Memo);
    let n_params = (has_command as usize) + (is_memo as usize);
    if n_params > 0 {
        let cnt = n_params.to_string();
        start_tag_attrs(w, "hp:parameters", &[("cnt", &cnt), ("name", "")])?;
        if has_command {
            start_tag_attrs(w, "hp:stringParam", &[("name", "Command")])?;
            write_text(w, &field.command)?;
            end_tag(w, "hp:stringParam")?;
        }
        if is_memo {
            let num = field.memo_index.to_string();
            start_tag_attrs(w, "hp:integerParam", &[("name", "Number")])?;
            write_text(w, &num)?;
            end_tag(w, "hp:integerParam")?;
        }
        end_tag(w, "hp:parameters")?;
    }
    if has_memo {
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
        for (idx, p) in field.memo_paragraphs.iter().enumerate() {
            write_sublist_paragraph(w, p, idx)?;
        }
        end_tag(w, "hp:subList")?;
    }
    end_tag(w, "hp:fieldBegin")
}

fn write_text<W: Write>(w: &mut Writer<W>, s: &str) -> Result<(), SerializeError> {
    w.write_event(quick_xml::events::Event::Text(
        quick_xml::events::BytesText::new(s),
    ))
    .map_err(|e| SerializeError::XmlError(format!("field text: {e}")))
}

/// 필드 subList 내부 문단 — shape.rs write_draw_text_paragraph 와 같은 최소 형태.
fn write_sublist_paragraph<W: Write>(
    w: &mut Writer<W>,
    p: &crate::model::paragraph::Paragraph,
    idx: usize,
) -> Result<(), SerializeError> {
    let id = idx.to_string();
    let ps_id = p.para_shape_id.to_string();
    let st_id = p.style_id.to_string();
    start_tag_attrs(
        w,
        "hp:p",
        &[
            ("id", &id),
            ("paraPrIDRef", &ps_id),
            ("styleIDRef", &st_id),
            ("pageBreak", "0"),
            ("columnBreak", "0"),
            ("merged", "0"),
        ],
    )?;
    let cs = p.char_shapes.first().map(|r| r.char_shape_id).unwrap_or(0);
    let cs_str = cs.to_string();
    start_tag_attrs(w, "hp:run", &[("charPrIDRef", &cs_str)])?;
    start_tag(w, "hp:t")?;
    write_text(w, &p.text)?;
    end_tag(w, "hp:t")?;
    end_tag(w, "hp:run")?;
    start_tag(w, "hp:linesegarray")?;
    empty_tag(
        w,
        "hp:lineseg",
        &[
            ("textpos", "0"),
            ("vertpos", "0"),
            ("vertsize", "1000"),
            ("textheight", "1000"),
            ("baseline", "850"),
            ("spacing", "600"),
            ("horzpos", "0"),
            ("horzsize", "42520"),
            ("flags", "393216"),
        ],
    )?;
    end_tag(w, "hp:linesegarray")?;
    end_tag(w, "hp:p")?;
    Ok(())
}

/// `<hp:fieldEnd>` — 필드 끝 마커.
pub fn write_field_end<W: Write>(w: &mut Writer<W>, field_id: u32) -> Result<(), SerializeError> {
    let id_str = field_id.to_string();
    empty_tag(w, "hp:fieldEnd", &[("beginIDRef", &id_str)])
}

// =====================================================================
// 하이퍼링크 (필드의 특수형) — <hp:fieldBegin type="HYPERLINK"> 변형
// =====================================================================

pub fn write_hyperlink_begin<W: Write>(
    w: &mut Writer<W>,
    link: &Hyperlink,
    field_id: u32,
) -> Result<(), SerializeError> {
    // command 에 URL 이 들어감. 실제 한컴은 별도 command 파싱 필요.
    let id_str = field_id.to_string();
    let url = &link.url;
    empty_tag(
        w,
        "hp:fieldBegin",
        &[
            ("id", &id_str),
            ("type", "HYPERLINK"),
            ("name", ""),
            ("editable", "0"),
            ("command", url),
        ],
    )
}

// =====================================================================
// 각주 / 미주 뼈대 — <hp:fn> / <hp:en>
// =====================================================================

/// `<hp:fn>` 각주 뼈대 (내부 문단 직렬화는 #186 에서 연결).
pub fn write_footnote_open<W: Write>(w: &mut Writer<W>, number: u16) -> Result<(), SerializeError> {
    let n = number.to_string();
    start_tag(w, "hp:fn")?;
    empty_tag(w, "hp:autoNum", &[("num", &n)])?;
    Ok(())
}

pub fn write_footnote_close<W: Write>(w: &mut Writer<W>) -> Result<(), SerializeError> {
    end_tag(w, "hp:fn")
}

pub fn write_endnote_open<W: Write>(w: &mut Writer<W>, number: u16) -> Result<(), SerializeError> {
    let n = number.to_string();
    start_tag(w, "hp:en")?;
    empty_tag(w, "hp:autoNum", &[("num", &n)])?;
    Ok(())
}

pub fn write_endnote_close<W: Write>(w: &mut Writer<W>) -> Result<(), SerializeError> {
    end_tag(w, "hp:en")
}

// =====================================================================
// 헬퍼
// =====================================================================

fn bool01(b: bool) -> &'static str {
    if b {
        "1"
    } else {
        "0"
    }
}

fn field_type_str(t: FieldType) -> &'static str {
    use FieldType::*;
    match t {
        Unknown => "UNKNOWN",
        Date => "DATE",
        DocDate => "DOCDATE",
        Path => "PATH",
        Bookmark => "BOOKMARK",
        MailMerge => "MAILMERGE",
        CrossRef => "CROSSREF",
        Formula => "FORMULA",
        ClickHere => "CLICKHERE",
        Summary => "SUMMARY",
        UserInfo => "USERINFO",
        Hyperlink => "HYPERLINK",
        Memo => "MEMO",
        PrivateInfoSecurity => "PRIVATE_INFO",
        TableOfContents => "TOC",
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::control::{Bookmark, Field, FieldType, Hyperlink};

    fn to_string<F: FnOnce(&mut Writer<Vec<u8>>) -> Result<(), SerializeError>>(f: F) -> String {
        let mut w: Writer<Vec<u8>> = Writer::new(Vec::new());
        f(&mut w).expect("write");
        String::from_utf8(w.into_inner()).unwrap()
    }

    #[test]
    fn bookmark_emits_name() {
        let bm = Bookmark {
            name: "chapter1".to_string(),
        };
        let xml = to_string(|w| write_bookmark(w, &bm));
        assert!(xml.contains(r#"<hp:bookmark name="chapter1"/>"#), "{}", xml);
    }

    #[test]
    fn field_begin_emits_type_attr() {
        let mut f = Field::default();
        f.field_type = FieldType::ClickHere;
        f.field_id = 42;
        let xml = to_string(|w| write_field_begin(w, &f));
        assert!(xml.contains(r#"id="42""#));
        assert!(xml.contains(r#"type="CLICKHERE""#));
    }

    #[test]
    fn field_end_references_begin_id() {
        let xml = to_string(|w| write_field_end(w, 42));
        assert!(xml.contains(r#"<hp:fieldEnd beginIDRef="42"/>"#));
    }

    #[test]
    fn memo_field_preserves_content_paragraphs() {
        // 편집 후 재직렬화에서 MEMO subList 가 통째로 유실되던 회귀 가드
        // (20_overseas_training 메모 4건, 19_org_diagnosis Ⅳ 배너 메모).
        use crate::model::paragraph::Paragraph;
        let mut f = Field::default();
        f.field_type = FieldType::Memo;
        f.field_id = 7;
        f.memo_index = 3;
        f.command = "MEMO/65535/1/x/y/moe/\\;;".to_string();
        f.memo_paragraphs.push(Paragraph {
            text: "기획과, 총무과".to_string(),
            ..Default::default()
        });
        let xml = to_string(|w| write_field_begin(w, &f));
        assert!(xml.contains(r#"type="MEMO""#), "{}", xml);
        assert!(xml.contains("기획과, 총무과"), "memo text must survive: {}", xml);
        assert!(xml.contains(r#"<hp:stringParam name="Command">"#), "{}", xml);
        assert!(xml.contains(r#"<hp:integerParam name="Number">3"#), "{}", xml);
        assert!(xml.contains("</hp:fieldBegin>"), "{}", xml);
    }

    #[test]
    fn plain_field_still_emits_empty_tag() {
        let mut f = Field::default();
        f.field_type = FieldType::Bookmark;
        f.field_id = 9;
        let xml = to_string(|w| write_field_begin(w, &f));
        assert!(xml.contains(r#"<hp:fieldBegin"#) && xml.ends_with("/>"), "{}", xml);
    }

    #[test]
    fn hyperlink_begin_uses_url_command() {
        let link = Hyperlink {
            url: "https://example.com".to_string(),
            text: "".to_string(),
        };
        let xml = to_string(|w| write_hyperlink_begin(w, &link, 7));
        assert!(xml.contains(r#"type="HYPERLINK""#));
        assert!(xml.contains(r#"command="https://example.com""#));
    }

    #[test]
    fn footnote_emits_autoNum() {
        let xml = to_string(|w| {
            write_footnote_open(w, 3)?;
            write_footnote_close(w)
        });
        assert!(xml.contains("<hp:fn>"));
        assert!(xml.contains(r#"<hp:autoNum num="3"/>"#));
        assert!(xml.contains("</hp:fn>"));
    }

    #[test]
    fn field_type_str_covers_main_variants() {
        assert_eq!(field_type_str(FieldType::Hyperlink), "HYPERLINK");
        assert_eq!(field_type_str(FieldType::Bookmark), "BOOKMARK");
        assert_eq!(field_type_str(FieldType::Date), "DATE");
        assert_eq!(field_type_str(FieldType::TableOfContents), "TOC");
    }
}
