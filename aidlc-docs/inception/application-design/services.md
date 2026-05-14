# 서비스 레이어 정의 (Services)
# 집에 가구 쉽다 (Easy Furniture Fit)

---

## 서비스 아키텍처 개요

```
[React PWA]
    |
    | REST / SSE
    v
[FastAPI -- AWS EC2]
    |          |           |            |              |
    v          v           v            v              v
[Crawling] [ImageSelector] [Preprocessor] [DimEstimator] [PipelineService]
 Service     Service         Service        Service           |
                                                         RunPod API
                                                              |
                                                         [RunPod Serverless]
                                                              |
                                                         [TRELLIS → S3 Upload]
                                                              |
                                                         glb_url 반환
                                                              |
                                                    [PostgreSQL -- job 결과 저장]
```

---

## Backend Services

### CrawlingService
**역할**: 중고 플랫폼 URL에서 가구 이미지와 텍스트 정보 수집

| 항목 | 내용 |
|------|------|
| 입력 | 게시글 URL (당근마켓 / 번개장터 / 중고나라) |
| 출력 | 이미지 URL 목록, 게시글 텍스트, 플랫폼 구분 |
| 의존성 | 없음 (외부 HTTP 요청) |
| 에러 케이스 | 게시글 삭제, 지원하지 않는 플랫폼, 네트워크 오류 |

### ImageSelectorService
**역할**: GPT-4o Vision으로 가구가 가장 잘 보이는 이미지 1장 선정

| 항목 | 내용 |
|------|------|
| 입력 | CrawlingService가 수집한 이미지 URL 목록 |
| 출력 | 선정된 이미지 1장 |
| 의존성 | GPT-4o Vision API |

### PreprocessorService
**역할**: 배경 제거 및 인페인팅으로 이미지 전처리

| 항목 | 내용 |
|------|------|
| 입력 | 선정된 이미지 |
| 출력 | 전처리된 이미지 (배경 제거 + 인페인팅 완료) |
| 의존성 | Grounding DINO, SAM, LaMa |

### DimensionEstimatorService
**역할**: 단일 이미지에서 가구 치수(W×H×D) 추정

| 항목 | 내용 |
|------|------|
| 입력 | 전처리된 이미지 |
| 출력 | dimensions { w, h, d } (cm) |
| 의존성 | Metric3D / Depth Pro |

### PipelineService
**역할**: RunPod Serverless 3D 모델 생성 작업 생명주기 관리

| 항목 | 내용 |
|------|------|
| 입력 | 전처리된 이미지 |
| 출력 | glb_url |
| 의존성 | RunPod API |
| 에러 케이스 | RunPod 타임아웃, 모델 생성 실패, Cold Start 지연 |

**RunPod 엔드포인트 관리**:
- RunPod 배포 시 고정 엔드포인트 ID가 발급되며 환경변수로 관리
- `POST https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}/run`

**작업 종류 확장 시 대응 방법**:
- 단일 엔드포인트: handler 내부에서 `event["input"]["task"]`로 분기 처리
- 작업이 독립적이거나 GPU 사양이 다를 경우: 엔드포인트 분리 (`endpoint-3d`, `endpoint-upscale` 등)

**비동기 처리 흐름**:
```
UUID로 job_id 생성 → 프론트엔드에 즉시 반환
    → 백그라운드에서 순차 처리
        -> CrawlingService
        -> ImageSelectorService
        -> PreprocessorService
        -> DimensionEstimatorService
        -> RunPod 작업 시작 (runpod_job_id 메모리에만 저장)
        -> 2초마다 RunPod 상태 폴링
        -> 각 단계마다 SSE progress 이벤트 발행
        -> RunPod 완료 시 glb_url 수신
        -> DB에 완료 결과 저장 (job_id, source_url, dimensions, glb_url)
        -> complete 이벤트 발행 (glb_url + dimensions)
```

---

## AI Pipeline Steps

### 파이프라인 실행 순서

```
[FastAPI 백엔드]
      |
      v
[1] CrawlingService    이미지 목록 + 텍스트 수집
      |
      v
[2] ImageSelector      GPT-4o Vision -> 최적 이미지 1장 선택
      |
      v
[3] Preprocessor       DINO+SAM -> 객체 추출 / LaMa -> 인페인팅
      |
      v
[4] DimensionEstimator Metric3D -> W x H x D 치수 추정 (cm)
      |
      v (RunPod API 호출)
[RunPod Serverless]
      |
      v
[5] ModelGenerator     TRELLIS -> .glb 생성
      |
      v
[6] S3 Upload          생성된 .glb -> S3 업로드 -> glb_url 반환
      |
      v (폴링으로 감지)
[FastAPI 백엔드]
      |
      v
[DB 저장]              job_id, source_url, dimensions, glb_url
      |
      v
[SSE complete 이벤트]  glb_url + dimensions -> 프론트엔드 전송
```

### 각 단계 진행률 매핑 (시간 기반 배분)

| 단계 | 실행 위치 | 예상 소요 시간 | 진행률 범위 |
|------|---------|--------------|------------|
| 크롤링 | FastAPI | ~10초 | 0% → 5% |
| 이미지 선정 | FastAPI | ~10초 | 5% → 10% |
| 전처리 | FastAPI | ~20초 | 10% → 20% |
| 치수 추정 | FastAPI | ~15초 | 20% → 30% |
| **3D 모델 생성** | **RunPod** | **~120초** | **30% → 95%** |
| S3 업로드 | RunPod | ~5초 | 95% → 100% |

> 3D 생성(TRELLIS)이 전체 진행률의 65%를 차지하여 실제 소요 시간을 반영합니다.
