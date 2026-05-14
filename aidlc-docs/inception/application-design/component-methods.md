# 주요 메서드 시그니처 (Component Methods)
# 집에 가구 쉽다 (Easy Furniture Fit)

> 상세 비즈니스 로직은 CONSTRUCTION 단계 Functional Design에서 정의됩니다.

---

## Unit 1 — Frontend

### React Router 라우트 구조
```
/HomePage         → HomePage
/UrlInputPage     → UrlInputPage
/LoadingPage      → LoadingPage
/PreviewPage      → ModelPreviewPage
/ARPage           → ARPage
/HistoryPage      → HistoryPage
/ResultPage       → ResultPage
```

---

### 화면 간 데이터 전달
> React Router `navigate(path, { state })` + `useLocation().state`로 전달. Context 없음.
> - UrlInputPage → LoadingPage: `{ jobId }` (POST /furniture/gen/start 호출 후 수신)
> - LoadingPage → ModelPreviewPage: `{ glbUrl, dimensions }`
> - ModelPreviewPage → ARPage: props로 `glbUrl` 전달

### LoadingPage
```typescript
// SSE 연결 시작 및 진행 상태 수신
connectSSE(jobId: string): EventSource
handleProgressEvent(event: MessageEvent): void  // 단계 및 진행률 업데이트
handleCompleteEvent(event: MessageEvent): void  // glbUrl, dimensions 저장 후 화면 전환
handleErrorEvent(event: MessageEvent): void     // 에러 메시지 표시
```

### ARPage
```typescript
// Unity 인스턴스 초기화 및 브리지 설정
initUnity(canvasId: string): Promise<UnityInstance>
sendGlbToUnity(glbUrl: string): void            // SendMessage("ARController", "LoadModel", url)
handleUnityEvent(event: CustomEvent): void      // unity:planeFound, unity:placed 등 수신
```

### ModelPreviewPage
```typescript
loadModel(glbUrl: string): void                 // model-viewer src 설정
switchTab(tab: '3d' | 'dimensions'): void
```

---

## Unit 2 — Backend API

### routers/generation.py
```python
POST /furniture/gen/start
  입력: { url: str }
  출력: { job_id: str }

GET /furniture/gen/status/{job_id}     # SSE 엔드포인트
  출력: text/event-stream
  이벤트:
    { step: str, progress: int }       # 진행 상태
    { status: "complete", glb_url: str, dimensions: {...} }
    { status: "error", message: str }
```

### routers/crawling.py (테스트용)
```python
POST /furniture/crawl/test             # 크롤링 단독 테스트용
  입력: { url: str }
  출력: { images: list[str], text: str, platform: str }
```

### routers/furniture.py
```python
GET /furniture/{job_id}
  출력: { glb_url: str, dimensions: { w: float, h: float, d: float } }
```

### services/image_selector.py
```python
select_best_image(images: list[str]) -> str     # GPT-4o Vision으로 최적 이미지 선택
```

### services/preprocessor.py
```python
remove_background(image_path: str) -> str       # DINO + SAM 세그멘테이션
inpaint(image_path: str, mask_path: str) -> str # LaMa 인페인팅
```

### services/dimension_estimator.py
```python
estimate_dimensions(image_path: str) -> dict    # Metric3D → { w, h, d } cm 단위
```

### services/generation_service.py
```python
create_job(url: str) -> str                     # UUID job_id 생성 후 즉시 반환
run_pipeline(job_id: str, url: str) -> None     # 백그라운드에서 전체 파이프라인 실행
poll_runpod(runpod_job_id: str) -> dict         # RunPod 상태 폴링 (메모리의 runpod_job_id 사용)
stream_progress(job_id: str) -> AsyncGenerator  # SSE용 진행 상태 스트림
save_result(job_id: str, result: dict) -> None  # 완료 결과 DB 저장
```

### services/crawling_service.py
```python
crawl(url: str) -> CrawlResult                  # 플랫폼 감지 후 파싱
detect_platform(url: str) -> str                # 'daangn' | 'bunjang' | 'junggonara'
parse_daangn(url: str) -> CrawlResult
parse_bunjang(url: str) -> CrawlResult
parse_junggonara(url: str) -> CrawlResult
```


---

## Unit 3 — AI Pipeline

### handler.py
```python
handler(job: dict) -> dict
  입력: { image: str }   # 백엔드에서 전처리 완료된 이미지
  출력: { glb_url: str }  # dimensions는 백엔드에서 이미 계산됨
```

### steps/model_generator.py
```python
generate_glb(image_path: str) -> str            # TRELLIS → .glb 파일 경로
upload_to_s3(glb_path: str, job_id: str) -> str # S3 업로드 후 URL 반환
```

---

## Unit 4 — Unity AR

### ARController (C#)
```csharp
void LoadModel(string glbUrl)        // JSBridge 통해 React로부터 수신
void OnModelLoaded()                 // 모델 로드 완료 시 React에 이벤트 전송
```

### PlacementManager (C#)
```csharp
void PlaceModel(GameObject model)    // 화면에 모델 배치
void OnDrag(Vector2 delta)           // 터치 드래그 → 위치 이동
void OnRotate(float angle)           // 두 손가락 회전 제스처
void DuplicateSelected()
void DeleteSelected()
```

### JSBridge (C#)
```csharp
// Unity → React
void DispatchToReact(string eventName, string data)
  // window.dispatchEvent(new CustomEvent(eventName, { detail: data }))

// React → Unity (C# 메서드가 JS SendMessage로 호출됨)
void ReceiveMessage(string json)
```
