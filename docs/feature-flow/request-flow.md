# URL 입력 → 3D 가구 생성 결과 수신까지 전체 흐름
# 집에 가구 쉽다 (Easy Furniture Fit)

> 처음 개발을 시작하는 사람을 위한 흐름 설명서입니다.  
> "URL을 입력하면 어떤 일이 일어나는가?"를 처음부터 끝까지 순서대로 설명합니다.

---

## 한 눈에 보기

```
[사용자]
  URL 입력
     |
     v
[프론트엔드]                          [백엔드]                        [RunPod]          [DB]      [S3]
  URL 전송 (POST /furniture/gen/start)
  ─────────────────────────────────►
                                      job_id 생성 (UUID)
                                      job_id 즉시 반환
  ◄─────────────────────────────────
                                      [백그라운드 처리 시작]
                                      크롤링 수행
                                      이미지 선정 (GPT-4o)
                                      배경 제거 / 인페인팅
                                      치수 추정 (Metric3D)
                                      작업 요청 전송 (전처리 이미지)
                                      ────────────────────────────►
                                                                    runpod_job_id 반환 (DB 저장 x)
                                      ◄────────────────────────────

  SSE 연결 요청 (GET /furniture/gen/status/{job_id})
  ─────────────────────────────────►
  LoadingPage로 이동
  ┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
  │ LoadingPage                                                                                      │
  │                                     진행 이벤트 전송 (크롤링 ~ 전처리 구간)                         │
  │ ◄─────────────────────────────────                                                               │
  │                                     상태 조회 요청 (2초마다 폴링, runpod_job_id 사용)               │
  │                                     ────────────────────────────►                                │
  │                                                                   { status: "IN_PROGRESS" } 반환 │
  │                                     ◄────────────────────────────                                │
  │                                     진행 이벤트 전송 (RunPod 구간)                                 │
  │ ◄─────────────────────────────────                                                               │
  │       (반복)                                                                                     │
  └──────────────────────────────────────────────────────────────────────────────────────────────────┘

                                      상태 조회 요청
                                      ────────────────────────────►
                                                                    .glb 저장
                                                                    ─────────────────────────────────────►
                                                                    { status: "COMPLETED", glb_url } 반환
                                      ◄────────────────────────────

                                      완료 결과 저장 (job_id, source_url, dimensions, glb_url)
                                      ──────────────────────────────────────────────────────►

                                      
                                      complete 이벤트 전송 (glb_url, dimensions)
  ◄─────────────────────────────────

  3D 모델 화면으로 이동
```

---

## STEP 1. 사용자가 URL을 입력한다

- 화면: `UrlInputPage`
- 사용자가 당근마켓, 번개장터, 중고나라 중 하나의 가구 게시글 URL을 입력하고 버튼을 누릅니다.

**프론트엔드가 하는 일:**
1. URL이 비어있으면 → 흔들림 애니메이션 표시, 중단
2. 지원하지 않는 플랫폼이면 → 에러 메시지 표시, 중단
3. 유효한 URL이면 → 백엔드에 POST 요청 전송

```
POST /furniture/gen/start
Body: { "url": "https://www.daangn.com/..." }
```

---

## STEP 2. 백엔드가 job_id를 즉시 반환하고 백그라운드에서 처리를 시작한다

- 담당 파일: `routers/generation.py`, `services/crawling_service.py`, `services/image_selector.py`, `services/preprocessor.py`, `services/dimension_estimator.py`

**백엔드가 하는 일:**
1. UUID로 `job_id`를 직접 생성
2. `job_id`를 프론트엔드에 즉시 반환
3. 백그라운드에서 아래 처리를 순차 실행:
   1. URL로 플랫폼 자동 감지 후 **이미지 목록**과 **텍스트 설명** 수집
   2. GPT-4o Vision으로 **가구가 가장 잘 보이는 사진 1장 선정**
   3. 선정된 이미지에서 **배경 제거**(DINO+SAM) 및 **인페인팅**(LaMa)으로 전처리
   4. Metric3D 모델로 가구의 **가로/세로/깊이(cm) 치수 추정**
   5. 전처리된 이미지를 RunPod에 전송 → `runpod_job_id` 수신 (메모리에만 저장, DB저장x)

```
응답: { "job_id": "uuid-xxxx" }   // 전처리 완료를 기다리지 않고 즉시 반환
```

> `job_id`는 백엔드가 UUID로 생성합니다. RunPod이 반환하는 `runpod_job_id`는 폴링 용도로만 메모리에 보관하며 DB에는 저장하지 않습니다.

**DB에 저장되는 job 레코드 (MVP - 로그인 없음):**
```
{
  job_id:     "uuid-xxxx",
  source_url: "https://www.daangn.com/...",   // 사용자가 입력한 원본 게시글 URL
  dimensions: { w: 80, h: 60, d: 40 },
  glb_url:    "https://s3.../model.glb",
  created_at: "2026-05-14T12:00:00Z"
}
```

