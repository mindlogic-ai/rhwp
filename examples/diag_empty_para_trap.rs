// Diagnose the insertFootnote/insertEquation 'unreachable' trap on form_19's
// empty body paragraph by emulating the agent-bridge call sequence natively.
use rhwp::model::control::Control;
use rhwp::wasm_api::HwpDocument;
use std::panic::{catch_unwind, AssertUnwindSafe};

fn load() -> HwpDocument {
    let bytes = std::fs::read("samples/form_19_empty_para.hwpx").expect("read fixture");
    HwpDocument::from_bytes(&bytes).expect("parse")
}

fn step(name: &str, f: impl FnOnce()) {
    match catch_unwind(AssertUnwindSafe(f)) {
        Ok(()) => println!("  ok    {name}"),
        Err(e) => {
            let msg = e
                .downcast_ref::<String>()
                .cloned()
                .or_else(|| e.downcast_ref::<&str>().map(|s| s.to_string()))
                .unwrap_or_else(|| "<non-string panic>".into());
            println!("  PANIC {name}: {msg}");
        }
    }
}

fn main() {
    let doc = load();
    {
        let document = doc.document();
        let section = &document.sections[0];
        println!("paragraphs: {}", section.paragraphs.len());
        for (pi, para) in section.paragraphs.iter().enumerate().take(12) {
            let has_table = para.controls.iter().any(|c| matches!(c, Control::Table(_)));
            let kinds: Vec<&str> = para
                .controls
                .iter()
                .map(|c| match c {
                    Control::Table(_) => "Table",
                    Control::Shape(_) => "Shape",
                    Control::Footnote(_) => "Footnote",
                    Control::Bookmark(_) => "Bookmark",
                    Control::AutoNumber(_) => "AutoNumber",
                    _ => "Other",
                })
                .collect();
            println!(
                "  p{pi}: table={has_table} text={:?} chars(text)={} char_count={} offsets={} controls={:?} linesegs={}",
                para.text.chars().take(30).collect::<String>(),
                para.text.chars().count(),
                para.char_count,
                para.char_offsets.len(),
                kinds,
                para.line_segs.len(),
            );
        }
    }

    // The probe's P_TEXT actually resolves to an empty-text TABLE-HOSTING
    // paragraph: both form_19 paragraphs host tables, the probe splits p0 to
    // manufacture a text para at p1, and P_TEXT = s0:p2 = the shifted
    // original p1 (table host, text="", char_offsets=[]).
    let p_text = 1usize; // pristine-doc equivalent: the second table para
    println!("P_TEXT equivalent = s0:p{p_text} (table host, empty text)");

    println!("--- footnote sequence (bridge emulation, offset 0, with inner text) ---");
    let mut d = load();
    step("beginBatch", || {
        d.begin_batch().unwrap();
    });
    let mut ctrl_idx = 0usize;
    step("insertFootnote(sec=0, para=P_TEXT, offset=0)", || {
        let r = d.insert_footnote_native(0, p_text, 0).expect("insert");
        println!("        -> {r}");
        ctrl_idx = r
            .split("\"controlIdx\":")
            .nth(1)
            .and_then(|s| s.split([',', '}']).next())
            .and_then(|s| s.parse().ok())
            .unwrap_or(0);
    });
    step("insertTextInFootnote(..., inner=0, off=0)", || {
        let r = d
            .insert_text_in_footnote_native(0, p_text, ctrl_idx, 0, 0, "프로브 각주")
            .expect("insert text in footnote");
        println!("        -> {r}");
    });
    step("endBatch", || {
        d.end_batch().unwrap();
    });
    step("render all pages", || {
        for pg in 0..d.page_count() {
            d.render_page_svg(pg).unwrap();
        }
    });
    step("snapshot save+restore", || {
        let id = d.save_snapshot();
        d.restore_snapshot(id).unwrap();
    });

    println!("--- equation sequence (offset 0) ---");
    let mut d2 = load();
    step("beginBatch", || {
        d2.begin_batch().unwrap();
    });
    step("insertEquation(sec=0, para=P_TEXT, offset=0)", || {
        let r = d2
            .insert_equation_native(0, p_text, 0, "a^2+b^2=c^2", 1200, 0)
            .expect("insert equation");
        println!("        -> {r}");
    });
    step("endBatch", || {
        d2.end_batch().unwrap();
    });
    step("render all pages", || {
        for pg in 0..d2.page_count() {
            d2.render_page_svg(pg).unwrap();
        }
    });
    step("snapshot save+restore", || {
        let id = d2.save_snapshot();
        d2.restore_snapshot(id).unwrap();
    });

    println!("--- exact probe emulation: split p0, text at p1, footnote at p2 off 0 ---");
    let mut d3 = load();
    step("splitParagraph(p0 at end) + insertText(p1)", || {
        let len = {
            let para = &d3.document().sections[0].paragraphs[0];
            para.text.chars().count() as u32
        };
        d3.split_paragraph(0, 0, len).unwrap();
        d3.insert_text(0, 1, 0, "프로브 텍스트 문단").unwrap();
    });
    step("beginBatch", || {
        d3.begin_batch().unwrap();
    });
    let mut ctrl_idx3 = 0usize;
    step("insertFootnote(sec=0, para=2, offset=0)", || {
        let r = d3.insert_footnote_native(0, 2, 0).expect("insert");
        println!("        -> {r}");
        ctrl_idx3 = r
            .split("\"controlIdx\":")
            .nth(1)
            .and_then(|s| s.split([',', '}']).next())
            .and_then(|s| s.parse().ok())
            .unwrap_or(0);
    });
    step("insertTextInFootnote(..., inner=0, off=0)", || {
        let r = d3
            .insert_text_in_footnote_native(0, 2, ctrl_idx3, 0, 0, "프로브 각주")
            .expect("insert text in footnote");
        println!("        -> {r}");
    });
    step("endBatch", || {
        d3.end_batch().unwrap();
    });
    step("render all pages", || {
        for pg in 0..d3.page_count() {
            d3.render_page_svg(pg).unwrap();
        }
    });
    step("snapshot save+restore", || {
        let id = d3.save_snapshot();
        d3.restore_snapshot(id).unwrap();
    });

    println!("done");
}
