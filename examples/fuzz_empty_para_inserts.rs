// Corpus-wide regression fuzz for the ctrl_data_records trap family:
// for every .hwpx in samples/corpus_tmp/, insert a footnote and an equation
// at offset 0 of each of the first paragraphs (covers p0 sectiondef hosts,
// table hosts, and plain text paras), then render every page and round-trip
// a snapshot. Any panic = the 'unreachable' WASM trap shape. Exits non-zero
// if anything fails.
use rhwp::wasm_api::HwpDocument;
use std::panic::{catch_unwind, AssertUnwindSafe};

fn main() {
    let dir = "samples/corpus_tmp";
    let mut files: Vec<_> = std::fs::read_dir(dir)
        .expect("read corpus dir")
        .filter_map(|e| e.ok())
        .map(|e| e.path())
        .filter(|p| p.extension().map(|x| x == "hwpx").unwrap_or(false))
        .collect();
    files.sort();
    assert!(!files.is_empty(), "no corpus files in {dir}");

    let mut failures = 0usize;
    let mut checks = 0usize;
    for path in &files {
        let name = path.file_name().unwrap().to_string_lossy().to_string();
        let bytes = match std::fs::read(path) {
            Ok(b) => b,
            Err(e) => {
                println!("FAIL read {name}: {e}");
                failures += 1;
                continue;
            }
        };
        let para_count = match catch_unwind(AssertUnwindSafe(|| {
            HwpDocument::from_bytes(&bytes)
                .map(|d| d.document().sections[0].paragraphs.len())
        })) {
            Ok(Ok(n)) => n,
            Ok(Err(e)) => {
                println!("SKIP parse {name}: {e:?}");
                continue;
            }
            Err(_) => {
                println!("FAIL parse-panic {name}");
                failures += 1;
                continue;
            }
        };

        for para in 0..para_count.min(4) {
            for op in ["footnote", "equation"] {
                checks += 1;
                let bytes = bytes.clone();
                let ok = catch_unwind(AssertUnwindSafe(|| {
                    let mut doc = HwpDocument::from_bytes(&bytes).unwrap();
                    let res = match op {
                        "footnote" => doc.insert_footnote_native(0, para, 0),
                        _ => doc.insert_equation_native(0, para, 0, "a^2+b^2=c^2", 1200, 0),
                    };
                    res.expect("insert");
                    for pg in 0..doc.page_count() {
                        doc.render_page_svg(pg).expect("render");
                    }
                    let id = doc.save_snapshot();
                    doc.restore_snapshot(id).expect("restore");
                }))
                .is_ok();
                if !ok {
                    println!("FAIL {op} {name} p{para}");
                    failures += 1;
                }
            }
        }
        println!("ok   {name} ({} paras probed)", para_count.min(4));
    }
    println!("---\n{checks} insert checks over {} docs, {failures} failures", files.len());
    if failures > 0 {
        std::process::exit(1);
    }
}