처리 중 상태는 SSE가 담당하므로 DB에는 **완료된 결과만** 저장합니다.

> **[TODO] 로그인 추가 시**: `user_id` 컬럼(FK)을 추가하고 Alembic으로 마이그레이션하면 됩니다.

---

## STEP 3. 프론트엔드가 로딩 화면으로 이동하고 SSE 연결을 시작한다

- 화면: `LoadingPage`
- 담당 파일: `routers/generation.py`, `services/generation_service.py`

**프론트엔드가 하는 일:**
1. 백엔드로부터 `job_id` 수신
2. `job_id`로 SSE 연결 요청
3. SSE 연결 완료 후 LoadingPage로 이동

```
GET /furniture/gen/status/{job_id}
(연결을 유지하며 서버로부터 실시간 이벤트를 수신)
```

> SSE 연결을 먼저 열고 LoadingPage로 이동하기 때문에, 페이지 전환 중에 발생하는 진행 이벤트를 놓치지 않습니다.

### SSE가 무엇이고 왜 필요한가?

**SSE(Server-Sent Events)** 는 서버가 HTTP 연결을 끊지 않고, 데이터를 준비될 때마다 클라이언트에 밀어주는 단방향 실시간 통신 방식입니다.

**이 프로젝트에서 SSE가 필요한 이유:**

3D 모델 생성은 전체 완료까지 **최대 3분 가까이 소요**됩니다. 이 긴 대기 시간 동안 사용자에게 진행 상황을 보여주려면 서버로부터 중간 상태를 계속 받아와야 합니다.

이를 구현하는 방법은 크게 세 가지인데, SSE가 가장 적합합니다:

| 방식 | 동작 | 이 프로젝트에서의 문제 |
|------|------|----------------------|
| **일반 REST 폴링** | 프론트가 2초마다 "다 됐어?" 요청을 반복 | 불필요한 요청이 계속 발생, 서버 부하 |
| **WebSocket** | 양방향 실시간 통신 | 서버→클라이언트 단방향만 필요한데 구현이 과함 |
| **SSE** ✅ | 연결을 유지하며 서버가 준비될 때만 데이터를 전송 | 단방향에 최적, 구현 간단, 불필요한 요청 없음 |

**SSE가 사용되는 구체적인 위치:**

- `job_id` 수신 직후 `EventSource` 객체를 생성해 SSE 연결을 열고, 연결 완료 후 LoadingPage로 이동합니다
- 백엔드에서 RunPod 상태가 바뀔 때마다 이벤트를 전송하고, LoadingPage는 이를 받아 진행 바와 단계 UI를 업데이트합니다
- 완료 또는 에러 이벤트를 받으면 연결을 닫고 다음 화면으로 이동합니다
- LoadingPage에서 벗어날 때(언마운트)도 반드시 연결을 닫아 리소스를 정리합니다

```
LoadingPage 마운트
  → EventSource 열림 (연결 유지)
      ↓ 서버에서 이벤트 올 때마다
  → progress 이벤트: 진행 바 업데이트
  → progress 이벤트: 단계 아이콘 업데이트
      ↓ 최종 이벤트
  → complete: EventSource 닫기 → PreviewPage 이동
  → error:    EventSource 닫기 → 에러 UI 표시
```

**백엔드가 하는 일:**
- 2초마다 RunPod에 작업 상태를 폴링(조회)
- 단계가 바뀔 때마다 프론트엔드에 진행 이벤트를 전송

> **[TODO] 웹훅 방식으로 전환 고려**  
> 현재는 폴링 방식을 사용하지만, 배포 후 웹훅으로 전환할 수 있습니다.  
> 전환 시 `generation_service.py`의 폴링 루프를 제거하고 `/webhook` 엔드포인트를 추가하면 됩니다. SSE 전송 로직은 그대로 재사용 가능합니다.  
> (로컬 개발 환경에서는 RunPod이 localhost에 콜백을 보낼 수 없으므로 ngrok 등 터널링 툴이 필요합니다.)

```
// 진행 중 이벤트
{ "step": "전처리 중", "progress": 15 }

// 완료 이벤트
{ "status": "complete", "glb_url": "https://s3.../model.glb", "dimensions": { "w": 80, "h": 60, "d": 40 } }

// 에러 이벤트
{ "status": "error", "message": "모델 생성 실패" }
```

---

## STEP 4. RunPod에서 AI 파이프라인이 실행된다

- 담당 파일: `handler.py`, `steps/` 디렉토리
- 실행 위치: RunPod Serverless (GPU 서버, 백엔드와 별도)

**AI 파이프라인 2단계:**

| 단계 | 파일 | 하는 일 | 진행률 |
|------|------|---------|--------|
| 1. 3D 모델 생성 | `model_generator.py` | TRELLIS로 전처리된 이미지 → .glb 3D 파일 생성 (가장 오래 걸림) | 30% → 95% |
| 2. S3 업로드 | `model_generator.py` | 생성된 .glb 파일을 AWS S3에 저장하고 URL 반환 | 95% → 100% |

