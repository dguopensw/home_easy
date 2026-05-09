# Code Summary — Unit 1 Frontend
# 집에 가구 쉽다 (Easy Furniture Fit)

---

## 생성된 파일 목록

### 프로젝트 설정
- `frontend/package.json`
- `frontend/vite.config.ts` — Tailwind v4 플러그인, `@/` alias
- `frontend/tsconfig.json` / `tsconfig.app.json` / `tsconfig.node.json`
- `frontend/index.html` — model-viewer 스크립트 글로벌 로드
- `frontend/eslint.config.js`
- `frontend/.prettierrc`
- `frontend/vercel.json` — SPA 리라이트
- `frontend/public/manifest.json` — PWA manifest
- `frontend/public/example.glb` — 개발용 예시 3D 모델
- `frontend/.env.example`

### 소스 코드
- `frontend/src/vite-env.d.ts`
- `frontend/src/index.css` — @theme 디자인 토큰, shake/bounceDot/spin 애니메이션
- `frontend/src/main.tsx`
- `frontend/src/router.tsx` — createBrowserRouter + React.lazy

### 공통 컴포넌트
- `src/components/Button.tsx`
- `src/components/NavBar.tsx` — 투명 배경 (bg 없음, border 없음)
- `src/components/ProgressBar.tsx`
- `src/components/Toast.tsx`

### API 레이어
- `src/api/furniture.ts`

### 페이지
- `src/pages/HomePage/HomePage.tsx` — 다크 Hero + 회전 3D 큐브 + How it works 타임라인 + 최근 기록
- `src/pages/UrlInputPage/UrlInputPage.tsx` — 링크 아이콘 input + 플랫폼 칩 + 데모 카드 (현재 API 호출 mock)
- `src/pages/LoadingPage/LoadingPage.tsx` — 회전 3D 큐브 + 그라디언트 진행바 (현재 mock 자동 진행)
- `src/pages/LoadingPage/components/StepList.tsx`
- `src/pages/LoadingPage/components/BouncingDots.tsx`
- `src/pages/PreviewPage/ModelPreviewPage.tsx` — 헤더 내 탭 스위처, model-viewer, 정보 카드, SVG 치수 도식
- `src/pages/ARPage/ARPage.tsx`
- `src/pages/ARPage/components/ARHint.tsx`
- `src/pages/ARPage/components/ARControls.tsx`
- `src/pages/HistoryPage/HistoryPage.tsx`
- `src/pages/ResultPage/ResultPage.tsx` — 완료 아이콘, 결과 카드, 공유/재시작/구매하러 가기 버튼

---

## 삭제된 파일 (UI 리팩터링 중 제거)
- `src/pages/UrlInputPage/components/DemoLinkButton.tsx` — UrlInputPage 인라인으로 통합
- `src/pages/PreviewPage/components/TabBar.tsx` — ModelPreviewPage 헤더에 인라인으로 통합
- `src/pages/PreviewPage/components/DimensionsView.tsx` — ModelPreviewPage 내부로 통합

---

## 구현된 스토리
US-01 ~ US-18 (MVP 필수), US-19 ~ US-20 (UI만)

---

## 현재 Mock 처리 중인 항목 (백엔드 연동 전)
| 항목 | 현재 | 실제 연동 시 |
|------|------|------------|
| URL 제출 | mock jobId로 바로 `/loading` 이동 | `startGeneration(url)` API 호출 |
| AI 파이프라인 진행 | 1.2초 간격 자동 단계 진행 | SSE `createSSEConnection(jobId)` |
| 3D 모델 URL | `/example.glb` | 백엔드 응답 `glb_url` |
| ResultPage sourceUrl | 하드코딩 fallback | navigate state로 전달 |
