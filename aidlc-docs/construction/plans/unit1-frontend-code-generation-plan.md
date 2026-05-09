# Unit 1 Frontend — Code Generation Plan
# 집에 가구 쉽다 (Easy Furniture Fit)

**코드 위치**: `/Users/ddong/opensw/frontend/`
**스토리 커버리지**: US-01~18 (MVP), US-19~21 UI만

---

## 컨텍스트

| 항목 | 내용 |
|------|------|
| 기술 스택 | React 18 + Vite + TypeScript + Tailwind CSS v4 |
| 패키지 매니저 | pnpm |
| 라우팅 | React Router v6 |
| 배포 | Vercel |
| 외부 의존성 | Backend API (`VITE_API_URL`) |

---

## 실행 단계

### Step 1: 프로젝트 초기 설정 ✅
- [x] Vite + React + TypeScript 프로젝트 생성 (`frontend/`)
- [x] Tailwind CSS v4 설치 및 설정 (`@tailwindcss/vite` 플러그인, `vite.config.ts`에 추가)
- [x] React Router v6 설치
- [x] ESLint + Prettier 설정 (`eslint.config.js`, `.prettierrc`)
- [x] `tsconfig.json` 경로 alias 설정 (`@/` → `src/`)
- [x] `vercel.json` 생성 (SPA 리라이트 설정)
- [x] `public/manifest.json` 생성 (PWA 설치 지원)
- [x] `.env.example` 생성 (`VITE_API_URL`)
- [x] `src/index.css` — Tailwind import + shake/bounceDot 애니메이션
- [x] `src/vite-env.d.ts` — 환경변수 타입 선언

### Step 2: 공통 컴포넌트 ✅
> 관련 스토리: 전체 공통 사용
- [x] `src/components/Button.tsx`
- [x] `src/components/NavBar.tsx`
- [x] `src/components/ProgressBar.tsx`
- [x] `src/components/Toast.tsx`

### Step 3: API 레이어 ✅
> 관련 스토리: US-04, US-08
- [x] `src/api/furniture.ts`

### Step 4: 라우터 설정 ✅
> 관련 스토리: US-02, US-13
- [x] `src/router.tsx`
- [x] `src/main.tsx`
- [x] `src/index.css` — @theme 디자인 토큰 + 커스텀 애니메이션

### Step 5: HomePage ✅
- [x] `src/pages/HomePage/HomePage.tsx`

### Step 6: UrlInputPage ✅
- [x] `src/pages/UrlInputPage/UrlInputPage.tsx` — 링크 아이콘 input, 플랫폼 칩, 데모 카드 인라인
- ~~`src/pages/UrlInputPage/components/DemoLinkButton.tsx`~~ — UrlInputPage 내부로 통합으로 제거

### Step 7: LoadingPage ✅
- [x] `src/pages/LoadingPage/components/BouncingDots.tsx`
- [x] `src/pages/LoadingPage/components/StepList.tsx`
- [x] `src/pages/LoadingPage/LoadingPage.tsx`

### Step 8: ModelPreviewPage ✅
- [x] `src/pages/PreviewPage/ModelPreviewPage.tsx` — TabBar·DimensionsView 인라인 통합, 정보 카드, SVG 치수 도식
- ~~`src/pages/PreviewPage/components/TabBar.tsx`~~ — ModelPreviewPage 헤더에 인라인 통합으로 제거
- ~~`src/pages/PreviewPage/components/DimensionsView.tsx`~~ — ModelPreviewPage 내부로 통합으로 제거

### Step 9: ARPage ✅
- [x] `src/pages/ARPage/components/ARHint.tsx`
- [x] `src/pages/ARPage/components/ARControls.tsx`
- [x] `src/pages/ARPage/ARPage.tsx`

### Step 10: HistoryPage / ResultPage ✅
- [x] `src/pages/HistoryPage/HistoryPage.tsx`
- [x] `src/pages/ResultPage/ResultPage.tsx`

### Step 11: 코드 요약 문서 ✅
- [x] `aidlc-docs/construction/unit1-frontend/code/code-summary.md`

### Step 12: UI 리파인 (app_init.html 기준 디자인 동기화) ✅
- [x] 라우트 경로 `/Page` suffix 제거 (`/home`, `/url-input`, `/loading`, `/preview`, `/ar`, `/history`, `/result`)
- [x] `NavBar` 투명 배경 적용
- [x] `HomePage` — 다크 Hero, 회전 3D 큐브, How it works 타임라인, 컬러 최근 기록
- [x] `UrlInputPage` — 링크 아이콘 input, X 클리어 버튼, 플랫폼 칩, 데모 카드
- [x] `LoadingPage` — 회전 3D 큐브, 그라디언트 진행바, StepList sub-label
- [x] `ModelPreviewPage` — 헤더 내 탭 스위처, 로딩 오버레이, 드래그 힌트, 정보 카드, SVG 치수 도식
- [x] `ResultPage` — 완료 아이콘, 결과 카드, 별점, 구매하러 가기(sourceUrl) 버튼
- [x] `sourceUrl` navigate state 체인 (UrlInput → Loading → Preview → AR → Result)
- [x] `frontend/index.html` model-viewer 스크립트 글로벌 로드
- [x] `frontend/public/example.glb` 개발용 샘플 모델 추가

---

## 스토리 트레이서빌리티

| 스토리 | 구현 단계 |
|--------|---------|
| US-01 서비스 소개 | Step 5 |
| US-02 가구 탐색 시작 | Step 4, 5 |
| US-03 최근 기록 미리보기 | Step 5, 10 |
| US-04 URL 입력 | Step 3, 6 |
| US-05 데모 링크 | Step 6 |
| US-06 빈 URL 에러 | Step 6 |
| US-07 미지원 플랫폼 에러 | Step 6 |
| US-08 AI 진행 상태 | Step 7 |
| US-09 크롤링 실패 에러 | Step 7 |
| US-10 3D 생성 실패 에러 | Step 7 |
| US-11 3D 모델 인터랙션 | Step 8 |
| US-12 가구 치수 확인 | Step 8 |
| US-13 AR 배치로 이동 | Step 8 |
| US-14 AR 배치 및 조작 | Step 9 |
| US-15 가구 회전 | Step 9 |
| US-16 복제 및 삭제 | Step 9 |
| US-17 AR 인식 실패 안내 | Step 9 |
| US-18 AR 결과 촬영 | Step 9 |
| US-19 배치 기록 조회 (UI) | Step 10 |
| US-20 결과 공유 (UI) | Step 10 |
