# 애플리케이션 설계 통합 문서 (Application Design)
# 집에 가구 쉽다 (Easy Furniture Fit)

---

## 1. 아키텍처 개요

```
+------------------+     SSE / REST      +------------------+
|  React PWA       | ------------------> |  FastAPI         |
|  (Vercel)        |                     |  (AWS EC2)       |
|                  |                     |                  |
|  - React Router  |                     |  - crawling.py   |
|  - 7개 Page      |                     |  - generation.py |
|  - Unity iframe  |                     |  - ImageSelector |
+------------------+                     |  - Preprocessor  |
        |                                |  - DimEstimator  |
        | SendMessage /                  +--------+---------+
        | CustomEvent                        |         |
        v                               RunPod|    SQLAlchemy
+------------------+                    API  |         |
|  Unity WebGL     |                         v         v
|  (AR 씬)         |                +----------+  +----------+
|                  |                |  RunPod  |  | PostgreSQL|
|  - ARController  |                | (TRELLIS)|  | (job 결과)|
|  - ModelLoader   |                +----+-----+  +----------+
|  - Placement     |                     |
|  - JSBridge      |                  boto3
+------------------+                     |
                                         v
                                  +------------------+
                                  |  AWS S3          |
                                  |  (.glb 저장)     |
                                  +------------------+
```

---

## 2. 핵심 설계 결정 사항

| 항목 | 결정 | 이유 |
|------|------|------|
| AI 진행 상태 통신 | SSE | 단방향 실시간, 구현 간단, Polling 대비 불필요한 요청 없음 |
| FE 컴포넌트 구조 | Page 단위 + 공통 컴포넌트 | 7개 Page 규모에 적합, Atomic Design은 오버엔지니어링 |
| FE 상태 관리 | React Router navigate state | Context 불필요, 화면 간 데이터는 navigate로 전달 |
| Backend 구조 | 라우터 모듈 분리 | 기능별 책임 분리, 유지보수 용이 |
| Unity 통신 | SendMessage + CustomEvent | app.html 기존 방식, Unity WebGL 공식 패턴 |
| 3D 진행률 배분 | 시간 기반 (TRELLIS 65%) | 실제 소요 시간 반영, 자연스러운 UX |

---

## 3. 단위별 기술 스택 요약

| Unit | 기술 | 배포 |
|------|------|------|
| Frontend | React + Vite + TypeScript + Tailwind CSS | Vercel |
| Backend API | Python + FastAPI + sse-starlette + SQLAlchemy | AWS EC2 |
| Backend AI 처리 | GPT-4o Vision + DINO + SAM + LaMa + Metric3D | AWS EC2 (FastAPI 내) |
| AI Pipeline | Python + TRELLIS | RunPod Serverless |
| Unity AR | Unity WebGL | Frontend 번들에 포함 |
| 파일 저장 | AWS S3 | - |
| DB | PostgreSQL (RDS) | AWS RDS |

---

## 4. 상세 문서 참조

| 문서 | 내용 |
|------|------|
| `components.md` | 전체 컴포넌트 정의 및 책임 |
| `component-methods.md` | 주요 메서드 시그니처 |
| `services.md` | 서비스 레이어 및 진행률 배분 |
| `component-dependency.md` | 의존성 및 통신 패턴 |
