# 실행 계획 (Execution Plan)
# 집에 가구 쉽다 (Easy Furniture Fit)

---

## 1. 변경 영향 분석

| 항목 | 여부 | 설명 |
|------|------|------|
| User-facing changes | YES | 7개 화면 신규 구현 |
| Structural changes | YES | 멀티 서비스 아키텍처 (FE + API + AI + Unity) |
| Data model changes | YES | API 스키마, .glb 파일 구조, Post-MVP DB 스키마 |
| API changes | YES | 신규 REST API 전체 설계 |
| NFR impact | YES | 3D 생성 성능(3분), RunPod Cold Start, PWA 요구사항 |

**Risk Level**: HIGH
- AI 파이프라인 다수 모델 통합 (TRELLIS, SAM, Metric3D 등)
- Unity WebGL ↔ React 브리지 통신
- RunPod Serverless Cold Start
- 중고 플랫폼 크롤링 안정성

---

## 2. 개발 단위 (Units of Work)

| Unit | 이름 | 기술 스택 |
|------|------|-----------|
| Unit 1 | Frontend (PWA) | React + Vite + TypeScript + Tailwind CSS → Vercel |
| Unit 2 | Backend API | Python + FastAPI → AWS EC2 |
| Unit 3 | AI Pipeline | Python + TRELLIS/SAM/Metric3D → RunPod Serverless |
| Unit 4 | Unity AR | Unity WebGL |

---

## 3. 워크플로우 시각화

```
[User Request]
      |
      v
+--------------------------------------------------+
|  INCEPTION PHASE                                 |
|  [x] Workspace Detection        COMPLETED        |
|  [-] Reverse Engineering        SKIPPED          |
|  [x] Requirements Analysis      COMPLETED        |
|  [ ] User Stories               EXECUTE          |
|  [~] Workflow Planning          IN PROGRESS      |
|  [ ] Application Design         EXECUTE          |
|  [ ] Units Generation           EXECUTE          |
+--------------------------------------------------+
      |
      v
+--------------------------------------------------+
|  CONSTRUCTION PHASE  (Unit 1 ~ 4 순차 실행)      |
|  [ ] Functional Design          EXECUTE          |
|  [ ] NFR Requirements           EXECUTE          |
|  [ ] NFR Design                 EXECUTE          |
|  [ ] Infrastructure Design      EXECUTE          |
|  [ ] Code Generation            EXECUTE          |
|  [ ] Build and Test             EXECUTE          |
+--------------------------------------------------+
      |
      v
+--------------------------------------------------+
|  OPERATIONS PHASE                                |
|  [ ] Operations                 PLACEHOLDER      |
+--------------------------------------------------+
      |
      v
[Complete]
```

---

## 4. 단계별 실행 계획

### INCEPTION PHASE

| 단계 | 상태 | 근거 |
|------|------|------|
| Workspace Detection | COMPLETED | - |
| Reverse Engineering | SKIPPED | Greenfield 프로젝트 |
| Requirements Analysis | COMPLETED | - |
| User Stories | **EXECUTE** | 신규 사용자 대면 기능 다수, 복잡한 사용자 여정, 명확한 인수 기준 필요 |
| Workflow Planning | IN PROGRESS | - |
| Application Design | **EXECUTE** | 4개 신규 서비스 컴포넌트 설계, React↔FastAPI↔RunPod↔Unity 의존성 정의 필요 |
| Units Generation | **EXECUTE** | 4개 독립 유닛 분해, 병렬 개발 구조 수립 필요 |

### CONSTRUCTION PHASE (Unit 1~4 각각 반복)

| 단계 | 상태 | 근거 |
|------|------|------|
| Functional Design | **EXECUTE** | 신규 데이터 모델, 복잡한 비즈니스 로직 (AI 파이프라인, AR 통신) |
| NFR Requirements | **EXECUTE** | 성능 목표(3분), Cold Start 대응, PWA 캐싱 전략 |
| NFR Design | **EXECUTE** | NFR Requirements 실행에 따라 자동 실행 |
| Infrastructure Design | **EXECUTE** | AWS EC2, RunPod, S3, Vercel 배포 아키텍처 명세 필요 |
| Code Generation | **EXECUTE** | ALWAYS |
| Build and Test | **EXECUTE** | ALWAYS |

### OPERATIONS PHASE

| 단계 | 상태 | 근거 |
|------|------|------|
| Operations | PLACEHOLDER | 미래 확장 예정 |

---

## 5. 예상 개발 순서

```
1단계 (병렬 가능)
  +-- Unit 1: Frontend 화면 구현 (Mock 데이터 기반, API 연동 전)
  +-- Unit 3: AI Pipeline 각 모델 개별 테스트

2단계
  +-- Unit 4: Unity AR 씬 구현

3단계 (병렬 가능)
  +-- Unit 2: Backend API 기본 엔드포인트 구현
  +-- 샘플 .glb로 RunPod → FastAPI → Frontend 전송 연결 테스트

4단계
  +-- Unit 3: AI 파이프라인 전체 통합 (RunPod Serverless)

5단계
  +-- Unit 1: Frontend + Backend API 연동

6단계
  +-- 전체 통합 테스트 및 배포
```

---

## 6. 성공 기준

**Primary Goal**: MVP — URL 입력 → 3D 생성 → AR 배치 전체 플로우 동작

**Key Deliverables**:
- React PWA: 5개 화면 완전 구현 + 2개 화면 UI만
- FastAPI 서버: 크롤링·3D 생성 요청·결과 반환 API
- RunPod AI Pipeline: .glb 파일 자동 생성 (3분 이내)
- Unity WebGL: AR 평면 인식 및 가구 배치

**Quality Gates**:
- 3D 모델 생성 3분 이내
- 모바일 Chrome / Safari 정상 동작
- AR 카메라 권한 정상 작동
- .glb 파일 model-viewer 렌더링 확인