> TRELLIS 3D 생성이 전체 시간의 약 65%를 차지합니다 (약 120초 소요).

---

## STEP 5. 백엔드가 완료 이벤트를 프론트엔드에 전송한다

- RunPod 작업이 완료되면 백엔드가 폴링으로 이를 감지
- RunPod 응답에서 `glb_url` 수신
- DB에 완료 결과 저장 (`job_id`, `source_url`, `dimensions`, `glb_url`, `created_at`)
- STEP 2에서 미리 추정해둔 `dimensions`와 합쳐 SSE로 `complete` 이벤트를 프론트엔드에 전송

```
{ "status": "complete", "glb_url": "https://s3.amazonaws.com/.../model.glb", "dimensions": { "w": 80, "h": 60, "d": 40 } }
//                       ^--- RunPod에서 수신                                  ^--- 백엔드가 STEP 2에서 이미 계산
```

---

## STEP 6. 프론트엔드가 3D 모델 화면으로 이동한다

- 화면: `ModelPreviewPage`

**프론트엔드가 하는 일:**
- SSE 연결을 닫음
- `glb_url`과 `dimensions`를 들고 ModelPreviewPage로 이동
- `<model-viewer>` 컴포넌트에 `glb_url`을 전달해 3D 모델 렌더링
- 치수 탭에서 가로/세로/깊이 표시

---

## 전체 진행률 타임라인

```
  0%   크롤링 시작 (FastAPI)                              ~10초
  5%   이미지 선정 중 (FastAPI / GPT-4o)                  ~10초
 10%   전처리 중 (FastAPI / 배경 제거 · 인페인팅)          ~20초
 20%   치수 추정 중 (FastAPI / Metric3D)                  ~15초
 30%   3D 모델 생성 중 (RunPod / TRELLIS) ← 가장 오래 걸림 ~120초
 95%   S3 업로드 중 (RunPod)                              ~5초
100%   완료 → ModelPreviewPage 이동
```

---

## 에러가 발생하면?

| 에러 발생 위치 | 처리 방식 |
|--------------|---------|
| URL 입력 검증 실패 | 프론트엔드에서 즉시 차단, 에러 메시지 표시 |
| 크롤링 실패 (게시글 삭제 등) | SSE `error` 이벤트 전송 → LoadingPage 에러 UI 표시 (DB 저장 없음) |
| 백엔드 전처리 실패 (이미지 선정 / 배경 제거 / 치수 추정) | SSE `error` 이벤트 전송 → LoadingPage 에러 UI 표시 (DB 저장 없음) |
| RunPod 작업 실패 | SSE `error` 이벤트 전송 → LoadingPage 에러 UI 표시 (DB 저장 없음) |
| RunPod 타임아웃 | SSE `error` 이벤트 전송 → LoadingPage 에러 UI 표시 (DB 저장 없음) |

---

## 관련 파일 위치 요약

```
frontend/
  src/pages/
    UrlInputPage.tsx       # URL 입력 및 POST 요청
    LoadingPage.tsx        # SSE 연결 및 진행 상태 표시
    ModelPreviewPage.tsx   # 3D 모델 렌더링

backend/
  routers/
    generation.py          # POST /furniture/gen/start, GET /furniture/gen/status/{job_id}
  services/
    crawling_service.py    # 플랫폼별 크롤링
    image_selector.py      # 최적 이미지 선정 (GPT-4o)
    preprocessor.py        # 배경 제거 / 인페인팅 (DINO+SAM, LaMa)
    dimension_estimator.py # 치수 추정 (Metric3D)
    generation_service.py  # RunPod 작업 시작 / 상태 폴링 / SSE 스트림
  models/
    job.py                 # Job DB 모델 (job_id, source_url, dimensions, glb_url, created_at)
  database.py              # DB 연결 설정 (engine, SessionLocal)
  main.py                  # 서버 시작 시 Base.metadata.create_all(engine) 호출 → 테이블 자동 생성

ai-pipeline/ (RunPod)
  handler.py               # 파이프라인 진입점
  steps/
    model_generator.py     # 3D 모델 생성 + S3 업로드
```

---

## DB 테이블 생성 방식

`job.py`에 정의한 모델을 SQLAlchemy가 SQL로 변환해 DB 서버에 실행합니다.

```
job.py (Python 클래스)
    ↓ SQLAlchemy 변환
CREATE TABLE jobs (...) (SQL)
    ↓ DB 서버에 실행
실제 테이블 생성
```

**최초 배포 시**: `main.py`에서 `Base.metadata.create_all(engine)`을 호출해 테이블을 자동 생성합니다. 이미 테이블이 있으면 건드리지 않습니다.

**이후 스키마 변경 시**: `create_all()`은 기존 테이블을 수정하지 않으므로 Alembic(마이그레이션 툴)을 사용합니다.

```bash
# 컬럼 추가 등 스키마 변경 후
alembic revision --autogenerate -m "변경 내용 설명"
alembic upgrade head  # 변경사항 DB에 반영
```
