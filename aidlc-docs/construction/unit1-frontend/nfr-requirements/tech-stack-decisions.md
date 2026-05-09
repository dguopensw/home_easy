# Tech Stack Decisions — Unit 1 Frontend
# 집에 가구 쉽다 (Easy Furniture Fit)

---

## 확정 기술 스택

| 항목 | 선택 | 이유 |
|------|------|------|
| 프레임워크 | React 18 + Vite | 빠른 빌드, HMR, TypeScript 기본 지원 |
| 언어 | TypeScript | 타입 안정성, 컴포넌트 Props/State 명확화 |
| 스타일링 | Tailwind CSS v4 | 유틸리티 클래스, Vite 전용 플러그인으로 설정 간소화 |
| 라우팅 | React Router v6 | 표준 React 라우팅, navigate state 지원 |
| 3D 뷰어 | Google model-viewer | .glb 렌더링, 터치 인터랙션 기본 제공 |
| AR | Unity WebGL (iframe) | React↔Unity SendMessage/CustomEvent 브리지 |
| 배포 | Vercel | GitHub 연동 자동 배포, HTTPS 기본 제공 |
| 패키지 매니저 | pnpm | npm 대비 빠른 설치, 디스크 효율적 |
| 코드 품질 | ESLint + Prettier | 코드 스타일 통일 |

---

## 주요 라이브러리

| 라이브러리 | 용도 | 설치 |
|-----------|------|------|
| `react-router-dom` | 라우팅 | `npm install react-router-dom` |
| `@google/model-viewer` | .glb 3D 렌더링 | CDN or `npm install @google/model-viewer` |
| `eslint` | 코드 린팅 | Vite 기본 포함 |
| `prettier` | 코드 포맷 | `pnpm add -D prettier` |

---

## 미사용 결정

| 항목 | 제외 이유 |
|------|---------|
| Zustand / Redux | React Router navigate state로 충분, 오버엔지니어링 |
| React Query | SSE는 EventSource로 직접 처리, 별도 라이브러리 불필요 |
| Service Worker | 오프라인 지원 불필요 (MVP) |
| Vitest | 테스트 없음 (MVP) |
| i18n | 한국어 전용 서비스 |
