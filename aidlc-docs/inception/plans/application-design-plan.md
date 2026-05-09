# Application Design 계획
# 집에 가구 쉽다 (Easy Furniture Fit)

아래 질문에 답변해주세요. 각 `[Answer]:` 태그 뒤에 알파벳을 입력하시고,
선택지에 맞는 항목이 없으면 마지막 옵션 선택 후 직접 설명을 적어주세요.

---

## Question 1
AI 파이프라인은 최대 3분이 걸립니다. 로딩 화면에서 진행 상태를 실시간으로 보여주려면
프론트엔드가 백엔드와 어떤 방식으로 통신해야 할까요?

A) Polling — 프론트가 2~3초마다 백엔드에 진행 상태를 요청 (구현 간단)
B) SSE (Server-Sent Events) — 백엔드가 단계 완료 시마다 프론트에 이벤트 푸시 (단방향 실시간)
C) WebSocket — 양방향 실시간 통신 (복잡하지만 가장 유연)
D) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Question 2
Frontend React 컴포넌트 구조를 어떻게 나눌까요?

A) 화면(Screen) 단위 — HomeScreen, UrlInputScreen, LoadingScreen 등 화면별 컴포넌트
B) Atomic Design — atoms(버튼 등) → molecules → organisms → screens 계층 구조
C) 화면 단위 기본 + 공통 컴포넌트 분리 (Button, Card 등)
D) Other (please describe after [Answer]: tag below)

[Answer]: C
---

## Question 3
Frontend 전역 상태 관리 방법을 선택해주세요.
(현재 생성 중인 가구 URL, 생성된 .glb URL, 현재 화면 등을 관리해야 합니다)

A) React Context API — 별도 라이브러리 없이 내장 기능 사용
B) Zustand — 가볍고 간단한 상태 관리 라이브러리
C) Redux Toolkit — 대규모 상태 관리에 적합, 보일러플레이트 있음
D) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 4
FastAPI 백엔드의 내부 구조를 어떻게 나눌까요?

A) 라우터 모듈 분리 — crawling, pipeline, model 등 기능별 router 파일 분리
B) 단일 main.py — 엔드포인트를 한 파일에 모두 작성 (소규모 MVP에 적합)
C) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 5
Unity WebGL과 React 간 통신 방식을 선택해주세요.
(React가 Unity에 .glb URL을 전달하고, Unity가 AR 상태를 React에 알려야 합니다)

A) postMessage API — iframe과 부모 창 간 메시지 통신 (웹 표준)
B) window 전역 함수 — Unity가 window.onAREvent() 같은 전역 함수를 직접 호출
C) app.html 방식 유지 — unityInstance.SendMessage() 기반
D) Other (please describe after [Answer]: tag below)

[Answer]: C

---

## 설계 아티팩트 생성 체크리스트 (답변 후 자동 실행)

- [x] components.md — 컴포넌트 정의 및 책임
- [x] component-methods.md — 주요 메서드 시그니처
- [x] services.md — 서비스 레이어 정의
- [x] component-dependency.md — 컴포넌트 의존성 및 통신 패턴
- [x] application-design.md — 전체 통합 문서
