//! Probe: edit a cell inside the secPr-hosting first paragraph and check the
//! re-serialized export keeps pageNum/newNum/autoNum/pageHiding controls.
//!
//!   cargo run --release --example probe_secctrl_survival -- <doc.hwpx> [...]

use std::env;
use std::fs;

use rhwp::document_core::DocumentCore;
use rhwp::model::control::Control;

fn count(hay: &str, needle: &str) -> usize {
    hay.matches(needle).count()
}

fn section_xml(bytes: &[u8]) -> String {
    let cursor = std::io::Cursor::new(bytes);
    let mut zip = zip::ZipArchive::new(cursor).expect("zip");
    let names: Vec<String> = (0..zip.len())
        .map(|i| zip.by_index(i).unwrap().name().to_string())
        .filter(|n| n.starts_with("Contents/section") && n.ends_with(".xml"))
        .collect();
    let mut out = String::new();
    for n in names {
        use std::io::Read;
        let mut xml = String::new();
        zip.by_name(&n).unwrap().read_to_string(&mut xml).unwrap();
        out.push_str(&xml);
    }
    out
}

fn main() {
    for path in env::args().skip(1) {
        let data = fs::read(&path).expect("read");
        let mut core = match DocumentCore::from_bytes(&data) {
            Ok(c) => c,
            Err(e) => {
                println!("{path}: PARSE ERR {e:?}");
                continue;
            }
        };
        // find first table control in section 0 paragraph 0 and its first
        // non-empty cell paragraph
        let mut target: Option<(usize, usize)> = None; // (ctrl_idx, cell_idx)
        {
            let para = &core.document().sections[0].paragraphs[0];
            for (ci, ctrl) in para.controls.iter().enumerate() {
                if let Control::Table(t) = ctrl {
                    for (xi, cell) in t.cells.iter().enumerate() {
                        if cell.paragraphs.iter().any(|p| !p.text.is_empty()) {
                            target = Some((ci, xi));
                            break;
                        }
                    }
                    if target.is_some() {
                        break;
                    }
                }
            }
        }
        let Some((ctrl_idx, cell_idx)) = target else {
            println!("{path}: NO p0 table cell — skip");
            continue;
        };
        let cp = vec![(ctrl_idx, cell_idx, 0usize)];
        core.insert_text_in_cell_by_path(0, 0, &cp, 0, "probe ")
            .expect("edit");
        let out = core.export_hwpx_native().expect("export");

        let src = section_xml(&data);
        let edited = section_xml(&out);
        let keys = ["<hp:pageNum ", "<hp:newNum ", "<hp:autoNum ", "<hp:pageHiding "];
        let mut ok = true;
        let mut detail = String::new();
        for k in keys {
            let (a, b) = (count(&src, k), count(&edited, k));
            if b < a {
                ok = false;
            }
            detail.push_str(&format!("{}={}→{} ", k.trim_start_matches("<hp:").trim(), a, b));
        }
        println!("{}: {} {}", path, if ok { "OK" } else { "LOST" }, detail);
    }
}
