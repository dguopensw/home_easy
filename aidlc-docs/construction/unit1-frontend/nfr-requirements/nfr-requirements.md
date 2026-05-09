# NFR Requirements — Unit 1 Frontend
# 집에 가구 쉽다 (Easy Furniture Fit)

---

## 성능 (Performance)

| 요구사항 | 목표 |
|---------|------|
| 초기 앱 로딩 | 3G 환경에서 3초 이내 |
| 화면 전환 | 즉각적 (React Router, 네트워크 요청 없음) |
| model-viewer 렌더링 | .glb 로드 후 5초 이내 렌더링 |
| SSE 연결 지연 | 1초 이내 연결 수립 |

---

## 가용성 (Availability)

| 항목 | 결정 |
|------|------|
| 오프라인 지원 | ❌ 없음 — 인터넷 연결 필수 |
| Service Worker | ❌ 미사용 |
| PWA 설치 | manifest.json 제공 (홈 화면 추가 가능) |

---

## 브라우저 지원 (Compatibility)

| 브라우저 | 지원 여부 |
|---------|---------|
| 모바일 Chrome (Android) | ✅ 필수 |
| 모바일 Safari (iOS) | ✅ 필수 |
| 데스크톱 Chrome/Safari | ❌ 미지원 (MVP 범위 외) |

> AR 기능은 모바일 카메라 접근이 필수이므로 모바일 전용

---

## 보안 (Security)

| 항목 | 내용 |
|------|------|
| HTTPS | Vercel 기본 제공 |
| CORS | 백엔드 API 요청만 허용 (FastAPI CORS 설정) |
| 민감 정보 | 없음 — MVP에서 로그인/개인정보 없음 |

---

## 테스트 (Testing)

| 항목 | 결정 |
|------|------|
| 단위 테스트 | ❌ 없음 |
| 통합 테스트 | ❌ 없음 |
| 수동 테스트 | ✅ 모바일 Chrome/Safari에서 직접 확인 |

---

## 사용성 (Usability)

| 항목 | 내용 |
|------|------|
| 대상 기기 | 모바일 (세로 방향 고정) |
| 최소 화면 크기 | 375px (iPhone SE 기준) |
| 웹 접근성(a11y) | MVP 범위 외 |
| 다크모드 | 미지원 (MVP 범위 외) |
