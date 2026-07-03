//! Scan: for each input doc, compare <hp:t> char counts between the no-edit
//! export (raw pass-through) and an edited export (forced re-serialize).
//! Any deficit beyond the inserted text = content destroyed by edit-path
//! re-serialization.
//!
//!   cargo run --release --example edit_textloss_scan -- <doc.hwpx> [...]

use std::env;
use std::fs;

use rhwp::document_core::DocumentCore;

fn t_chars(bytes: &[u8]) -> usize {
    let cursor = std::io::Cursor::new(bytes);
    let mut zip = zip::ZipArchive::new(cursor).expect("zip");
    let mut total = 0usize;
    let names: Vec<String> = (0..zip.len())
        .map(|i| zip.by_index(i).unwrap().name().to_string())
        .filter(|n| n.starts_with("Contents/section") && n.ends_with(".xml"))
        .collect();
    for n in names {
        use std::io::Read;
        let mut xml = String::new();
        zip.by_name(&n).unwrap().read_to_string(&mut xml).unwrap();
        let mut rest = xml.as_str();
        while let Some(i) = rest.find("<hp:t>") {
            rest = &rest[i + 6..];
            if let Some(j) = rest.find("</hp:t>") {
                total += rest[..j].chars().count();
                rest = &rest[j..];
            } else {
                break;
            }
        }
    }
    total
}

fn main() {
    const INS: &str = "probe ";
    for path in env::args().skip(1) {
        let data = match fs::read(&path) {
            Ok(d) => d,
            Err(e) => { println!("{path}: READ ERR {e}"); continue; }
        };
        let core = match DocumentCore::from_bytes(&data) {
            Ok(c) => c,
            Err(e) => { println!("{path}: PARSE ERR {e:?}"); continue; }
        };
        let dump = env::var("DUMP_DIR").ok();
        let stem = std::path::Path::new(&path)
            .file_stem()
            .map(|s| s.to_string_lossy().to_string())
            .unwrap_or_else(|| "doc".into());
        let base_bytes = match core.export_hwpx_native() { Ok(b) => b, Err(e) => { println!("{path}: EXPORT ERR {e:?}"); continue; } };
        if let Some(ref d) = dump { let _ = fs::write(format!("{d}/{stem}.base.hwpx"), &base_bytes); }
        let base = t_chars(&base_bytes);

        let mut core = DocumentCore::from_bytes(&data).expect("parse2");
        if core.insert_text_native(0, 0, 0, INS).is_err() {
            println!("{path}: EDIT ERR");
            continue;
        }
        match core.export_hwpx_native() {
            Ok(b) => {
                if let Some(ref d) = dump { let _ = fs::write(format!("{d}/{stem}.edited.hwpx"), &b); }
                let after = t_chars(&b);
                let expected = base + INS.chars().count();
                let delta = after as i64 - expected as i64;
                let flag = if delta < 0 { "LOSS" } else { "ok" };
                println!("{path}: base={base} after={after} delta_vs_expected={delta} {flag}");
            }
            Err(e) => println!("{path}: EXPORT2 ERR {e:?}"),
        }
    }
}
