# Functional Design Plan — Unit 2 Backend API
# 집에 가구 쉽다 (Easy Furniture Fit)

---

## 목적
FastAPI 기반 백엔드의 비즈니스 로직, 도메인 모델, 비즈니스 규칙을 기술 중립적으로 설계한다.

## 담당 User Stories
- US-04: 중고 가구 URL 입력 → UUID job_id 즉시 반환, 비동기 처리 시작
- US-07: 지원하지 않는 플랫폼 감지
- US-08: AI 진행 상태 SSE 스트리밍 (크롤링 ~ 치수 추정)
- US-08: 최적 이미지 선정 (GPT-4o Vision)
- US-08: 이미지 전처리 (DINO+SAM 배경 제거, LaMa 인페인팅)
- US-12: 가구 치수 추정 (Metric3D)
- US-09: 크롤링/전처리 실패 SSE error 이벤트 반환
- US-10: 3D 생성 실패 SSE error 이벤트 반환
- DB 구축 (PostgreSQL 연결 설정, Job 테이블 생성)
- 완료 결과 DB 저장 (job_id, source_url, dimensions, glb_url)

---

## 실행 체크리스트

- [ ] Step 1: 유닛 컨텍스트 분석 (unit-of-work.md, story-map.md)
- [ ] Step 2: 질문 파일 작성 및 사용자 응답 수집
- [ ] Step 3: 도메인 엔티티 설계 (domain-entities.md)
- [ ] Step 4: 비즈니스 로직 모델 설계 (business-logic-model.md)
- [ ] Step 5: 비즈니스 규칙 정의 (business-rules.md)

---

## 질문 (Functional Design Questions)

아래 질문에 **[Answer]: 선택지** 형태로 답해 주세요.

---

### Q1. 크롤링 구현 방식
당근마켓, 번개장터, 중고나라는 모두 동적 렌더링(JavaScript SPA)을 사용합니다. 어떤 방식으로 크롤링할까요?

A. **Playwright (Headless Chromium)** — JS 렌더링 지원, EC2에서 실행 가능, 설치 무거움 (~200MB)  
B. **requests + BeautifulSoup** — 빠르고 가볍지만 JS 미지원, 정적 HTML만 파싱  
C. **requests + 각 플랫폼 내부 API** — 각 플랫폼의 비공개 API를 역공학으로 호출 (불안정)  
D. **Selenium** — Playwright과 유사하나 더 무거움

[Answer]:

---

### Q2. 이미지 전처리 실행 환경
DINO+SAM 배경 제거 및 LaMa 인페인팅은 GPU가 필요한 무거운 모델입니다. 어디서 실행할까요?

A. **EC2 로컬 실행** — EC2에 GPU 인스턴스 사용 (비용 높음), 모델 로컬 설치  
B. **RunPod에 전처리도 위임** — 전처리 + 3D 생성 모두 RunPod handler에서 처리 (통합 단순)  
C. **외부 전처리 API 사용** — Remove.bg / Replicate 등 유료 API 활용  
D. **CPU 전용 경량 모델 사용** — rembg (U2Net CPU) 등 경량화 모델로 EC2 CPU에서 처리

[Answer]:

---

### Q3. 비동기 작업 처리 방식
백그라운드에서 크롤링 → 전처리 → RunPod 순서로 실행할 때 어떤 방식을 사용할까요?

A. **FastAPI BackgroundTasks + asyncio** — 추가 의존성 없음, 단일 프로세스, EC2 재시작 시 작업 손실  
B. **Celery + Redis** — 분산 큐, 재시도 지원, Redis 설치 필요  
C. **asyncio.create_task** — FastAPI 이벤트 루프 내 비동기 태스크, BackgroundTasks와 유사  
D. **RQ (Redis Queue)** — Celery보다 단순한 Redis 기반 큐

[Answer]:

---

### Q4. 데이터베이스 선택
Job 결과를 저장할 데이터베이스를 선택해 주세요.

A. **PostgreSQL** — 운영 DB 표준, EC2에 설치하거나 RDS 사용  
B. **SQLite** — 파일 기반, 추가 설치 불필요, 단일 서버에서는 충분  
C. **AWS RDS PostgreSQL** — 관리형 PostgreSQL, 별도 비용 발생  
D. **MySQL/MariaDB** — PostgreSQL과 유사한 운영 DB

[Answer]:

---

### Q5. SSE(Server-Sent Events) 구현 방식
진행 상태를 프론트엔드에 스트리밍할 때 어떻게 구현할까요?

A. **FastAPI + EventSourceResponse (sse-starlette)** — 표준 SSE, 별도 라이브러리 필요  
B. **FastAPI StreamingResponse** — 직접 text/event-stream 구현, 추가 의존성 없음  
C. **WebSocket** — 양방향 통신, 오버스펙이지만 유연  
D. **Short Polling** — 클라이언트가 주기적으로 상태 조회 (SSE 대신 REST API)

[Answer]:

---

### Q6. 인증/인가 (MVP 범위)
MVP에서 백엔드 API에 인증이 필요한가요?

A. **인증 없음** — URL만 입력하면 누구나 사용 가능 (MVP 단순화)  
B. **API Key 방식** — 환경변수로 공유 키 설정, 헤더로 전달  
C. **JWT 인증** — 로그인 기반, Post-MVP 카카오 연동 전제  
D. **IP 화이트리스트** — 특정 IP(Vercel 프론트엔드)만 허용

[Answer]:

---

### Q7. RunPod 폴링 방식
RunPod 3D 생성 완료를 어떻게 감지할까요?

A. **주기적 폴링 (2초 간격)** — RunPod `/status/{id}` API를 2초마다 호출  
B. **RunPod Webhook** — RunPod이 완료 시 FastAPI 엔드포인트 호출 (설정 필요)  
C. **폴링 + 점진적 간격** — 처음 2초, 이후 5초 간격으로 증가  
D. **RunPod 동기 엔드포인트** — `/runsync` 사용 (타임아웃 위험, 최대 90초)

[Answer]:

---

### Q8. 지원 플랫폼 범위
MVP에서 크롤링을 지원할 중고 플랫폼을 선택해 주세요.

A. **당근마켓만** — 가장 트래픽 많음, 우선 집중  
B. **당근마켓 + 번개장터** — 상위 2개 플랫폼  
C. **당근마켓 + 번개장터 + 중고나라** — 3개 플랫폼 모두  
D. **플랫폼 무관 범용 크롤러** — og:image 등 메타태그 기반

[Answer]:

---

### Q9. 치수 추정 모델 실행 위치
Metric3D 치수 추정 모델은 어디서 실행할까요?

A. **EC2 로컬 실행** — CPU 모드로 실행 가능 (느리지만 비용 절감)  
B. **RunPod에 통합** — 전처리와 함께 RunPod handler에서 처리  
C. **Replicate/Hugging Face API** — 외부 추론 API 사용  
D. **더 가벼운 모델 대체** — MiDaS 등 CPU 친화적 Depth 모델

[Answer]:

---

### Q10. 환경 설정 방식
환경변수(DB URL, RunPod API Key, OpenAI Key 등)는 어떻게 관리할까요?

A. **python-dotenv (.env 파일)** — 로컬 개발과 EC2 모두 .env 파일 사용  
B. **AWS SSM Parameter Store** — AWS 관리형 비밀 저장소, boto3 필요  
C. **AWS Secrets Manager** — 더 강력한 비밀 관리, 비용 발생  
D. **OS 환경변수만** — .env 없이 EC2 서버 환경변수 직접 설정

[Answer]:
