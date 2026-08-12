import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

// [FactChat 포크] 저장 위임 계약.
//
// 임베드에서 스튜디오가 스스로 파일을 내려주면 안 된다. exportHwp 바이트는 rhwp
// 밖에서 열리지 않는다 — 한컴은 "손상된 파일" 이라 하고 한컴 컨버터도 F040 으로
// 거부한다. 그래서 저장 진입점은 전부 부모 FE 로 넘겨 서버 변환을 태운다.
//
// index.html 의 `disabled` 클래스는 방어선이 아니다. menu-bar 가 드롭다운을 열
// 때마다 dispatcher.isEnabled() 로 다시 칠하므로 항목은 실제로 살아 있다.

const rootDir = dirname(dirname(fileURLToPath(import.meta.url)));
const read = (rel: string) => readFileSync(join(rootDir, rel), 'utf8');

test('브리지가 스튜디오 저장 커맨드를 부모로 위임한다', () => {
  const bridge = read('public/agent-bridge.js');

  for (const [cmd, format] of [
    ['file:save', 'default'],
    ['file:save-as', 'default'],
    ['file:save-as-hwp', 'hwp'],
    ['file:save-as-hwpx', 'hwpx'],
  ]) {
    assert.match(
      bridge,
      new RegExp(`'${cmd}':\\s*'${format}'`),
      `${cmd} → save_requested ${format} 매핑이 없다`,
    );
  }

  assert.match(bridge, /\.md-item\[data-cmd\]/);
  assert.match(bridge, /stopImmediatePropagation\(\)/);
});

test('임베드가 아니면 가로채지 않는다', () => {
  const bridge = read('public/agent-bridge.js');

  // 넘길 부모가 없는 단독 실행에서는 스튜디오 자체 저장이 유일한 저장 수단이다.
  assert.match(bridge, /const fcEmbedded = window\.parent !== window/);
  assert.match(bridge, /fcEmbedded\s*\n?\s*\?\s*FC_SAVE_CMD_FORMATS/);
});

test('menu-bar 가 disabled 를 매번 다시 칠한다 — 마크업은 방어선이 아니다', () => {
  const menuBar = read('src/ui/menu-bar.ts');

  assert.match(menuBar, /isEnabled\(cmdId\)/);
  assert.match(menuBar, /classList\.toggle\('disabled', !enabled\)/);
});
