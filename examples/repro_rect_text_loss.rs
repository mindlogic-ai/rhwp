//! Repro: any edit → export loses hp:rect/hp:drawText content (Ⅳ banner)
//! in 19_org_diagnosis.hwpx. No-edit export keeps it (raw pass-through).
//!
//!   cargo run --example repro_rect_text_loss -- <입력.hwpx>

use std::env;
use std::fs;

use rhwp::document_core::DocumentCore;

fn has_banner(bytes: &[u8], label: &str) {
    let cursor = std::io::Cursor::new(bytes);
    let mut zip = zip::ZipArchive::new(cursor).expect("zip");
    let mut xml = String::new();
    {
        use std::io::Read;
        let mut f = zip.by_name("Contents/section0.xml").expect("section0");
        f.read_to_string(&mut xml).expect("utf8");
    }
    println!(
        "{label}: Ⅳ={} 기획과={} 인력효율화={}",
        xml.contains('Ⅳ'),
        xml.contains("기획과, 총무과"),
        xml.contains("인력 효율화 방안"),
    );
}

fn visit(shape: &rhwp::model::shape::ShapeObject, pi: usize, label: &str, n_rects: &mut u32, n_tb_chars: &mut usize) {
    use rhwp::model::shape::ShapeObject;
    match shape {
        ShapeObject::Rectangle(r) => {
            *n_rects += 1;
            let chars: usize = r
                .drawing
                .text_box
                .as_ref()
                .map(|tb| tb.paragraphs.iter().map(|pp| pp.text.chars().count()).sum())
                .unwrap_or(0);
            *n_tb_chars += chars;
            if chars > 0 {
                let first: String = r.drawing.text_box.as_ref().unwrap().paragraphs[0]
                    .text
                    .chars()
                    .take(20)
                    .collect();
                println!("  {label} p{pi} rect tb_chars={chars} first={first:?}");
            }
        }
        ShapeObject::Group(g) => {
            for ch in &g.children {
                visit(ch, pi, label, n_rects, n_tb_chars);
            }
        }
        _ => {}
    }
}

fn dump_model(core: &DocumentCore, label: &str) {
    use rhwp::model::control::Control;
    let sec = &core.document().sections[0];
    let mut n_rects = 0;
    let mut n_tb_chars = 0usize;
    for (pi, p) in sec.paragraphs.iter().enumerate() {
        for c in &p.controls {
            if let Control::Shape(shape) = c {
                visit(shape, pi, label, &mut n_rects, &mut n_tb_chars);
            }
        }
    }
    println!("{label}: paragraphs={} rects={} tb_chars_total={}", sec.paragraphs.len(), n_rects, n_tb_chars);
}

fn main() {
    let path = env::args().nth(1).expect("usage: repro_rect_text_loss <input.hwpx>");
    let data = fs::read(&path).expect("read");

    // no-edit round trip
    let core = DocumentCore::from_bytes(&data).expect("parse");
    dump_model(&core, "parsed  ");
    let out = core.export_hwpx_native().expect("export");
    has_banner(&out, "no-edit ");

    // trivial edit then export
    let mut core = DocumentCore::from_bytes(&data).expect("parse");
    core.insert_text_native(0, 0, 0, "probe ").expect("insert");
    dump_model(&core, "edited  ");
    let out = core.export_hwpx_native().expect("export");
    has_banner(&out, "edited  ");
}
