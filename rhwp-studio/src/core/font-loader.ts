/**
 * 웹폰트 로더 — web/editor.html의 폰트 로딩 시스템을 TypeScript로 포팅
 *
 * 2계층 로딩:
 *   1. CSS @font-face 규칙 생성 (Canvas 2D 호환)
 *   2. FontFace API로 즉시 로드 + document.fonts.add()
 */

interface FontEntry {
  name: string;
  file: string;
  /** woff2(기본), woff, 또는 원본 TTF 파일용 truetype */
  format?: 'woff2' | 'woff' | 'truetype';
  /** CSS unicode-range — 지정 시 해당 코드포인트만 매칭, 다운로드도 해당 영역 사용 시에만 발생 */
  unicodeRange?: string;
}

// 한컴 webhwp CSS(@font-face) 매핑 기준 + HWP 문서에서 사용하는 별칭
const FONT_LIST: FontEntry[] = [
  // === 함초롬/함초롱/한컴 폰트 (webhwp WebHWP SDK 동봉본 — Hancom UnlicenseFontList 등재) ===
  { name: '함초롬돋움', file: 'fonts/HANDotum.ttf', format: 'truetype' },
  { name: '함초롬돋움 Bold', file: 'fonts/HANDotumB.ttf', format: 'truetype' },
  { name: '함초롬돋움 확장', file: 'fonts/HANDotumExt.ttf', format: 'truetype' },
  { name: '함초롬바탕', file: 'fonts/HANBatang.ttf', format: 'truetype' },
  { name: '함초롬바탕 Bold', file: 'fonts/HANBatangB.ttf', format: 'truetype' },
  { name: '함초롬바탕 확장', file: 'fonts/HANBatangExt.ttf', format: 'truetype' },
  { name: '함초롬바탕 확장B', file: 'fonts/HANBatangExtB.ttf', format: 'truetype' },
  { name: '함초롬바탕 확장B Bold', file: 'fonts/HANBatangExtBB.ttf', format: 'truetype' },
  { name: '함초롱돋움', file: 'fonts/HANDotum.ttf', format: 'truetype' },
  { name: '함초롱바탕', file: 'fonts/HANBatang.ttf', format: 'truetype' },
  { name: '한컴돋움', file: 'fonts/HANDotum.ttf', format: 'truetype' },
  { name: '한컴바탕', file: 'fonts/HANBatang.ttf', format: 'truetype' },
  { name: '새돋움', file: 'fonts/HANDotum.ttf', format: 'truetype' },
  { name: '새바탕', file: 'fonts/HANBatang.ttf', format: 'truetype' },
  // === 한컴 HY 폰트 → 오픈소스 대체 ===
  { name: 'HY헤드라인M', file: 'fonts/NotoSansKR-Bold.woff2' },
  { name: 'HYHeadLine M', file: 'fonts/NotoSansKR-Bold.woff2' },
  { name: 'HYHeadLine Medium', file: 'fonts/NotoSansKR-Bold.woff2' },
  { name: 'HY견고딕', file: 'fonts/NotoSansKR-Bold.woff2' },
  { name: 'HYGothic-Extra', file: 'fonts/NotoSansKR-Bold.woff2' },
  { name: 'HY그래픽', file: 'fonts/NotoSansKR-Regular.woff2' },
  { name: 'HYGraphic-Medium', file: 'fonts/NotoSansKR-Regular.woff2' },
  { name: 'HY그래픽M', file: 'fonts/NotoSansKR-Regular.woff2' },
  { name: 'HY견명조', file: 'fonts/NotoSerifKR-Bold.woff2' },
  { name: 'HYMyeongJo-Extra', file: 'fonts/NotoSerifKR-Bold.woff2' },
  { name: 'HY신명조', file: 'fonts/NotoSerifKR-Regular.woff2' },
  { name: 'HY중고딕', file: 'fonts/NotoSansKR-Regular.woff2' },
  { name: '양재튼튼체B', file: 'fonts/NotoSansKR-Bold.woff2' },
  { name: '휴먼명조', file: 'fonts/NanumMyeongjo-Regular.woff2' },
  { name: '휴먼고딕', file: 'fonts/NanumGothic-Regular.woff2' },
  // === 한글 시스템 폰트 → 오픈소스 대체 (OS 폰트 없을 때 폴백) ===
  { name: 'Malgun Gothic', file: 'fonts/Pretendard-Regular.woff2' },
  { name: '맑은 고딕', file: 'fonts/Pretendard-Regular.woff2' },
  { name: '돋움', file: 'fonts/NotoSansKR-Regular.woff2' },
  { name: '돋움체', file: 'fonts/NotoSansKR-Regular.woff2' },
  { name: '굴림', file: 'fonts/NotoSansKR-Regular.woff2' },
  { name: '굴림체', file: 'fonts/D2Coding-Regular.woff2' },
  { name: '새굴림', file: 'fonts/NotoSansKR-Regular.woff2' },
  { name: '바탕', file: 'fonts/NotoSerifKR-Regular.woff2' },
  { name: '바탕체', file: 'fonts/D2Coding-Regular.woff2' },
  { name: '궁서', file: 'fonts/GowunBatang-Regular.woff2' },
  { name: '궁서체', file: 'fonts/GowunBatang-Regular.woff2' },
  { name: '새궁서', file: 'fonts/GowunBatang-Regular.woff2' },
  // === 경기천년체 (경기도 공식 배포, 로컬) ===
  { name: '경기천년바탕', file: 'fonts/GyeonggiBatang-Regular.woff', format: 'woff' },
  { name: '경기천년바탕 Regular', file: 'fonts/GyeonggiBatang-Regular.woff', format: 'woff' },
  { name: '경기천년바탕 Bold', file: 'fonts/GyeonggiBatang-Bold.woff', format: 'woff' },
  { name: '경기천년제목', file: 'fonts/GyeonggiTitle-Medium.woff', format: 'woff' },
  { name: '경기천년제목 Light', file: 'fonts/GyeonggiTitle-Light.woff', format: 'woff' },
  { name: '경기천년제목 Medium', file: 'fonts/GyeonggiTitle-Medium.woff', format: 'woff' },
  { name: '경기천년제목 Bold', file: 'fonts/GyeonggiTitle-Bold.woff', format: 'woff' },
  { name: '경기천년제목V', file: 'fonts/GyeonggiTitleV.woff', format: 'woff' },
  { name: '경기천년제목V Bold', file: 'fonts/GyeonggiTitleV.woff', format: 'woff' },
  // === KoPubWorld 원본 TTF (한국출판인회의 배포) ===
  { name: 'KoPub돋움체 Light', file: 'fonts/KoPubWorld Dotum Light.ttf', format: 'truetype' },
  { name: 'KoPub돋움체 Medium', file: 'fonts/KoPubWorld Dotum Medium.ttf', format: 'truetype' },
  { name: 'KoPub돋움체 Bold', file: 'fonts/KoPubWorld Dotum Bold.ttf', format: 'truetype' },
  { name: 'KoPub바탕체 Light', file: 'fonts/KoPubWorld Batang Light.ttf', format: 'truetype' },
  { name: 'KoPub바탕체 Bold', file: 'fonts/KoPubWorld Batang Bold.ttf', format: 'truetype' },
  { name: 'KoPubWorld돋움체 Light', file: 'fonts/KoPubWorld Dotum Light.ttf', format: 'truetype' },
  { name: 'KoPubWorld돋움체 Medium', file: 'fonts/KoPubWorld Dotum Medium.ttf', format: 'truetype' },
  { name: 'KoPubWorld돋움체 Bold', file: 'fonts/KoPubWorld Dotum Bold.ttf', format: 'truetype' },
  { name: 'KoPubWorld바탕체 Light', file: 'fonts/KoPubWorld Batang Light.ttf', format: 'truetype' },
  { name: 'KoPubWorld바탕체 Bold', file: 'fonts/KoPubWorld Batang Bold.ttf', format: 'truetype' },
  // === EBS 주시경체 원본 TTF (EBS 공식 배포) ===
  { name: 'EBS전용서체-L', file: 'fonts/EBS-Jusigyeong-L.ttf', format: 'truetype' },
  { name: 'EBS주시경 Light', file: 'fonts/EBS-Jusigyeong-L.ttf', format: 'truetype' },
  { name: 'EBSJSK Light', file: 'fonts/EBS-Jusigyeong-L.ttf', format: 'truetype' },
  // === Garamond → EB Garamond (OFL, Garamond 호환 리바이벌, 로컬) ===
  { name: 'Garamond', file: 'fonts/EBGaramond-Regular.ttf', format: 'truetype' },
  // === 한컴/HY 번들 서체 (webhwp WebHWP SDK 동봉본 — Hancom UnlicenseFontList 등재) ===
  { name: '한컴 고딕', file: 'fonts/Hancom Gothic Regular.ttf', format: 'truetype' },
  { name: 'Hancom Gothic', file: 'fonts/Hancom Gothic Regular.ttf', format: 'truetype' },
  { name: '한컴 고딕 Bold', file: 'fonts/Hancom Gothic Bold.ttf', format: 'truetype' },
  { name: 'HY수평선M', file: 'fonts/HYSUPM.TTF', format: 'truetype' },
  { name: 'HY수평선B', file: 'fonts/HYSUPB.TTF', format: 'truetype' },
  { name: 'HY울릉도M', file: 'fonts/HYWULM.TTF', format: 'truetype' },
  { name: 'HY울릉도B', file: 'fonts/HYWULB.TTF', format: 'truetype' },
  { name: 'HY태백B', file: 'fonts/HYTBRB.TTF', format: 'truetype' },
  { name: 'HY동녘M', file: 'fonts/HYDNKM.TTF', format: 'truetype' },
  { name: 'HY동녘B', file: 'fonts/HYDNKB.TTF', format: 'truetype' },
  { name: 'HY산B', file: 'fonts/HYSANB.TTF', format: 'truetype' },
  // === 한컴 윤고딕 (HWP 번들 Yoon 서체 — 2026-06-10 한컴 사용 허락 확보, webhwp SDK 원본) ===
  { name: '한컴 윤고딕 230', file: 'fonts/HANYGO230.ttf', format: 'truetype' },
  { name: '한컴 윤고딕 240', file: 'fonts/HANYGO240.ttf', format: 'truetype' },
  { name: '한컴 윤고딕 250', file: 'fonts/HANYGO250.ttf', format: 'truetype' },
  { name: '한컴 윤고딕 720', file: 'fonts/HANYoonGothic720.ttf', format: 'truetype' },
  { name: '한컴 윤고딕 740', file: 'fonts/HANYoonGothic740.ttf', format: 'truetype' },
  { name: '한컴 윤고딕 760', file: 'fonts/HANYoonGothic760.ttf', format: 'truetype' },
  // === 윤폰트 명시적 폴백 정책 (윤디자인 1XX/3XX 시리즈 — 라이선스 확보 전까지; 윤명조→KoPub바탕, 윤고딕→KoPub돋움) ===
  { name: '-윤명조120', file: 'fonts/KoPubWorld Batang Light.ttf', format: 'truetype' },
  { name: '-윤명조140', file: 'fonts/KoPubWorld Batang Light.ttf', format: 'truetype' },
  { name: '-윤명조310', file: 'fonts/KoPubWorld Batang Light.ttf', format: 'truetype' },
  { name: '-윤명조320', file: 'fonts/KoPubWorld Batang Light.ttf', format: 'truetype' },
  { name: '-윤명조330', file: 'fonts/KoPubWorld Batang Light.ttf', format: 'truetype' },
  { name: '-윤명조340', file: 'fonts/KoPubWorld Batang Bold.ttf', format: 'truetype' },
  { name: '-윤명조350', file: 'fonts/KoPubWorld Batang Bold.ttf', format: 'truetype' },
  { name: '-윤고딕120', file: 'fonts/KoPubWorld Dotum Light.ttf', format: 'truetype' },
  { name: '-윤고딕130', file: 'fonts/KoPubWorld Dotum Light.ttf', format: 'truetype' },
  { name: '-윤고딕320', file: 'fonts/KoPubWorld Dotum Medium.ttf', format: 'truetype' },
  { name: '-윤고딕330', file: 'fonts/KoPubWorld Dotum Medium.ttf', format: 'truetype' },
  { name: '-윤고딕340', file: 'fonts/KoPubWorld Dotum Bold.ttf', format: 'truetype' },
  { name: 'Yoon가변 윤명조 320_TT', file: 'fonts/KoPubWorld Batang Light.ttf', format: 'truetype' },
  { name: 'Yoon가변 윤고딕 140_TT', file: 'fonts/KoPubWorld Dotum Light.ttf', format: 'truetype' },
  { name: 'Yoon가변 윤고딕 320_TT', file: 'fonts/KoPubWorld Dotum Medium.ttf', format: 'truetype' },
  { name: 'Yoon가변 윤고딕 330_TT', file: 'fonts/KoPubWorld Dotum Medium.ttf', format: 'truetype' },
  // === 기타 미보유 서체 폴백 ===
  { name: '휴먼둥근헤드라인', file: 'fonts/NotoSansKR-Bold.woff2' },
  { name: '순천향체', file: 'fonts/KoPubWorld Batang Light.ttf', format: 'truetype' },
  // === 나눔 폰트 (OFL, 로컬) ===
  { name: '나눔고딕', file: 'fonts/NanumGothic-Regular.woff2' },
  { name: '나눔고딕 Light', file: 'fonts/NanumGothic-Light.woff2' },
  { name: '나눔고딕 Bold', file: 'fonts/NanumGothic-Bold.woff2' },
  { name: '나눔고딕 ExtraBold', file: 'fonts/NanumGothic-ExtraBold.woff2' },
  { name: 'NanumGothic Light', file: 'fonts/NanumGothic-Light.woff2' },
  { name: 'NanumGothicLight', file: 'fonts/NanumGothic-Light.woff2' },
  { name: 'NanumGothic Bold', file: 'fonts/NanumGothic-Bold.woff2' },
  { name: 'NanumGothic ExtraBold', file: 'fonts/NanumGothic-ExtraBold.woff2' },
  { name: 'NanumGothicExtraBold', file: 'fonts/NanumGothic-ExtraBold.woff2' },
  { name: '나눔명조', file: 'fonts/NanumMyeongjo-Regular.woff2' },
  { name: '나눔명조 Bold', file: 'fonts/NanumMyeongjo-Bold.woff2' },
  { name: '나눔명조 ExtraBold', file: 'fonts/NanumMyeongjo-ExtraBold.woff2' },
  { name: 'NanumMyeongjo Bold', file: 'fonts/NanumMyeongjo-Bold.woff2' },
  { name: 'NanumMyeongjo ExtraBold', file: 'fonts/NanumMyeongjo-ExtraBold.woff2' },
  { name: 'NanumMyeongjoExtraBold', file: 'fonts/NanumMyeongjo-ExtraBold.woff2' },
  { name: '나눔고딕코딩', file: 'fonts/NanumGothicCoding-Regular.woff2' },
  // === 영문 폰트 → OS 폴백 (번들 제거) ===
  { name: 'Palatino Linotype', file: 'fonts/NotoSerifKR-Regular.woff2' },
  // === Noto (OFL, 로컬) ===
  { name: 'Noto Sans KR', file: 'fonts/NotoSansKR-Regular.woff2' },
  { name: 'Noto Serif KR', file: 'fonts/NotoSerifKR-Regular.woff2' },
  // === Pretendard ===
  { name: 'Pretendard', file: 'fonts/Pretendard-Regular.woff2' },
  { name: 'Pretendard Thin', file: 'fonts/Pretendard-Thin.woff2' },
  { name: 'Pretendard ExtraLight', file: 'fonts/Pretendard-ExtraLight.woff2' },
  { name: 'Pretendard Light', file: 'fonts/Pretendard-Light.woff2' },
  { name: 'Pretendard Medium', file: 'fonts/Pretendard-Medium.woff2' },
  { name: 'Pretendard SemiBold', file: 'fonts/Pretendard-SemiBold.woff2' },
  { name: 'Pretendard Bold', file: 'fonts/Pretendard-Bold.woff2' },
  { name: 'Pretendard ExtraBold', file: 'fonts/Pretendard-ExtraBold.woff2' },
  { name: 'Pretendard Black', file: 'fonts/Pretendard-Black.woff2' },
  // === D2 Coding (OFL, 로컬) ===
  { name: 'D2Coding', file: 'fonts/D2Coding-Regular.woff2' },
  // === Happiness Sans ===
  { name: '해피니스 산스 레귤러', file: 'fonts/Happiness-Sans-Regular.woff2' },
  { name: 'Happiness Sans Regular', file: 'fonts/Happiness-Sans-Regular.woff2' },
  { name: '해피니스 산스 볼드', file: 'fonts/Happiness-Sans-Bold.woff2' },
  { name: 'Happiness Sans Bold', file: 'fonts/Happiness-Sans-Bold.woff2' },
  { name: '해피니스 산스 타이틀', file: 'fonts/Happiness-Sans-Title.woff2' },
  { name: 'Happiness Sans Title', file: 'fonts/Happiness-Sans-Title.woff2' },
  { name: '해피니스 산스 VF', file: 'fonts/HappinessSansVF.woff2' },
  { name: 'Happiness Sans VF', file: 'fonts/HappinessSansVF.woff2' },
  // === Cafe24 ===
  { name: 'Cafe24 Ssurround Bold', file: 'fonts/Cafe24Ssurround-v2.0.woff2' },
  { name: '카페24 슈퍼매직', file: 'fonts/Cafe24Supermagic-Regular-v1.0.woff2' },
  { name: 'Cafe24 Supermagic', file: 'fonts/Cafe24Supermagic-Regular-v1.0.woff2' },
  // === 수식 전용 폰트 (OFL/GUST, 로컬) ===
  { name: 'Latin Modern Math', file: 'fonts/LatinModernMath-Regular.woff2' },
  // === 기타 ===
  { name: 'SpoqaHanSans', file: 'fonts/SpoqaHanSans-Regular.woff2' },
  // === Gowun (OFL, 로컬) ===
  { name: '고운바탕', file: 'fonts/GowunBatang-Regular.woff2' },
  { name: '고운돋움', file: 'fonts/GowunDodum-Regular.woff2' },
  // === Source Han Serif K Old Hangul (Task #528, OFL, 로컬, 옛한글 자모 한정 subset) ===
  // PUA 옛한글 (HanCom 자체 인코딩) 을 KS X 1026-1:2007 자모 시퀀스로 변환 후
  // 합자 렌더링용. unicode-range 로 옛한글 영역에서만 매칭 → 일반 한글 영향 0.
  {
    name: 'Source Han Serif K Old Hangul',
    file: 'fonts/SourceHanSerifK-OldHangul-subset.woff2',
    unicodeRange: 'U+1100-11FF, U+A960-A97F, U+D7B0-D7FF',
  },
];

