# Business Rules — Unit 1 Frontend
# 집에 가구 쉽다 (Easy Furniture Fit)

---

## BR-01: URL 유효성 검사 (2단계)

### 1차 검사 — 프론트엔드 (즉시)
| 규칙 | 내용 |
|------|------|
| BR-01-1 | URL 필드가 비어있으면 API 호출 없이 입력 필드 흔들림 애니메이션 + 포커스 |
| BR-01-2 | URL이 `daangn.com`, `bunjang.kr`, `joongna.com` 도메인을 포함하지 않으면 "현재 당근마켓, 번개장터, 중고나라만 지원합니다" 에러 표시 |

### 2차 검사 — 백엔드 응답
| 규칙 | 내용 |
|------|------|
| BR-01-3 | API에서 크롤링 실패 응답 수신 시 LoadingPage에서 에러 UI 표시 |

---

## BR-02: 플랫폼 감지 규칙

| 플랫폼 | URL 패턴 |
|--------|---------|
| 당근마켓 | `daangn.com` 포함 |
| 번개장터 | `bunjang.kr` 포함 |
| 중고나라 | `joongna.com` 포함 |
| 미지원 | 위 패턴 없음 → BR-01-2 적용 |

---

## BR-03: SSE 연결 및 에러 처리

| 규칙 | 내용 |
|------|------|
| BR-03-1 | SSE 연결은 LoadingPage 마운트 시 즉시 시작 |
| BR-03-2 | SSE `error` 이벤트 수신 시 에러 타입에 따라 메시지 분기 표시 |
| BR-03-3 | SSE `complete` 이벤트 수신 시 `navigate('/PreviewPage', { state: { glbUrl, dimensions } })` |
| BR-03-4 | LoadingPage 언마운트 시 SSE 연결 반드시 종료 (EventSource.close()) |
| BR-03-5 | 타임아웃 없음 — SSE 에러 이벤트에만 의존 |

---

## BR-04: 에러 메시지 규칙

| 에러 타입 | 표시 메시지 | 버튼 |
|----------|------------|------|
| `crawling_failed` | "게시글을 불러올 수 없습니다. 게시글이 삭제되었거나 URL을 확인해주세요" | "다시 시도하기" → UrlInputPage |
| `generation_failed` | "3D 모델 생성에 실패했습니다. 다시 시도해주세요" | "처음으로" → HomePage |
| `unknown` | "오류가 발생했습니다. 다시 시도해주세요" | "처음으로" → HomePage |

---

## BR-05: 데모 링크 규칙

| 규칙 | 내용 |
|------|------|
| BR-05-1 | 데모 링크 탭 시 해당 URL이 입력 필드에 자동 입력 |
| BR-05-2 | 데모 링크는 플레이스홀더 URL 사용 (실제 URL은 개발 중 교체) |
| BR-05-3 | 당근마켓 1개만 제공 |

---

## BR-06: ModelPreviewPage 탭 규칙

| 규칙 | 내용 |
|------|------|
| BR-06-1 | 기본 활성 탭은 3D 탭 |
| BR-06-2 | 탭 전환 시 model-viewer는 DOM에 유지 (숨김 처리), 치수 탭은 조건부 렌더링 |
