# 유저 스토리 생성 계획 (Story Generation Plan)
# 집에 가구 쉽다 (Easy Furniture Fit)

아래 질문에 답변해주세요. 각 `[Answer]:` 태그 뒤에 알파벳을 입력하시고,
선택지에 맞는 항목이 없으면 마지막 옵션 선택 후 직접 설명을 적어주세요.

---

## Question 1
주요 사용자 페르소나를 어떻게 정의할까요?

A) 단일 페르소나 — 중고 가구 구매를 고려하는 일반 사용자 한 명
B) 2개 페르소나 — 구매 고려자 + 가구 배치에 민감한 인테리어 관심자
C) 3개 페르소나 — 구매 고려자 + 인테리어 관심자 + 자취/이사 준비생
D) Other (please describe after [Answer]: tag below)

[Answer]: C

---

## Question 2
유저 스토리 분류 방식을 선택해주세요.

A) 화면(Feature) 기준 — 홈, URL입력, 로딩, 3D미리보기, AR배치 화면별로 스토리 구성
B) 사용자 여정(Journey) 기준 — 가구 발견 → 3D 확인 → AR 배치 → 결과 저장 흐름으로 구성
C) 기능(Epic) 기준 — 크롤링, 3D생성, AR배치를 Epic으로 묶고 하위 스토리 구성
D) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 3
인수 기준(Acceptance Criteria)의 상세 수준을 선택해주세요.

A) 간단 — "~할 수 있다" 형식의 1~2줄 기준
B) 표준 — Given / When / Then 형식으로 시나리오 기술
C) 상세 — 엣지 케이스, 에러 처리까지 포함한 완전한 기준
D) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Question 4
MVP 범위 외 Post-MVP 기능(배치 기록, 소셜 로그인)에 대한 유저 스토리도 작성할까요?

A) Yes — MVP + Post-MVP 전체 스토리 작성 (우선순위 표시)
B) No — MVP 범위 스토리만 작성
C) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 5
AR 배치 실패 / 크롤링 실패 등 에러 시나리오에 대한 스토리도 포함할까요?

A) Yes — 에러 케이스 스토리 포함
B) No — 정상 플로우(Happy Path)만 작성
C) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## 스토리 생성 체크리스트 (답변 후 자동 실행)

- [x] 페르소나 정의 및 personas.md 생성
- [x] 유저 스토리 작성 (INVEST 기준 충족)
- [x] 인수 기준 작성
- [x] 페르소나 ↔ 스토리 매핑
- [x] stories.md 생성