/** @font-face에 등록된 폰트 이름 Set */
export const REGISTERED_FONTS = new Set(FONT_LIST.map(f => f.name));

/** 초기 렌더링에 필수인 폰트 (대부분의 HWP 문서 기본 서체) */
const CRITICAL_FONTS = new Set(['함초롬바탕', '함초롬돋움']);

/** CSS @font-face 등록 여부 (중복 등록 방지) */
let fontFaceRegistered = false;

/** 이미 로드 완료된 woff2 파일 (중복 네트워크 요청 방지) */
const loadedFiles = new Set<string>();

/**
 * OS에 설치된 폰트인지 감지한다 (document.fonts.check 기반).
 * @font-face 등록 전에 호출해야 정확하다.
 */
const OS_FONT_CANDIDATES = [
  // Windows
  '맑은 고딕', 'Malgun Gothic', '바탕', 'Batang', '돋움', 'Dotum',
  '굴림', 'Gulim', '굴림체', 'GulimChe', '바탕체', 'BatangChe', '궁서', 'Gungsuh',
  // macOS / iOS
  'Apple SD Gothic Neo', 'AppleMyungjo', 'AppleGothic',
  // Android
  'Noto Sans KR', 'Noto Serif KR',
];
const detectedOSFonts = new Set<string>();

