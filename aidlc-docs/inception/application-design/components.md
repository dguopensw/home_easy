# 컴포넌트 정의 (Components)
# 집에 가구 쉽다 (Easy Furniture Fit)

---

## Unit 1 — Frontend (React + Vite + TypeScript + Tailwind CSS)

### App
- **책임**: React Router 라우트 정의 — 경로에 따라 화면 컴포넌트 렌더링
- **데이터 전달**: 화면 간 데이터는 `navigate(path, { state })` / `useLocation().state` 사용

### 라우트 경로

| 컴포넌트 | 경로 |
|---------|------|
| `HomePage` | `/home` |
| `UrlInputPage` | `/url-input` |
| `LoadingPage` | `/loading` |
| `ModelPreviewPage` | `/preview` |
| `ARPage` | `/ar` |
| `HistoryPage` | `/history` |
| `ResultPage` | `/result` |

### Pages (화면 컴포넌트)

| 컴포넌트 | 책임 | MVP 여부 |
|---------|------|---------|
| `HomePage` | 다크 Hero + 회전 3D 큐브, 시작하기 버튼, How it works 타임라인, 최근 기록 | MVP 완전 구현 |
| `UrlInputPage` | 링크 아이콘 input, 플랫폼 칩, 데모 카드, sourceUrl을 state로 전달 | MVP 완전 구현 |
| `LoadingPage` | 회전 3D 큐브, 그라디언트 진행바, StepList — SSE 연동 예정 (현재 mock) | MVP 완전 구현 |
| `ModelPreviewPage` | 헤더 내 탭 스위처(3D/치수), model-viewer, 정보 카드, SVG 치수 도식 | MVP 완전 구현 |
| `ARPage` | Unity WebGL iframe, React↔Unity 브리지, 촬영 후 `/result`로 이동 | MVP 완전 구현 |
| `HistoryPage` | 배치 기록 그리드 UI | MVP UI만 |
| `ResultPage` | 완료 아이콘, 결과 카드, 공유/재시작/구매하러 가기(sourceUrl) 버튼 | MVP UI만 |

### Shared Components (공통 컴포넌트)

| 컴포넌트 | 책임 |
|---------|------|
| `Button` | 공통 버튼 (accent, outline 변형) |
| `ProgressBar` | AI 파이프라인 진행률 바 |
| `Toast` | 저장 완료 등 일회성 알림 |
| `NavBar` | 뒤로가기 버튼 + 화면 제목 (투명 배경, 페이지 bg 그대로 사용) |

### 화면 간 데이터 흐름 (navigate state)

```
UrlInputPage  →  /loading   { jobId, sourceUrl }
LoadingPage   →  /preview   { glbUrl, dimensions, sourceUrl }
PreviewPage   →  /ar        { glbUrl, sourceUrl }
ARPage        →  /result    { sourceUrl }
ResultPage        sourceUrl로 "구매하러 가기" 외부 링크 표시
```

---

## Unit 2 — Backend API (Python + FastAPI)

### main.py
- **책임**: FastAPI 앱 초기화, 라우터 등록, CORS 설정

### routers/crawling.py
- **책임**: `/furniture/crawl/test` — 크롤링 단독 테스트 엔드포인트

### routers/generation.py
- **책임**: `/furniture/gen/start`, `/furniture/gen/status/{id}` — AI 파이프라인 작업 시작, SSE 스트림으로 진행 상태 전달

### routers/furniture.py
- **책임**: `/furniture/{id}` — 완성된 .glb 파일 URL 및 치수 데이터 반환

### services/crawling_service.py
- **책임**: 당근마켓·번개장터·중고나라 게시글 파싱, 이미지·텍스트 수집

### services/image_selector.py
- **책임**: GPT-4o Vision으로 가구가 가장 잘 보이는 이미지 1장 선정

### services/preprocessor.py
- **책임**: Grounding DINO + SAM으로 가구 객체 추출, LaMa로 인페인팅

### services/dimension_estimator.py
- **책임**: Metric3D / Depth Pro로 단일 이미지에서 W·H·D 치수 추정 (cm)

### services/generation_service.py
- **책임**: UUID로 job_id 생성, RunPod 작업 요청(runpod_job_id 메모리 보관), 상태 폴링, SSE 스트림 관리, 완료 결과 DB 저장

### models/job.py
- **책임**: Job DB 모델 정의 (job_id, source_url, dimensions, glb_url, created_at)

### database.py
- **책임**: DB 연결 설정 (engine, SessionLocal)


---

## Unit 3 — AI Pipeline (Python + RunPod Serverless)

> RunPod Serverless는 FastAPI 같은 웹 프레임워크를 사용하지 않습니다.
> AWS Lambda와 유사하게 `handler` 함수 하나가 진입점이며, RunPod 인프라가 HTTP 라우팅·큐잉·스케일링을 전담합니다.
> 현재 프로젝트는 3D 생성 작업 하나만 처리하므로 단일 handler로 충분합니다.

```python
import runpod

def handler(event):
    input = event["input"]   # 백엔드가 보낸 전처리 이미지 등
    # 3D 생성 처리...
    return { "glb_url": "..." }

runpod.serverless.start({ "handler": handler })
```

### handler.py
- **책임**: RunPod Serverless 진입점, 전처리된 이미지 수신 후 3D 생성 파이프라인 실행

### steps/model_generator.py
- **책임**: TRELLIS로 전처리 이미지 → .glb 3D 모델 생성, S3 업로드 후 glb_url 반환

---

## Unit 4 — Unity AR (Unity WebGL)

### ARController (C#)
- **책임**: AR 씬 전체 관리, JSBridge 이벤트 수신 및 처리

### ModelLoader (C#)
- **책임**: React로부터 전달받은 .glb URL을 런타임에 로드

### PlacementManager (C#)
- **책임**: 가구 3D 모델 화면 표시, 터치 드래그 이동, 회전 제스처 처리

### JSBridge (C#)
- **책임**: Unity ↔ React 통신 — `SendMessage` 수신, `CustomEvent` 발생
