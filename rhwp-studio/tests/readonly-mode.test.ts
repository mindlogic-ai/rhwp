import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { isBlockedInEditMode } from '../src/command/edit-mode-policy.ts';
import type { EditorContext } from '../src/command/types.ts';

// [FactChat 포크] 읽기 전용 모드 가드.
//
// 편집을 막는 지점이 한 곳이 아니다. 커맨드 디스패처(메뉴·툴바·단축키), 입력 핸들러의
// 중앙 라우터(executeOperation), 그리고 executeOperation 을 우회해 wasm 을 직접 부르는
// 머리말/꼬리말·각주 경로, 마지막으로 브리지 RPC 까지 네 층이다. 한 층만 뚫려도 읽기
// 전용이 아니게 되므로 각 층을 개별로 고정한다.

const rootDir = dirname(dirname(fileURLToPath(import.meta.url)));
const read = (rel: string) => readFileSync(join(rootDir, rel), 'utf8');

function ctx(overrides: Partial<EditorContext> = {}): EditorContext {
  return {
    hasDocument: true,
    hasSelection: false,
    hasCopiedFormat: false,
    inTable: false,
    inCellSelectionMode: false,
    hasMultiCellSelection: false,
    hasTableTransposeClipboard: false,
    inTableObjectSelection: false,
    inPictureObjectSelection: false,
    inField: false,
    isEditable: false,
    editMode: 'readonly',
    isFormMode: false,
    isReadonly: true,
    canEditFormField: false,
    canUndo: true,
    canRedo: true,
    zoom: 1,
    showControlCodes: false,
    showParagraphMarks: false,
    isDirty: false,
    ...overrides,
  };
}

test('읽기 전용은 문서를 바꾸는 커맨드를 막는다', () => {
  const readonly = ctx();
  const mutating = [
    'edit:paste', 'edit:cut', 'edit:delete', 'edit:undo', 'edit:redo',
    'edit:find-replace', 'format:bold', 'insert:image', 'table:create',
    'page:break', 'field:edit', 'field:remove', 'file:page-setup',
  ];
  for (const id of mutating) {
    assert.equal(isBlockedInEditMode(id, readonly), true, `${id} 가 읽기 전용을 통과했다`);
  }
});

test('읽기 전용에서도 보기·복사·찾기·내보내기는 열려 있다', () => {
  const readonly = ctx();
  const allowed = [
    'view:zoom-in', 'view:ctrl-mark', 'edit:copy', 'edit:select-all',
    'edit:find', 'edit:goto', 'file:print', 'file:print-to-pdf', 'file:save',
  ];
  for (const id of allowed) {
    assert.equal(isBlockedInEditMode(id, readonly), false, `${id} 가 읽기 전용에서 막혔다`);
  }
});

test('읽기 전용은 스스로를 해제하는 양식 모드 전환을 막는다', () => {
  // view: 접두어라 허용리스트를 그냥 통과하면 읽기 전용이 벗겨진다.
  assert.equal(isBlockedInEditMode('view:form-mode', ctx()), true);
});

test('허용리스트 방식이라 새 커맨드는 기본값이 차단이다', () => {
  assert.equal(isBlockedInEditMode('insert:something-added-later', ctx()), true);
  assert.equal(isBlockedInEditMode('brand-new:namespace', ctx()), true);
});

test('일반 모드는 그대로 통과한다 (읽기 전용 게이트가 새지 않는다)', () => {
  const normal = ctx({ editMode: 'normal', isReadonly: false, isEditable: true });
  assert.equal(isBlockedInEditMode('format:bold', normal), false);
  assert.equal(isBlockedInEditMode('edit:paste', normal), false);
  assert.equal(isBlockedInEditMode('view:form-mode', normal), false);
});

test('양식 모드 차단 규칙이 읽기 전용 도입으로 바뀌지 않는다', () => {
  const form = ctx({ editMode: 'form', isFormMode: true, isReadonly: false });
  assert.equal(isBlockedInEditMode('format:bold', form), true);
  assert.equal(isBlockedInEditMode('file:page-setup', form), true);
  assert.equal(isBlockedInEditMode('edit:cut', form), true);
  // 양식 모드는 입력 자체는 허용한다 — 위치별 판정은 입력 핸들러 몫.
  assert.equal(isBlockedInEditMode('edit:copy', form), false);
});

