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
    let bytes = std::fs::read(&path).unwrap_or_else(|e| panic!("read {}: {}", path.display(), e));
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
        "학교명",         // top row
        "지원동기",       // mid row
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
fn small_04_trailing_blank_stays_on_page1() {
    // BUG (cell-height cluster / trailing-blank-page): the document's final
    // paragraph is an empty blank line (vpos=61120) whose 13.3px line
    // overflows the page-1 text area by 12.8px — just past the 10px
    // LAYOUT_DRIFT_SAFETY_PX window the existing trailing-empty-paragraph
    // guard used — so rhwp spawned a phantom blank page 2. Hancom collapses
    // a trailing blank line at the page bottom and renders 1 page. After the
    // terminal-empty-paragraph absorb fix the page count must be 1 and the
    // last body sentence ("다섯째") must be on page 1.
    let doc = load_sample("small_04_trailing_blank.hwpx");
    assert_eq!(
        doc.page_count(),
        1,
        "doc must paginate to 1 page (no trailing blank page)"
    );

    let svg = doc.render_page_svg_native(0).expect("render page 1");
    let page_text = svg_text(&svg);
    let dense = page_text.replace(' ', "");
    assert!(
        dense.contains("다섯째"),
        "page 1 must contain the final body paragraph '다섯째' — the trailing \
         blank line must not push content (or itself) onto a phantom page 2",
    );
}

#[test]
fn overseas_training_text_table_paginates_like_hancom() {
    // BUG (non-TAC TopAndBottom shrink cluster): this document has a tall
    // text-only 48x5 form table with a declared outer height far shorter
    // than its natural row content. The photo-grid shrink rule used to
    // scale it down to the declared height, collapsing Hancom's 4 pages
    // into 2. Text-only tables must grow and paginate instead; only picture
    // grids can be proportionally shrunk to the outer <hp:sz> height.
    let doc = load_sample("overseas_training.hwpx");
    assert_eq!(doc.page_count(), 4, "doc must paginate to 4 pages");

    let svg = doc.render_page_svg_native(3).expect("render page 4");
    let page_text = svg_text(&svg);
    let dense = page_text.replace(' ', "");
    let has_final_table = ["가습마스크", "장바구니", "마스크"].iter().all(|s| {
        let needle = s.replace(' ', "");
        dense.contains(&needle)
    });
    assert!(
        has_final_table,
        "page 4 must contain the final accommodation/pledge table content; \
         the text-only form table must not be crushed into earlier pages",
    );
}

// [Bucket C] #[ignore]'d 2026-05-29. The cross-paragraph vpos-reset detector
// (hwpx_cross_para_reset_breaks) DOES move the infographic onto page 4 as this
// test requires — but it also cascades a phantom page (rhwp -> 12 pages, Hancom
// = 11) because rhwp packs body text ~13.5px/page tighter than Hancom and a
// second spurious break fires at the pi=132->133 transition. The detector
// therefore ships DEFAULT-OFF (see DocumentCore default in document_core/mod.rs)
// so production pagination is unchanged. Re-enable the flag AND remove #[ignore]
// once the "table already filled this page" narrowing lands to suppress the
// second break. Do NOT delete this test — it is the regression gate for that
// follow-up.
#[test]
#[ignore = "Bucket C regression gate: detector ships default-off (helps 0 corpus files, \
            cascades a phantom 12th page on internship_plan). Re-enable the flag and remove \
            this #[ignore] once the 'table already filled this page' narrowing lands."]
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
