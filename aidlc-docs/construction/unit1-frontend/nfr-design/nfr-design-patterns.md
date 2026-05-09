# NFR Design Patterns — Unit 1 Frontend
# 집에 가구 쉽다 (Easy Furniture Fit)

---

## 성능 패턴 (Performance)

### 코드 스플리팅 (React.lazy)
페이지 컴포넌트를 lazy load하여 초기 번들 크기 최소화.

```typescript
// router.tsx
const HomePage         = lazy(() => import('./pages/HomePage/HomePage'))
const UrlInputPage     = lazy(() => import('./pages/UrlInputPage/UrlInputPage'))
const LoadingPage      = lazy(() => import('./pages/LoadingPage/LoadingPage'))
const ModelPreviewPage = lazy(() => import('./pages/PreviewPage/ModelPreviewPage'))
const ARPage           = lazy(() => import('./pages/ARPage/ARPage'))
```

> model-viewer, Unity WebGL 같은 무거운 리소스는 해당 페이지 진입 시점에만 로드됨

### model-viewer 지연 로드
`<model-viewer>` 웹 컴포넌트는 ModelPreviewPage 진입 시에만 스크립트 로드.

---

## 복원력 패턴 (Resilience)

### SSE 에러 처리
- SSE `error` 이벤트 수신 시 즉시 연결 종료 + 에러 UI 표시
- 재연결 없음 (MVP 결정) — 사용자가 "다시 시도" 버튼으로 재시작

### API 호출 에러 처리
- `POST /furniture/gen/start` 실패 시 Toast 메시지 표시
- HTTP 상태 코드별 메시지 분기 없음 — 단일 에러 메시지

### Unity WebGL 로드 실패
- iframe 로드 타임아웃(10초) 시 "AR을 불러올 수 없습니다" 안내 표시

---

## 보안 패턴 (Security)

### URL 입력 정제
- 프론트엔드에서 플랫폼 도메인 패턴 매칭만 수행
- XSS 방지: URL을 직접 innerHTML에 삽입하지 않음, React JSX로만 렌더링

### HTTPS
- Vercel 자동 적용 — 별도 설정 불필요

---

## 사용성 패턴 (Usability)

### 모바일 세로 고정
```html
<!-- index.html -->
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
```

### PWA manifest
홈 화면 추가 지원 (오프라인 미지원이지만 설치 가능).
```json
{
  "name": "집에 가구 쉽다",
  "short_name": "가구쉽다",
  "display": "standalone",
  "orientation": "portrait"
}
```
