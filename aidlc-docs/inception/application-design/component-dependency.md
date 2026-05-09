# 컴포넌트 의존성 및 통신 패턴 (Component Dependency)
# 집에 가구 쉽다 (Easy Furniture Fit)

---

## 전체 통신 흐름

```
[React PWA -- Vercel]
    |
    | 1) POST /furniture/gen/start  { url }
    | 2) GET  /furniture/gen/status/{job_id}  (SSE)
    | 3) GET  /furniture/{job_id}
    v
[FastAPI -- AWS EC2]
    |                  |
    | RunPod API        | boto3
    v                  v
[RunPod Serverless]  [AWS S3]
    |
    | 내부 순차 실행
    v
[ImageSelector -> Preprocessor -> DimensionEstimator -> ModelGenerator]
                                                               |
                                                        .glb 파일 S3 업로드
```

---

## Unit 간 통신 패턴

### Frontend <-> Backend API
| 통신 | 방식 | 엔드포인트 |
|------|------|-----------|
| 3D 모델 생성 파이프라인 시작 | HTTP POST | `/furniture/gen/start` |
| 진행 상태 수신 | SSE (GET) | `/furniture/gen/status/{job_id}` |
| 모델 정보 조회 | HTTP GET | `/furniture/{job_id}` |
| 크롤링 단독 테스트 | HTTP POST | `/furniture/crawl/test` |

### Backend API <-> RunPod
| 통신 | 방식 | 내용 |
|------|------|------|
| 작업 시작 | RunPod REST API | 이미지 목록, 텍스트 전달 |
| 상태 조회 | RunPod REST API | 2초마다 폴링 |
| 결과 수신 | RunPod REST API | glb_url, dimensions 반환 |

### React <-> Unity WebGL
| 통신 방향 | 방식 | 예시 |
|----------|------|------|
| React -> Unity | `unityInstance.SendMessage()` | `SendMessage("ARController", "LoadModel", glbUrl)` |
| Unity -> React | `window.dispatchEvent(CustomEvent)` | `new CustomEvent("unity:modelLoaded")` |

---

## 의존성 매트릭스

| 컴포넌트 | 의존 대상 |
|---------|----------|
| `LoadingPage` | React Router(useNavigate, useLocation), BackendAPI(/furniture/gen/status) |
| `ModelPreviewPage` | React Router(useLocation), model-viewer |
| `ARPage` | React Router(useNavigate), Unity WebGL (unityInstance) |
| `GenerationService` | CrawlingService, RunPod API |
| `ModelGenerator` | DimensionEstimator 결과, S3 |
| `handler.py` | 모든 Pipeline Steps |

---

## 데이터 흐름 요약

```
사용자 URL 입력
    -> UrlInputScreen -> POST /pipeline/start
    -> job_id 수신 -> LoadingScreen SSE 연결
    -> SSE 이벤트마다 진행률 업데이트
    -> complete 이벤트 -> glbUrl + dimensions -> AppContext 저장
    -> ModelPreviewScreen -> model-viewer로 .glb 렌더링
    -> ARScreen -> Unity에 glbUrl 전달 -> AR 배치
```
