//! Compare the CharOverlap host paragraph IR between two HWPX files
//! (source vs edited export) to find why reopen drops the compose glyphs.
//!
//!   cargo run --release --example probe_compose_ir -- <a.hwpx> <b.hwpx>

use rhwp::document_core::DocumentCore;
use rhwp::model::control::Control;

fn dump(path: &str) {
    let data = std::fs::read(path).expect("read");
    let core = DocumentCore::from_bytes(&data).expect("parse");
    for (si, sec) in core.document().sections.iter().enumerate() {
        for (pi, para) in sec.paragraphs.iter().enumerate() {
            for ctrl in &para.controls {
                if let Control::Table(t) = ctrl {
                    for cell in &t.cells {
                        for (cpi, cp) in cell.paragraphs.iter().enumerate() {
                            for c in &cp.controls {
                                if let Control::CharOverlap(co) = c {
                                    println!(
                                        "{path}: s{si} p{pi} cell r{}c{} cp{cpi} chars={:?} border={} exp={} ids={} | text={:?} char_count={} offsets={:?} segs={} char_shapes={:?}",
                                        cell.row, cell.col, co.chars, co.border_type, co.expansion,
                                        co.char_shape_ids.len(),
                                        cp.text, cp.char_count, cp.char_offsets,
                                        cp.line_segs.len(),
                                        cp.char_shapes.iter().map(|r| (r.start_pos, r.char_shape_id)).collect::<Vec<_>>(),
                                    );
                                }
                            }
                        }
                    }
                }
            }
            for c in &para.controls {
                if let Control::CharOverlap(co) = c {
                    println!(
                        "{path}: s{si} p{pi} BODY chars={:?} text={:?} char_count={} offsets={:?}",
                        co.chars, para.text, para.char_count, para.char_offsets
                    );
                }
            }
        }
    }
}

fn main() {
    for p in std::env::args().skip(1) {
        dump(&p);
    }
}