/** OS 폰트 감지 실행 (@font-face 등록 전에 호출) */
function detectOSFonts(): void {
  for (const name of OS_FONT_CANDIDATES) {
    try {
      if (document.fonts.check(`16px "${name}"`)) {
        detectedOSFonts.add(name);
      }
    } catch { /* 무시 */ }
  }
  if (detectedOSFonts.size > 0) {
    console.log(`[FontLoader] OS 폰트 감지: ${Array.from(detectedOSFonts).join(', ')}`);
  }
}

/** 감지된 OS 폰트 목록 (외부 참조용) */
export function getDetectedOSFonts(): ReadonlySet<string> {
  return detectedOSFonts;
}

/**
 * 웹폰트를 선별 로드한다.
 *   1단계(동기): CSS @font-face 전체 등록 (최초 1회, 네트워크 미발생)
 *   2단계: 대상 폰트 로드 (이미 로드된 파일은 건너뜀)
 *
 * @param docFonts 문서에서 사용하는 폰트 이름 목록 (있으면 해당 폰트 + CRITICAL만 로드, 없으면 전체)
 * @param onProgress 폰트 로드 진행률 콜백 (loaded, total)
 */
export async function loadWebFonts(
  docFonts?: string[],
  onProgress?: (loaded: number, total: number) => void,
): Promise<void> {
  // 0) OS 폰트 감지 (@font-face 등록 전에 실행해야 정확)
  if (!fontFaceRegistered) {
    detectOSFonts();
  }

  // 1) CSS @font-face 규칙 전체 등록 (네트워크 미발생, 최초 1회만)
  if (!fontFaceRegistered) {
    const style = document.createElement('style');
    style.textContent = FONT_LIST.map(f => {
      const fmt = f.format ?? 'woff2';
      const ur = f.unicodeRange ? ` unicode-range: ${f.unicodeRange};` : '';
      return `@font-face { font-family: "${f.name}"; src: url("${f.file}") format("${fmt}"); font-display: swap;${ur} }`;
    }).join('\n');
    document.head.appendChild(style);
    fontFaceRegistered = true;
  }

  // 2) 로드 대상 결정: docFonts에 포함된 폰트 + CRITICAL만 로드
  //    OS에 설치된 폰트는 웹폰트 로딩 건너뜀
  const targetSet = new Set([...(docFonts ?? []), ...CRITICAL_FONTS]);
  const toLoad = FONT_LIST.filter(f => {
    if (!targetSet.has(f.name)) return false;
    // OS에 동일 이름 폰트가 있으면 웹폰트 로딩 불필요
    if (detectedOSFonts.has(f.name)) return false;
    return true;
  });

  // woff2 파일 기준으로 중복 제거 + 이미 로드된 파일 건너뜀
  const seenFiles = new Set<string>();
  const uniqueToLoad: FontEntry[] = [];
  for (const f of toLoad) {
    if (!seenFiles.has(f.file) && !loadedFiles.has(f.file)) {
      seenFiles.add(f.file);
      uniqueToLoad.push(f);
    }
  }

  if (uniqueToLoad.length === 0) return;

  const total = uniqueToLoad.length;
  console.log(`[FontLoader] 웹폰트 로드 시작: ${total}개 woff2 (이미 로드됨: ${loadedFiles.size}개)`);

  // 같은 woff2 파일에 매핑된 모든 이름도 함께 등록
  const fileToNames = new Map<string, string[]>();
  for (const f of toLoad) {
    if (!loadedFiles.has(f.file)) {
      const names = fileToNames.get(f.file) ?? [];
      names.push(f.name);
      fileToNames.set(f.file, names);
    }
  }

  let loaded = 0;
  let failed = 0;
  const BATCH = 4;

  for (let i = 0; i < uniqueToLoad.length; i += BATCH) {
    const batch = uniqueToLoad.slice(i, i + BATCH);
    await Promise.all(batch.map(async (f) => {
      try {
        const names = fileToNames.get(f.file) ?? [f.name];
        const fmt = f.format ?? 'woff2';
        for (const name of names) {
          const face = new FontFace(name, `url(${f.file}) format('${fmt}')`);
          const result = await face.load();
          document.fonts.add(result);
        }
        loadedFiles.add(f.file);
        loaded++;
      } catch {
        failed++;
      }
      onProgress?.(loaded + failed, total);
    }));
    if (i + BATCH < uniqueToLoad.length) {
      await new Promise(r => setTimeout(r, 0));
    }
  }

  console.log(`[FontLoader] 폰트 로드 완료: ${loaded}개 성공, ${failed}개 실패 (총 ${loadedFiles.size}개 woff2 로드됨)`);
}
