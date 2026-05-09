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
    |               |               |
    v               v               v
[CrawlingService] [PipelineService] [StorageService]
                      |
                      | RunPod API
                      v
               [RunPod Serverless]
                      |
              [AI Pipeline Handler]
               |      |      |      |
           [Image] [Preproc] [Dim] [TRELLIS]
                                      |
                                      v
                                   [S3 Upload]
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

### PipelineService
**역할**: RunPod Serverless AI 작업 생명주기 관리

| 항목 | 내용 |
|------|------|
| 입력 | CrawlingService 결과 |
| 출력 | job_id (즉시), 진행 상태 스트림 (SSE), 최종 glb_url + dimensions |
| 의존성 | CrawlingService, StorageService, RunPod API |
| 에러 케이스 | RunPod 타임아웃, 모델 생성 실패, Cold Start 지연 |

**SSE 이벤트 흐름**:
```
start_job() 호출
    -> RunPod 작업 시작
    -> 2초마다 RunPod 상태 폴링
    -> 단계 변경 시 SSE 이벤트 발행
    -> 완료 시 glb_url + dimensions 포함 complete 이벤트 발행
```

---

## AI Pipeline Steps (RunPod 내부)

### 파이프라인 실행 순서

```
입력 이미지 목록
      |
      v
[1] ImageSelector      GPT-4o Vision -> 최적 이미지 1장 선택
      |
      v
[2] Preprocessor       DINO+SAM -> 객체 추출 / LaMa -> 인페인팅
      |
      v
[3] DimensionEstimator Metric3D -> W x H x D 치수 추정 (cm)
      |
      v
[4] ModelGenerator     TRELLIS -> .glb 생성
      |
      v
[5] S3 Upload          생성된 .glb -> S3 업로드 -> URL 반환
```

### 각 단계 진행률 매핑 (시간 기반 배분)

| 단계 | 예상 소요 시간 | 진행률 범위 |
|------|--------------|------------|
| 크롤링 완료 (FastAPI) | ~10초 | 0% → 5% |
| 이미지 선정 완료 | ~10초 | 5% → 10% |
| 전처리 완료 | ~20초 | 10% → 20% |
| 치수 추정 완료 | ~15초 | 20% → 30% |
| **3D 모델 생성 완료** | **~120초** | **30% → 95%** |
| S3 업로드 완료 | ~5초 | 95% → 100% |

> 3D 생성(TRELLIS)이 전체 진행률의 65%를 차지하여 실제 소요 시간을 반영합니다.
