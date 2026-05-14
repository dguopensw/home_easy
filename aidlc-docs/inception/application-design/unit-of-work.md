# Unit of Work 정의
# 집에 가구 쉽다 (Easy Furniture Fit)

---

## 모노레포 디렉토리 구조

```
opensw/                    ← git repo 루트
├── frontend/              ← Unit 1: React PWA
├── backend/               ← Unit 2: FastAPI
├── ai-pipeline/           ← Unit 3: RunPod Serverless
└── unity-ar/              ← Unit 4: Unity WebGL
    └── (빌드 시 frontend/public/unity/ 에 복사)
```

---

## Unit 1 — Frontend

| 항목 | 내용 |
|------|------|
| **경로** | `frontend/` |
| **기술 스택** | React + Vite + TypeScript + Tailwind CSS |
| **배포** | Vercel |
| **책임** | 전체 UI 렌더링, React Router 화면 전환, SSE 수신, Unity WebGL 로드 |

### 내부 구조
```
frontend/
├── .eslintrc.cjs
├── .prettierrc
├── src/
│   ├── index.css       ← Tailwind directives + 전역 스타일
│   ├── router.tsx      ← 라우트 정의 (Post-MVP Protected Route 대비)
│   ├── pages/
│   │   ├── HomePage/
│   │   │   ├── HomePage.tsx
│   │   │   └── components/     ← Home 전용 컴포넌트
│   │   ├── UrlInputPage/
│   │   │   ├── UrlInputPage.tsx
│   │   │   └── components/
│   │   ├── LoadingPage/
│   │   │   ├── LoadingPage.tsx
│   │   │   └── components/
│   │   ├── PreviewPage/
│   │   │   ├── ModelPreviewPage.tsx
│   │   │   └── components/
│   │   ├── ARPage/
│   │   │   ├── ARPage.tsx
│   │   │   └── components/
│   │   ├── HistoryPage/
│   │   │   ├── HistoryPage.tsx
│   │   │   └── components/
│   │   └── ResultPage/
│   │       ├── ResultPage.tsx
│   │       └── components/
│   ├── components/     ← 공통 컴포넌트 (Button, ProgressBar, Toast, NavBar)
│   └── api/            ← 백엔드 API 호출 함수
├── public/
│   └── unity/          ← Unity WebGL 빌드 결과물 (unity-ar에서 복사)
└── index.html
```

### 포함 페이지
- HomePage, UrlInputPage, LoadingPage
- ModelPreviewPage, ARPage, HistoryPage, ResultPage

---

## Unit 2 — Backend API

| 항목 | 내용 |
|------|------|
| **경로** | `backend/` |
| **기술 스택** | Python + FastAPI + SQLAlchemy |
| **배포** | AWS EC2 |
| **책임** | 크롤링, 이미지 선정, 전처리, 치수 추정, UUID job_id 비동기 처리, RunPod 작업 관리, SSE 스트리밍, 완료 결과 DB 저장 |

### 내부 구조
```
backend/
├── main.py              ← FastAPI 앱 초기화, create_all()로 테이블 생성
├── database.py          ← DB 연결 설정 (engine, SessionLocal)
├── routers/
│   ├── generation.py    ← /furniture/gen/start, /furniture/gen/status/{id}
│   ├── crawling.py      ← /furniture/crawl/test
│   └── furniture.py     ← /furniture/{id}
├── services/
│   ├── crawling_service.py      ← 플랫폼별 크롤링
│   ├── image_selector.py        ← GPT-4o Vision 이미지 선정
│   ├── preprocessor.py          ← DINO+SAM 배경 제거, LaMa 인페인팅
│   ├── dimension_estimator.py   ← Metric3D 치수 추정
│   └── generation_service.py    ← UUID job_id 생성, RunPod 요청/폴링, SSE 스트림, DB 저장
└── models/
    └── job.py           ← Job DB 모델 (job_id, source_url, dimensions, glb_url, created_at)
```

---

## Unit 3 — AI Pipeline

| 항목 | 내용 |
|------|------|
| **경로** | `ai-pipeline/` |
| **기술 스택** | Python + RunPod Serverless SDK |
| **배포** | RunPod (GPU 서버리스) |
| **책임** | 전처리된 이미지로 3D 모델 생성 (TRELLIS) → S3 업로드 → glb_url 반환 |

### 내부 구조
```
ai-pipeline/
├── handler.py          ← RunPod 진입점 (단일 handler 함수, FastAPI 없음)
└── steps/
    └── model_generator.py   ← TRELLIS 3D 생성 + S3 업로드
```

---

## Unit 4 — Unity AR

| 항목 | 내용 |
|------|------|
| **경로** | `unity-ar/` |
| **기술 스택** | Unity (WebGL 빌드) |
| **배포** | 빌드 결과물 → `frontend/public/unity/` 복사 후 Vercel |
| **책임** | AR 씬, .glb 모델 로드, 터치 조작, React↔Unity 브리지 |

### 내부 구조
```
unity-ar/
├── Assets/
│   └── Scripts/
│       ├── ARController.cs
│       ├── ModelLoader.cs
│       ├── PlacementManager.cs
│       └── JSBridge.cs
└── ProjectSettings/
```

### 빌드 및 배포 흐름
```
unity-ar/ 에서 WebGL 빌드
    → Build/ 결과물 생성
    → frontend/public/unity/ 에 복사
    → Vercel 배포 시 자동 포함
```
