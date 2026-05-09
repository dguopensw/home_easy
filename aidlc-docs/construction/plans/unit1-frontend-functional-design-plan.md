# Unit 1 Frontend — Functional Design Plan
# 집에 가구 쉽다 (Easy Furniture Fit)

---

## 생성 대상 아티팩트

- [x] `functional-design/domain-entities.md` — 데이터 구조 정의
- [x] `functional-design/business-rules.md` — 유효성 검사 및 비즈니스 규칙
- [x] `functional-design/business-logic-model.md` — 페이지별 로직 흐름
- [x] `functional-design/frontend-components.md` — 컴포넌트 Props/State/상호작용

---

## 질문

### Question 1
URL 유효성 검사를 프론트엔드에서 처리할까요, 백엔드에서만 처리할까요?
(US-07: 지원하지 않는 플랫폼 에러)

A) 프론트에서 먼저 검사 — URL 패턴으로 플랫폼 감지 후 바로 에러 표시 (API 호출 없이)
B) 백엔드에서만 — API 호출 후 에러 응답 받아서 표시
C) 양쪽 모두 — 프론트에서 1차 검사, 백엔드에서 2차 검사

[Answer]:C

---

### Question 2
SSE 연결 중 타임아웃 처리가 필요합니다. AI 파이프라인은 최대 3분 걸려요.
연결이 끊기거나 응답이 없을 때 어떻게 처리할까요?

A) 5분 타임아웃 — 5분 초과 시 "시간이 초과되었습니다. 다시 시도해주세요" 에러 표시
B) 타임아웃 없음 — SSE 에러 이벤트가 올 때만 에러 처리
C) Other (please describe after [Answer]: tag below)

[Answer]:B

---

### Question 3
UrlInputPage의 데모 링크 (US-05)는 실제 어떤 URL을 사용할까요?

A) 개발팀이 미리 크롤링 테스트한 실제 당근/번개/중고나라 URL 3개
B) 플레이스홀더 URL — 나중에 채워 넣기로 하고 일단 `https://www.daangn.com/articles/example` 형태로
C) Other (please describe after [Answer]: tag below)

[Answer]:B

---

### Question 4
LoadingPage에서 각 AI 단계 표시 방식을 선택해주세요. (US-08)

A) 단계명 + 진행률 바 — "3D 모델 생성 중... 65%" 텍스트와 프로그레스 바
B) 체크리스트 방식 — 완료된 단계는 ✅, 현재 단계는 스피너, 대기 단계는 ○
C) 두 가지 모두 — 상단에 전체 진행률 바 + 하단에 단계 체크리스트

[Answer]:C
> app_init.html 디자인 기준:
> - 상단: 현재 단계명 + 진행률(%) + 그라디언트 프로그레스 바 + 단계 설명 텍스트
> - 하단: 단계 리스트 (완료 → ✓ 채운 원 + "완료" / 현재 → 바운싱 dot 애니메이션 / 대기 → 흐린 아이콘)

---

### Question 5
ModelPreviewPage에서 3D 탭과 치수 탭 중 기본으로 보여줄 탭은?

A) 3D 탭 (기본) — model-viewer 먼저 표시
B) 치수 탭 (기본) — 수치 먼저 표시

[Answer]:A
