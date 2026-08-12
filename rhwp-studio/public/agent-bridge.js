// Agent bridge for the HWP spike — runs inside rhwp-studio's window.
// Reads window.__wasm (exposed in src/main.ts) and exposes the same RPC
// surface as the spike's standalone studio.html so the FastAPI agent can
// drive the editor without changes.
//
// Sends 'studio_ready' to parent when wasm globals appear.
// Receives:
//   { type: 'rpc_request', id, method, params } — dispatch to handler
//   { type: 'editor_lock' }   — show overlay, disable user input
//   { type: 'editor_unlock' } — hide overlay
// Sends:
//   { type: 'rpc_reply', id, result | error }
//   { type: 'user_edit', kind, summary } — fired on document-changed when
//                                          agent is NOT the source
//   { type: 'studio_ready' }

(function () {
  'use strict';

  // Wait for main.ts's initialize() to FULLY complete before announcing
  // studio_ready. Polling wasm.initialized alone fired mid-boot — after
  // wasm.initialize() but before CanvasKit/canvasView/toolbar existed — so an
  // immediate loadFile skipped canvasView?.loadDocument() silently and the
  // parent revealed a blank pane. __initPromise resolves only when the whole
  // boot sequence is done; the globals poll remains as a fallback for older
  // main.ts bundles that don't expose it.
  function whenReady(cb, tries = 0) {
    if (window.__initPromise) {
      window.__initPromise.then(() => {
        const w = window.__wasm;
        if (!(w && window.__eventBus && w.initialized === true)) {
          // initialize() swallows boot failures (paints the error screen and
          // resolves anyway) — an engine that never came up must not announce
          // ready, or the parent's first loadFile crashes into the
          // uninitialized glue (`__wbindgen_malloc` undefined). Tell the
          // parent explicitly instead of leaving it to a timeout.
          console.error('[agent-bridge] init finished but engine unusable — studio_ready withheld');
          try { window.parent && window.parent.postMessage({ type: 'studio_init_failed' }, '*'); } catch (e) {}
          return;
        }
        // initialize()가 마지막으로 남기는 유휴 상태("HWP 파일을
        // 선택해주세요." + 툴바/눈금자)가 실제로 화면에 반영된 뒤에
        // ready를 알린다. resolve 직후는 마지막 셋업 문장과 같은
        // 태스크라 아직 페인트 전 — 더블 rAF로 페인트 커밋을 기다린다.
        requestAnimationFrame(() => {
          requestAnimationFrame(() => cb());
        });
      });
      return;
    }
    const w = window.__wasm;
    if (w && window.__eventBus && w.initialized === true) return cb();
    if (tries > 400) { console.error('[agent-bridge] __wasm never initialized'); return; }
    setTimeout(() => whenReady(cb, tries + 1), 50);
  }

  whenReady(() => {
    const wasm = window.__wasm;
    const eventBus = window.__eventBus;

    function getDoc() {
      if (!wasm.doc) throw new Error('no document loaded');
      return wasm.doc;
    }
    function sendToParent(msg) {
      try { window.parent && window.parent.postMessage(msg, '*'); } catch (e) {}
    }
    function safeParse(s) {
      try { return JSON.parse(s); }
      catch (e) {
        return {
          ok: false,
          raw: s,
          raw_type: typeof s,
          raw_string: String(s),
          parse_error: e && e.message ? e.message : String(e),
        };
      }
    }
    function pathToCoords(path) {
      const m = /^s(\d+):p(\d+)(?::c(\d+))?$/.exec(path);
      if (!m) throw new Error(`bad path: ${path}`);
      return { sec: +m[1], para: +m[2], ctrl: m[3] !== undefined ? +m[3] : 0 };
    }
    // Grow a body-table row so a just-written cell whose text overflows its
    // fixed box becomes fully visible — matching native 한글, which treats a
    // stored row height as a minimum and grows it to fit. Overflow is MEASURED
    // from the render tree (content-bottom vs cell-box-bottom), so a cell that
    // already fits reports overflow<=0 and is left untouched. Grow-only,
    // capped, best-effort (callers wrap in try/catch — this never throws up).
    function autoFitCellRow(doc, sec, para, ctrl, row, col) {
      const bboxes = safeParse(doc.getTableCellBboxes(sec, para, ctrl));
      if (!Array.isArray(bboxes) || !bboxes.length) return;
      const me = bboxes.find(b => b.row === row && b.col === col);
      if (!me) return;
      const tree = safeParse(doc.getPageRenderTree(me.pageIndex || 0));
      if (!tree || tree.ok === false) return;
      const root = tree.root || tree;
      const walk = (n, cb) => { cb(n); const ch = n.children; if (ch) for (let i = 0; i < ch.length; i++) walk(ch[i], cb); };
      let node = null, pageH = 0;
      walk(root, (n) => {
        const t = n.type || n.nodeType;
        if (t === 'Page') { const b = n.bbox || n.box || {}; pageH = b.height ?? b.h ?? pageH; }
        if (t && /cell/i.test(String(t)) && n.row === row && n.col === col) node = n;
      });
      if (!node || !pageH) return;
      const box = node.bbox || node.box || {};
      const boxBottom = (box.y || 0) + (box.height ?? box.h ?? 0);
      let contentBottom = boxBottom;
      walk(node, (n) => {
        const b = n.bbox || n.box;
        if (b && typeof b.y === 'number') contentBottom = Math.max(contentBottom, b.y + (b.height ?? b.h ?? 0));
      });
      const overflowRU = contentBottom - boxBottom;
      if (overflowRU <= 2) return;                          // fits (sub-pixel) → leave alone
      const pd = safeParse(doc.getPageDef(sec));
      if (!pd || pd.ok === false) return;
      const pageHwpH = pd.landscape ? pd.width : pd.height; // render is orientation-applied
      if (!pageHwpH) return;
      const scale = pageH / pageHwpH;                       // render units per HWPUNIT
      if (!(scale > 0)) return;
      let deltaHwp = Math.round(overflowRU / scale + 300);  // +3pt of bottom padding
      deltaHwp = Math.min(deltaHwp, 40000);                 // cap ~400pt
      const rowCells = bboxes.filter(b => b.row === row);   // native cells starting on this row
      if (!rowCells.length) return;
      const json = rowCells.map(b => ({ cellIdx: b.cellIdx, heightDelta: deltaHwp }));
      const gr = safeParse(doc.resizeTableCells(sec, para, ctrl, JSON.stringify(json)));
      if (!(gr && gr.ok === false)) refresh();
    }
    function tryGetTableDims(sec, para, ctrl) {
      try { return JSON.parse(getDoc().getTableDimensions(sec, para, ctrl)); }
      catch { return null; }
    }
    // Resolve a visual (row, col) to the table's physical cellIdx.
    // Naive `row * colCount + col` is wrong for any merged table — a
    // 응시원서 form with 27 logical rows × 8 cols has only ~69 physical
    // cells, and the bbox API knows which (row,col) anchor maps to
    // which cellIdx. Falls back to the flat formula when the bbox API
    // is unavailable (older WASM) so we degrade gracefully.
    function resolveCellIdx(sec, para, ctrl, row, col, colCount) {
      try {
        const bboxes = JSON.parse(getDoc().getTableCellBboxes(sec, para, ctrl)) || [];
        // Anchor: cell whose (row, col) equals the requested position.
        const anchor = bboxes.find(b => b.row === row && b.col === col);
        if (anchor) return anchor.cellIdx;
        // No anchor at (row, col) means the position is INSIDE a merged
        // region. Find the enclosing anchor (covers row..row+rowSpan-1,
        // col..col+colSpan-1) so the agent's write still hits a real
        // cell instead of silently landing somewhere unexpected.
        const enclosing = bboxes.find(b =>
          b.row <= row && row < b.row + b.rowSpan &&
          b.col <= col && col < b.col + b.colSpan
        );
        if (enclosing) return enclosing.cellIdx;
      } catch {}
      return row * (colCount || 1) + col;
    }
    function cellPathJson(ctrl, cellIdx, cellPara = 0) {
      return JSON.stringify([
        { controlIndex: ctrl, cellIndex: cellIdx, cellParaIndex: cellPara },
      ]);
    }
    function getCellTextCompat(doc, sec, para, ctrl, cellIdx, cellPara, start, count) {
      const pathJson = cellPathJson(ctrl, cellIdx, cellPara);
      if (typeof doc.getTextInCellByPath === 'function') {
        return doc.getTextInCellByPath(sec, para, pathJson, start, count);
      }
      return doc.getTextInCell(sec, para, ctrl, cellIdx, cellPara, start, count);
    }
    function deleteCellTextCompat(doc, sec, para, ctrl, cellIdx, cellPara, start, count) {
      const pathJson = cellPathJson(ctrl, cellIdx, cellPara);
      if (typeof doc.deleteTextInCellByPath === 'function') {
        return doc.deleteTextInCellByPath(sec, para, pathJson, start, count);
      }
      return doc.deleteTextInCell(sec, para, ctrl, cellIdx, cellPara, start, count);
    }
    function insertCellTextCompat(doc, sec, para, ctrl, cellIdx, cellPara, start, text) {
      const pathJson = cellPathJson(ctrl, cellIdx, cellPara);
      if (typeof doc.insertTextInCellByPath === 'function') {
        return doc.insertTextInCellByPath(sec, para, pathJson, start, text);
      }
      return doc.insertTextInCell(sec, para, ctrl, cellIdx, cellPara, start, text);
    }
    // ── Nested-table addressing ─────────────────────────────────────────
    // Path grammar (extends the body-table form):
    //   body table:    s{sec}:p{para}[:c{ctrl}]
    //   nested table:  <table path>:cell({row},{col}):p{cellPara}[:c{ctrl}]
    //                  — repeatable for tables inside cells of nested tables.
    // The WASM's *ByPath APIs address nested content with a JSON hop list
    // [{controlIndex, cellIndex, cellParaIndex}, …]: each hop descends one
    // table control → cell → cell paragraph. The LAST hop's controlIndex is
    // the target table; its cellIndex/cellParaIndex address a cell inside it
    // for cell-scoped calls and are ignored by table-scoped ones (dims,
    // bboxes). A tableRef normalizes both forms: {sec, para, ctrl, hops[]},
    // hops always non-empty with the last hop's cell fields zeroed.
    function resolveTablePath(path) {
      const m = /^s(\d+):p(\d+)((?::.*)?)$/.exec(path);
      if (!m) throw new Error(`bad path: ${path}`);
      const sec = +m[1], para = +m[2];
      let rest = m[3] || '';
      let ctrl = 0;
      const cm = /^:c(\d+)(?=$|:)/.exec(rest);
      if (cm) { ctrl = +cm[1]; rest = rest.slice(cm[0].length); }
      const hops = [{ controlIndex: ctrl, cellIndex: 0, cellParaIndex: 0 }];
      const segRe = /^:cell\((\d+),(\d+)\):p(\d+)(?::c(\d+)(?=$|:))?/;
      while (rest.length) {
        const sm = segRe.exec(rest);
        if (!sm) throw new Error(`bad nested path segment ${JSON.stringify(rest)} in ${path}`);
        const row = +sm[1], col = +sm[2], cellPara = +sm[3];
        const nextCtrl = sm[4] !== undefined ? +sm[4] : 0;
        const cur = hops[hops.length - 1];
        cur.cellIndex = resolveCellIdxAt({ sec, para, hops }, row, col);
        cur.cellParaIndex = cellPara;
        hops.push({ controlIndex: nextCtrl, cellIndex: 0, cellParaIndex: 0 });
        rest = rest.slice(sm[0].length);
      }
      return { sec, para, ctrl, hops, nested: hops.length > 1, path };
    }
    function tableDimsAt(ref) {
      const doc = getDoc();
      if (ref.hops.length === 1) return JSON.parse(doc.getTableDimensions(ref.sec, ref.para, ref.hops[0].controlIndex));
      if (typeof doc.getTableDimensionsByPath !== 'function') throw new Error('nested tables need a newer WASM (getTableDimensionsByPath missing)');
      return JSON.parse(doc.getTableDimensionsByPath(ref.sec, ref.para, JSON.stringify(ref.hops)));
    }
    function tryTableDimsAt(ref) { try { return tableDimsAt(ref); } catch { return null; } }
    function tableBboxesAt(ref) {
      const doc = getDoc();
      if (ref.hops.length === 1) return JSON.parse(doc.getTableCellBboxes(ref.sec, ref.para, ref.hops[0].controlIndex)) || [];
      if (typeof doc.getTableCellBboxesByPath !== 'function') throw new Error('nested tables need a newer WASM (getTableCellBboxesByPath missing)');
      return JSON.parse(doc.getTableCellBboxesByPath(ref.sec, ref.para, JSON.stringify(ref.hops))) || [];
    }
    // Cell-scoped hop list: the ref's hops with the final hop pointed at
    // (cellIdx, cellPara). This is the pathJson every *InCellByPath call takes.
    function cellPathJsonAt(ref, cellIdx, cellPara = 0) {
      const hops = ref.hops.map((h) => ({ ...h }));
      const last = hops[hops.length - 1];
      last.cellIndex = cellIdx;
      last.cellParaIndex = cellPara;
      return JSON.stringify(hops);
    }
    // Visual (row, col) → physical cellIdx, merge-aware, at any nesting level.
    function resolveCellIdxAt(ref, row, col) {
      let bboxes = [];
      try { bboxes = tableBboxesAt(ref); } catch {}
      const anchor = bboxes.find((b) => b.row === row && b.col === col);
      if (anchor) return anchor.cellIdx;
      const enclosing = bboxes.find((b) =>
        b.row <= row && row < b.row + b.rowSpan &&
        b.col <= col && col < b.col + b.colSpan
      );
      if (enclosing) return enclosing.cellIdx;
      let colCount = 1;
      const dims = tryTableDimsAt(ref);
      if (dims && dims.colCount) colCount = dims.colCount;
      return row * colCount + col;
    }
    function cellParagraphCountAt(ref, cellIdx) {
      const doc = getDoc();
      if (typeof doc.getCellParagraphCountByPath === 'function') {
        return doc.getCellParagraphCountByPath(ref.sec, ref.para, cellPathJsonAt(ref, cellIdx, 0)) || 1;
      }
      if (ref.hops.length === 1) return doc.getCellParagraphCount(ref.sec, ref.para, ref.hops[0].controlIndex, cellIdx) || 1;
      throw new Error('nested tables need a newer WASM (getCellParagraphCountByPath missing)');
    }
    function cellTextAt(ref, cellIdx, cellPara, start, count) {
      const doc = getDoc();
      if (typeof doc.getTextInCellByPath === 'function') {
        return doc.getTextInCellByPath(ref.sec, ref.para, cellPathJsonAt(ref, cellIdx, cellPara), start, count);
      }
      if (ref.hops.length === 1) return doc.getTextInCell(ref.sec, ref.para, ref.hops[0].controlIndex, cellIdx, cellPara, start, count);
      throw new Error('nested tables need a newer WASM (getTextInCellByPath missing)');
    }
    // Probe one cell for nested table controls. The WASM has no direct
    // "controls in cell" enumerator; the only signal is that
    // getTableDimensionsByPath succeeds for a hop that points at a control
    // hosting a table and throws (범위 초과) otherwise. Bounded: paraCap
    // paragraphs × ctrl 0..2 probes.
    function scanCellNestedTables(ref, cellIdx, paraCap = 12) {
      const doc = getDoc();
      if (typeof doc.getTableDimensionsByPath !== 'function') return [];
      let nParas = 1;
      try { nParas = cellParagraphCountAt(ref, cellIdx); } catch {}
      const found = [];
      for (let cp = 0; cp < Math.min(nParas, paraCap); cp++) {
        for (let k = 0; k < 3; k++) {
          const hops = JSON.parse(cellPathJsonAt(ref, cellIdx, cp));
          hops.push({ controlIndex: k, cellIndex: 0, cellParaIndex: 0 });
          try {
            const d = JSON.parse(doc.getTableDimensionsByPath(ref.sec, ref.para, JSON.stringify(hops)));
            if (d && d.rowCount) found.push({ cell_para: cp, ctrl: k, rows: d.rowCount, cols: d.colCount });
          } catch { /* no table control at (cp, k) */ }
        }
      }
      return found;
    }
    // Agent-facing path for a table nested in (row, col) of the table at
    // basePath: `${basePath}:cell(r,c):p{cellPara}:c{ctrl}`.
    function nestedTablePath(basePath, row, col, cellPara, ctrl) {
      return `${basePath}:cell(${row},${col}):p${cellPara}:c${ctrl || 0}`;
    }
    // For ops whose WASM API is body-level only: accept legacy paths, refuse
    // nested ones with a message the agent can act on.
    function bodyTableCoordsOrThrow(path, opName) {
      const ref = resolveTablePath(path);
      if (ref.nested) {
        throw new Error(
          `${opName} cannot target a NESTED table yet (${path}) — the engine's ` +
          `${opName} API only reaches body-level tables. Cell text edits work via ` +
          'set_cell_text and row/column changes via insert/delete_table_row/column ' +
          'with this nested path; tell the user this specific operation is not ' +
          'supported on inner tables yet instead of rewriting the outer cell.'
        );
      }
      return { sec: ref.sec, para: ref.para, ctrl: ref.hops[0].controlIndex };
    }
    // Older WASM builds (before the *ByPath structural exports) trap with an
    // unrecoverable 'unreachable' panic when a footnote/equation is inserted
    // into an HWPX paragraph that already hosts a control (empty
    // ctrl_data_records + Vec::insert OOB). Guard: on old WASM, refuse the
    // known-fatal shape (control-hosting paragraph) instead of bricking the
    // editor until refresh.
    //
    // Fixed-engine sentinels, either of which is enough:
    //   - insertTableRowByPath  — the fork engine (v0.7.13-x) shipped the trap
    //     fix and the *ByPath structural exports in the same build.
    //   - getCursorRectByPathNear — upstream v0.8.x, which fixed the trap
    //     independently and never had the *ByPath exports. Verified on
    //     v0.8.2-1: insertFootnote/insertEquation into a table-hosting
    //     paragraph return ok and the engine stays alive.
    function guardLegacyInsertTrap(sec, para, opName) {
      const doc = getDoc();
      if (typeof doc.insertTableRowByPath === 'function') return null; // fixed engine (fork)
      if (typeof doc.getCursorRectByPathNear === 'function') return null; // fixed engine (upstream v0.8.x)
      // Trap shapes on the old engine: paragraph 0 (hosts the section/column
      // def controls) and table-hosting paragraphs. Both leave the insert
      // index past the (empty) ctrl_data_records vec.
      let hosts = para === 0 ? 'the section definition' : null;
      if (!hosts) {
        for (let ctrl = 0; ctrl < 3; ctrl++) {
          if (tryGetTableDims(sec, para, ctrl)) { hosts = 'a table'; break; }
        }
      }
      if (hosts) {
        return {
          ok: false,
          error: `${opName} into a paragraph that hosts ${hosts} is not ` +
            'supported on this engine build — target a plain text ' +
            'paragraph (insert one with insert_paragraph_after first).',
        };
      }
      return null;
    }
    // Structural row/col op shared shell: body tables use the legacy flat
    // API, nested paths use the *ByPath variant (hop-list JSON). On an older
    // WASM without the *ByPath export the TypeError becomes an actionable
    // refusal rather than a silent mutation of the outer table.
    function structuralTableOp(path, opName, flatCall, byPathCall) {
      const doc = getDoc();
      let ref;
      try { ref = resolveTablePath(path); }
      catch (e) { return { ok: false, error: e?.message || String(e) }; }
      let r;
      try {
        if (ref.nested) {
          r = safeParse(byPathCall(doc, ref.sec, ref.para, JSON.stringify(ref.hops)));
        } else {
          r = safeParse(flatCall(doc, ref.sec, ref.para, ref.hops[0].controlIndex));
        }
      } catch (e) {
        if (e instanceof TypeError && /is not a function/.test(e.message || '')) {
          return {
            ok: false,
            error: `${opName} on a NESTED table is not supported by this ` +
              'engine build (*ByPath structural API missing) — tell the user ' +
              'structural changes to this inner table are not available yet.',
          };
        }
        return { ok: false, error: e?.message || String(e) };
      }
      refresh();
      return r;
    }
    // ── Cell fill read-back ─────────────────────────────────────────────
    // getCellProperties exposes fillType/fillColor (the same read that
    // setCellFill round-trips). Body-level tables only — there is no *ByPath
    // variant of getCellProperties, so nested refs read as null and callers
    // skip. null = no solid fill (white/transparent/gradient).
    function cellFillAt(ref, cellIdx) {
      if (ref.nested) return null;
      const doc = getDoc();
      if (typeof doc.getCellProperties !== 'function') return null;
      try {
        const p = JSON.parse(doc.getCellProperties(ref.sec, ref.para, ref.hops[0].controlIndex, cellIdx));
        if (p && p.fillType === 'solid' && typeof p.fillColor === 'string') {
          return p.fillColor.toUpperCase();
        }
        return null;
      } catch { return null; }
    }
    // Background fills of one visual row: [{col, fill}] per anchor cell.
    function rowFillsAt(ref, bboxes, row) {
      return bboxes
        .filter((b) => b.row === row)
        .sort((a, b) => a.col - b.col)
        .map((b) => ({ col: b.col, fill: cellFillAt(ref, b.cellIdx) }));
    }
    // Read a cell's FULL text across ALL its paragraphs, joined with "\n".
    // A cell often holds several paragraphs (e.g. an address cell has a
    // 제출주소 line + a 사업담당자 line). Reading only cell paragraph 0 — as the
    // table views used to — hid every line after the first from the agent.
    // Joining with "\n" mirrors how setCellText writes multi-line cells, so
    // read and write use the same line-break convention. `cap` bounds the
    // returned length so huge cells don't blow up the agent's context.
    function readCellAllParas(doc, sec, para, ctrl, cellIdx, cap) {
      const limit = cap || 2000;
      let n = 1;
      try { n = doc.getCellParagraphCount(sec, para, ctrl, cellIdx) || 1; } catch {}
      const parts = [];
      let total = 0;
      for (let p = 0; p < n; p++) {
        let t = '';
        try { t = getCellTextCompat(doc, sec, para, ctrl, cellIdx, p, 0, 9999) || ''; } catch {}
        parts.push(t);
        total += t.length;
        if (total >= limit) break;
      }
      let joined = parts.join('\n');
      if (joined.length > limit) joined = joined.slice(0, limit) + '…';
      return joined;
    }
    // tableRef-aware sibling of readCellAllParas — same join convention,
    // works at any nesting depth via the *ByPath APIs.
    function readCellAllParasAt(ref, cellIdx, cap) {
      const limit = cap || 2000;
      let n = 1;
      try { n = cellParagraphCountAt(ref, cellIdx); } catch {}
      const parts = [];
      let total = 0;
      for (let p = 0; p < n; p++) {
        let t = '';
        try { t = cellTextAt(ref, cellIdx, p, 0, 9999) || ''; } catch {}
        parts.push(t);
        total += t.length;
        if (total >= limit) break;
      }
      let joined = parts.join('\n');
      if (joined.length > limit) joined = joined.slice(0, limit) + '…';
      return joined;
    }
    function refresh() {
      cleanSinceLoad = false;
      originalHwpxBytes = null;
      // Style mutations (applyCharFormat, etc.) update the doc tree but
      // do not invalidate the per-paragraph `<hp:linesegarray>` layout
      // cache. Rendering / export then uses stale vertpos values and
      // restyled paragraphs collapse to vertpos=0 → headings stack at
      // top of page, body text overlaps. rhwp.d.ts:1055 exposes
      // `reflowLinesegs()` exactly for this (upstream #177). Idempotent —
      // returns 0 when nothing dirty. Wrapped in try/catch so older
      // WASM builds without the method still work.
      try { const d = getDoc?.(); if (d && typeof d.reflowLinesegs === 'function') d.reflowLinesegs(); } catch {}
      // rhwp-studio's CanvasView subscribes to this — triggers refreshPages().
      eventBus.emit('document-changed', 'agent-mutation');
    }
    // Tool surface uses snake_case + points (font_size_pt: 39). WASM's
    // applyCharFormat / applyCharFormatInCell both expect camelCase + HWPUnit
    // (fontSize: 3900). Shared by applyTextStyle and applyCellTextStyle so the
    // two paths can't drift — font_size_pt was silently dropped on one of
    // them before (B1 in PROGRESS.md).
    function translateCharProps(props) {
      const wasmProps = {};
      for (const [k, v] of Object.entries(props || {})) {
        if (v === null || v === undefined) continue;
        switch (k) {
          case 'font_size_pt': wasmProps.fontSize = Math.round(Number(v) * 100); break;
          case 'font_name':    wasmProps.fontFamily = v; break;
          case 'color':        wasmProps.textColor = v; break;
          case 'highlight':    wasmProps.shadeColor = v; break;
          default:             wasmProps[k] = v;
        }
      }
      return wasmProps;
    }
    // Tool surface uses snake_case + display units (align: 'center',
    // line_spacing_pct: 180, space_before_pt: 6). WASM applyParaFormat /
    // parse_para_shape_mods expects camelCase engine keys + HWPUnit
    // (alignment: 'center', lineSpacing: 180, spacingBefore: 600). Without
    // this translation the props were passed straight through and SILENTLY
    // DROPPED — alignment/spacing edits returned ok:true but never applied
    // (the 2026-06-17 "중앙정렬 안됨" QA bug). Engine-shaped keys (alignment,
    // lineSpacing, indent, ...) pass through unchanged so direct callers work.
    // ── 삽입 문단의 "문단 앞에서 항상 쪽 나눔" 승계 차단 ──
    // insertParagraphAfter/insertParagraphsAfter는 사람이 줄 끝에서 Enter를 친
    // 것과 같게 splitParagraph로 문단을 만든다. 그래서 새 문단이 앵커의
    // ParaShape를 그대로 물려받는데, 여기엔 pageBreakBefore도 포함된다.
    // 앵커에 쪽 나눔이 걸려 있으면(공문 서식의 제목/결재 문단 등 흔함) 에이전트가
    // 넣는 문단마다 페이지가 갈리고, 여백용 빈 줄이 대개 그 문단들이라 "빈 줄마다
    // 페이지가 넘어간다"로 보인다. 실측: 쪽 나눔 문단 뒤에 5문단 삽입 → 6페이지.
    // 새 문단에서만 플래그를 끈다. 앵커와 나머지 서식(정렬/들여쓰기/줄간격/글자
    // 모양)은 그대로 승계된다. 진짜 쪽 나눔이 필요하면 insertPageBreak나
    // applyParaStyle{pageBreakBefore:true}로 명시적으로 건다.
    function clearInheritedPageBreak(doc, sec, paraIdx) {
      try {
        const cur = JSON.parse(doc.getParaPropertiesAt(sec, paraIdx));
        if (cur.pageBreakBefore !== true) return false;
        doc.applyParaFormat(sec, paraIdx, '{"pageBreakBefore":false}');
        return true;
      } catch { return false; }
    }
    // shape_matched 읽기-검증용 정규화. 위에서 일부러 끈 플래그 때문에 정상
    // 삽입이 shape_matched=false로 보고되면 안 된다.
    //   pageBreakBefore — 의도적으로 끈 값.
    //   paraShapeId     — 플래그를 끄면 다른 ParaShape 항목으로 해소되므로 id가
    //                     달라진다. 도큐먼트 내부 테이블 인덱스일 뿐이고, 이
    //                     검증이 잡으려는 건 "새 문단이 기본 서식(작은 글꼴·가운데
    //                     정렬)으로 떨어지는" 회귀다. 정렬/들여쓰기/줄간격 등 실제
    //                     서식 값은 그대로 비교된다.
    function normalizeParaShape(json) {
      try {
        const o = JSON.parse(json);
        delete o.pageBreakBefore;
        delete o.paraShapeId;
        // breakType은 ParaShape가 아니라 문단 자체의 값이라 서식 비교 대상이 아니다.
        delete o.breakType;
        return JSON.stringify(o);
      } catch { return json; }
    }
    function translateParaProps(props) {
      const out = {};
      for (const [k, v] of Object.entries(props || {})) {
        if (v === null || v === undefined) continue;
        switch (k) {
          case 'align':                out.alignment = v; break;                       // left|center|right|justify|distribute
          case 'line_spacing_pct':     out.lineSpacing = Math.round(Number(v)); out.lineSpacingType = 'Percent'; break;
          case 'indent_first_line_mm': out.indent = Math.round(Number(v) * 283.465); break; // mm → HWPUnit (1/7200")
          case 'space_before_pt':      out.spacingBefore = Math.round(Number(v) * 100); break; // pt → HWPUnit
          case 'space_after_pt':       out.spacingAfter = Math.round(Number(v) * 100); break;
          default:                     out[k] = v;
        }
      }
      return out;
    }

    // ── Agent-active flag — suppress user_edit during our own mutations ──
    let agentDepth = 0;
    let cleanSinceLoad = false;
    let originalHwpxBytes = null;
    let originalFileName = null;
    async function withAgent(fn) {
      agentDepth++;
      try { return await fn(); } finally { agentDepth--; }
    }
    // The studio fires document-changed a beat AFTER a load/restore RPC
    // resolves (agentDepth is back to 0), so the depth check alone lets
    // those trailing emissions masquerade as user edits — the BE then
    // kills its redo stack and autosaves a phantom user_edit revision
    // that severs the forward timeline. Stay quiet from init and after
    // every editor_lock (doc load / agent turn / undo / redo / jump)
    // until the user actually touches the editor: only input can make a
    // change that's genuinely theirs.
    let quietUntilUserInput = true;
    ['keydown', 'pointerdown', 'beforeinput', 'paste', 'drop'].forEach((type) => {
      document.addEventListener(type, () => {
        // 잠금 중에는 갱신하지 않는다. 잠금이 스크롤·드래그 선택을 허용하게 되면서
        // 사용자가 문서를 읽기만 해도 pointerdown 이 뜬다 — 여기서 quiet 를 풀면
        // 에이전트 mutation 의 트레일링 document-changed 가 진짜 user_edit 으로
        // 새어 나가 BE 가 redo 스택을 죽이고 phantom 리비전을 저장한다.
        // 잠금 중 사용자 입력은 어차피 스튜디오 readonly 가 막으므로 "사용자가
        // 진짜 편집했다"는 신호가 될 수 없다.
        if (document.body.classList.contains('agent-locked')) return;
        quietUntilUserInput = false;
      }, true);
    });
    // First agent-made mutation of the current lock cycle — lets the FE
    // pill flip from "확인 중" to "편집 중" without duplicating a tool list.
    let agentMutationReported = false;
    eventBus.on('document-changed', (reason) => {
      if (agentDepth > 0) {
        if (!agentMutationReported) {
          agentMutationReported = true;
          sendToParent({ type: 'agent_mutation' });
        }
        return;
      }
      if (quietUntilUserInput) return;
      cleanSinceLoad = false;
      originalHwpxBytes = null;
      // Skip our own re-render emissions (reason === 'agent-mutation' implies depth > 0;
      // user dialogs use other strings).
      const summary = typeof reason === 'string' ? reason : 'user edit';
      sendToParent({ type: 'user_edit', kind: 'document-changed', summary });
    });

    // ── FactChat save menu (파일 > HWP/HWPX/PDF로 저장) ──
    // 저장 진입점은 format-explicit `data-fc-save` 항목이 담당한다. data-cmd가
    // 없어 스튜디오 디스패처는 무시하고, 브리지가 enable 상태를 소유하며 클릭을
    // 부모 FE로 넘겨 기존 native/converter 다운로드 파이프라인(리비전 스냅샷 +
    // fidelity 라우팅)을 태운다.
    // 현재 index.html에는 이 항목이 없다 — 다운로드 UI를 부모 FE가 전부 소유하기로
    // 해서 걷어냈다. 아래 코드는 빈 목록에 대해 no-op이므로, 메뉴에 다시 넣으면
    // 그대로 동작한다. 남아 있는 스튜디오 자체 저장 커맨드는 아래 클릭
    // 핸들러가 data-cmd 로 가로챈다.
    const fcSaveItems = Array.from(
      document.querySelectorAll('.md-item[data-fc-save]'),
    );
    let fcSaveEnabled = false;
    function setFcSaveEnabled(on) {
      fcSaveEnabled = !!on;
      fcSaveItems.forEach((el) => el.classList.toggle('disabled', !on));
    }
    function closeOpenMenu() {
      // Toggle the open menu shut through its own title. The controller
      // listens on MOUSEDOWN (not click), and openMenu === el routes to
      // closeAll(), keeping its internal state in sync — removing the
      // `open` class directly would desync the openMenu field.
      const openTitle = document.querySelector('.menu-item.open .menu-title');
      if (openTitle instanceof HTMLElement) {
        openTitle.dispatchEvent(
          new MouseEvent('mousedown', { bubbles: true, cancelable: true }),
        );
      }
    }
    // 스튜디오 자체 저장 커맨드도 같은 곳으로 보낸다. 이 항목들은 index.html에
    // `disabled` 로 적혀 있지만 menu-bar 가 드롭다운을 열 때마다
    // `dispatcher.isEnabled()` 로 상태를 다시 칠하므로 실제로는 살아 있고,
    // 눌리면 iframe 안에서 exportHwp/exportHwpx 바이트를 그대로 내려받는다.
    // 그 바이트는 rhwp 밖에서 열리지 않는다 — 한컴은 rhwp 의 .hwp 를
    // "손상된 파일" 이라 하고 한컴 컨버터조차 F040 으로 거부한다. 그래서
    // 클릭을 가로채 부모 FE 의 서버 변환 파이프라인으로 넘긴다.
    // 임베드가 아니면 넘길 부모가 없다 — 그때는 스튜디오 자체 저장이 유일한
    // 저장 수단이므로 가로채지 않는다.
    const fcEmbedded = window.parent !== window;
    const FC_SAVE_CMD_FORMATS = {
      'file:save': 'default',
      'file:save-as': 'default',
      'file:save-as-hwp': 'hwp',
      'file:save-as-hwpx': 'hwpx',
    };
    document.addEventListener('click', (e) => {
      const item = e.target && e.target.closest
        ? e.target.closest('.md-item[data-fc-save], .md-item[data-cmd]')
        : null;
      if (!item) return;
      const format = item.hasAttribute('data-fc-save')
        ? item.getAttribute('data-fc-save')
        : fcEmbedded
          ? FC_SAVE_CMD_FORMATS[item.getAttribute('data-cmd')]
          : null;
      if (!format) return;
      e.preventDefault();
      e.stopPropagation();
      // 디스패처는 container 의 버블 리스너라 stopPropagation 으로 막히지만,
      // 같은 캡처 단계에 다른 리스너가 붙으면 그쪽은 계속 받는다.
      e.stopImmediatePropagation();
      if (item.classList.contains('disabled')) return;
      sendToParent({ type: 'save_requested', format });
      closeOpenMenu();
    }, true);

    // ── FactChat unified undo/redo (되돌리기/다시 실행) ──
    // Single entry point over TWO histories that never overlap in time:
    // the editor's local input history (typing since the last agent-turn
    // boundary — the editor_lock handler clears it, see the router) and
    // the BE revision timeline (agent turns + coalesced user edits, state
    // mirrored in from the parent via history_state). Routing: local
    // first (char-level, instant); when local is exhausted, forward to
    // the parent → WS undo_last_turn / redo_last_turn.
    const fcBe = { canUndo: false, canRedo: false, busy: false };
    const fcHistoryEls = Array.from(
      document.querySelectorAll('[data-fc-undo], [data-fc-redo]'),
    );
    function readInputHandler() {
      // Re-read on every call: resilient whether the studio keeps one
      // InputHandler instance or swaps it on doc load.
      return (
        (window.__canvasView && window.__canvasView.getInputHandler
          ? window.__canvasView.getInputHandler()
          : null) || window.__inputHandler || null
      );
    }
    function localCanUndo() {
      try { return !!readInputHandler()?.canUndo(); } catch { return false; }
    }
    function localCanRedo() {
      try { return !!readInputHandler()?.canRedo(); } catch { return false; }
    }
    function clearLocalHistory() {
      // Same unminified API deactivate() uses. Called at every agent-turn
      // boundary (editor_lock) so the local stack only ever holds typing
      // newer than the last turn/rollback — the non-overlap invariant the
      // chronological routing depends on.
      const ih = readInputHandler();
      try { ih?.history?.clear?.(ih.wasm); } catch (err) {
        console.warn('[agent-bridge] local history clear failed', err);
      }
    }
    function fcBusy() {
      return fcBe.busy || document.body.classList.contains('agent-locked');
    }
    function refreshFcHistoryUi() {
      const busy = fcBusy();
      const canUndo = !busy && (localCanUndo() || fcBe.canUndo);
      const canRedo = !busy && (localCanRedo() || fcBe.canRedo);
      fcHistoryEls.forEach((el) => {
        const can = el.hasAttribute('data-fc-undo') ? canUndo : canRedo;
        if (el.tagName === 'BUTTON') {
          el.disabled = !can;
        } else {
          el.classList.toggle('disabled', !can);
        }
      });
    }
    function unifiedUndo() {
      if (fcBusy()) return;
      if (localCanUndo()) {
        try { readInputHandler()?.performUndo(); } catch (err) {
          console.warn('[agent-bridge] local undo failed', err);
        }
      } else if (fcBe.canUndo) {
        sendToParent({ type: 'undo_requested' });
      }
      refreshFcHistoryUi();
    }
    function unifiedRedo() {
      if (fcBusy()) return;
      if (localCanRedo()) {
        try { readInputHandler()?.performRedo(); } catch (err) {
          console.warn('[agent-bridge] local redo failed', err);
        }
      } else if (fcBe.canRedo) {
        sendToParent({ type: 'redo_requested' });
      }
      refreshFcHistoryUi();
    }
    document.addEventListener('click', (e) => {
      const el = e.target && e.target.closest
        ? e.target.closest('[data-fc-undo], [data-fc-redo]')
        : null;
      if (!el) return;
      e.preventDefault();
      e.stopPropagation();
      const isDisabled = el.tagName === 'BUTTON'
        ? el.disabled
        : el.classList.contains('disabled');
      const fromMenu = !!el.closest('.menu-dropdown');
      if (!isDisabled) {
        if (el.hasAttribute('data-fc-undo')) unifiedUndo();
        else unifiedRedo();
      }
      if (fromMenu) closeOpenMenu();
    }, true);
    // Local edits flip canUndo/canRedo — keep the buttons live. Runs for
    // agent mutations too (harmless: just class toggles).
    eventBus.on('document-changed', () => refreshFcHistoryUi());

    // ── Swallow file-shortcuts we hid from the menu ──
    // file:open / file:new-doc are removed from the menu (doc lifecycle is
    // owned by the FactChat session model), so Ctrl+O / Ctrl+Alt+N are
    // swallowed. Plain Ctrl+S is remapped to the FE download in the doc's
    // original format ('default' — the FE resolves it to hwp/hwpx); without
    // the preventDefault it would fall through to the browser ("Save Page
    // As…"). Ctrl+Shift+S passes through — 다른 이름으로 저장 stays
    // studio-native (the only path with a location/filename picker).
    // Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y are ALWAYS swallowed and routed
    // through the unified undo/redo — even when busy or empty, so the
    // studio's own shortcut map (edit:undo/edit:redo) never runs
    // underneath and can't bypass the turn-boundary invariant.
    window.addEventListener('keydown', (e) => {
      const k = e.key?.toLowerCase();
      // Alt+Shift+V (문서 비교) has no ctrl — swallow before the ctrl
      // guard. The menu/toolbar entries are removed in index.html; the
      // parent FE's 작업 내역 popover replaces the native history UI.
      if (e.altKey && e.shiftKey && k === 'v') {
        e.preventDefault();
        e.stopPropagation();
        return;
      }
      const ctrl = e.ctrlKey || e.metaKey;
      if (!ctrl) return;
      if (k === 'z' || k === 'y') {
        e.preventDefault();
        e.stopPropagation();
        if (k === 'z' && !e.shiftKey) unifiedUndo();
        else unifiedRedo();
        return;
      }
      // Ctrl+Shift+H (문서 이력 관리) — same removal as Alt+Shift+V.
      if (k === 'h' && e.shiftKey) {
        e.preventDefault();
        e.stopPropagation();
        return;
      }
      if (k === 's' && e.shiftKey) return;
      if (k === 's' || k === 'o' || (e.altKey && k === 'n')) {
        e.preventDefault();
        e.stopPropagation();
        if (k === 's' && fcSaveEnabled) {
          sendToParent({ type: 'save_requested', format: 'default' });
        }
      }
    }, true);

    // ── Lock state ──
    // The visible "에이전트 작업 중" indicator is owned by the parent FE
    // (HwpEditor renders a top strip above the iframe). The bridge only
    // disables pointer events on the editor body so the user can't race
    // the agent's mutations. The user still sees the doc updating in
    // real time — no dim, no center pill, no covered toolbar.
    const lockStyle = document.createElement('style');
    lockStyle.textContent = [
      // #editor-area 는 뺀다 — pointer-events:none 이면 스크롤과 드래그 선택까지
      // 죽어서, 사용자에게는 "쓰기 금지"가 아니라 "화면이 멈춤"으로 보인다.
      // 에이전트가 손대지 않는 페이지조차 읽을 수 없었다. 그 자리는 스튜디오
      // readonly(= setLocked 이 켠다)가 메운다: 키 이벤트를 직접 필터링하는 방식은
      // 한글 IME 조합 입력이 preventDefault 를 우회해 새기 쉽다.
      'body.agent-locked #menu-bar, body.agent-locked #icon-toolbar, body.agent-locked #style-bar { pointer-events: none !important; }',
      // rhwp-studio raises a sticky top-right toast on every HWPX load
      // ("HWPX 문서는 저장 시 HWP 형식으로 변환 저장됩니다…"). It covers
      // the toolbar and is redundant with the inline hint in the parent
      // FE's "저장 ▼" menu. `rhwp-toast-container` is an *id* (the
      // bundle uses `document.getElementById(...)`), so the selector
      // must use #, not .
      '#rhwp-toast-container { display: none !important; }',
    ].join('\n');
    document.head.appendChild(lockStyle);

    // ── 잠금 = 툴바 차단(CSS) + 편집 차단(스튜디오 readonly) ──
    //
    // readonly 에는 두 가지 유래가 있고 둘을 구분해야 한다:
    //   viewer     — ?readonly=1 이나 호스트의 setReadonly RPC. 문서를 아무도
    //                바꾸면 안 되는 세션이라 에이전트 RPC 도 거절한다.
    //   agent-turn — editor_lock 으로 브리지가 켠 것. 사용자 입력만 막고 에이전트
    //                편집 RPC 는 통과해야 한다. 이걸 구분하지 않으면 턴 중에
    //                readonly 를 켜는 순간 그 턴의 편집이 전부 거절된다.
    //
    // agentTurnReadonly 는 "지금 readonly 인 이유가 잠금인가"를 뜻한다.
    let agentTurnReadonly = false;
    let preLockEditMode = null;

    function studioEditMode() {
      const api = window.rhwpStudio;
      return api && typeof api.getEditMode === 'function' ? api.getEditMode() : 'normal';
    }

    function setStudioEditMode(mode) {
      const api = window.rhwpStudio;
      if (!api || typeof api.setEditMode !== 'function') return false;
      try {
        api.setEditMode(mode);
        return true;
      } catch (err) {
        console.warn('[agent-bridge] setEditMode 실패:', err);
        return false;
      }
    }

    /** 뷰어 유래 readonly 인가? (에이전트 RPC 를 거절해야 하는 상태) */
    function isViewerReadonly() {
      return studioEditMode() === 'readonly' && !agentTurnReadonly;
    }

    function setLocked(b) {
      document.body.classList.toggle('agent-locked', b);
      if (b) {
        // 이미 viewer readonly 인 세션은 건드리지 않는다 — 잠금이 풀렸다고
        // 뷰어 세션이 편집 가능해지면 안 된다.
        if (agentTurnReadonly || studioEditMode() === 'readonly') return;
        // 양식 모드였다면 그 모드로 정확히 되돌려야 하므로 이전 모드를 기억한다.
        const before = studioEditMode();
        if (setStudioEditMode('readonly')) {
          preLockEditMode = before;
          agentTurnReadonly = true;
        }
      } else if (agentTurnReadonly) {
        setStudioEditMode(preLockEditMode || 'normal');
        agentTurnReadonly = false;
        preLockEditMode = null;
      }
    }

    // ── Suppress "HWPX 비표준 감지" validation modal ──
    // rhwp-studio raises a modal on every HWPX load that references
    // non-standard lineseg (lineseg-per-paragraph dependent on 한컴 textRun
    // reflow). The modal offers "자동 보정 (권장)" / "그대로 보기" — but we
    // already call `reflowLinesegs()` on every refresh() above, so the
    // "auto-fix" is happening regardless. The modal is pure noise that
    // blocks the chat UX until dismissed.
    //
    // The newer rhwp-studio source supports `skipValidationModal` via
    // `agentLoad: true`, and our loadFile handler already passes that —
    // but the deployed bundle (index-ZhKOdagf.js) predates that wiring
    // and renders the modal unconditionally. Until the deployed bundle is
    // rebuilt, we intercept the modal at the DOM level: MutationObserver
    // is set up here, BEFORE any doc load triggers the modal, so when the
    // node is appended to <body> we remove it in the same microtask —
    // before the browser paints. The user sees nothing.
    //
    // We auto-resolve to 자동 보정 (the rhwp-recommended path) by clicking
    // the primary button BEFORE removing the overlay, so the modal's
    // resolver promise completes cleanly and the post-load flow finishes.
    const validationObserver = new MutationObserver((mutations) => {
      for (const m of mutations) {
        for (const node of m.addedNodes) {
          if (!(node instanceof HTMLElement)) continue;
          if (!node.classList || !node.classList.contains('modal-overlay')) continue;
          const titleEl = node.querySelector('.dialog-title');
          if (!titleEl) continue;
          // Match only the validation modal by title text — leave other
          // dialogs (저장 확인, 폰트 누락 등) untouched.
          if (!/HWPX 비표준 감지/.test(titleEl.textContent || '')) continue;
          // Click 자동 보정 first so reflowLinesegs runs and the modal's
          // resolver settles to 'auto-fix' (matches the recommended path).
          const primaryBtn = node.querySelector('.dialog-btn-primary');
          if (primaryBtn instanceof HTMLButtonElement) {
            try { primaryBtn.click(); } catch {}
          }
          // Belt + suspenders: remove the overlay in case the click didn't
          // tear it down synchronously, so it never reaches paint.
          node.style.display = 'none';
          try { node.remove(); } catch {}
        }
      }
    });
    validationObserver.observe(document.body, { childList: true });

    // ── Outline ──
    function buildOutline(maxItems = 200) {
      const doc = getDoc();
      const sections = doc.getSectionCount();
      // Count total paragraphs upfront so the agent knows when its
      // outline is a truncated slice — without this it silently assumes
      // it saw the whole doc, which fails on >200-paragraph government
      // forms and university templates.
      let totalParagraphs = 0;
      for (let s = 0; s < sections; s++) {
        try { totalParagraphs += doc.getParagraphCount(s); } catch {}
      }
      const out = {
        page_count: doc.pageCount(),
        sections,
        source_format: doc.getSourceFormat(),
        paragraphs: [],
        tables: [],
        fields: [],
        total_paragraphs: totalParagraphs,
        truncated: false,
      };
      let count = 0;
      for (let s = 0; s < sections && count < maxItems; s++) {
        const pCount = doc.getParagraphCount(s);
        for (let p = 0; p < pCount && count < maxItems; p++) {
          try {
            const len = doc.getParagraphLength(s, p);
            const preview = (doc.getTextRange(s, p, 0, Math.min(len, 80)) || '').replace(/\s+/g, ' ').trim();
            const path = `s${s}:p${p}`;
            const entry = { path, length: len, preview: preview.slice(0, 80) + (preview.length > 80 ? '…' : '') };
            // Probe ctrl 0..5 — a paragraph that hosts a form table often
            // has an inline image / shape at ctrl=0 and the actual table
            // at ctrl=1 (or higher). Only checking ctrl=0 made the entire
            // 응시원서 form invisible to the agent. 6 probes is cheap;
            // most paragraphs have 0-1 controls so the loop bails fast.
            for (let ctrl = 0; ctrl < 6; ctrl++) {
              const dims = tryGetTableDims(s, p, ctrl);
              if (!dims) continue;
              entry.has_table = true;
              // First cell's text snippet helps the agent see WHAT the
              // table contains without a second round-trip via get_table.
              let firstCellPreview = '';
              try {
                firstCellPreview = (doc.getTextInCell(s, p, ctrl, 0, 0, 0, 60) || '')
                  .replace(/\s+/g, ' ').trim().slice(0, 60);
              } catch {}
              // Tables at ctrl>0 need the explicit :c<n> suffix in their
              // path so the agent's downstream get_table / set_cell_text
              // calls address the right control. ctrl=0 keeps the legacy
              // bare s${s}:p${p} path for backward compatibility.
              const tblPath = ctrl === 0 ? path : `${path}:c${ctrl}`;
              out.tables.push({
                path: tblPath,
                rows: dims.rowCount,
                cols: dims.colCount,
                cells: dims.cellCount,
                ...(firstCellPreview ? { first_cell: firstCellPreview } : {}),
              });
            }
            out.paragraphs.push(entry);
            count++;
          } catch (e) {}
        }
      }
      try { out.fields = JSON.parse(doc.getFieldList()); } catch { out.fields = []; }
      out.truncated = count >= maxItems && totalParagraphs > count;
      return out;
    }

    // ── User focus probe ──
    // Snapshot of where the user is looking right now — caret position +
    // visible page range. Cheap to compute (caret is one WASM call;
    // viewport is derived from the scroll container's offset). Used by
    // the server to prepend a "[system note: user is currently at …]"
    // block to each agent turn so the LLM can resolve spatial deixis
    // ("이 표", "여기", "현재 페이지") without the user repeating
    // themselves. Everything is best-effort — any sub-probe that throws
    // is silently omitted, since stale focus is better than a hard fail.
    function buildUserFocus() {
      const focus = { total_pages: null, caret: null, viewport: null, selection: null };
      const doc = getDoc();
      try { focus.total_pages = doc.pageCount(); } catch {}
      // Caret + selection come from the studio's live CursorState
      // (window.__inputHandler), NOT doc.getCaretPosition(): the WASM caret
      // is decoupled from studio cursor movement and always reports
      // {0,0,0} no matter where the user clicks. Verified empirically
      // 2026-06-18 (rhwp v0.7.13). CursorState is the single source of
      // truth for "where the user is". Best-effort throughout. Falls back
      // to total_pages-only when __inputHandler isn't exposed (older studio
      // bundle), so this is safe to ship ahead of the bundle rebuild.
      const ih = window.__inputHandler;
      const cur = ih && ih.cursor;
      try {
        const pos = cur && cur.getPosition && cur.getPosition();
        if (pos && pos.sectionIndex != null) {
          focus.caret = {
            sec: pos.sectionIndex,
            para: pos.paragraphIndex,
            offset: pos.charOffset,
            path: `s${pos.sectionIndex}:p${pos.paragraphIndex}`,
          };
        }
      } catch {}
      // Cell-block selection (F5 / drag across table cells) takes priority —
      // it's a table-scoped range the agent should act on as cells.
      try {
        if (ih && ih.isInCellSelectionMode && ih.isInCellSelectionMode()) {
          const range = ih.getSelectedCellRange && ih.getSelectedCellRange();
          const ctx = ih.getCellTableContext && ih.getCellTableContext();
          if (range) {
            focus.selection = {
              kind: 'cells',
              table_path: ctx && ctx.sec != null ? `s${ctx.sec}:p${ctx.ppi}` : null,
              start_row: range.startRow, start_col: range.startCol,
              end_row: range.endRow, end_col: range.endCol,
            };
          }
        }
      } catch {}
      // Text selection (drag-highlight). Skipped if a cell selection won.
      try {
        if (!focus.selection && cur && cur.hasSelection && cur.hasSelection()) {
          const sel = cur.getSelectionOrdered && cur.getSelectionOrdered();
          if (sel && sel.start && sel.end) {
            let text = '';
            try {
              const r = safeParse(doc.copySelection(
                sel.start.sectionIndex, sel.start.paragraphIndex, sel.start.charOffset,
                sel.end.paragraphIndex, sel.end.charOffset));
              if (r && r.ok) text = r.text || '';
            } catch {}
            focus.selection = {
              kind: 'text',
              start_path: `s${sel.start.sectionIndex}:p${sel.start.paragraphIndex}`,
              start_offset: sel.start.charOffset,
              end_path: `s${sel.end.sectionIndex}:p${sel.end.paragraphIndex}`,
              end_offset: sel.end.charOffset,
              // Cap the inlined snippet — a multi-page selection must not
              // blow up per-turn context. Server truncates again anyway.
              text: text.length > 500 ? text.slice(0, 500) + '…' : text,
            };
          }
        }
      } catch {}
      // Viewport is the studio's concept, not rhwp's. We map scrollTop
      // → page range via the canvas container's child <canvas> elements
      // (one per page; each carries a data-page-index attribute set by
      // CanvasView). Fall back to null if the container layout changed.
      try {
        const sc = document.getElementById('scroll-container') || document.querySelector('.canvas-scroll-container');
        if (sc) {
          const rect = sc.getBoundingClientRect();
          const top = rect.top;
          const bottom = rect.bottom;
          const pages = sc.querySelectorAll('[data-page-index]');
          let first = null, last = null;
          pages.forEach((el) => {
            const r = el.getBoundingClientRect();
            if (r.bottom < top || r.top > bottom) return;
            const idx = parseInt(el.getAttribute('data-page-index') || '', 10);
            if (Number.isFinite(idx)) {
              if (first == null || idx < first) first = idx;
              if (last == null || idx > last) last = idx;
            }
          });
          if (first != null && last != null) {
            focus.viewport = { first_page: first, last_page: last };
          }
        }
      } catch {}
      return focus;
    }

    // ── Handlers ──
    const handlers = {
      async loadFile(params) {
        const { url, fileName, bytes: providedBytes } = params;
        // Parent (FE) hands us bytes when the source lives behind cookie
        // auth that the iframe origin can't reach. structured-clone
        // preserves Uint8Array across postMessage; an ArrayBuffer is
        // wrapped on the way in. Fall back to fetch(url) when no bytes
        // were provided — keeps the standalone-spike flow working.
        let bytes;
        if (providedBytes) {
          bytes = providedBytes instanceof Uint8Array
            ? providedBytes
            : new Uint8Array(providedBytes);
        } else if (url) {
          const res = await fetch(url);
          if (!res.ok) throw new Error(`fetch ${url}: ${res.status}`);
          bytes = new Uint8Array(await res.arrayBuffer());
        } else {
          throw new Error('loadFile: either bytes or url is required');
        }
        // The full load flow resets zoom/scroll and parks the caret at the
        // document end — fine for opening, jarring for undo/redo/jump.
        // Capture the view before, re-apply after (no-op on a fresh open).
        let savedView = null;
        try {
          const vm = window.__canvasView && window.__canvasView.viewportManager;
          if (vm && typeof vm.getZoom === 'function') {
            savedView = {
              zoom: vm.getZoom(),
              scrollY: typeof vm.getScrollY === 'function' ? vm.getScrollY() : 0,
              caret: null,
            };
            // Caret only on a RE-load — restoring the empty-state cursor
            // on the initial open would focus-steal the chat composer.
            const ih = readInputHandler();
            const pos = originalFileName !== null &&
              ih && ih.cursor && ih.cursor.getPosition && ih.cursor.getPosition();
            if (pos && pos.sectionIndex != null) {
              savedView.caret = {
                sectionIndex: pos.sectionIndex,
                paragraphIndex: pos.paragraphIndex,
                charOffset: pos.charOffset,
              };
            }
          }
        } catch {}
        // Use rhwp-studio's full load flow so CanvasView attaches caret, runs
        // validation, applies font fallback, etc. We listen for the matching
        // :done event to know when loading is finished.
        const requestId = `agent-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
        const resolved = await new Promise((resolve, reject) => {
          const timer = setTimeout(() => reject(new Error('open-document-bytes timeout')), 30_000);
          const off = eventBus.on('open-document-bytes:done', (payload) => {
            const p = payload || {};
            if (p.requestId !== requestId) return;
            clearTimeout(timer);
            off();
            if (p.ok) resolve(true); else reject(new Error(p.error || 'load failed'));
          });
          eventBus.emit('open-document-bytes', {
            bytes,
            fileName: fileName || 'document.hwp',
            fileHandle: null,
            skipUnsavedGuard: true,
            // Suppress the HWPX validation modal — for agent-driven loads we
            // treat warnings as 그대로 보기 (no auto-fix). User sees the doc
            // exactly as the agent sees it via tools.
            agentLoad: true,
            requestId,
          });
        });
        if (savedView) {
          const applyView = () => {
            try {
              const vm = window.__canvasView && window.__canvasView.viewportManager;
              if (!vm) return;
              // Zoom → caret → scroll: moveCursorTo may nudge the
              // viewport, so the user's scroll position goes last.
              if (typeof vm.setZoom === 'function') vm.setZoom(savedView.zoom);
              // moveCursorTo focuses the editor textarea — skip when the
              // parent owns focus (편집 기록 jump) so it isn't yanked.
              if (savedView.caret && document.hasFocus()) {
                const ih = readInputHandler();
                if (ih && typeof ih.moveCursorTo === 'function') {
                  // Restored content may be shorter — fall back to the
                  // paragraph start.
                  const exact = ih.moveCursorTo(savedView.caret);
                  if (!exact) {
                    ih.moveCursorTo({
                      sectionIndex: savedView.caret.sectionIndex,
                      paragraphIndex: savedView.caret.paragraphIndex,
                      charOffset: 0,
                    });
                  }
                }
              }
              if (typeof vm.setScrollTop === 'function') vm.setScrollTop(savedView.scrollY);
            } catch {}
          };
          applyView();
          // Layout may still be settling when :done fires (setScrollTop
          // clamps) — re-apply once after layout, idempotent.
          requestAnimationFrame(() => requestAnimationFrame(applyView));
        }
        const loadedName = fileName || 'document.hwp';
        const sourceFormat = wasm.doc.getSourceFormat();
        cleanSinceLoad = true;
        // Save is meaningful only once a document is loaded — the
        // FactChat 파일 menu items start disabled in the markup.
        setFcSaveEnabled(true);
        originalFileName = loadedName;
        originalHwpxBytes = sourceFormat === 'hwpx' || /\.hwpx$/i.test(loadedName)
          ? new Uint8Array(bytes)
          : null;
        return {
          page_count: wasm.doc.pageCount(),
          source_format: sourceFormat,
          file_name: loadedName,
        };
      },

      // Read
      async outline(params) { return buildOutline(params?.max_items || 200); },
      async getUserFocus() { return buildUserFocus(); },
      async getBlock(params) {
        const { sec, para } = pathToCoords(params.path);
        const doc = getDoc();
        const len = doc.getParagraphLength(sec, para);
        const text = doc.getTextRange(sec, para, 0, len);
        let char_props = null, para_props = null;
        try { char_props = safeParse(doc.getCharPropertiesAt(sec, para, 0)); } catch {}
        try { para_props = safeParse(doc.getParaPropertiesAt(sec, para)); } catch {}
        // 문단 자체의 나누기(쪽/단/구역). ParaShape의 pageBreakBefore와 다른
        // 채널이라 apply_para_style로는 끌 수 없고 remove_page_break를 써야 한다.
        // para_props 안에도 있지만 진단에서 놓치지 않도록 최상위로 올린다.
        const break_type = (para_props && para_props.breakType) || 'none';
        return { path: params.path, text, length: len, char_props, para_props, break_type };
      },
      async getSection(params) {
        const sec = params.sec;
        const doc = getDoc();
        const pCount = doc.getParagraphCount(sec);
        const paragraphs = [];
        for (let p = 0; p < pCount; p++) {
          try {
            const len = doc.getParagraphLength(sec, p);
            const text = doc.getTextRange(sec, p, 0, Math.min(len, 200));
            // 강제 쪽/단 나누기가 걸린 문단을 한 번의 조회로 찾을 수 있게 한다.
            // 이 값이 없던 탓에 "빈 줄마다 페이지가 갈리는" 문서를 진단하려면
            // 문단을 하나씩 찔러봐야 했다.
            // page/column만 싣는다 — section(0x01)은 모든 구역의 첫 문단이 늘
            // 달고 있는 구조 표시라 목록에 나오면 노이즈이고, removePageBreak도
            // 보존 대상이라 손댈 수 없다. 전체 값이 필요하면 getBlock을 쓴다.
            let break_type = 'none';
            try { break_type = safeParse(doc.getParaPropertiesAt(sec, p))?.breakType || 'none'; } catch {}
            const row = { path: `s${sec}:p${p}`, length: len, text };
            if (break_type === 'page' || break_type === 'column') row.break_type = break_type;
            paragraphs.push(row);
          } catch {}
        }
        return { sec, paragraphs };
      },
      // Full-text dump — replaces multi-call find_text exploration. Returns
      // every paragraph's full body text AND every table cell flattened
      // inline with [path]/[rRcC] markers, so the agent reads the whole
      // doc in one round-trip and can map text back to set_cell_text /
      // replace_block_text targets.
      async getFullText(params) {
        const scope = (params && params.scope) || 'doc';
        const doc = getDoc();
        const lines = [];
        let charCount = 0;
        const CELL_HARD_CAP = 2000;
        const PARA_HARD_CAP = 8000;

        function flattenTable(sec, para, ctrl, tblPath) {
          const dims = tryGetTableDims(sec, para, ctrl);
          if (!dims) return;
          lines.push(`[${tblPath} table ${dims.rowCount}x${dims.colCount}]`);
          let bboxes = [];
          try { bboxes = JSON.parse(doc.getTableCellBboxes(sec, para, ctrl)) || []; } catch {}
          if (bboxes.length > 0) {
            const sorted = [...bboxes].sort((a, b) => a.row - b.row || a.col - b.col);
            for (const b of sorted) {
              // Full multi-paragraph cell text. A cell can hold several
              // paragraphs (one per line); render the first on the [rXcY] line
              // and each following paragraph as an indented continuation line
              // aligned under it — so multi-line cells read naturally with no
              // mystery glyph.
              const ct = readCellAllParas(doc, sec, para, ctrl, b.cellIdx, CELL_HARD_CAP).trim();
              const span = (b.rowSpan > 1 || b.colSpan > 1) ? ` span=${b.rowSpan}x${b.colSpan}` : '';
              const tag = `  [r${b.row}c${b.col}${span}] `;
              const cl = ct.split('\n');
              lines.push(tag + cl[0]);
              for (let k = 1; k < cl.length; k++) lines.push(' '.repeat(tag.length) + cl[k]);
              charCount += ct.length;
            }
          } else {
            for (let r = 0; r < dims.rowCount; r++) {
              for (let c = 0; c < dims.colCount; c++) {
                const idx = r * dims.colCount + c;
                const ct = readCellAllParas(doc, sec, para, ctrl, idx, CELL_HARD_CAP).trim();
                const tag = `  [r${r}c${c}] `;
                const cl = ct.split('\n');
                lines.push(tag + cl[0]);
                for (let k = 1; k < cl.length; k++) lines.push(' '.repeat(tag.length) + cl[k]);
                charCount += ct.length;
              }
            }
          }
        }

        function flattenParagraph(s, p) {
          try {
            const len = doc.getParagraphLength(s, p);
            const text = (doc.getTextRange(s, p, 0, Math.min(len, PARA_HARD_CAP)) || '');
            const path = `s${s}:p${p}`;
            if (text.trim()) {
              lines.push(`[${path}] ${text}`);
              charCount += text.length;
            } else {
              lines.push(`[${path}] (empty)`);
            }
            for (let ctrl = 0; ctrl < 6; ctrl++) {
              if (!tryGetTableDims(s, p, ctrl)) continue;
              const tblPath = ctrl === 0 ? path : `${path}:c${ctrl}`;
              flattenTable(s, p, ctrl, tblPath);
            }
          } catch {}
        }

        if (scope === 'table') {
          if (!params || !params.path) throw new Error('get_full_text(scope="table") requires path');
          const { sec, para, ctrl } = pathToCoords(params.path);
          flattenTable(sec, para, ctrl, params.path);
        } else if (scope === 'section') {
          const sec = (params && typeof params.sec === 'number')
            ? params.sec
            : (params && params.path ? parseInt(String(params.path).replace(/^s/, ''), 10) : 0);
          const pCount = doc.getParagraphCount(sec);
          for (let p = 0; p < pCount; p++) flattenParagraph(sec, p);
        } else {
          const sections = doc.getSectionCount();
          for (let s = 0; s < sections; s++) {
            const pCount = doc.getParagraphCount(s);
            for (let p = 0; p < pCount; p++) flattenParagraph(s, p);
          }
        }
        return { scope, text: lines.join('\n'), char_count: charCount };
      },
      async getTable(params) {
        const ref = resolveTablePath(params.path);
        const { sec, para, ctrl } = ref;
        const doc = getDoc();
        const dims = tryTableDimsAt(ref);
        if (!dims) throw new Error(`no table at ${params.path}`);
        // Merge-aware layout: getTableCellBboxes returns the real cellIdx
        // for each (row, col) anchor along with rowSpan/colSpan. The naive
        // formula `cellIdx = row * colCount + col` is wrong for any table
        // with merged cells (= every Korean 응시원서/지원서 form), and
        // caused the agent to write to the wrong visual column. Fall back
        // to the flat formula if the bbox API is unavailable.
        let bboxes = [];
        try { bboxes = tableBboxesAt(ref); } catch {}
        // Nested-table probe budget for the whole call — 27-cell forms use
        // ~250 probes; the cap only bites on pathological 100+-cell tables,
        // where we set nested_scan_truncated instead of stalling the UI.
        let probeBudget = 900;
        const scanCell = (cellIdx) => {
          if (probeBudget <= 0) return null;
          let nParas = 1;
          try { nParas = cellParagraphCountAt(ref, cellIdx); } catch {}
          probeBudget -= Math.min(nParas, 12) * 3;
          try { return scanCellNestedTables(ref, cellIdx); } catch { return []; }
        };
        if (bboxes.length > 0) {
          const cells = bboxes.map(b => {
            // Full multi-paragraph cell text. Newlines kept literal here —
            // this is structured JSON, so the agent can see exactly where the
            // cell's line breaks are (one "\n" per cell paragraph).
            const text = readCellAllParasAt(ref, b.cellIdx, 2000).trim();
            const entry = {
              row: b.row, col: b.col,
              row_span: b.rowSpan, col_span: b.colSpan,
              cell_idx: b.cellIdx,
              text,
              lines: text === '' ? 0 : text.split('\n').length,
            };
            // Non-white solid background → surface it. Header/label rows in
            // Korean forms carry gray shading; the agent needs to SEE fills
            // to keep new/edited rows visually consistent with sibling data
            // rows (and to notice when a header's shading leaked into one).
            const fill = cellFillAt(ref, b.cellIdx);
            if (fill && fill !== '#FFFFFF') entry.fill = fill;
            // Tables nested INSIDE this cell are invisible in the text
            // (their host paragraphs read as "") — surface them explicitly
            // so the agent can address them and never overwrites them
            // blind (the form_19 postmortem: setCellText silently deleted
            // two data tables the read path never showed).
            const nested = scanCell(b.cellIdx);
            if (nested === null) entry.nested_scan_skipped = true;
            else if (nested.length > 0) {
              entry.nested_tables = nested.map(n => ({
                path: nestedTablePath(params.path, b.row, b.col, n.cell_para, n.ctrl),
                rows: n.rows,
                cols: n.cols,
              }));
            }
            return entry;
          });
          // Sort row-major so the agent reads top-to-bottom, left-to-right.
          cells.sort((a, b) => a.row - b.row || a.col - b.col);
          const out = {
            path: params.path,
            rows: dims.rowCount,
            cols: dims.colCount,
            merged: cells.some(c => c.row_span > 1 || c.col_span > 1),
            cells,
          };
          if (probeBudget <= 0) out.nested_scan_truncated = true;
          if (cells.some(c => c.nested_tables)) {
            out.has_nested_tables = true;
            out.nested_note = 'some cells contain nested tables (see nested_tables[].path) — ' +
              'read/edit them via get_table / set_cell_text with that path; ' +
              'set_cell_text on the OUTER cell would destroy them.';
          }
          return out;
        }
        // Fallback (no bbox API): old flat-grid behaviour.
        const cells = [];
        for (let r = 0; r < dims.rowCount; r++) {
          const row = [];
          for (let c = 0; c < dims.colCount; c++) {
            const cellIdx = r * dims.colCount + c;
            try { row.push(readCellAllParasAt(ref, cellIdx, 2000)); }
            catch { row.push(''); }
          }
          cells.push(row);
        }
        return { path: params.path, rows: dims.rowCount, cols: dims.colCount, cells };
      },
      async getFieldList() { return JSON.parse(getDoc().getFieldList()); },
      async getFieldValue(params) {
        try {
          const r = safeParse(getDoc().getFieldValueByName(params.name));
          return { value: r.ok ? r.value : '' };
        } catch { return { value: '' }; }
      },
      async findText(params) {
        const { query, max_results = 20 } = params;
        try {
          const json = getDoc().searchAllText(query, false, true);
          const parsed = safeParse(json);
          // searchAllText returns the result array directly across the
          // rhwp versions we ship — older code only checked .matches /
          // .results and silently returned [] when the WASM gave back a
          // raw array, which made every find_text() call look empty even
          // when matches existed inside table cells. Mirror the bulk-ops
          // parsing pattern (line ~468) which gets this right.
          const arr = Array.isArray(parsed)
            ? parsed
            : (parsed?.matches || parsed?.results || parsed?.items || []);
          return arr.slice(0, max_results);
        } catch (e) {
          console.warn('[bridge] findText failed:', e);
          return [];
        }
      },
      async getWarnings() {
        try { return safeParse(getDoc().getValidationWarnings()); }
        catch { return { warnings: [] }; }
      },
      async getPageInfo(params) { return safeParse(getDoc().getPageInfo(params.page)); },
      async getPageDef(params) { return safeParse(getDoc().getPageDef(params.sec)); },
      async getPageOfPosition(params) {
        const { sec, para } = pathToCoords(params.path);
        return safeParse(getDoc().getPageOfPosition(sec, para));
      },
      async getStyleList() {
        try { return JSON.parse(getDoc().getStyleList()); } catch { return []; }
      },
      async getBookmarks() {
        try { return safeParse(getDoc().getBookmarks()); }
        catch (e) { return { ok: false, error: e.message }; }
      },
      async getHeaderFooterList(params) {
        try { return safeParse(getDoc().getHeaderFooterList(params.sec || 0, true, 0)); }
        catch (e) { return { ok: false, error: e.message }; }
      },
      async getHeaderFooter(params) {
        const { sec = 0, is_header = true, apply_to = 0 } = params;
        try { return safeParse(getDoc().getHeaderFooter(sec, is_header, apply_to)); }
        catch (e) { return { ok: false, error: e.message }; }
      },

      // viewPage — render one page to an offscreen canvas and return it as a
      // PNG so the agent can SEE what the doc looks like. Used for visual
      // self-validation when the user says "it's broken" / "doesn't look
      // right" / asks to verify a visual edit, and for diagnosing layout
      // issues the read tools can't expose (table overflow, header
      // positioning, page break placement, image alignment).
      //
      // Renders via wasm.doc.renderPageToCanvasFiltered with 'all' filter
      // (text + tables + borders + inline images + watermarks) into a
      // *separate* offscreen canvas so the user's viewport is not disturbed.
      //
      // Default scale 1.5 ≈ 1.5× page size in CSS px; A4 (595×842 pt @ 72dpi)
      // → ~893×1263 px PNG → ~80-250 KB base64 → ~1500 vision tokens. Caller
      // can pass scale up to 3.0 (clamped) for closer inspection at the cost
      // of more tokens.
      async viewPage(params) {
        const doc = getDoc();
        const pageCount = doc.pageCount();
        let page = Number.isInteger(params?.page) ? params.page : 0;
        if (page < 0 || page >= pageCount) {
          throw new Error(`page out of range: ${page} (doc has ${pageCount} pages)`);
        }
        let scale = typeof params?.scale === 'number' && isFinite(params.scale) ? params.scale : 1.5;
        scale = Math.max(0.5, Math.min(3.0, scale));

        const info = wasm.getPageInfo ? wasm.getPageInfo(page) : doc.getPageInfo(page);
        const pageInfo = typeof info === 'string' ? safeParse(info) : info;
        const w = Math.max(1, Math.round((pageInfo?.width || 595) * scale));
        const h = Math.max(1, Math.round((pageInfo?.height || 842) * scale));

        const canvas = document.createElement('canvas');
        canvas.width = w;
        canvas.height = h;
        // White background — some pages have transparent margin areas; without
        // this the vision model sees noise at the edges.
        const cx = canvas.getContext('2d');
        if (cx) { cx.fillStyle = '#ffffff'; cx.fillRect(0, 0, w, h); }

        // Prefer 'all' filter (includes BehindText + InFrontOfText images in
        // the bitmap so watermarks/letterheads are visible) when available.
        try {
          if (typeof doc.renderPageToCanvasFiltered === 'function') {
            doc.renderPageToCanvasFiltered(page, canvas, scale, 'all');
          } else {
            doc.renderPageToCanvas(page, canvas, scale);
          }
        } catch (e) {
          throw new Error(`render page ${page} failed: ${e?.message || e}`);
        }

        const dataUrl = canvas.toDataURL('image/png');
        // strip "data:image/png;base64," prefix so callers can b64decode
        // directly without re-parsing the data-URI.
        const comma = dataUrl.indexOf(',');
        const b64 = comma >= 0 ? dataUrl.slice(comma + 1) : dataUrl;
        return {
          page,
          page_count: pageCount,
          width: w,
          height: h,
          scale,
          mime: 'image/png',
          png_base64: b64,
        };
      },

      // Stable IDs — walks every paragraph + table block in the doc and emits
      // {engine_path, stable_id, kind} pairs. stable_id is content-derived:
      //
      //     blk_ + sha256(`${kind}|s${sec}|${dims?}|${text}`)[:16]
      //
      // Same formula on the Python side (factchat/chat/hwp/id_map.py) so a
      // re-walk after an edit can match unchanged blocks even when their
      // engine_path shifted. Blocks whose text changed get a new stable_id —
      // the minter handles that as "new block" semantically.
      async getStableIds() {
        const doc = getDoc();
        const sections = doc.getSectionCount();
        const enc = new TextEncoder();
        async function hashHex(s) {
          const buf = await crypto.subtle.digest('SHA-256', enc.encode(s));
          return Array.from(new Uint8Array(buf))
            .map(b => b.toString(16).padStart(2, '0'))
            .join('');
        }
        const entries = [];
        for (let s = 0; s < sections; s++) {
          const pCount = doc.getParagraphCount(s);
          for (let p = 0; p < pCount; p++) {
            let len = 0;
            let text = '';
            try {
              len = doc.getParagraphLength(s, p);
              text = doc.getTextRange(s, p, 0, len) || '';
            } catch { continue; }
            const paraSig = `para|s${s}|${text}`;
            const paraHash = await hashHex(paraSig);
            entries.push({
              engine_path: `s${s}:p${p}`,
              stable_id: 'blk_' + paraHash.slice(0, 16),
              kind: 'paragraph',
            });
            const dims = tryGetTableDims(s, p, 0);
            if (dims) {
              const tableSig = `table|s${s}|${dims.rowCount}x${dims.colCount}|${text}`;
              const tableHash = await hashHex(tableSig);
              entries.push({
                engine_path: `s${s}:p${p}:c0`,
                stable_id: 'blk_' + tableHash.slice(0, 16),
                kind: 'table',
                rows: dims.rowCount,
                cols: dims.colCount,
              });
            }
          }
        }
        return { entries };
      },

      // Text edit
      async insertText(params) {
        const { sec, para } = pathToCoords(params.path);
        const doc = getDoc();
        doc.beginBatch();
        try {
          doc.insertText(sec, para, params.offset, params.text);
          doc.endBatch();
          refresh();
          return { ok: true };
        } catch (e) { try { doc.endBatch(); } catch {} throw e; }
      },
      async deleteRange(params) {
        const { sec, para } = pathToCoords(params.path);
        const doc = getDoc();
        doc.beginBatch();
        try {
          doc.deleteText(sec, para, params.start, params.end);
          doc.endBatch();
          refresh();
          return { ok: true };
        } catch (e) { try { doc.endBatch(); } catch {} throw e; }
      },
      async replaceBlockText(params) {
        const { sec, para } = pathToCoords(params.path);
        const doc = getDoc();
        const len = doc.getParagraphLength(sec, para);
        doc.beginBatch();
        try {
          if (len > 0) doc.deleteText(sec, para, 0, len);
          doc.insertText(sec, para, 0, params.new_text);
          doc.endBatch();
          refresh();
          return { ok: true };
        } catch (e) { try { doc.endBatch(); } catch {} throw e; }
      },
      async replaceOne(params) {
        const r = safeParse(getDoc().replaceOne(params.query, params.replacement, !!params.case_sensitive));
        refresh();
        return { ok: !!r.ok, replaced: r.replaced ?? (r.ok ? 1 : 0) };
      },
      async replaceAll(params) {
        const r = safeParse(getDoc().replaceAll(params.query, params.replacement, !!params.case_sensitive));
        refresh();
        // The WASM returns {ok, count} — NOT `replaced`. Reading the wrong key
        // made replaceAll always report 0 even when it replaced text (the
        // 2026-06-17 "일괄치환 안먹음" QA bug: agent saw 0 and assumed failure).
        return { ok: !!r.ok, replaced: r.count ?? r.replaced ?? 0 };
      },
      // ── Bulk ops over searchAllText hits ──
      // The agent reaches for these when a single semantic action ("clear
      // placeholder gray/italic", "delete every ◾교사는~~~ line") would
      // otherwise unfold into N×cell tool calls. Server-side iteration
      // makes the agent's intent one call regardless of match count.
      async applyTextStyleToMatches(params) {
        const {
          query,
          props,
          case_sensitive = false,
          include_cells = true,
          max_matches = 200,
        } = params;
        const doc = getDoc();
        let hits = [];
        try {
          const parsed = safeParse(doc.searchAllText(query, !!case_sensitive, !!include_cells));
          hits = (parsed.matches || parsed.results || parsed || []).slice(0, max_matches);
        } catch (e) {
          throw new Error(`searchAllText failed: ${e?.message || e}`);
        }
        if (!Array.isArray(hits) || hits.length === 0) {
          return { ok: true, applied: 0, matches: 0 };
        }
        const wasmProps = translateCharProps(props || {});
        const propsJson = JSON.stringify(wasmProps);
        let applied = 0;
        const failures = [];
        doc.beginBatch();
        try {
          for (const h of hits) {
            const start = h.charOffset;
            const end = h.charOffset + h.length;
            try {
              if (h.cellContext) {
                const c = h.cellContext;
                const r = safeParse(
                  doc.applyCharFormatInCell(h.sec, c.parentPara, c.ctrlIdx, c.cellIdx, c.cellPara, start, end, propsJson)
                );
                if (r.ok === false) throw new Error(r.error || 'applyCharFormatInCell failed');
              } else {
                const r = safeParse(
                  doc.applyCharFormat(h.sec, h.para, start, end, propsJson)
                );
                if (r.ok === false) throw new Error(r.error || 'applyCharFormat failed');
              }
              applied++;
            } catch (err) {
              failures.push({ hit: h, error: err?.message || String(err) });
            }
          }
          doc.endBatch();
        } catch (e) {
          try { doc.endBatch(); } catch {}
          throw e;
        }
        refresh();
        return { ok: failures.length === 0, applied, matches: hits.length, failures: failures.slice(0, 5) };
      },
      async deleteTextMatches(params) {
        const {
          query,
          case_sensitive = false,
          include_cells = true,
          max_matches = 200,
        } = params;
        const doc = getDoc();
        let hits = [];
        try {
          const parsed = safeParse(doc.searchAllText(query, !!case_sensitive, !!include_cells));
          hits = (parsed.matches || parsed.results || parsed || []).slice(0, max_matches);
        } catch (e) {
          throw new Error(`searchAllText failed: ${e?.message || e}`);
        }
        if (!Array.isArray(hits) || hits.length === 0) {
          return { ok: true, deleted: 0, matches: 0 };
        }
        // Group by location key and sort within each group by charOffset
        // DESCENDING so earlier matches in the same paragraph remain valid
        // after later ones are deleted. Cross-paragraph order is irrelevant.
        const locKey = (h) => {
          const c = h.cellContext;
          return c
            ? `c|${h.sec}|${c.parentPara}|${c.ctrlIdx}|${c.cellIdx}|${c.cellPara}`
            : `b|${h.sec}|${h.para}`;
        };
        const groups = new Map();
        for (const h of hits) {
          const k = locKey(h);
          if (!groups.has(k)) groups.set(k, []);
          groups.get(k).push(h);
        }
        for (const arr of groups.values()) arr.sort((a, b) => b.charOffset - a.charOffset);

        let deleted = 0;
        const failures = [];
        doc.beginBatch();
        try {
          for (const arr of groups.values()) {
            for (const h of arr) {
              try {
                if (h.cellContext) {
                  const c = h.cellContext;
                  const r = safeParse(
                    doc.deleteTextInCell(h.sec, c.parentPara, c.ctrlIdx, c.cellIdx, c.cellPara, h.charOffset, h.length)
                  );
                  if (r.ok === false) throw new Error(r.error || 'deleteTextInCell failed');
                } else {
                  const r = safeParse(
                    doc.deleteText(h.sec, h.para, h.charOffset, h.length)
                  );
                  if (r.ok === false) throw new Error(r.error || 'deleteText failed');
                }
                deleted++;
              } catch (err) {
                failures.push({ hit: h, error: err?.message || String(err) });
              }
            }
          }
          doc.endBatch();
        } catch (e) {
          try { doc.endBatch(); } catch {}
          throw e;
        }
        refresh();
        return { ok: failures.length === 0, deleted, matches: hits.length, failures: failures.slice(0, 5) };
      },
      async replaceAllStyled(params) {
        const { query, replacement, props, case_sensitive = false } = params;
        const doc = getDoc();
        const r1 = safeParse(doc.replaceAll(query, replacement, !!case_sensitive));
        const replaced = r1.replaced ?? r1.count ?? 0;
        if (!r1.ok || replaced === 0 || !props) {
          refresh();
          return { ok: !!r1.ok, replaced, styled: 0 };
        }
        // Restyle every freshly-written occurrence. Re-searching on the
        // replacement string is the simplest way to locate the just-written
        // ranges across both body paragraphs and table cells.
        const styleResult = await handlers.applyTextStyleToMatches({
          query: replacement,
          props,
          case_sensitive: true,
          include_cells: true,
          max_matches: Math.max(replaced * 2, 200),
        });
        return {
          ok: r1.ok && (styleResult.ok ?? true),
          replaced,
          styled: styleResult.applied ?? 0,
          style_failures: styleResult.failures ?? [],
        };
      },
      async applyTableTextStyle(params) {
        const { sec, para, ctrl } = pathToCoords(params.path);
        const { props } = params;
        const dims = tryGetTableDims(sec, para, ctrl);
        if (!dims) throw new Error(`no table at ${params.path}`);
        const rowCount = dims.rowCount;
        const colCount = dims.colCount;
        const rowStart = Math.max(0, params.row_start ?? 0);
        const colStart = Math.max(0, params.col_start ?? 0);
        const rowEnd = params.row_end == null || params.row_end < 0 ? rowCount - 1 : Math.min(params.row_end, rowCount - 1);
        const colEnd = params.col_end == null || params.col_end < 0 ? colCount - 1 : Math.min(params.col_end, colCount - 1);
        const cellPara = params.cell_para ?? 0;
        const wasmProps = translateCharProps(props || {});
        const propsJson = JSON.stringify(wasmProps);
        const doc = getDoc();
        let applied = 0;
        let skipped = 0;
        const failures = [];
        doc.beginBatch();
        try {
          // Merge-aware: the flat `row * colCount + col` formula is wrong for
          // any table with merged cells (= every Korean 응시원서/지원서 form)
          // — high indices don't exist (skipped via catch) and low ones hit
          // the wrong visual cell while still reporting ok. Resolve through
          // the bbox anchors like every other cell handler, and dedupe so a
          // merged region spanning several (row,col) positions is styled once.
          const styledCells = new Set();
          for (let row = rowStart; row <= rowEnd; row++) {
            for (let col = colStart; col <= colEnd; col++) {
              const cellIdx = resolveCellIdx(sec, para, ctrl, row, col, colCount);
              if (styledCells.has(cellIdx)) continue;
              styledCells.add(cellIdx);
              // Style EVERY paragraph in the cell. A multi-line cell holds one
              // paragraph per line; styling only cellPara (default 0) left
              // lines 2+ untouched (blue/italic residue on "style whole table",
              // form_08). Honor an explicit cell_para as a single-paragraph target.
              let cellParas;
              if (params.cell_para != null) {
                cellParas = [cellPara];
              } else {
                let nParas = 1;
                try { nParas = doc.getCellParagraphCount(sec, para, ctrl, cellIdx) || 1; } catch {}
                cellParas = Array.from({ length: nParas }, (_, i) => i);
              }
              let cellApplied = 0;
              for (const cp of cellParas) {
                let len = 0;
                try { len = (doc.getTextInCell(sec, para, ctrl, cellIdx, cp, 0, 9999) || '').length; }
                catch { continue; }
                if (len === 0) continue;
                try {
                  const r = safeParse(
                    doc.applyCharFormatInCell(sec, para, ctrl, cellIdx, cp, 0, len, propsJson)
                  );
                  if (r.ok === false) throw new Error(r.error || 'applyCharFormatInCell failed');
                  cellApplied++;
                } catch (err) {
                  failures.push({ row, col, cell_para: cp, error: err?.message || String(err) });
                }
              }
              if (cellApplied > 0) applied++; else skipped++;
            }
          }
          doc.endBatch();
        } catch (e) {
          try { doc.endBatch(); } catch {}
          throw e;
        }
        refresh();
        return {
          ok: failures.length === 0,
          applied,
          skipped,
          range: { row_start: rowStart, row_end: rowEnd, col_start: colStart, col_end: colEnd },
          failures: failures.slice(0, 5),
        };
      },
      async insertParagraphAfter(params) {
        const { sec, para } = pathToCoords(params.path);
        const doc = getDoc();
        doc.beginBatch();
        try {
          // Inherit the source paragraph's shape the way a human pressing
          // Enter at end-of-line does: split the source paragraph at its end.
          // The engine's split_at() carries para_shape_id + the trailing
          // char_shape into the new (empty) paragraph, and the text we then
          // insert adopts that char_shape. The old path — insertParagraph()
          // → Paragraph::new_empty() — produced a blank paragraph with
          // para_shape_id=0 and no char_shapes, so the new line fell back to
          // the document-default shape (smaller font, often center-aligned)
          // instead of matching the list it was appended to.
          const srcLen = doc.getParagraphLength(sec, para);
          doc.splitParagraph(sec, para, srcLen);
          if (params.text) doc.insertText(sec, para + 1, 0, params.text);
          clearInheritedPageBreak(doc, sec, para + 1);
          doc.endBatch();
          refresh();
          // Read-back: confirm the new paragraph actually inherited the
          // source's char + para shape, so a silent regression surfaces as
          // shape_matched=false rather than a wrong-size/alignment line the
          // agent can't see.
          let shape_matched = null;
          try {
            const srcChar = doc.getCharPropertiesAt(sec, para, Math.max(0, srcLen - 1));
            const newChar = doc.getCharPropertiesAt(sec, para + 1, 0);
            const srcPara = normalizeParaShape(doc.getParaPropertiesAt(sec, para));
            const newPara = normalizeParaShape(doc.getParaPropertiesAt(sec, para + 1));
            shape_matched = (srcChar === newChar) && (srcPara === newPara);
          } catch {}
          return { ok: true, new_path: `s${sec}:p${para + 1}`, shape_matched };
        } catch (e) { try { doc.endBatch(); } catch {} throw e; }
      },
      async insertParagraphsAfter(params) {
        const { sec, para } = pathToCoords(params.path);
        const lines = Array.isArray(params.lines) ? params.lines : [];
        if (lines.length === 0) return { ok: false, error: 'lines must not be empty' };
        const formatPath = params.match_format_from || params.path;
        const fmt = pathToCoords(formatPath);
        if (fmt.sec !== sec) return { ok: false, error: 'match_format_from must be in the same section' };
        const doc = getDoc();
        doc.beginBatch();
        try {
          let anchorPara = para;
          const paths = [];
          for (const line of lines) {
            const anchorLen = doc.getParagraphLength(sec, anchorPara);
            doc.splitParagraph(sec, anchorPara, anchorLen);
            const newPara = anchorPara + 1;
            if (line) doc.insertText(sec, newPara, 0, line);
            clearInheritedPageBreak(doc, sec, newPara);
            paths.push(`s${sec}:p${newPara}`);
            anchorPara = newPara;
          }
          doc.endBatch();
          refresh();
          let shape_matched = null;
          try {
            const fmtPara = fmt.para <= para ? fmt.para : fmt.para + lines.length;
            const refLen = doc.getParagraphLength(fmt.sec, fmtPara);
            const refChar = doc.getCharPropertiesAt(fmt.sec, fmtPara, Math.max(0, refLen - 1));
            const refPara = normalizeParaShape(doc.getParaPropertiesAt(fmt.sec, fmtPara));
            shape_matched = paths.every((path) => {
              const current = pathToCoords(path);
              return (
                doc.getCharPropertiesAt(current.sec, current.para, 0) === refChar
                && normalizeParaShape(doc.getParaPropertiesAt(current.sec, current.para)) === refPara
              );
            });
          } catch {}
          return {
            ok: true,
            inserted: lines.length,
            paths,
            first_path: paths[0],
            last_path: paths[paths.length - 1],
            shape_matched,
          };
        } catch (e) { try { doc.endBatch(); } catch {} throw e; }
      },
      async deleteParagraph(params) {
        const { sec, para } = pathToCoords(params.path);
        const doc = getDoc();
        doc.beginBatch();
        try {
          doc.deleteParagraph(sec, para);
          doc.endBatch();
          refresh();
          return { ok: true };
        } catch (e) { try { doc.endBatch(); } catch {} throw e; }
      },
      // Reformat `to_path` to match `reference_path` on BOTH axes that govern
      // how a list item lines up:
      //   1. Paragraph + character shape (indent, margins, alignment, font).
      //      Copied BY REFERENCE — we DON'T read reference props and re-apply
      //      them: getParaPropertiesAt emits a 96-DPI dialog projection (px,
      //      with the hanging indent folded into marginLeft, plus an HWP3-
      //      variant branch), so round-tripping through applyParaFormat
      //      double-counts the indent and mis-scales. Splitting the reference
      //      paragraph at its end carries para_shape_id + the trailing
      //      char_shape into the new empty paragraph unit-free.
      //   2. Leading-whitespace prefix. Korean form docs (gov/univ templates)
      //      very often align sub-items with literal leading spaces in the
      //      TEXT while paragraph indent stays 0 (e.g. "     5. …"). Shape copy
      //      alone leaves a new line flush-left under such a list, so we strip
      //      the target's own leading whitespace and re-apply the reference's.
      // The line ends up directly after the reference — the natural "make this
      // line match the one it sits under" case.
      async matchParagraphFormat(params) {
        const ref = pathToCoords(params.reference_path);
        const tgt = pathToCoords(params.to_path);
        const doc = getDoc();
        if (ref.sec !== tgt.sec) {
          return { ok: false, error: 'match across sections is not supported' };
        }
        if (ref.para === tgt.para) {
          return { ok: false, error: 'reference and target are the same paragraph' };
        }
        // Leading run of spaces / tabs / full-width spaces (U+3000) / NBSP.
        const LEAD_WS = /^[ \t　 ]*/;
        doc.beginBatch();
        try {
          const tgtLen = doc.getParagraphLength(tgt.sec, tgt.para);
          const rawText = doc.getTextRange(tgt.sec, tgt.para, 0, tgtLen);
          // Delete first so reference-index bookkeeping is trivial afterward.
          doc.deleteParagraph(tgt.sec, tgt.para);
          const refAfter = ref.para > tgt.para ? ref.para - 1 : ref.para;
          const refLen = doc.getParagraphLength(ref.sec, refAfter);
          const refText = doc.getTextRange(ref.sec, refAfter, 0, refLen);
          // Reproduce the reference's leading-whitespace indentation on the
          // target body (its own leading whitespace stripped first).
          const refLead = (refText.match(LEAD_WS) || [''])[0];
          const text = refLead + rawText.replace(LEAD_WS, '');
          doc.splitParagraph(ref.sec, refAfter, refLen);
          const newPara = refAfter + 1;
          if (text) doc.insertText(ref.sec, newPara, 0, text);
          doc.endBatch();
          refresh();
          // Read-back: confirm the VISIBLE formatting transferred. We compare
          // the fields a user actually sees (alignment, indent, margins, list
          // head type) rather than full-JSON equality — split intentionally
          // advances per-instance numbering counters, and a reference with
          // mixed character runs contributes its trailing run, so a strict
          // whole-object compare would report false mismatches.
          let shape_matched = null;
          try {
            const rp = JSON.parse(doc.getParaPropertiesAt(ref.sec, refAfter));
            const np = JSON.parse(doc.getParaPropertiesAt(ref.sec, newPara));
            const fields = ['alignment', 'indent', 'marginLeft', 'marginRight', 'headType'];
            // char: split copies the reference's trailing run → compare that.
            const rc = doc.getCharPropertiesAt(ref.sec, refAfter, Math.max(0, refLen - 1));
            const nc = doc.getCharPropertiesAt(ref.sec, newPara, 0);
            // leading-whitespace indentation transferred?
            const newLen = doc.getParagraphLength(ref.sec, newPara);
            const newText = doc.getTextRange(ref.sec, newPara, 0, newLen);
            const leadOk = (newText.match(LEAD_WS) || [''])[0] === refLead;
            shape_matched = fields.every((f) => np[f] === rp[f]) && rc === nc && leadOk;
          } catch {}
          return { ok: true, new_path: `s${ref.sec}:p${newPara}`, shape_matched };
        } catch (e) { try { doc.endBatch(); } catch {} throw e; }
      },
      async insertPageBreak(params) {
        const { sec, para } = pathToCoords(params.path);
        const doc = getDoc();
        const beforePages = doc.pageCount();
        const snapshotId = doc.saveSnapshot();
        doc.beginBatch();
        try {
          const result = safeParse(doc.insertPageBreak(sec, para, params.offset || 0));
          doc.endBatch();
          const afterPages = doc.pageCount();
          if (afterPages <= beforePages) {
            const restoreResult = safeParse(doc.restoreSnapshot(snapshotId));
            refresh();
            const kind = afterPages < beforePages ? 'unsafe shrink' : 'no page growth';
            throw new Error(`insertPageBreak ${kind}: ${beforePages} -> ${afterPages} at ${params.path}:${params.offset || 0}; restored=${JSON.stringify(restoreResult)}`);
          }
          refresh();
          return { ok: true, result, before_pages: beforePages, after_pages: afterPages };
        } catch (e) { try { doc.endBatch(); } catch {} throw e; }
      },
      // 문단에 걸린 강제 나누기(쪽/단/구역) 해제 — insertPageBreak의 짝.
      // 이 나누기는 ParaShape의 pageBreakBefore와 다른 채널이라
      // applyParaStyle{pageBreakBefore:false}로는 꺼지지 않는다(changed:false만
      // 돌아온다). 지금까지는 문단을 통째로 지우는 것 말고는 방법이 없어서
      // 여백용 빈 줄을 지우고 문단 간격으로 다시 채워 넣어야 했다.
      // 문단은 보존되므로 텍스트·서식·문단 안 그림/표가 그대로 남는다.
      async removePageBreak(params) {
        const { sec, para } = pathToCoords(params.path);
        const doc = getDoc();
        const beforePages = doc.pageCount();
        doc.beginBatch();
        try {
          const result = safeParse(doc.removePageBreak(sec, para));
          doc.endBatch();
          refresh();
          return {
            ok: true,
            changed: result?.changed === true,
            before_pages: beforePages,
            after_pages: doc.pageCount(),
          };
        } catch (e) { try { doc.endBatch(); } catch {} throw e; }
      },

      // Format
      // start/end are paragraph-relative char offsets. Omit (or pass end<0)
      // to mean "to end of paragraph" — bridge fills via getParagraphLength
      // so the agent doesn't have to measure Korean text length itself. The
      // agent was passing range:[0,10] for 30-char titles and only the
      // first run was getting the new char shape (multi-run paragraphs).
      async applyTextStyle(params) {
        const { sec, para } = pathToCoords(params.path);
        const { props } = params;
        const doc = getDoc();
        let start = (params.start === undefined || params.start === null) ? 0 : params.start;
        let end = params.end;
        if (end === undefined || end === null || end < 0) {
          try { end = doc.getParagraphLength(sec, para); }
          catch (e) { throw new Error(`getParagraphLength(${sec},${para}) failed: ${e?.message || e}`); }
        }
        if (end <= start) {
          return { ok: false, error: `range is empty (start=${start} end=${end} at ${params.path})` };
        }
        const wasmProps = translateCharProps(props);
        let beforeShape = null;
        try { beforeShape = doc.getCharPropertiesAt(sec, para, start); } catch {}
        const r = safeParse(doc.applyCharFormat(sec, para, start, end, JSON.stringify(wasmProps)));
        if (!r.ok && r.raw === undefined) throw new Error(r.error || 'applyCharFormat failed');
        refresh();
        // Read-back: confirm the char shape actually moved. changed=false means
        // the engine accepted the call but the run was already in that state, OR
        // the format was clamped/ignored — surface it so the agent doesn't claim
        // a visible change that never happened.
        let afterShape = null, changed = null;
        try { afterShape = doc.getCharPropertiesAt(sec, para, start); } catch {}
        if (beforeShape !== null && afterShape !== null) changed = beforeShape !== afterShape;
        return { ok: true, applied_to: { start, end }, changed };
      },
      // Scale the paragraph's character font size by a ratio (e.g. 1.5x).
      // Bridge reads the current size from getCharPropertiesAt so the agent
      // doesn't have to do unit math — fontSize in the WASM is HWPUnit
      // (= pt × 100), but the tool surface uses points. Returns the
      // before/after pt so the agent can quote them back.
      async scaleParagraphFont(params) {
        const { sec, para } = pathToCoords(params.path);
        const multiplier = +params.multiplier;
        if (!isFinite(multiplier) || multiplier <= 0) {
          throw new Error(`scale multiplier must be > 0, got ${params.multiplier}`);
        }
        const doc = getDoc();
        // Pull the FULL current char shape — earlier attempts that sent only
        // {fontSize: ...} sometimes left rhwp's render unchanged (suspected
        // replace-not-merge semantics). Reading the full shape and re-applying
        // it with only `fontSize` mutated removes any ambiguity.
        let currentShape = null;
        try { currentShape = JSON.parse(doc.getCharPropertiesAt(sec, para, 0)); }
        catch (e) { throw new Error(`getCharPropertiesAt(${sec},${para}) failed: ${e?.message || e}`); }
        const currentHwpUnit = (currentShape && currentShape.fontSize | 0) || 0;
        if (!currentHwpUnit) throw new Error(`no font size at ${params.path}`);
        const currentPt = currentHwpUnit / 100;
        const targetHwpUnit = Math.round(currentPt * multiplier * 100);
        const targetPt = targetHwpUnit / 100;
        const len = doc.getParagraphLength(sec, para);
        if (len <= 0) return { ok: false, error: `paragraph empty at ${params.path}` };
        // Defensive: strip out keys that applyCharFormat won't accept as
        // input (server-emitted readonly stuff). Whitelist the props we
        // actually want to preserve.
        const PRESERVE = ['bold','italic','underline','underlineType','underlineColor',
          'strikethrough','fontFamily','textColor','shadeColor','fillColor',
          'subscript','superscript','outlineType','emphasisDot'];
        const props = { fontSize: targetHwpUnit };
        for (const k of PRESERVE) {
          if (currentShape[k] !== undefined && currentShape[k] !== null) {
            props[k] = currentShape[k];
          }
        }
        const r = safeParse(doc.applyCharFormat(sec, para, 0, len, JSON.stringify(props)));
        if (!r.ok && r.raw === undefined) throw new Error(r.error || 'applyCharFormat failed');
        refresh();
        // Verify the change actually landed by re-reading. Surface a clear
        // error if rhwp silently ignored us (e.g. some preset clamp).
        let verifyPt = null;
        try {
          const v = JSON.parse(doc.getCharPropertiesAt(sec, para, 0));
          verifyPt = (v.fontSize | 0) / 100;
        } catch {}
        return {
          ok: true,
          before_pt: currentPt,
          after_pt: targetPt,
          verified_pt: verifyPt,
          changed: verifyPt === targetPt,
          length: len,
        };
      },
      async applyParaStyle(params) {
        const { sec, para } = pathToCoords(params.path);
        const doc = getDoc();
        const wasmProps = translateParaProps(params.props);
        let beforeShape = null;
        try { beforeShape = doc.getParaPropertiesAt(sec, para); } catch {}
        const r = safeParse(doc.applyParaFormat(sec, para, JSON.stringify(wasmProps)));
        if (!r.ok && r.raw === undefined) throw new Error(r.error || 'applyParaFormat failed');
        refresh();
        // Read-back: alignment / indent / spacing that doesn't move the paragraph
        // shape (e.g. "center" when already centered, or a value the engine
        // rejected) comes back changed=false.
        let afterShape = null, changed = null;
        try { afterShape = doc.getParaPropertiesAt(sec, para); } catch {}
        if (beforeShape !== null && afterShape !== null) changed = beforeShape !== afterShape;
        return { ok: true, changed };
      },
      async applyStyleByName(params) {
        const { sec, para } = pathToCoords(params.path);
        const styles = JSON.parse(getDoc().getStyleList());
        const target = styles.find(s => s.name === params.style_name);
        if (!target) throw new Error(`style not found: ${params.style_name}`);
        const r = safeParse(getDoc().applyStyle(sec, para, target.id));
        refresh();
        return { ok: true, style_id: target.id };
      },
      async createStyle(params) {
        const newId = getDoc().createStyle(JSON.stringify({
          name: params.name,
          englishName: params.english_name || params.name,
          type: params.type || 0,
          nextStyleId: 0,
        }));
        if (newId < 0) throw new Error('createStyle failed');
        return { ok: true, style_id: newId };
      },

      // Tables
      async setCellText(params) {
        const ref = resolveTablePath(params.path);
        const { sec, para } = ref;
        const ctrl = ref.hops[ref.hops.length - 1].controlIndex;
        let { row, col, text, col_count } = params;
        const doc = getDoc();
        if (col_count === undefined || col_count === null) {
          const dims = tryTableDimsAt(ref);
          col_count = dims?.colCount;
          if (!col_count) throw new Error(`no table at ${params.path}`);
        }
        const cellIdx = resolveCellIdxAt(ref, row, col);
        text = text || '';
        // Resolve the ANCHOR bbox of the cell we actually landed on. A (row,col)
        // that falls inside a merged region (colSpan/rowSpan) resolves silently
        // to the enclosing anchor — so the write goes to a cell whose coords are
        // NOT the ones the caller named. Surfacing {row,col,span} lets the agent
        // detect "I addressed a covered slot / a different cell than I meant"
        // (the form_21 wrong-cell postmortem: verified=true couldn't catch it).
        let _resolved = null;
        try {
          const _bx = tableBboxesAt(ref);
          const _b = _bx.find((b) => b.cellIdx === cellIdx);
          if (_b) _resolved = {
            row: _b.row, col: _b.col, row_span: _b.rowSpan, col_span: _b.colSpan,
            addressed_interior: _b.row !== row || _b.col !== col,
          };
        } catch {}
        // GUARDRAIL: a cell can host nested tables that the text read path
        // does not show (their host paragraphs read as ""). Collapsing the
        // cell would silently delete them AND their data — and the text
        // read-back below would still report verified=true (the form_19
        // postmortem). Refuse unless the caller explicitly forces.
        if (params.force !== true) {
          const nested = scanCellNestedTables(ref, cellIdx);
          if (nested.length > 0) {
            return {
              ok: false,
              error: 'cell_contains_nested_tables',
              nested_tables: nested.map(n => ({
                path: nestedTablePath(params.path, row, col, n.cell_para, n.ctrl),
                rows: n.rows,
                cols: n.cols,
              })),
              hint: 'This cell hosts nested table(s) that a full-cell rewrite would DELETE. ' +
                'To edit a nested table cell, call set_cell_text with the nested table path ' +
                'above. To really replace the whole cell including its tables, pass force=true.',
            };
          }
        }
        // Per-cell hop json for the *InCellByPath calls at this paragraph.
        const cp = (cellPara) => cellPathJsonAt(ref, cellIdx, cellPara);
        const byPath = typeof doc.insertTextInCellByPath === 'function';
        if (ref.nested && !byPath) throw new Error('nested tables need a newer WASM (insertTextInCellByPath missing)');
        const delText = (p, start, count) => byPath
          ? doc.deleteTextInCellByPath(sec, para, cp(p), start, count)
          : doc.deleteTextInCell(sec, para, ctrl, cellIdx, p, start, count);
        const insText = (p, start, t) => byPath
          ? doc.insertTextInCellByPath(sec, para, cp(p), start, t)
          : doc.insertTextInCell(sec, para, ctrl, cellIdx, p, start, t);
        const getText = (p) => {
          try {
            return byPath
              ? (doc.getTextInCellByPath(sec, para, cp(p), 0, 9999) || '')
              : (doc.getTextInCell(sec, para, ctrl, cellIdx, p, 0, 9999) || '');
          } catch { return ''; }
        };
        const paraCount = () => { try { return cellParagraphCountAt(ref, cellIdx); } catch { return 1; } };
        const mergePara = (p) => {
          if (typeof doc.mergeParagraphInCellByPath === 'function') return doc.mergeParagraphInCellByPath(sec, para, cp(p));
          if (!ref.nested) return doc.mergeParagraphInCell(sec, para, ctrl, cellIdx, p);
        };
        const splitPara = (p, at) => {
          if (typeof doc.splitParagraphInCellByPath === 'function') return doc.splitParagraphInCellByPath(sec, para, cp(p), at);
          return doc.splitParagraphInCell(sec, para, ctrl, cellIdx, p, at);
        };
        // An HWP cell holds MULTIPLE paragraphs. A literal "\n" stuffed into a
        // single cell paragraph is NOT a line break — the renderer's width
        // reflow ignores it, so the text runs off the page edge. So split on
        // "\n" and write one cell paragraph per line. splitParagraphInCell
        // carries the cell paragraph's shape into the new line (same as Enter).
        // Capture the cell's PRIOR content before we clear it. set_cell_text is a
        // full replace, so a wrong-cell write silently destroys whatever was here
        // AND still reports verified=true (read-back only checks the text we just
        // wrote). Returning previous_text makes every overwrite auditable and lets
        // the agent notice it just replaced unrelated content (form_21 postmortem).
        let previous_text = '';
        try {
          const _pc = paraCount();
          const _prev = [];
          for (let p = 0; p < _pc; p++) _prev.push(getText(p));
          previous_text = _prev.join('\n');
        } catch {}
        const segments = text.split('\n');
        doc.beginBatch();
        try {
          // 1) Collapse the cell to a single empty paragraph — handles re-writes
          //    of cells that already hold several paragraphs (clear each, then
          //    merge the extras down into paragraph 0).
          const pcount = paraCount();
          for (let p = pcount - 1; p >= 0; p--) {
            const len = getText(p).length;
            if (len > 0) delText(p, 0, len);
            if (p > 0) { try { mergePara(p); } catch {} }
          }
          // 2) Write each line as its own cell paragraph.
          insText(0, 0, segments[0]);
          for (let i = 1; i < segments.length; i++) {
            const prev = i - 1;
            let len = 0;
            try { len = doc.getCellParagraphLength && !ref.nested
              ? doc.getCellParagraphLength(sec, para, ctrl, cellIdx, prev)
              : getText(prev).length; }
            catch { len = getText(prev).length; }
            splitPara(prev, len);
            if (segments[i]) insText(i, 0, segments[i]);
          }
          // 3) Normalize justify → left on the written paragraphs. Korean form
          //    cells default to 양쪽정렬(justify); justify is visually identical
          //    to left for any line that doesn't wrap, but on a WRAPPED line it
          //    spreads the words edge-to-edge (the ugly gaps in a narrow cell).
          //    So downgrade justify/distribute to left — never worse, fixes the
          //    wrap case. center/right are intentional and left untouched.
          //    (Body-level tables only — the *InCell format APIs have no
          //    ByPath variants yet, so nested writes keep the template align.)
          if (!ref.nested &&
              typeof doc.applyParaFormatInCell === 'function' &&
              typeof doc.getCellParaPropertiesAt === 'function') {
            for (let i = 0; i < segments.length; i++) {
              try {
                const a = JSON.parse(doc.getCellParaPropertiesAt(sec, para, ctrl, cellIdx, i)).alignment;
                if (a === 'justify' || a === 'distribute') {
                  doc.applyParaFormatInCell(sec, para, ctrl, cellIdx, i, JSON.stringify({ alignment: 'left' }));
                }
              } catch {}
            }
          }
          doc.endBatch();
          refresh();
          // Read-back: reconstruct the cell as paragraph0\nparagraph1\n… and
          // compare to the requested text. verified=false means the write didn't
          // land (bad cellIdx, merged-region surprise, line count mismatch) — so
          // the agent doesn't report a cell as filled when it isn't. `lines` is
          // the resulting cell paragraph count (1 for single-line text).
          let verified = null, lines = null;
          try {
            const n = paraCount();
            const got = [];
            for (let p = 0; p < n; p++) got.push(getText(p));
            lines = got.length;
            verified = got.join('\n') === text;
          } catch {}
          // AUTO-FIT ROW HEIGHT: rhwp draws table rows at their stored (fixed)
          // height and clips overflow; native 한글 grows the row to fit. After
          // writing this cell, measure — via the render tree — whether its
          // content now overflows the cell box, and if so grow just this row to
          // fit. GROW-ONLY and MEASURED: a cell whose content already fits
          // reports overflow<=0 and is never touched, so this can only ADD
          // height where text truly clips (no side effect on fitting cells).
          // Body-level tables only (resizeTableCells has no *ByPath variant).
          // Fully best-effort: any failure falls through to the normal result.
          try {
            if (!ref.nested && typeof doc.getPageRenderTree === 'function') {
              autoFitCellRow(doc, sec, para, ctrl, row, col);
            }
          } catch {}
          return {
            ok: true, verified, lines,
            previous_text,
            replaced_nonempty: previous_text.trim().length > 0,
            resolved: _resolved,
          };
        } catch (e) { try { doc.endBatch(); } catch {} throw e; }
      },
      async fillEmptyTableCells(params) {
        const { sec, para, ctrl } = pathToCoords(params.path);
        const doc = getDoc();
        const dims = tryGetTableDims(sec, para, ctrl);
        if (!dims) throw new Error(`no table at ${params.path}`);

        const rowStart = Math.max(0, params.row_start ?? 0);
        const rowEnd = params.row_end == null || params.row_end < 0
          ? dims.rowCount - 1
          : Math.min(params.row_end, dims.rowCount - 1);
        const colStart = Math.max(0, params.col_start ?? 0);
        const colEnd = params.col_end == null || params.col_end < 0
          ? dims.colCount - 1
          : Math.min(params.col_end, dims.colCount - 1);
        const maxCells = params.max_cells ?? 500;
        const text = params.text || '';
        const segments = text.split('\n');

        let anchors = [];
        try {
          const bboxes = JSON.parse(doc.getTableCellBboxes(sec, para, ctrl)) || [];
          anchors = bboxes.map(b => ({
            row: b.row,
            col: b.col,
            cellIdx: b.cellIdx,
            row_span: b.rowSpan,
            col_span: b.colSpan,
          }));
        } catch {}
        if (anchors.length === 0) {
          for (let r = 0; r < dims.rowCount; r++) {
            for (let c = 0; c < dims.colCount; c++) {
              anchors.push({ row: r, col: c, cellIdx: r * dims.colCount + c, row_span: 1, col_span: 1 });
            }
          }
        }
        anchors = anchors
          .filter(a => a.row >= rowStart && a.row <= rowEnd && a.col >= colStart && a.col <= colEnd)
          .sort((a, b) => a.row - b.row || a.col - b.col);

        const failures = [];
        const filledCells = [];
        let scanned = 0;
        let skippedNonEmpty = 0;
        let truncated = false;

        doc.beginBatch();
        try {
          for (const a of anchors) {
            scanned += 1;
            if (filledCells.length >= maxCells) { truncated = true; break; }
            let existing = '';
            try {
              existing = readCellAllParas(doc, sec, para, ctrl, a.cellIdx, 9999).trim();
            } catch (e) {
              failures.push({ row: a.row, col: a.col, error: e?.message || String(e) });
              continue;
            }
            if (existing !== '') {
              skippedNonEmpty += 1;
              continue;
            }
            // A cell whose TEXT reads empty can still host nested tables
            // (their anchor paragraphs have no text). Filling it would
            // collapse the cell and delete them — skip like non-empty.
            try {
              const fillRef = { sec, para, ctrl, hops: [{ controlIndex: ctrl, cellIndex: 0, cellParaIndex: 0 }], nested: false };
              if (scanCellNestedTables(fillRef, a.cellIdx).length > 0) {
                skippedNonEmpty += 1;
                continue;
              }
            } catch {}

            try {
              let pcount = 1;
              try { pcount = doc.getCellParagraphCount(sec, para, ctrl, a.cellIdx) || 1; } catch {}
              for (let p = pcount - 1; p >= 0; p--) {
                let len = 0;
                try { len = (getCellTextCompat(doc, sec, para, ctrl, a.cellIdx, p, 0, 9999) || '').length; } catch {}
                if (len > 0) deleteCellTextCompat(doc, sec, para, ctrl, a.cellIdx, p, 0, len);
                if (p > 0) { try { doc.mergeParagraphInCell(sec, para, ctrl, a.cellIdx, p); } catch {} }
              }
              insertCellTextCompat(doc, sec, para, ctrl, a.cellIdx, 0, 0, segments[0]);
              for (let i = 1; i < segments.length; i++) {
                const prev = i - 1;
                let len = 0;
                try { len = doc.getCellParagraphLength(sec, para, ctrl, a.cellIdx, prev); }
                catch { len = (getCellTextCompat(doc, sec, para, ctrl, a.cellIdx, prev, 0, 9999) || '').length; }
                doc.splitParagraphInCell(sec, para, ctrl, a.cellIdx, prev, len);
                if (segments[i]) insertCellTextCompat(doc, sec, para, ctrl, a.cellIdx, i, 0, segments[i]);
              }
              filledCells.push({ row: a.row, col: a.col, row_span: a.row_span, col_span: a.col_span });
            } catch (e) {
              failures.push({ row: a.row, col: a.col, error: e?.message || String(e) });
            }
          }
          doc.endBatch();
        } catch (e) {
          try { doc.endBatch(); } catch {}
          throw e;
        }

        refresh();
        let verified = true;
        for (const a of filledCells) {
          const cellIdx = resolveCellIdx(sec, para, ctrl, a.row, a.col, dims.colCount);
          try {
            const got = readCellAllParas(doc, sec, para, ctrl, cellIdx, 9999).trim();
            if (got !== text.trim()) verified = false;
          } catch {
            verified = false;
          }
        }
        return {
          ok: failures.length === 0,
          filled: filledCells.length,
          scanned,
          skipped_non_empty: skippedNonEmpty,
          truncated,
          verified,
          range: { row_start: rowStart, row_end: rowEnd, col_start: colStart, col_end: colEnd },
          cells: filledCells.slice(0, 50),
          failures,
        };
      },
      // setCellText only replaces content — the cell template's character
      // formatting (italic/color from the original HWPX style sheet) sticks
      // to the new text. This is the format-override path: same prop shape
      // as applyTextStyle, but addresses a (row, col) inside a table.
      // `cell_para` defaults to 0 (cells typically have one paragraph).
      // `end < 0` means "to end of cell paragraph" — we measure via
      // getTextInCell so the agent doesn't have to know the length.
      async applyCellTextStyle(params) {
        const { sec, para, ctrl } = pathToCoords(params.path);
        const { row, col, props } = params;
        const cellPara = params.cell_para ?? 0;
        let { start, end, col_count } = params;
        if (col_count === undefined || col_count === null) {
          const dims = tryGetTableDims(sec, para, ctrl);
          col_count = dims?.colCount;
          if (!col_count) throw new Error(`no table at ${params.path}`);
        }
        const cellIdx = resolveCellIdx(sec, para, ctrl, row, col, col_count);
        const doc = getDoc();
        if (start === undefined || start === null) start = 0;
        if (end === undefined || end === null || end < 0) {
          let cellText = '';
          try { cellText = doc.getTextInCell(sec, para, ctrl, cellIdx, cellPara, 0, 9999) || ''; }
          catch (e) { throw new Error(`failed to read cell (${row},${col}): ${e?.message || e}`); }
          end = cellText.length;
        }
        if (end <= start) {
          // Empty cell — applying char format to a zero-length range would
          // succeed silently and look like a bug. Surface it.
          return { ok: false, error: `cell (${row},${col}) range is empty (start=${start} end=${end})` };
        }
        const wasmProps = translateCharProps(props);
        const r = safeParse(
          doc.applyCharFormatInCell(sec, para, ctrl, cellIdx, cellPara, start, end, JSON.stringify(wasmProps))
        );
        if (!r.ok && r.raw === undefined) throw new Error(r.error || 'applyCharFormatInCell failed');
        refresh();
        return { ok: true, applied_to: { row, col, cell_para: cellPara, start, end } };
      },
      // Set a cell's BACKGROUND fill color (셀 채우기색 / 배경색). The WASM gates
      // the fill path on the JSON also carrying border definitions, so we read
      // the cell's current properties (which already include borderLeft/Right/
      // Top/Bottom + the existing fill) via getCellProperties, flip
      // fillType→solid + fillColor, and write the whole object back — borders
      // are round-tripped untouched. color: '#RRGGBB' (use '#FFFFFF' to clear a
      // gray placeholder fill to white).
      async setCellFill(params) {
        const { sec, para, ctrl } = pathToCoords(params.path);
        const { row, col, color } = params;
        let { col_count } = params;
        const doc = getDoc();
        if (col_count === undefined || col_count === null) {
          const dims = tryGetTableDims(sec, para, ctrl);
          col_count = dims?.colCount;
          if (!col_count) throw new Error(`no table at ${params.path}`);
        }
        const cellIdx = resolveCellIdx(sec, para, ctrl, row, col, col_count);
        let props;
        try { props = JSON.parse(doc.getCellProperties(sec, para, ctrl, cellIdx)); }
        catch (e) { throw new Error(`failed to read cell (${row},${col}): ${e?.message || e}`); }
        const norm = (c) => (typeof c === 'string' ? c.trim().toLowerCase() : c);
        const before = { fillType: props.fillType, fillColor: props.fillColor };
        props.fillType = 'solid';
        props.fillColor = color;
        doc.beginBatch();
        try {
          const r = safeParse(doc.setCellProperties(sec, para, ctrl, cellIdx, JSON.stringify(props)));
          doc.endBatch();
          if (!r.ok && r.raw === undefined) throw new Error(r.error || 'setCellProperties failed');
          refresh();
          // Read-back: verified = the cell IS now the requested color (the fill
          // took). changed = the color actually moved from before (false when it
          // was already that color — a no-op, not a failure).
          let after = null, changed = null, verified = null;
          try {
            const v = JSON.parse(doc.getCellProperties(sec, para, ctrl, cellIdx));
            after = { fillType: v.fillType, fillColor: v.fillColor };
            verified = v.fillType === 'solid' && norm(v.fillColor) === norm(color);
            changed = norm(before.fillColor) !== norm(after.fillColor) || before.fillType !== after.fillType;
          } catch {}
          return { ok: true, applied_to: { row, col }, before, after, changed, verified };
        } catch (e) { try { doc.endBatch(); } catch {} throw e; }
      },
      // Structural row/col ops reach ANY nesting depth via the *ByPath WASM
      // APIs (hop-list JSON, same grammar as getTableDimensionsByPath). On an
      // older WASM without them, nested paths get a clear refusal instead of
      // silently mutating the OUTER table. merge/split stay body-level only.
      async insertTableRow(params) {
        const r = structuralTableOp(params.path, 'insert_table_row',
          (doc, sec, para, ctrl) => doc.insertTableRow(sec, para, ctrl, params.after_row, true),
          (doc, sec, para, hopsJson) => doc.insertTableRowByPath(sec, para, hopsJson, params.after_row, true));
        // Fill read-back: the engine clones an ADJACENT row's cell style for
        // the new row — when that template is a header/label/topic row the
        // new data row inherits its shading (the gray-헤더-배경 bug). Return
        // the new row's fills next to its neighbors' so the agent can spot
        // the leak and normalize with set_cell_fill in the same turn.
        if (r && r.ok !== false) {
          try {
            const ref = resolveTablePath(params.path);
            if (!ref.nested) {
              const bboxes = tableBboxesAt(ref);
              const newRow = (typeof params.after_row === 'number' ? params.after_row : -1) + 1;
              const fills = {
                inserted_row: newRow,
                inserted: rowFillsAt(ref, bboxes, newRow),
                row_above: newRow > 0 ? rowFillsAt(ref, bboxes, newRow - 1) : [],
                row_below: rowFillsAt(ref, bboxes, newRow + 1),
              };
              const key = (cells) => JSON.stringify(cells.map((c) => c.fill));
              const reference = fills.row_below.length ? fills.row_below : fills.row_above;
              if (reference.length && key(fills.inserted) !== key(reference)) {
                fills.fill_note =
                  'inserted row cell backgrounds differ from the adjacent row — ' +
                  'check whether it cloned header/label shading (or dropped the ' +
                  'data rows\' shading) and normalize with set_cell_fill.';
              }
              r.fill_check = fills;
            }
          } catch {}
        }
        return r;
      },
      async insertTableColumn(params) {
        const r = structuralTableOp(params.path, 'insert_table_column',
          (doc, sec, para, ctrl) => doc.insertTableColumn(sec, para, ctrl, params.after_col, true),
          (doc, sec, para, hopsJson) => doc.insertTableColumnByPath(sec, para, hopsJson, params.after_col, true));
        return r;
      },
      async deleteTableRow(params) {
        const r = structuralTableOp(params.path, 'delete_table_row',
          (doc, sec, para, ctrl) => doc.deleteTableRow(sec, para, ctrl, params.row),
          (doc, sec, para, hopsJson) => doc.deleteTableRowByPath(sec, para, hopsJson, params.row));
        return r;
      },
      async deleteTableColumn(params) {
        const r = structuralTableOp(params.path, 'delete_table_column',
          (doc, sec, para, ctrl) => doc.deleteTableColumn(sec, para, ctrl, params.col),
          (doc, sec, para, hopsJson) => doc.deleteTableColumnByPath(sec, para, hopsJson, params.col));
        return r;
      },
      // Create a NEW body-level table at a paragraph, optionally pre-filled.
      //
      // Column widths are left to the engine unless col_widths is given:
      // create_table_native sizes the columns to the section's text area
      // (page width - margins - the table's own 283hu outer margins) and
      // appends the empty paragraph HWP keeps after a table control. Doing
      // either of those caller-side is how tables end up overflowing the
      // page edge, so this handler deliberately passes neither by default.
      //
      // Returns the NEW table's path. Creating a table splits or shifts the
      // host paragraph (create_table_native inserts before/after depending on
      // whether the host is empty), so the caller's `path` is stale the
      // moment this returns — everything downstream must use the returned one.
      async insertTable(params) {
        const { sec, para } = pathToCoords(params.path);
        const guard = guardLegacyInsertTrap(sec, para, 'insertTable');
        if (guard) return guard;
        const rows = params.rows;
        const cols = params.cols;
        if (!Number.isInteger(rows) || !Number.isInteger(cols) ||
            rows < 1 || cols < 1 || cols > 256) {
          return {
            ok: false,
            error: `insert_table: bad dimensions (rows=${rows}, cols=${cols}) — ` +
              'rows >= 1 and 1 <= cols <= 256.',
          };
        }
        const doc = getDoc();
        const opts = {
          sectionIdx: sec,
          paraIdx: para,
          charOffset: params.offset || 0,
          rowCount: rows,
          colCount: cols,
        };
        if (Array.isArray(params.col_widths) && params.col_widths.length === cols) {
          opts.colWidths = params.col_widths;
        }
        const rowsData = Array.isArray(params.rows_data) ? params.rows_data : null;
        doc.beginBatch();
        let created;
        let filled = 0;
        const failures = [];
        try {
          created = safeParse(doc.createTableEx(JSON.stringify(opts)));
          if (!created.ok && created.raw === undefined) {
            throw new Error(created.error || 'createTableEx failed');
          }
          const newPara = created.paraIdx ?? created.para_idx;
          const newCtrl = created.controlIdx ?? created.control_idx ?? 0;
          if (typeof newPara !== 'number') {
            throw new Error('createTableEx returned no paraIdx');
          }
          // Fill inside the SAME batch — a fresh table has no merged regions,
          // so cellIdx is exactly row*cols+col and no bbox round-trip is
          // needed. Cells start empty, so unlike setCellText there is nothing
          // to clear first; multi-line text still becomes one cell paragraph
          // per line (a literal "\n" in a single cell paragraph does not wrap).
          if (rowsData) {
            for (let r = 0; r < Math.min(rowsData.length, rows); r++) {
              const rowCells = Array.isArray(rowsData[r]) ? rowsData[r] : [];
              for (let c = 0; c < Math.min(rowCells.length, cols); c++) {
                const text = rowCells[c] == null ? '' : String(rowCells[c]);
                if (text === '') continue;
                const cellIdx = r * cols + c;
                const segments = text.split('\n');
                try {
                  insertCellTextCompat(doc, sec, newPara, newCtrl, cellIdx, 0, 0, segments[0]);
                  for (let i = 1; i < segments.length; i++) {
                    const prev = i - 1;
                    let len = 0;
                    try { len = doc.getCellParagraphLength(sec, newPara, newCtrl, cellIdx, prev); }
                    catch { len = (getCellTextCompat(doc, sec, newPara, newCtrl, cellIdx, prev, 0, 9999) || '').length; }
                    doc.splitParagraphInCell(sec, newPara, newCtrl, cellIdx, prev, len);
                    if (segments[i]) insertCellTextCompat(doc, sec, newPara, newCtrl, cellIdx, i, 0, segments[i]);
                  }
                  filled += 1;
                } catch (e) {
                  failures.push({ row: r, col: c, error: e?.message || String(e) });
                }
              }
            }
          }
          doc.endBatch();
        } catch (e) {
          try { doc.endBatch(); } catch {}
          throw e;
        }
        refresh();
        const newPara = created.paraIdx ?? created.para_idx;
        const newCtrl = created.controlIdx ?? created.control_idx ?? 0;
        // ctrl 0 keeps the bare s{sec}:p{para} form the outline reports for
        // a table that owns its paragraph; anything else needs the :c suffix.
        const path = newCtrl === 0 ? `s${sec}:p${newPara}` : `s${sec}:p${newPara}:c${newCtrl}`;
        // Read the dims back off the engine rather than echoing the request —
        // a table that did not actually materialize would otherwise be
        // reported as created.
        const dims = tryGetTableDims(sec, newPara, newCtrl);
        return {
          ok: failures.length === 0,
          path,
          rows: dims ? dims.rowCount : rows,
          cols: dims ? dims.colCount : cols,
          verified: !!dims && dims.rowCount === rows && dims.colCount === cols,
          ...(rowsData ? { filled } : {}),
          ...(failures.length ? { failures } : {}),
        };
      },
      // Delete an ENTIRE table (the control, its cells, and all their text).
      // Body-level only — deleteTableControl has no *ByPath variant, so a
      // nested path gets the standard refusal instead of silently blowing
      // away the outer table.
      async deleteTable(params) {
        const { sec, para, ctrl } = bodyTableCoordsOrThrow(params.path, 'delete_table');
        const doc = getDoc();
        const dims = tryGetTableDims(sec, para, ctrl);
        if (!dims) return { ok: false, error: `no table at ${params.path}` };
        let removed_host_paragraph = false;
        doc.beginBatch();
        try {
          const r = safeParse(doc.deleteTableControl(sec, para, ctrl));
          if (!r.ok && r.raw === undefined) {
            throw new Error(r.error || 'deleteTableControl failed');
          }
          // deleteTableControl drops the control but keeps its host paragraph.
          // A body table lives in a paragraph of its own, so what is left is a
          // stray blank line — delete it, or every removed table leaves one
          // behind and the doc slowly fills with empty paragraphs. Guarded:
          // only when the paragraph now has NO text and NO remaining controls
          // (getControlTextPositions counts every control kind, so a paragraph
          // that also hosted an image or shape is left alone).
          try {
            const len = doc.getParagraphLength(sec, para);
            const text = len ? (doc.getTextRange(sec, para, 0, len) || '') : '';
            const ctrls = JSON.parse(doc.getControlTextPositions(sec, para) || '[]');
            if (text.trim() === '' && Array.isArray(ctrls) && ctrls.length === 0) {
              doc.deleteParagraph(sec, para);
              removed_host_paragraph = true;
            }
          } catch {}
          doc.endBatch();
        } catch (e) {
          try { doc.endBatch(); } catch {}
          throw e;
        }
        refresh();
        // Paragraph indices after the deleted table have shifted — say so
        // explicitly so the agent re-reads instead of reusing stale paths.
        return {
          ok: true,
          deleted: { path: params.path, rows: dims.rowCount, cols: dims.colCount },
          removed_host_paragraph,
          paths_invalidated: true,
        };
      },
      async mergeTableCells(params) {
        const { sec, para, ctrl } = bodyTableCoordsOrThrow(params.path, 'merge_table_cells');
        const r = safeParse(getDoc().mergeTableCells(sec, para, ctrl,
          params.start_row, params.start_col, params.end_row, params.end_col));
        refresh();
        return r;
      },
      async splitTableCell(params) {
        const { sec, para, ctrl } = bodyTableCoordsOrThrow(params.path, 'split_table_cell');
        const r = safeParse(getDoc().splitTableCell(sec, para, ctrl, params.row, params.col));
        refresh();
        return r;
      },
      // Grow a table row so text that clips in the PREVIEW (fixed row height,
      // wrapped to 2+ lines) becomes visible. GROW-ONLY by design: extra_pt is
      // clamped to a positive value, so this can never shrink a row below its
      // content (the destructive direction). Worst case of an over-estimate is
      // extra whitespace — 한글 renders that faithfully, so it never damages the
      // export the way trimming the user's text would.
      async growTableRow(params) {
        const { sec, para, ctrl } = bodyTableCoordsOrThrow(params.path, 'grow_table_row');
        const row = params.row;
        if (typeof row !== 'number' || row < 0) {
          return { ok: false, error: 'grow_table_row needs a non-negative row index' };
        }
        let extraPt = Number(params.extra_pt);
        if (!Number.isFinite(extraPt) || extraPt <= 0) extraPt = 24; // ~one body line
        extraPt = Math.min(extraPt, 400);                            // sanity cap
        const heightDelta = Math.round(extraPt * 100);               // pt→HWPUNIT (1pt=100)
        const doc = getDoc();
        let bboxes;
        try { bboxes = JSON.parse(doc.getTableCellBboxes(sec, para, ctrl)) || []; }
        catch (e) { return { ok: false, error: `getTableCellBboxes failed: ${e?.message || e}` }; }
        // Grow the cells that START on this visual row (its native cells). A
        // vertically-merged cell anchored on an EARLIER row is left alone — the
        // engine already sizes it across the rows it spans, and adding to it
        // would over-grow the rows above. Horizontally-merged (colSpan) cells
        // still anchor on this row, so they're included.
        const cells = bboxes.filter((b) => b.row === row);
        if (!cells.length) {
          const rows = new Set(bboxes.map((b) => b.row)).size;
          return { ok: false, error: `row ${row} not found (table has ${rows} rows)` };
        }
        const json = cells.map((b) => ({ cellIdx: b.cellIdx, heightDelta }));
        const r = safeParse(doc.resizeTableCells(sec, para, ctrl, JSON.stringify(json)));
        refresh();
        if (r && r.ok === false) return r;
        let after = [];
        try {
          after = (JSON.parse(doc.getTableCellBboxes(sec, para, ctrl)) || [])
            .filter((b) => b.row === row);
        } catch {}
        return {
          ok: true,
          row,
          extra_pt: extraPt,
          height_delta_hwpunit: heightDelta,
          cells_grown: cells.map((b) => b.cellIdx),
          before_h: cells.map((b) => Math.round(b.h)),
          after_h: after.map((b) => Math.round(b.h)),
        };
      },

      // Fields
      async setFieldValue(params) {
        const r = safeParse(getDoc().setFieldValueByName(params.field_name, params.value));
        if (!r.ok && r.raw === undefined) throw new Error(r.error || 'setFieldValue failed');
        refresh();
        return { ok: true };
      },
      async applyTemplate(params) {
        const values = params.values || {};
        const errors = [];
        let filled = 0;
        const doc = getDoc();
        doc.beginBatch();
        try {
          for (const [name, value] of Object.entries(values)) {
            try {
              const r = safeParse(doc.setFieldValueByName(name, value));
              if (r.ok || r.raw === undefined) filled++;
              else errors.push({ field: name, error: r.error || 'failed' });
            } catch (e) { errors.push({ field: name, error: e.message }); }
          }
          doc.endBatch();
        } catch (e) { try { doc.endBatch(); } catch {} throw e; }
        refresh();
        return { ok: true, filled, errors };
      },

      // Rich content
      async insertFootnote(params) {
        const { sec, para } = pathToCoords(params.path);
        const guard = guardLegacyInsertTrap(sec, para, 'insertFootnote');
        if (guard) return guard;
        const doc = getDoc();
        doc.beginBatch();
        try {
          const r = safeParse(doc.insertFootnote(sec, para, params.offset));
          if (!r.ok && r.raw === undefined) throw new Error(r.error || 'insertFootnote failed');
          if (params.text) {
            const ctrlIdx = r.controlIdx ?? r.control_idx ?? 0;
            try { doc.insertTextInFootnote(sec, para, ctrlIdx, 0, 0, params.text); } catch {}
          }
          doc.endBatch();
          refresh();
          return { ok: true, ...r };
        } catch (e) { try { doc.endBatch(); } catch {} throw e; }
      },
      async insertEquation(params) {
        const { sec, para } = pathToCoords(params.path);
        const guard = guardLegacyInsertTrap(sec, para, 'insertEquation');
        if (guard) return guard;
        const doc = getDoc();
        const colorInt = parseInt((params.color || '#000000').replace('#', ''), 16);
        const fontSize = (params.font_size || 12) * 100;
        doc.beginBatch();
        try {
          const r = safeParse(doc.insertEquation(sec, para, params.offset || 0, params.script, fontSize, colorInt));
          if (!r.ok && r.raw === undefined) throw new Error(r.error || 'insertEquation failed');
          doc.endBatch();
          refresh();
          return { ok: true, ...r };
        } catch (e) { try { doc.endBatch(); } catch {} throw e; }
      },
      async insertPicture(params) {
        const { sec, para } = pathToCoords(params.path);
        const {
          image_url,
          image_b64,
          ext: extHint,
          offset = 0,
          width_mm = 80,
          height_mm = 60,
          description = '',
        } = params;

        // Prefer bytes-via-RPC. Server reads S3 -> base64 -> bridge -> bytes,
        // avoiding cross-origin fetch from the iframe. image_url stays as
        // a legacy fallback.
        let bytes, ext;
        if (image_b64) {
          const binStr = atob(image_b64);
          bytes = new Uint8Array(binStr.length);
          for (let i = 0; i < binStr.length; i++) bytes[i] = binStr.charCodeAt(i);
          ext = (extHint || 'png').toLowerCase().replace(/^\./, '');
        } else if (image_url) {
          const res = await fetch(image_url);
          if (!res.ok) throw new Error(`fetch image: ${res.status}`);
          bytes = new Uint8Array(await res.arrayBuffer());
          ext = (image_url.match(/\.(png|jpg|jpeg|gif|webp|bmp)/i) || [, 'png'])[1].toLowerCase();
        } else {
          throw new Error('insertPicture: image_b64 or image_url required');
        }

        const widthHwp = Math.round(width_mm * 283.5);
        const heightHwp = Math.round(height_mm * 283.5);

        // Decode natural PNG pixel dims for the crop calc (see rhwp
        // object_ops.rs:1490).
        let naturalWPx = 0, naturalHPx = 0;
        try {
          const blob = new Blob([bytes], { type: `image/${ext === 'jpg' ? 'jpeg' : ext}` });
          const bitmap = await createImageBitmap(blob);
          naturalWPx = bitmap.width || 0;
          naturalHPx = bitmap.height || 0;
          bitmap.close && bitmap.close();
        } catch (e) {
          console.warn('[bridge] could not decode image dims via createImageBitmap', e);
        }
        if (!naturalWPx || !naturalHPx) {
          naturalWPx = Math.max(1, Math.round(widthHwp / 75));
          naturalHPx = Math.max(1, Math.round(heightHwp / 75));
        }

        const doc = getDoc();
        doc.beginBatch();
        try {
          // v0.8.2 engine: insertPicture gained a cell_path_json param in 4th
          // position (hop-list JSON, same grammar as getTableDimensionsByPath).
          // pathToCoords only parses body paths (s{sec}:p{para}[:c{ctrl}]), so
          // pictures are always body-level here — pass an empty hop list.
          const r = safeParse(doc.insertPicture(sec, para, offset, '[]', bytes,
            widthHwp, heightHwp, naturalWPx, naturalHPx, ext, description));
          if (!r.ok && r.raw === undefined) throw new Error(r.error || 'insertPicture failed');
          doc.endBatch();
          refresh();
          return { ok: true, ...r };
        } catch (e) { try { doc.endBatch(); } catch {} throw e; }
      },

      // Header/Footer
      async setHeaderFooter(params) {
        const { sec, is_header, apply_to = 0, text } = params;
        const doc = getDoc();
        doc.beginBatch();
        try {
          try { safeParse(doc.createHeaderFooter(sec, is_header, apply_to)); } catch {}
          const r = safeParse(doc.insertTextInHeaderFooter(sec, is_header, apply_to, 0, 0, text));
          doc.endBatch();
          refresh();
          if (!r.ok && r.raw === undefined) throw new Error(r.error || 'setHeaderFooter failed');
          return { ok: true };
        } catch (e) { try { doc.endBatch(); } catch {} throw e; }
      },
      async deleteHeaderFooter(params) {
        const r = safeParse(getDoc().deleteHeaderFooter(params.sec, params.is_header, params.apply_to || 0));
        refresh();
        return r;
      },

      // Page setup
      async setPageDef(params) {
        const doc = getDoc();
        const current = safeParse(doc.getPageDef(params.sec));
        const merged = { ...current, ...(params.overrides || {}) };
        const r = safeParse(doc.setPageDef(params.sec, JSON.stringify(merged)));
        refresh();
        return r;
      },

      // Bookmarks
      async addBookmark(params) {
        const { sec, para } = pathToCoords(params.path);
        const r = safeParse(getDoc().addBookmark(sec, para, params.offset || 0, params.name));
        return r;
      },
      async deleteBookmark(params) {
        try {
          const list = safeParse(getDoc().getBookmarks());
          const items = list.bookmarks || list.items || (Array.isArray(list) ? list : []);
          const found = items.find(b => b.name === params.name);
          if (!found) return { ok: false, error: `bookmark not found: ${params.name}` };
          return safeParse(getDoc().deleteBookmark(
            found.sec ?? found.sectionIdx ?? 0,
            found.para ?? found.paraIdx ?? 0,
            found.ctrlIdx ?? found.controlIdx ?? found.ctrl_idx ?? 0,
          ));
        } catch (e) { return { ok: false, error: e.message }; }
      },

      // Transaction / export
      async saveSnapshot() {
        const id = getDoc().saveSnapshot();
        return { ok: true, snapshot_id: id };
      },
      async restoreSnapshot(params) {
        const r = safeParse(getDoc().restoreSnapshot(params.snapshot_id));
        refresh();
        return r;
      },
      async exportDocument(params) {
        const fmt = (params.format || 'hwp').toLowerCase();
        const doc = getDoc();
        let hwpVerify = null;
        if (fmt === 'hwp' && typeof doc.exportHwpVerify === 'function') {
          try { hwpVerify = safeParse(doc.exportHwpVerify()); }
          catch (e) {
            hwpVerify = {
              ok: false,
              error: e && e.message ? e.message : String(e),
              error_type: typeof e,
              error_name: e && e.name ? e.name : undefined,
            };
          }
        }
        const hwpVerifyFailed = fmt === 'hwp' && hwpVerify
          && (
            hwpVerify.ok === false
            || hwpVerify.recovered === false
            || (hwpVerify.invalidPageCountAfter || 0) > 0
          );
        if (hwpVerifyFailed && params.allow_unverified !== true) {
          throw new Error(`HWP export self-verify failed: ${JSON.stringify(hwpVerify)}`);
        }
        const preserveOriginalHwpx = fmt === 'hwpx'
          && params.force_reserialize !== true
          && cleanSinceLoad
          && originalHwpxBytes instanceof Uint8Array;
        // Belt-and-suspenders: a mutation handler that bypassed refresh()
        // would leave linesegarray stale and the export would bake those
        // stale vertpos values into the bytes (see rhwp #177). Reflow
        // here so persisted snapshots + user downloads always carry a
        // fresh layout cache. For unchanged HWPX, return the original package
        // bytes instead: RHWP's HWPX serializer is not structure-preserving
        // yet, and no-op export must not drop unsupported tables.
        if (!preserveOriginalHwpx) {
          try { if (typeof doc.reflowLinesegs === 'function') doc.reflowLinesegs(); } catch {}
        }
        const bytes = preserveOriginalHwpx
          ? originalHwpxBytes
          : (fmt === 'hwpx' ? doc.exportHwpx() : doc.exportHwp());
        // wasm.fileName is a getter (not getFileName()); the old check
        // silently fell back to 'document' so every export was named that.
        const fileName = wasm.fileName || originalFileName || 'document.hwp';
        const baseName = fileName.replace(/\.[^.]+$/, '') || 'document';
        const fullName = `${baseName}.${fmt}`;
        // upload:false (user-clicked download) skips the server round-trip —
        // bytes go straight back to the parent which builds the Blob URL and
        // triggers <a download>. ~5-10ms for typical docs vs. ~50-200ms over
        // the network. Default (no flag) keeps the agent's upload-and-link
        // flow so chat replies can hand the user a clickable URL.
        if (params.upload === false) {
          return { ok: true, file_name: fullName, bytes_len: bytes.length, hwp_verify: hwpVerify, preserved_original: preserveOriginalHwpx, bytes };
        }
        const blob = new Blob([bytes], { type: fmt === 'hwpx' ? 'application/hwp+zip' : 'application/x-hwp' });
        const formData = new FormData();
        formData.append('file', blob, fullName);
        const res = await fetch('/api/upload-export', { method: 'POST', body: formData });
        const data = await res.json();
        return { ok: true, file_name: fullName, bytes_len: bytes.length, hwp_verify: hwpVerify, preserved_original: preserveOriginalHwpx, download_url: data.url };
      },
      // 호스트 저장 완료 통지 (rhwp #2660 계약의 브리지 표면).
      //
      // 저장 흐름은 브리지가 끝내지 않는다: 저장 메뉴는 parent 로
      // 'save_requested' 를 보내고, FE 가 자기 다운로드/업로드 파이프라인을
      // 돌린다. 그 파이프라인이 성공으로 끝난 뒤 FE 가 이 RPC 를 부르면
      // 그때 비로소 문서가 clean 이 되고 복구 draft 가 지워진다.
      //
      // exportDocument 성공만으로 clean 처리하지 않는 이유: export 는 바이트를
      // 만들 뿐 영속화를 보장하지 않는다. 업로드/저장이 실패해도 복구 draft 는
      // 남아 있어야 하므로, 영속화를 아는 쪽(FE)이 명시적으로 통지한다.
      //
      // 통지가 오지 않으면 draft 가 IndexedDB 에 남아 다음 세션 진입 때마다
      // "문서 복구" 안내가 다시 뜬다 (e2e/embed-save-ack.test.mjs TC-2 가
      // 그 음성 대조를 고정하고 있다).
      //
      // params.file_name — 저장된 최종 파일명(선택). 주면 studio 의 fileName 을
      // 그 이름으로 갱신해 이후 export/제목 표기가 실제 저장본과 일치한다.
      async notifySaved(params) {
        const api = window.rhwpStudio;
        if (!api || typeof api.notifySaved !== 'function') {
          return { ok: false, error: 'notifySaved is not supported by this Studio build' };
        }
        const requested = params && params.file_name;
        const fileName = typeof requested === 'string' && requested ? requested : undefined;
        // draft 삭제 완료까지 await 한다 — 응답 이후 팝업/탭을 닫아도
        // IndexedDB 삭제가 잘리지 않는다.
        const ack = await api.notifySaved(fileName);
        return { ok: true, was_dirty: !!(ack && ack.wasDirty), file_name: wasm.fileName };
      },
      async convertToEditable() {
        try { return safeParse(getDoc().convertToEditable()); }
        catch (e) { return { ok: false, error: e.message }; }
      },
      // Cheap structural census for the BE's per-turn content-loss gate:
      // if tables (body or nested) vanish across a turn without an explicit
      // delete op, the turn destroyed content it couldn't see. Bounded by a
      // probe budget so 200-page docs return a truncated (but comparable —
      // same budget both sides of the turn) count instead of stalling.
      async getDocStats() {
        const doc = getDoc();
        const sections = doc.getSectionCount();
        let paragraphs = 0, bodyTables = 0, nestedTables = 0, cellsScanned = 0;
        let budget = 3000;
        let truncated = false;
        for (let s = 0; s < sections; s++) {
          const pCount = doc.getParagraphCount(s);
          paragraphs += pCount;
          for (let p = 0; p < pCount; p++) {
            if (budget <= 0) { truncated = true; break; }
            for (let ctrl = 0; ctrl < 6; ctrl++) {
              budget -= 1;
              const dims = tryGetTableDims(s, p, ctrl);
              if (!dims) continue;
              bodyTables += 1;
              const ref = { sec: s, para: p, ctrl, hops: [{ controlIndex: ctrl, cellIndex: 0, cellParaIndex: 0 }], nested: false };
              let bboxes = [];
              try { bboxes = tableBboxesAt(ref); } catch {}
              const cellIdxs = bboxes.length
                ? bboxes.map(b => b.cellIdx)
                : Array.from({ length: Math.min(dims.cellCount || dims.rowCount * dims.colCount, 200) }, (_, i) => i);
              for (const cellIdx of cellIdxs) {
                if (budget <= 0) { truncated = true; break; }
                cellsScanned += 1;
                let hits = [];
                try { hits = scanCellNestedTables(ref, cellIdx); } catch {}
                budget -= 3;
                nestedTables += hits.length;
              }
            }
          }
          if (budget <= 0) truncated = true;
        }
        let pageCount = 0;
        try { pageCount = doc.pageCount(); } catch {}
        return {
          paragraphs,
          body_tables: bodyTables,
          nested_tables: nestedTables,
          tables_total: bodyTables + nestedTables,
          cells_scanned: cellsScanned,
          page_count: pageCount,
          truncated,
        };
      },
      // 읽기 전용 토글. URL 의 ?readonly=1 과 같은 상태를 가리키며, 호스트가
      // 문서를 연 뒤에도 켜고 끌 수 있게 한다.
      async setReadonly(params) {
        const api = window.rhwpStudio;
        if (!api || typeof api.setReadonly !== 'function') {
          return { ok: false, error: 'studio does not expose setReadonly' };
        }
        const result = api.setReadonly(params.on !== false);
        // 호스트가 명시로 건 readonly 는 viewer 유래다. 잠금이 켠 상태를
        // 덮어쓰는 것이므로 잠금 복원 정보도 버린다(잠금 해제 때 되살아나면
        // 호스트 의도가 조용히 뒤집힌다).
        agentTurnReadonly = false;
        preLockEditMode = null;
        return result;
      },
      async getEditMode() {
        const mode = studioEditMode();
        return {
          ok: true,
          edit_mode: mode,
          readonly: mode === 'readonly',
          // 'agent-turn' 이면 에이전트 편집 RPC 는 계속 통과한다.
          readonly_reason: mode === 'readonly' ? (agentTurnReadonly ? 'agent-turn' : 'viewer') : null,
        };
      },
    };

    // 읽기 전용에서 통과시킬 RPC. 스튜디오 커맨드 게이트와 같은 이유로 허용리스트다 —
    // 새 RPC 가 추가될 때 기본값이 "차단"이어야 문서 보호가 깨지지 않는다.
    //
    // exportDocument / saveSnapshot / notifySaved 는 문서를 바꾸지 않고 현재 상태를
    // 밖으로 내보내거나 통지만 하므로 열어 둔다. restoreSnapshot·convertToEditable 은
    // 문서를 바꾸므로 빠져 있다.
    const READONLY_SAFE_METHODS = new Set([
      'loadFile',
      'outline', 'getUserFocus', 'getBlock', 'getSection', 'getFullText', 'getTable',
      'getFieldList', 'getFieldValue', 'findText', 'getWarnings',
      'getPageInfo', 'getPageDef', 'getPageOfPosition', 'getStyleList', 'getBookmarks',
      'getHeaderFooterList', 'getHeaderFooter', 'viewPage', 'getStableIds',
      'exportDocument', 'saveSnapshot', 'notifySaved', 'getDocStats',
      'setReadonly', 'getEditMode',
    ]);

    // 게이트는 viewer 유래 readonly 에만 건다. editor_lock 이 켠 readonly 는
    // 사용자 입력을 막으려는 것이지 에이전트를 막으려는 것이 아니다 —
    // 구분하지 않으면 턴 중 잠금이 그 턴의 편집 RPC 를 전부 거절한다.
    function isReadonlyNow() {
      return isViewerReadonly();
    }

    // ── Router ──
    window.addEventListener('message', async (e) => {
      const msg = e.data;
      if (!msg || typeof msg !== 'object') return;
      if (msg.type === 'editor_lock') {
        setLocked(true);
        // Turn boundary: every agent turn AND every BE undo/redo starts
        // with editor_lock. Clearing the local input history here keeps
        // the two undo timelines non-overlapping (chronological routing).
        clearLocalHistory();
        // Changes until the user's next real input are machine-made.
        quietUntilUserInput = true;
        agentMutationReported = false;
        refreshFcHistoryUi();
        return;
      }
      if (msg.type === 'editor_unlock') {
        setLocked(false);
        refreshFcHistoryUi();
        return;
      }
      if (msg.type === 'history_state') {
        fcBe.canUndo = !!msg.canUndo;
        fcBe.canRedo = !!msg.canRedo;
        fcBe.busy = !!msg.busy;
        refreshFcHistoryUi();
        return;
      }
      if (msg.type !== 'rpc_request' || !msg.method) return;

      const method = msg.method.startsWith('agent.') ? msg.method.slice(6) : msg.method;
      const handler = handlers[method];
      if (!handler) {
        sendToParent({ type: 'rpc_reply', id: msg.id, error: `unknown method: ${msg.method}` });
        return;
      }
      if (isReadonlyNow() && !READONLY_SAFE_METHODS.has(method)) {
        sendToParent({
          type: 'rpc_reply',
          id: msg.id,
          error: `readonly mode: ${msg.method} is not allowed`,
        });
        return;
      }
      try {
        const result = await withAgent(() => handler(msg.params || {}));
        sendToParent({ type: 'rpc_reply', id: msg.id, result });
      } catch (err) {
        console.error(`[agent-bridge] RPC ${msg.method} failed:`, err);
        sendToParent({ type: 'rpc_reply', id: msg.id, error: err.message || String(err) });
      }
    });

    sendToParent({ type: 'studio_ready' });
    console.log('[agent-bridge] ready');
  });
})();
