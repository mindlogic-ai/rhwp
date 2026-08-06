import type { EditorContext } from './types';

/**
 * 편집 모드별 커맨드 차단 정책.
 *
 * 디스패처(클래스)에서 분리해 둔다 — 정책은 순수 함수라 레지스트리·이벤트버스 없이
 * 그대로 검증할 수 있어야 하고, "무엇이 막히는가"가 실행 경로와 섞이면 목록이 조용히
 * 어긋난다.
 */

const FORM_MODE_BLOCKED_IDS = new Set([
  'edit:cut',
  'edit:paste',
  'edit:delete',
  'field:edit',
  'field:remove',
  // [#2361 리뷰] 편집 용지의 파일 메뉴/F7 변형. page:setup 은 'page:' prefix 로 차단되는데
  // 이 변형만 열려 있었다 — 양식 모드에선 snapshot 이 드롭되므로(입력-핸들러 게이트) 다이얼로그가
  // 열리면 확인이 무언 폐기된다. 두 진입점을 동일하게 차단해 정합.
  'file:page-setup',
]);

const FORM_MODE_BLOCKED_PREFIXES = [
  'format:',
  'insert:',
  'table:',
  'page:',
];

export function isBlockedInFormMode(commandId: string, ctx: EditorContext): boolean {
  if (!ctx.isFormMode) return false;
  if (FORM_MODE_BLOCKED_IDS.has(commandId)) return true;
  return FORM_MODE_BLOCKED_PREFIXES.some(prefix => commandId.startsWith(prefix));
}

/**
 * 읽기 전용에서 허용되는 커맨드.
 *
 * 양식 모드가 차단 목록(블록리스트)인 것과 달리 읽기 전용은 허용 목록(허용리스트)이다.
 * 커맨드가 새로 늘어날 때 기본값이 "차단"이어야 안전하기 때문이다 — 블록리스트였다면
 * 신규 편집 커맨드가 목록에 등재되기 전까지 읽기 전용을 그대로 통과한다.
 */
const READONLY_ALLOWED_PREFIXES = ['view:'];

const READONLY_ALLOWED_IDS = new Set([
  'edit:copy',
  'edit:select-all',
  'edit:find',
  'edit:find-again',
  'edit:goto',
  'edit:compare-documents',
  'file:print',
  'file:print-to-pdf',
  'file:about',
  // 저장/내보내기는 문서를 바꾸지 않고 현재 상태를 밖으로 쓸 뿐이라 허용한다.
  'file:save',
  'file:save-as',
  'file:save-as-hwp',
  'file:save-as-hwpx',
  'tool:options',
]);

// view: 접두어로 열려 있지만 읽기 전용을 스스로 벗겨내므로 막아야 하는 것.
const READONLY_BLOCKED_IDS = new Set(['view:form-mode']);

export function isBlockedInReadonly(commandId: string, ctx: EditorContext): boolean {
  if (!ctx.isReadonly) return false;
  if (READONLY_BLOCKED_IDS.has(commandId)) return true;
  if (READONLY_ALLOWED_IDS.has(commandId)) return false;
  return !READONLY_ALLOWED_PREFIXES.some(prefix => commandId.startsWith(prefix));
}

/** 현재 모드에서 이 커맨드가 막히는가? */
export function isBlockedInEditMode(commandId: string, ctx: EditorContext): boolean {
  return isBlockedInFormMode(commandId, ctx) || isBlockedInReadonly(commandId, ctx);
}
