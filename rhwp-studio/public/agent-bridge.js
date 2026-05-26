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

  // Wait for BOTH the globals to exist AND WasmBridge.initialize() to have
  // completed. main.ts assigns window.__wasm before calling wasm.initialize(),
  // so checking only the globals would let us post studio_ready (and accept
  // RPCs) while the WASM module is still loading — first loadFile would crash
  // with `__wbindgen_malloc undefined`. The `initialized` field is a TS
  // `private` but at runtime it's a normal JS property — safe to read.
  function whenReady(cb, tries = 0) {
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
      try { return JSON.parse(s); } catch { return { ok: false, raw: s }; }
    }
    function pathToCoords(path) {
      const m = /^s(\d+):p(\d+)(?::c(\d+))?$/.exec(path);
      if (!m) throw new Error(`bad path: ${path}`);
      return { sec: +m[1], para: +m[2], ctrl: m[3] !== undefined ? +m[3] : 0 };
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
    function refresh() {
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

    // ── Agent-active flag — suppress user_edit during our own mutations ──
    let agentDepth = 0;
    async function withAgent(fn) {
      agentDepth++;
      try { return await fn(); } finally { agentDepth--; }
    }
    eventBus.on('document-changed', (reason) => {
      if (agentDepth > 0) return;
      // Skip our own re-render emissions (reason === 'agent-mutation' implies depth > 0;
      // user dialogs use other strings).
      const summary = typeof reason === 'string' ? reason : 'user edit';
      sendToParent({ type: 'user_edit', kind: 'document-changed', summary });
    });

    // ── Swallow file-shortcuts we hid from the menu ──
    // We disabled file:save / file:save-as / file:open / file:new-doc in
    // shortcut-map.ts so the chat flow owns those. Without this, Ctrl+S
    // would fall through to the browser ("Save Page As…") which is worse.
    window.addEventListener('keydown', (e) => {
      const ctrl = e.ctrlKey || e.metaKey;
      if (!ctrl) return;
      const k = e.key?.toLowerCase();
      if (k === 's' || k === 'o' || (e.altKey && k === 'n')) {
        e.preventDefault();
        e.stopPropagation();
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
      'body.agent-locked { cursor: progress !important; }',
      'body.agent-locked .editor-area, body.agent-locked main, body.agent-locked .menu, body.agent-locked .toolbar { pointer-events: none !important; }',
      // rhwp-studio raises a sticky top-right toast on every HWPX load
      // ("HWPX 문서는 저장 시 HWP 형식으로 변환 저장됩니다…"). It covers
      // the toolbar and is redundant with the inline hint in the parent
      // FE's "저장 ▼" menu. `rhwp-toast-container` is an *id* (the
      // bundle uses `document.getElementById(...)`), so the selector
      // must use #, not .
      '#rhwp-toast-container { display: none !important; }',
    ].join('\n');
    document.head.appendChild(lockStyle);

    function setLocked(b) {
      document.body.classList.toggle('agent-locked', b);
    }

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
      try {
        const raw = doc.getCaretPosition();
        const parsed = safeParse(raw);
        if (parsed && typeof parsed === 'object' && !parsed.ok === false) {
          // rhwp returns various shapes across versions — normalize the
          // common ones (sec/para/offset or section/paragraph/char).
          focus.caret = {
            sec: parsed.sec ?? parsed.section_idx ?? parsed.section ?? null,
            para: parsed.para ?? parsed.paragraph_idx ?? parsed.paragraph ?? null,
            offset: parsed.offset ?? parsed.char_offset ?? parsed.char ?? null,
            path: (parsed.sec ?? parsed.section_idx) != null
              ? `s${parsed.sec ?? parsed.section_idx}:p${parsed.para ?? parsed.paragraph_idx ?? 0}`
              : null,
          };
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
        return {
          page_count: wasm.doc.pageCount(),
          source_format: wasm.doc.getSourceFormat(),
          file_name: fileName || 'document.hwp',
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
        return { path: params.path, text, length: len, char_props, para_props };
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
            paragraphs.push({ path: `s${sec}:p${p}`, length: len, text });
          } catch {}
        }
        return { sec, paragraphs };
      },
      async getTable(params) {
        const { sec, para, ctrl } = pathToCoords(params.path);
        const doc = getDoc();
        const dims = tryGetTableDims(sec, para, ctrl);
        if (!dims) throw new Error(`no table at ${params.path}`);
        // Merge-aware layout: getTableCellBboxes returns the real cellIdx
        // for each (row, col) anchor along with rowSpan/colSpan. The naive
        // formula `cellIdx = row * colCount + col` is wrong for any table
        // with merged cells (= every Korean 응시원서/지원서 form), and
        // caused the agent to write to the wrong visual column. Fall back
        // to the flat formula if the bbox API is unavailable.
        let bboxes = [];
        try { bboxes = JSON.parse(doc.getTableCellBboxes(sec, para, ctrl)) || []; } catch {}
        if (bboxes.length > 0) {
          const cells = bboxes.map(b => {
            let text = '';
            try { text = (doc.getTextInCell(sec, para, ctrl, b.cellIdx, 0, 0, 200) || '').trim(); } catch {}
            return {
              row: b.row, col: b.col,
              row_span: b.rowSpan, col_span: b.colSpan,
              cell_idx: b.cellIdx,
              text,
            };
          });
          // Sort row-major so the agent reads top-to-bottom, left-to-right.
          cells.sort((a, b) => a.row - b.row || a.col - b.col);
          return {
            path: params.path,
            rows: dims.rowCount,
            cols: dims.colCount,
            merged: cells.some(c => c.row_span > 1 || c.col_span > 1),
            cells,
          };
        }
        // Fallback (no bbox API): old flat-grid behaviour.
        const cells = [];
        for (let r = 0; r < dims.rowCount; r++) {
          const row = [];
          for (let c = 0; c < dims.colCount; c++) {
            const cellIdx = r * dims.colCount + c;
            try { row.push(doc.getTextInCell(sec, para, ctrl, cellIdx, 0, 0, 200) || ''); }
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
        return { ok: !!r.ok, replaced: r.replaced ?? 0 };
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
        const replaced = r1.replaced ?? 0;
        if (!r1.ok || replaced === 0 || !props) {
          refresh();
          return { ok: !!r1.ok, replaced, styled: 0 };
        }
        // Restyle every freshly-written occurrence. Re-searching on the
        // replacement string is the simplest way to locate the just-written
        // ranges across both body paragraphs and table cells.
        const styleResult = await this.applyTextStyleToMatches({
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
          for (let row = rowStart; row <= rowEnd; row++) {
            for (let col = colStart; col <= colEnd; col++) {
              const cellIdx = row * colCount + col;
              let len = 0;
              try { len = (doc.getTextInCell(sec, para, ctrl, cellIdx, cellPara, 0, 9999) || '').length; }
              catch { skipped++; continue; }
              if (len === 0) { skipped++; continue; }
              try {
                const r = safeParse(
                  doc.applyCharFormatInCell(sec, para, ctrl, cellIdx, cellPara, 0, len, propsJson)
                );
                if (r.ok === false) throw new Error(r.error || 'applyCharFormatInCell failed');
                applied++;
              } catch (err) {
                failures.push({ row, col, error: err?.message || String(err) });
              }
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
          doc.insertParagraph(sec, para + 1);
          if (params.text) doc.insertText(sec, para + 1, 0, params.text);
          doc.endBatch();
          refresh();
          return { ok: true, new_path: `s${sec}:p${para + 1}` };
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
        const r = safeParse(doc.applyCharFormat(sec, para, start, end, JSON.stringify(wasmProps)));
        if (!r.ok && r.raw === undefined) throw new Error(r.error || 'applyCharFormat failed');
        refresh();
        return { ok: true, applied_to: { start, end } };
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
        const r = safeParse(getDoc().applyParaFormat(sec, para, JSON.stringify(params.props)));
        if (!r.ok && r.raw === undefined) throw new Error(r.error || 'applyParaFormat failed');
        refresh();
        return { ok: true };
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
        const { sec, para, ctrl } = pathToCoords(params.path);
        let { row, col, text, col_count } = params;
        const doc = getDoc();
        if (col_count === undefined || col_count === null) {
          const dims = tryGetTableDims(sec, para, ctrl);
          col_count = dims?.colCount;
          if (!col_count) throw new Error(`no table at ${params.path}`);
        }
        const cellIdx = resolveCellIdx(sec, para, ctrl, row, col, col_count);
        doc.beginBatch();
        try {
          let existingLen = 0;
          try { existingLen = (doc.getTextInCell(sec, para, ctrl, cellIdx, 0, 0, 9999) || '').length; } catch {}
          if (existingLen > 0) doc.deleteTextInCell(sec, para, ctrl, cellIdx, 0, 0, existingLen);
          doc.insertTextInCell(sec, para, ctrl, cellIdx, 0, 0, text);
          doc.endBatch();
          refresh();
          return { ok: true };
        } catch (e) { try { doc.endBatch(); } catch {} throw e; }
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
      async insertTableRow(params) {
        const { sec, para, ctrl } = pathToCoords(params.path);
        const r = safeParse(getDoc().insertTableRow(sec, para, ctrl, params.after_row, true));
        refresh();
        return r;
      },
      async insertTableColumn(params) {
        const { sec, para, ctrl } = pathToCoords(params.path);
        const r = safeParse(getDoc().insertTableColumn(sec, para, ctrl, params.after_col, true));
        refresh();
        return r;
      },
      async deleteTableRow(params) {
        const { sec, para, ctrl } = pathToCoords(params.path);
        const r = safeParse(getDoc().deleteTableRow(sec, para, ctrl, params.row));
        refresh();
        return r;
      },
      async deleteTableColumn(params) {
        const { sec, para, ctrl } = pathToCoords(params.path);
        const r = safeParse(getDoc().deleteTableColumn(sec, para, ctrl, params.col));
        refresh();
        return r;
      },
      async mergeTableCells(params) {
        const { sec, para, ctrl } = pathToCoords(params.path);
        const r = safeParse(getDoc().mergeTableCells(sec, para, ctrl,
          params.start_row, params.start_col, params.end_row, params.end_col));
        refresh();
        return r;
      },
      async splitTableCell(params) {
        const { sec, para, ctrl } = pathToCoords(params.path);
        const r = safeParse(getDoc().splitTableCell(sec, para, ctrl, params.row, params.col));
        refresh();
        return r;
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
        const { image_url, offset = 0, width_mm = 80, height_mm = 60, description = '' } = params;
        const res = await fetch(image_url);
        if (!res.ok) throw new Error(`fetch image: ${res.status}`);
        const bytes = new Uint8Array(await res.arrayBuffer());
        const ext = (image_url.match(/\.(png|jpg|jpeg|gif|webp|bmp)/i) || [, 'png'])[1].toLowerCase();
        const widthHwp = Math.round(width_mm * 283.5);
        const heightHwp = Math.round(height_mm * 283.5);
        const doc = getDoc();
        doc.beginBatch();
        try {
          const r = safeParse(doc.insertPicture(sec, para, offset, bytes,
            widthHwp, heightHwp, widthHwp, heightHwp, ext, description));
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
            found.sectionIdx ?? found.sec ?? 0,
            found.paraIdx ?? found.para ?? 0,
            found.controlIdx ?? found.ctrl_idx ?? 0,
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
          catch (e) { hwpVerify = { ok: false, error: e.message }; }
        }
        const hwpVerifyFailed = fmt === 'hwp' && hwpVerify
          && (hwpVerify.ok === false || hwpVerify.recovered === false);
        if (hwpVerifyFailed && params.allow_unverified !== true) {
          throw new Error(`HWP export self-verify failed: ${JSON.stringify(hwpVerify)}`);
        }
        // Belt-and-suspenders: a mutation handler that bypassed refresh()
        // would leave linesegarray stale and the export would bake those
        // stale vertpos values into the bytes (see rhwp #177). Reflow
        // here so persisted snapshots + user downloads always carry a
        // fresh layout cache.
        try { if (typeof doc.reflowLinesegs === 'function') doc.reflowLinesegs(); } catch {}
        const bytes = fmt === 'hwpx' ? doc.exportHwpx() : doc.exportHwp();
        // wasm.fileName is a getter (not getFileName()); the old check
        // silently fell back to 'document' so every export was named that.
        const fileName = wasm.fileName || 'document.hwp';
        const baseName = fileName.replace(/\.[^.]+$/, '') || 'document';
        const fullName = `${baseName}.${fmt}`;
        // upload:false (user-clicked download) skips the server round-trip —
        // bytes go straight back to the parent which builds the Blob URL and
        // triggers <a download>. ~5-10ms for typical docs vs. ~50-200ms over
        // the network. Default (no flag) keeps the agent's upload-and-link
        // flow so chat replies can hand the user a clickable URL.
        if (params.upload === false) {
          return { ok: true, file_name: fullName, bytes_len: bytes.length, hwp_verify: hwpVerify, bytes };
        }
        const blob = new Blob([bytes], { type: fmt === 'hwpx' ? 'application/hwp+zip' : 'application/x-hwp' });
        const formData = new FormData();
        formData.append('file', blob, fullName);
        const res = await fetch('/api/upload-export', { method: 'POST', body: formData });
        const data = await res.json();
        return { ok: true, file_name: fullName, bytes_len: bytes.length, hwp_verify: hwpVerify, download_url: data.url };
      },
      async convertToEditable() {
        try { return safeParse(getDoc().convertToEditable()); }
        catch (e) { return { ok: false, error: e.message }; }
      },
    };

    // ── Router ──
    window.addEventListener('message', async (e) => {
      const msg = e.data;
      if (!msg || typeof msg !== 'object') return;
      if (msg.type === 'editor_lock')   { setLocked(true);  return; }
      if (msg.type === 'editor_unlock') { setLocked(false); return; }
      if (msg.type !== 'rpc_request' || !msg.method) return;

      const method = msg.method.startsWith('agent.') ? msg.method.slice(6) : msg.method;
      const handler = handlers[method];
      if (!handler) {
        sendToParent({ type: 'rpc_reply', id: msg.id, error: `unknown method: ${msg.method}` });
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