test('디스패처가 정책을 실제로 호출한다', () => {
  // 정책 모듈만 통과시켜도 디스패처가 부르지 않으면 아무것도 막히지 않는다.
  const dispatcher = read('src/command/dispatcher.ts');
  assert.match(dispatcher, /import \{ isBlockedInEditMode \} from '\.\/edit-mode-policy'/);
  const dispatch = dispatcher.slice(dispatcher.indexOf('  dispatch('));
  assert.match(dispatch.slice(0, 600), /if \(isBlockedInEditMode\(commandId, ctx\)\)/);
  const isEnabled = dispatcher.slice(dispatcher.indexOf('  isEnabled('));
  assert.match(isEnabled.slice(0, 400), /if \(isBlockedInEditMode\(commandId, ctx\)\) return false;/);
});

test('중앙 편집 라우터가 읽기 전용을 종류 불문 차단한다', () => {
  const src = read('src/engine/input-handler.ts');
  const gate = src.slice(src.indexOf('private isOperationAllowedInEditMode'));
  const body = gate.slice(0, gate.indexOf('\n  }'));
  assert.match(
    body,
    /editMode === 'readonly'\) return false;/,
    'executeOperation 게이트가 읽기 전용을 막지 않으면 128개 호출부가 전부 통과한다',
  );
  // 양식 모드의 kind:'record' 예외보다 먼저 걸려야 한다.
  assert.ok(
    body.indexOf("editMode === 'readonly'") < body.indexOf("desc.kind === 'record'"),
    "record 예외가 읽기 전용보다 앞서면 기록 경로로 뮤테이션이 샌다",
  );
});

test('executeOperation 을 우회하는 경로도 읽기 전용을 막는다', () => {
  const text = read('src/engine/input-handler-text.ts');
  const keyboard = read('src/engine/input-handler-keyboard.ts');
  const handler = read('src/engine/input-handler.ts');

  // 머리말/꼬리말·각주는 wasm 을 직접 부르고 kind:'record' 로 기록만 한다.
  for (const fn of ['handleBackspace', 'handleDelete', 'onInput', 'onCompositionStart']) {
    const start = text.indexOf(`export function ${fn}(`);
    assert.notEqual(start, -1, `${fn} not found`);
    const head = text.slice(start, start + 500);
    assert.match(head, /isReadonly\?\.\(\)/, `${fn} 진입부에 읽기 전용 가드가 없다`);
  }

  for (const fn of ['onCut', 'onPaste']) {
    const start = keyboard.indexOf(`export function ${fn}(`);
    assert.notEqual(start, -1, `${fn} not found`);
    assert.match(keyboard.slice(start, start + 300), /isReadonly\?\.\(\)/,
      `${fn} 에 읽기 전용 가드가 없다`);
  }

  // 마우스 경로에도 중앙 라우터를 거치지 않는 직접 뮤테이션이 둘 있다:
  // 머리말/꼬리말 더블클릭 생성과 직선 끝점 드래그 미리보기.
  const mouse = read('src/engine/input-handler-mouse.ts');
  const hfCreate = mouse.indexOf('this.wasm.createHeaderFooter(');
  assert.notEqual(hfCreate, -1);
  assert.match(mouse.slice(hfCreate - 300, hfCreate), /isReadonly\?\.\(\)/,
    '읽기 전용에서 더블클릭이 빈 머리말/꼬리말을 만든다');
  const lineDrag = mouse.indexOf('isLineEndpointDragging && this.lineEndpointState');
  assert.notEqual(lineDrag, -1);
  assert.match(mouse.slice(lineDrag, lineDrag + 300), /isReadonly\?\.\(\)/,
    '읽기 전용에서 직선 끝점 드래그가 문서를 바꾼다');

  // 누름틀 제거는 양식 모드 분기에서 wasm 을 직접 부른다.
  const removeField = handler.slice(handler.indexOf('removeCurrentField('));
  assert.match(removeField.slice(0, 400), /editMode === 'readonly'\) return;/);

  // undo/redo 는 그 자체가 문서를 되돌리는 뮤테이션이다.
  for (const fn of ['handleUndo', 'handleRedo']) {
    const start = handler.indexOf(`private ${fn}(`);
    assert.notEqual(start, -1, `${fn} not found`);
    assert.match(handler.slice(start, start + 300), /editMode === 'readonly'\) return;/,
      `${fn} 가 읽기 전용에서 문서를 되돌린다`);
  }
});

