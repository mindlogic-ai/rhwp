//! Integration regression gate for the rhwp fidelity corpus work.
//!
//! Each test loads a real sample doc that previously hit a known bug,
//! drives the document through pagination, and asserts on either the
//! page count or the visible-content extent. These are the regression
//! gates for Bucket A (cell-height), B (wide-table), and C (vpos-reset)
//! fixes — see docs/superpowers/plans/2026-05-29-rhwp-fidelity-e2e.md.
//!
//! Sentinels are extracted from per-page SVG (the authoritative visual
//! output — rhwp's PDF exporter drops Korean glyphs, see Known gotchas
//! #3 in the rhwp-fidelity-fix skill). The SVG mirrors what factchat's
//! browser canvas renders.

use rhwp::wasm_api::HwpDocument;

/// Concatenate every `<text>…</text>` body in an SVG into one string for
/// substring search. Mirrors `svg_text` helper used in issue_1073 test.
fn svg_text(svg: &str) -> String {
    let mut out = String::new();
    let mut rest = svg;
    while let Some(open) = rest.find("<text") {
        if let Some(gt) = rest[open..].find('>') {
            let after = &rest[open + gt + 1..];
            if let Some(close) = after.find("</text>") {
                out.push_str(&after[..close]);
                rest = &after[close + 7..];
                continue;
            }
        }
        break;
    }
    out
}

fn load_sample(name: &str) -> HwpDocument {
    let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("tests/integration/samples")
        .join(name);
    let bytes = std::fs::read(&path)
        .unwrap_or_else(|e| panic!("read {}: {}", path.display(), e));
    HwpDocument::from_bytes(&bytes).expect("parse")
}

#[test]
fn gifted_application_renders_full_form() {
    // BUG: rhwp's cell row heights were thought to push the bottom rows of
    // the 10x7 form table (위와 같이.../학생-학부모/강원특별자치도... 귀하)
    // off the bottom of page 1. After Bucket D's metric work + Bucket A's
    // cell-height work, all 10 rows must be on page 1 (Hancom paginates
    // to 1 page).
    let doc = load_sample("gifted_application.hwpx");
    assert_eq!(doc.page_count(), 1, "doc must paginate to 1 page");

    let svg = doc.render_page_svg_native(0).expect("render page 1");
    let page_text = svg_text(&svg);
    // SVG renders text as one glyph per <text> element so we de-space.
    let dense = page_text.replace(' ', "");
    for sentinel in &[
        "학교명",       // top row
        "지원동기",     // mid row
        "강원특별자치도", // bottom-row sentinel — would be dropped on bug
    ] {
        let needle = sentinel.replace(' ', "");
        assert!(
            dense.contains(&needle),
            "page 1 must contain '{}' — currently dropped due to cell-height bug",
            sentinel,
        );
    }
}

#[test]
fn k_star_p14_renders_committee_footer() {
    // BUG: page 14 of the K-STAR visa track plan dropped the footer rows
    // (작성일 / 위원 성명 / 서울대학교 ... 학과). Hancom paginates to 19
    // pages with all rows visible on page 14. After Bucket A the same
    // page count + footer text must be present.
    let doc = load_sample("k_star_visa_track.hwpx");
    assert_eq!(doc.page_count(), 19, "doc must paginate to 19 pages");

    let svg = doc.render_page_svg_native(13).expect("render page 14");
    let page_text = svg_text(&svg);
    let dense = page_text.replace(' ', "");
    for sentinel in &["작성일", "성명", "학과"] {
        let needle = sentinel.replace(' ', "");
        assert!(
            dense.contains(&needle),
            "page 14 must contain '{}' — currently dropped",
            sentinel,
        );
    }
}

#[test]
fn internship_plan_p4_matches_hancom_content() {
    // BUG (Bucket C): Hancom paginates page 4 to contain a 4-circle infographic
    // ("학습연계" / "성공기반" labels) + a small table + a bullet list. rhwp
    // currently puts only the bullet list on page 4 because it missed a
    // cross-paragraph vpos reset that Hancom honors as a page break. Same page
    // count (11) but different per-page content. After Bucket C the page-4
    // content must match Hancom — sentinel text "학습연계" or "성공기반"
    // (infographic labels) must appear on p4.
    let doc = load_sample("internship_plan.hwpx");
    assert_eq!(doc.page_count(), 11, "doc must paginate to 11 pages");

    let svg = doc.render_page_svg_native(3).expect("render page 4");
    let page_text = svg_text(&svg);
    let dense = page_text.replace(' ', "");
    let has_sentinel = ["학습연계", "성공기반"].iter().any(|s| {
        let needle = s.replace(' ', "");
        dense.contains(&needle)
    });
    assert!(
        has_sentinel,
        "page 4 must contain '학습연계' or '성공기반' \
         (currently drifted to page 3 — cross-paragraph vpos-reset bug)",
    );
}
