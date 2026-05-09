# 요구사항 확인 질문 (Requirements Verification Questions)

`product_intro.md`와 `app.html`을 분석하여 아래 질문을 작성했습니다.
각 질문의 `[Answer]:` 태그 뒤에 선택한 알파벳을 입력해주세요.
선택지에 맞는 항목이 없으면 마지막 옵션을 선택 후 직접 설명을 적어주세요.

---

## Question 1
앱의 최종 배포 플랫폼은 무엇인가요?

A) 모바일 웹앱 (PWA) — 브라우저에서 실행, iOS/Android 모두 지원
B) 네이티브 앱 (iOS + Android) — React Native 또는 Flutter 사용
C) 웹앱 우선 개발 후 네이티브 앱 확장
D) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 2
백엔드 AI 파이프라인의 개발 언어/프레임워크를 선택해주세요.

A) Python + FastAPI (권장 — TRELLIS, SAM, Metric3D 등 AI 라이브러리 호환성 최적)
B) Python + Flask
C) Node.js + Express
D) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 3
AR 배치 기능 구현 방식을 선택해주세요.

A) Unity WebGL — app.html 코드 기준, iframe으로 React 앱에 통합
B) WebXR API — 브라우저 네이티브 AR, Unity 불필요
C) React Native + ARKit/ARCore — 네이티브 앱 방식
D) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 4
사용자 계정 및 인증 기능이 필요한가요?

A) 필요 없음 — 비로그인으로 사용, 기기 로컬에 배치 기록 저장
B) 소셜 로그인 (Google/Kakao) — 클라우드에 기록 동기화
C) 이메일/비밀번호 로그인
D) Other (please describe after [Answer]: tag below)

[Answer]: D
소셜 로그인을 도입할 것이지만 mvp에 넣어두진 않을 것 같음 그렇지만 배치기록 저장 기능을 mvp구현이후에 구현하게 된다면 같이 소셜 로그인 도입할 예정

---

## Question 5
MVP(최초 출시 버전)에 포함할 기능의 범위를 선택해주세요.

A) 핵심 기능만 — URL 입력 → 3D 모델 생성 → AR 배치 (기록/공유 제외)
B) app.html 전체 플로우 — 홈, URL 입력, 로딩, 3D 미리보기, AR, 기록, 결과 저장
C) AI 파이프라인 백엔드 우선 개발 (프론트엔드는 나중에)
D) Other (please describe after [Answer]: tag below)

[Answer]: D
홈, URL 입력, 로딩, 3D 미리보기, AR배치(기록/공유 제외) 까지, 나머지 기능들은 일단 UI들만

---

## Question 6
AI 파이프라인 서버의 배포 환경을 선택해주세요.

A) 클라우드 (AWS / GCP / Azure) — GPU 인스턴스에 배포
B) 로컬 개발 서버 — 개발 단계에서만 로컬 실행
C) Hugging Face Spaces / Modal.com 등 AI 특화 서비스
D) Other (please describe after [Answer]: tag below)

[Answer]: D
AI 파이프라인(TRELLIS, SAM, Metric3D)은 RunPod Serverless GPU로 배포,                            
  API 서버는 AWS EC2, 파일 저장은 S3 사용 

---

## Question 7
배치 기록(History) 데이터 저장 방식을 선택해주세요.

A) 브라우저 로컬스토리지 (localStorage / IndexedDB)
B) 백엔드 DB (PostgreSQL / MongoDB)
C) 클라우드 스토리지 (S3 + DynamoDB 등)
D) Other (please describe after [Answer]: tag below)

[Answer]: B+C

---

## Question 8
프론트엔드 프레임워크/빌드 도구를 선택해주세요.

A) React + Vite (권장 — app.html이 이미 React 기반)
B) React + Next.js (SSR이 필요한 경우)
C) React + Create React App
D) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question: Security Extensions
보안 확장 규칙을 이 프로젝트에 적용할까요?

A) Yes — 모든 보안 규칙을 강제 적용 (프로덕션 수준 앱에 권장)
B) No — 보안 규칙 생략 (PoC, 프로토타입, 실험적 프로젝트에 적합)
X) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Question: Property-Based Testing Extension
속성 기반 테스트(PBT) 규칙을 적용할까요?

A) Yes — 모든 PBT 규칙 강제 적용 (비즈니스 로직, 데이터 변환이 있는 프로젝트에 권장)
B) Partial — 순수 함수와 직렬화 테스트에만 PBT 적용
C) No — PBT 규칙 생략 (단순 CRUD, UI 전용, 얇은 통합 레이어에 적합)
X) Other (please describe after [Answer]: tag below)

[Answer]: C