test('텍스트 입력·삭제 술어가 읽기 전용에서 항상 false 다', () => {
  const src = read('src/engine/input-handler.ts');
  for (const fn of [
    'canInsertTextInFormMode',
    'canDeleteTextInFormMode',
    'canDeleteSelectionInFormMode',
  ]) {
    const start = src.indexOf(`  ${fn}(`);
    assert.notEqual(start, -1, `${fn} not found`);
    const body = src.slice(start, start + 400);
    assert.match(body, /editMode === 'readonly'\) return false;/, `${fn} 가 읽기 전용을 통과시킨다`);
    assert.ok(
      body.indexOf("=== 'readonly'") < body.indexOf("!== 'form'"),
      `${fn} 의 읽기 전용 검사가 양식 모드 early-return 뒤에 있으면 무력화된다`,
    );
  }
});

test('브리지 RPC 는 허용리스트 밖의 메서드를 읽기 전용에서 거부한다', () => {
  const bridge = read('public/agent-bridge.js');

  assert.match(bridge, /const READONLY_SAFE_METHODS = new Set\(/);
  assert.match(bridge, /isReadonlyNow\(\) && !READONLY_SAFE_METHODS\.has\(method\)/,
    '라우터가 게이트를 부르지 않으면 허용리스트가 장식이 된다');

  const safeBlock = bridge.slice(
    bridge.indexOf('const READONLY_SAFE_METHODS'),
    bridge.indexOf('function isReadonlyNow'),
  );
  // 문서를 바꾸는 RPC 가 허용리스트에 섞이면 안 된다.
  for (const method of [
    'insertText', 'deleteRange', 'replaceAll', 'setCellText', 'insertTable',
    'deleteTable', 'setFieldValue', 'insertPicture', 'setPageDef',
    'restoreSnapshot', 'convertToEditable', 'applyTemplate',
  ]) {
    assert.doesNotMatch(safeBlock, new RegExp(`'${method}'`), `${method} 가 허용리스트에 있다`);
  }
  for (const method of ['getFullText', 'findText', 'exportDocument', 'viewPage', 'getEditMode']) {
    assert.match(safeBlock, new RegExp(`'${method}'`), `${method} 가 읽기 전용에서 막힌다`);
  }
});

test('진입점이 URL 파라미터와 브리지 RPC 둘 다다', () => {
  const main = read('src/main.ts');
  const bridge = read('public/agent-bridge.js');

  assert.match(main, /function resolveInitialEditMode\(/);
  assert.match(main, /get\('readonly'\)/);
  // 초기 모드는 inputHandler 생성 시점에 반영돼야 첫 렌더부터 읽기 전용이다.
  assert.match(main, /let editMode: EditorEditMode = resolveInitialEditMode\(/);
  assert.match(main, /setReadonly: \(on: boolean\)/);

  assert.match(bridge, /async setReadonly\(params\)/);
  assert.match(bridge, /async getEditMode\(\)/);
});

test('?readonly=0 은 읽기 전용이 아니다', () => {
  const main = read('src/main.ts');
  const fn = main.slice(
    main.indexOf('function resolveInitialEditMode('),
    main.indexOf('let editMode: EditorEditMode'),
  );
  // 값 없는 ?readonly 는 켜짐, 명시적 0/false 만 꺼짐.
  assert.match(fn, /value === '0' \|\| value === 'false' \? 'normal' : 'readonly'/);
  assert.match(fn, /if \(value === null\) return 'normal';/);
});
