import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

// [FactChat 포크] editor_lock 중 읽기 허용.
//
// 잠금은 원래 #editor-area 까지 pointer-events:none 으로 덮어서 스크롤·드래그 선택까지
// 죽였다. 사용자에게는 "쓰기 금지"가 아니라 "화면이 멈춤"으로 보였고, 에이전트가 손대지
// 않는 페이지조차 읽을 수 없었다. 이제 편집 차단은 스튜디오 readonly 가 맡고 포인터는
// 열어 둔다. 그 대가로 세 가지가 동시에 성립해야 한다:
//
//   1. 잠금이 스튜디오 readonly 를 켜고, 해제 때 이전 모드로 정확히 되돌린다
//   2. RPC 게이트가 viewer readonly 와 잠금 readonly 를 구분한다
//      (구분 못 하면 턴 중 잠금이 그 턴의 편집 RPC 를 전부 거절한다)
//   3. 잠금 중 pointerdown 이 quietUntilUserInput 을 풀지 않는다
//      (풀리면 에이전트 mutation 이 phantom user_edit 리비전으로 샌다)

const rootDir = dirname(dirname(fileURLToPath(import.meta.url)));
const bridge = readFileSync(join(rootDir, 'public/agent-bridge.js'), 'utf8');
const main = readFileSync(join(rootDir, 'src/main.ts'), 'utf8');

/** 이름이 붙은 함수 선언의 본문을 대략 잘라 온다. */
function fnBody(src: string, decl: string, span = 900): string {
  const start = src.indexOf(decl);
  assert.notEqual(start, -1, `${decl} not found`);
  return src.slice(start, start + span);
}

test('잠금 CSS 가 편집 영역의 포인터를 죽이지 않는다', () => {
  const lockCss = bridge.slice(
    bridge.indexOf('lockStyle.textContent'),
    bridge.indexOf('document.head.appendChild(lockStyle)'),
  );
  assert.ok(lockCss.length > 0, '잠금 스타일 블록을 찾지 못했다');

  const pointerRule = lockCss
    .split('\n')
    .find(line => line.includes('pointer-events: none') && line.includes('agent-locked'));
  assert.ok(pointerRule, 'agent-locked pointer-events 규칙이 없다');

  assert.doesNotMatch(
    pointerRule,
    /#editor-area/,
    '#editor-area 가 다시 포함되면 잠금 중 스크롤·드래그 선택이 죽는다',
  );
  // 툴바·메뉴는 계속 죽인다.
  for (const sel of ['#menu-bar', '#icon-toolbar', '#style-bar']) {
    assert.match(pointerRule, new RegExp(sel), `${sel} 는 잠금 중 차단돼야 한다`);
  }
});

test('잠금이 스튜디오 readonly 를 켜고 해제 때 이전 모드로 되돌린다', () => {
  const body = fnBody(bridge, 'function setLocked(b) {');

  assert.match(body, /setStudioEditMode\('readonly'\)/, '잠금이 편집을 막지 않는다');
  assert.match(body, /agentTurnReadonly = true/);
  // 이전 모드 복원 — setReadonly(false) 로 뭉개면 양식 모드 세션이 일반 모드가 된다.
  assert.match(body, /setStudioEditMode\(preLockEditMode \|\| 'normal'\)/);
  assert.match(body, /agentTurnReadonly = false/);
});

test('이미 viewer readonly 인 세션은 잠금이 건드리지 않는다', () => {
  const body = fnBody(bridge, 'function setLocked(b) {');
  // 잠금 해제가 뷰어 세션을 편집 가능으로 바꿔 버리면 안 된다.
  assert.match(
    body,
    /if \(agentTurnReadonly \|\| studioEditMode\(\) === 'readonly'\) return;/,
    'viewer readonly 세션에 잠금 복원 정보가 덮어써진다',
  );
});

test('RPC 게이트는 viewer readonly 에만 걸린다', () => {
  assert.match(
    bridge,
    /function isViewerReadonly\(\) \{[\s\S]*?studioEditMode\(\) === 'readonly' && !agentTurnReadonly/,
  );
  const gate = fnBody(bridge, 'function isReadonlyNow()', 400);
  assert.match(gate, /return isViewerReadonly\(\);/,
    '잠금 readonly 까지 게이트에 걸리면 그 턴의 편집 RPC 가 전부 거절된다');

  // 라우터가 여전히 게이트를 부르는지도 같이 고정한다.
  assert.match(bridge, /isReadonlyNow\(\) && !READONLY_SAFE_METHODS\.has\(method\)/);
});

test('에이전트가 실제로 쓰는 편집 RPC 는 잠금 중 통과한다', () => {
  // 이 메서드들은 SAFE 목록에 없다 — 즉 viewer readonly 에서는 막히고, 잠금
  // readonly 에서는 게이트 자체가 꺼지므로 통과한다. 두 성질을 함께 핀한다.
  const safeBlock = bridge.slice(
    bridge.indexOf('const READONLY_SAFE_METHODS'),
    bridge.indexOf('function isReadonlyNow'),
  );
  for (const method of ['insertText', 'replaceAll', 'replaceOne', 'setCellText',
    'deleteRange', 'applyTextStyle', 'insertParagraphAfter']) {
    assert.doesNotMatch(safeBlock, new RegExp(`'${method}'`),
      `${method} 가 SAFE 에 들어가면 viewer readonly 가 뚫린다`);
  }
  // loadFile 은 뷰어 세션에서도 열려 있어야 한다(문서를 여는 것은 편집이 아니다).
  assert.match(safeBlock, /'loadFile'/);
});

test('잠금 중 스크롤·선택이 quietUntilUserInput 을 풀지 않는다', () => {
  const listener = bridge.slice(
    bridge.indexOf("['keydown', 'pointerdown', 'beforeinput', 'paste', 'drop']"),
    bridge.indexOf('agentMutationReported = false'),
  );
  assert.ok(listener.length > 0, 'quiet 리스너 블록을 찾지 못했다');
  assert.match(
    listener,
    /agent-locked'\)\) return;/,
    '잠금 중 드래그 선택만으로 quiet 가 풀리면 phantom user_edit 리비전이 생긴다',
  );
  // 가드가 대입보다 앞에 있어야 의미가 있다.
  assert.ok(
    listener.indexOf('agent-locked') < listener.indexOf('quietUntilUserInput = false'),
  );
});

test('호스트가 명시로 건 readonly 는 viewer 로 남는다', () => {
  const handler = fnBody(bridge, 'async setReadonly(params)');
  // 잠금이 켠 상태를 호스트가 덮어썼는데 잠금 해제 때 되살아나면 의도가 뒤집힌다.
  assert.match(handler, /agentTurnReadonly = false;/);
  assert.match(handler, /preLockEditMode = null;/);
});

test('getEditMode 가 readonly 의 유래를 알려준다', () => {
  const handler = fnBody(bridge, 'async getEditMode()');
  assert.match(handler, /readonly_reason/);
  assert.match(handler, /agentTurnReadonly \? 'agent-turn' : 'viewer'/);
});

test('스튜디오가 임의 편집 모드 지정을 노출한다', () => {
  // setReadonly 만으로는 readonly ↔ normal 만 오가서 양식 모드 복원이 불가능하다.
  const api = main.slice(
    main.indexOf('(window as any).rhwpStudio = {'),
    main.indexOf('// factchat HWP agent: expose globals'),
  );
  assert.match(api, /setEditMode: \(mode: EditorEditMode\)/);
  assert.match(api, /unknown edit mode/, '잘못된 모드 문자열을 그대로 넘기면 안 된다');
});
