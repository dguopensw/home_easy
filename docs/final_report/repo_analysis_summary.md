# 레포지토리 분석 요약 (repo_analysis_summary.md)

> 분석 기준: `/Users/dahoo/home_easy/backend` (브랜치: `feat/backend-migration`)
> 작성 기준일: 2026-05-22

---

## 1. 확인된 폴더 구조

```
home_easy/
├── backend/
│   ├── main.py                        # FastAPI 앱 진입점
│   ├── core.py                        # 공통 유틸리티 (_core, OUTPUT_DIR 등)
│   ├── app_core.py                    # 앱 코어 설정
│   ├── database.py                    # SQLAlchemy async 설정
│   ├── lama_inpaint_worker.py         # LaMa 인페인팅 워커 (서브프로세스용)
│   ├── requirements.txt               # 의존성 목록
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── setup.sh
│   ├── models/
│   │   ├── __init__.py
│   │   └── job.py                     # Job DB 모델
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── crawling.py                # POST /api/scrape
│   │   ├── generation.py              # POST /api/process, GET /api/gen/status/{job_id}
│   │   └── furniture.py               # GET /api/furniture/output/{job_id}/{filename}, GET /api/furniture/job/{job_id}
│   ├── services/
│   │   ├── __init__.py
│   │   ├── crawling_service.py        # 당근마켓/중고나라 스크래핑, 치수 파싱
│   │   ├── furniture_analysis_service.py  # 가구 유형 추론, 장애물/오염물 분석
│   │   ├── segmentation_service.py    # SAM3 마스크 생성 및 정제
│   │   ├── inpainting_service.py      # 인페인팅 라우팅 (Flux-Fill 주, LaMa 레거시)
│   │   ├── inpainting_flux.py         # Flux-Fill 인페인팅 구현
│   │   ├── dimension_estimator.py     # 치수 추정 (텍스트 파싱 우선, Vision 폴백)
│   │   ├── image_selector.py          # 이미지 순위 선택
│   │   ├── generation_service.py      # TRELLIS 3D 생성 연동 (별도 서비스)
│   │   ├── pipeline_service.py        # 전체 파이프라인 오케스트레이션
│   │   └── preprocessor.py            # 전처리 유틸리티
│   ├── segmentation_module/
│   │   └── segmentation.py            # SAM3 세그멘테이션 모듈
│   ├── static/
│   │   └── index.html                 # 임시 프론트엔드 (파이프라인 검증용)
│   └── output/                        # 파이프라인 결과물 저장 (job_id별 디렉토리)
├── docs/
│   └── final_report/                  # OSSP 최종보고서 (현재 작성 중)
├── frontend/                          # (미사용 또는 초기 상태 확인 필요)
├── unity-ar/                          # Unity 프로젝트 관련 (확인 필요)
├── ai-pipeline/                       # 별도 AI 파이프라인 (확인 필요)
└── CLAUDE.md
```

---

## 2. 확인된 주요 파일

| 파일 | 역할 | 확인 상태 |
|------|------|---------|
| `backend/main.py` | FastAPI 앱, 라우터 등록, 정적 파일 서빙, health 엔드포인트 | 확인 완료 |
| `backend/services/pipeline_service.py` | 전체 파이프라인 오케스트레이션 (13단계) | 확인 완료 |
| `backend/routers/generation.py` | `/api/process`, `/api/gen/status/{job_id}` 구현 | 확인 완료 |
| `backend/routers/crawling.py` | `/api/scrape` 구현 | 확인 완료 |
| `backend/routers/furniture.py` | 파일/결과 조회 API | 확인 완료 |
| `backend/services/inpainting_service.py` | LaMa 메서드 존재하나 실제로는 Flux-Fill 호출 | 확인 완료 |
| `backend/services/inpainting_flux.py` | Flux.1-Fill-dev 모델 로드 및 추론 | 확인 완료 |
| `backend/services/crawling_service.py` | 당근마켓/중고나라 스크래핑, 정규식 치수 파싱 | 확인 완료 |
| `backend/services/dimension_estimator.py` | 치수 추정 (listing_text 우선, vision_estimate 폴백) | 확인 완료 |
| `backend/static/index.html` | 임시 프론트엔드 (파이프라인 검증용 UI) | 확인 완료 |
| `backend/requirements.txt` | 의존성 목록 | 확인 완료 |
| `backend/lama_inpaint_worker.py` | LaMa 서브프로세스 워커 (레거시 잔존) | 존재 확인 (내용 상세 확인 필요) |

---

## 3. 확인된 API 목록

| 기능 | Method | URL | 입력 | 출력 |
|------|--------|-----|------|------|
| 헬스 체크 | GET | `/health` | - | `{"status": "ok"}` |
| API 헬스 체크 | GET | `/api/health` | - | `{"status": "ok", "framework": "fastapi", "pipeline": "service_v3_sam3_only"}` |
| 정적 UI | GET | `/` | - | index.html (FileResponse) |
| 게시글 스크래핑 | POST | `/api/scrape` | `{"url": "..."}` | 제목, 설명, 가격, 이미지 목록, AI 추천 이미지 인덱스, 치수 |
| 전체 파이프라인 실행 | POST | `/api/process` | `{"url": "...", "selected_image_index": 0}` | result.json, model_generation 상태 |
| 생성 상태 조회 | GET | `/api/gen/status/{job_id}` | job_id | 전체 result.json + 최신 TRELLIS 상태 |
| 파이프라인 시작(레거시) | POST | `/api/gen/start` | `url` (query param) | `{"job_id": "...", "status": "completed"}` |
| 출력 파일 서빙 | GET | `/api/furniture/output/{job_id}/{filename}` | job_id, filename | 이미지 파일 (FileResponse) |
| 작업 결과 조회 | GET | `/api/furniture/job/{job_id}` | job_id | result.json |
| 크롤링 테스트(개발용) | GET | `/api/crawl/test` | `url` (query param) | 크롤링 결과 |

---

## 4. 확인된 서비스 클래스

| 클래스 | 파일 | 주요 역할 |
|--------|------|---------|
| `PipelineService` | `pipeline_service.py` | 전체 파이프라인 오케스트레이션 (13단계) |
| `CrawlingService` | `crawling_service.py` | 스크래핑, 치수 파싱 (정규식 다수 패턴 지원) |
| `ImageSelectorService` | `image_selector.py` | 이미지 순위 선택 및 추천 |
| `FurnitureAnalysisService` | `furniture_analysis_service.py` | 가구 유형 추론, 장애물/오염물 분석 |
| `SegmentationService` | `segmentation_service.py` | SAM3 마스크 생성, 정제, 측정용 이미지, 누끼 생성 |
| `InpaintingService` | `inpainting_service.py` | 인페인팅 라우팅 (주: Flux-Fill, 레거시: LaMa) |
| `DimensionEstimatorService` | `dimension_estimator.py` | 치수 추정 (listing_text → vision_estimate 순) |

---

## 5. 확인된 output 파일 구조

`backend/output/{job_id}/` 내 파일 구성 (실제 output 폴더에 결과 없음):

| 파일명 | 설명 |
|--------|------|
| `01_original.jpg` | 선택된 원본 이미지 |
| `02_measurement.png` | SAM3 마스크 + 원본 픽셀 합성 (치수 추정 보조용) |
| `03_final_cutout.png` | 소프트 알파 마스크 적용 최종 누끼 (기본 3D 생성 입력) |
| `04_raw_mask.png` | SAM3 원시 마스크 |
| `04_final_mask.png` | 정제된 최종 마스크 |
| `04_final_alpha.png` | 소프트 알파 마스크 |
| `05_obstacle_mask.png` | 장애물 마스크 (조건부 생성) |
| `05_obstacle_removed.png` | Flux 인페인팅 결과 (조건부 생성) |
| `06_generation_cutout.png` | 인페인팅 후 SAM3 재실행 컷아웃 (TRELLIS 우선 입력) |
| `06_generation_mask.png` | 생성용 마스크 |
| `06_generation_raw_mask.png` | 생성용 원시 마스크 |
| `06_generation_alpha_mask.png` | 생성용 알파 마스크 |
| `07_contaminant_mask.png` | 오염물 마스크 (조건부 생성) |
| `07_union_mask.png` | 장애물+오염물 합집합 마스크 (조건부 생성) |
| `08_boundary_completion_mask.png` | 경계 복원 마스크 (조건부 생성) |
| `08_boundary_completed.png` | 경계 복원 인페인팅 결과 (조건부 생성) |
| `result.json` | 전체 파이프라인 결과 JSON |

---

## 6. 확인된 result.json 구조

```json
{
  "job_id": "string (8자리 hex)",
  "pipeline_version": "service_v3_sam3_only",
  "selected_image_index": 0,
  "furniture": {
    "type": "string",
    "type_source": "combined | listing_text | vision",
    "type_confidence": "high | medium | low",
    "warning": "string | null"
  },
  "listing_dimensions": {
    "width_cm": 0.0,
    "depth_cm": 0.0,
    "height_cm": 0.0,
    "source": "listing_text",
    "pattern": "WxDxH | ...",
    "approximate": false,
    "raw_match": "string"
  },
  "masking_strategy": {
    "primary": "sam3_only",
    "part_based": false,
    "family": "string",
    "category_subtype": "string",
    "strategy": "string",
    "risk_level": "normal | high",
    "manual_review_recommended": false
  },
  "obstacle_analysis": { "has_major_obstacle": false, "obstacles": [] },
  "generation_contaminant_analysis": { "has_generation_contaminants": false, "contaminants": [] },
  "dimensions": {
    "width_cm": 0.0,
    "depth_cm": 0.0,
    "height_cm": 0.0,
    "source": "listing_text | vision_estimate",
    "confidence": "high | medium | low",
    "approximate": false,
    "reasoning": "string"
  },
  "cutout_quality": { "quality": "ok | warning | error | unknown", "warnings": [] },
  "generation_cutout_quality": { "quality": "ok | warning | error | unknown", "warnings": [] },
  "final_decision": {
    "can_use_for_dimension": true,
    "can_use_for_3d_generation": true,
    "can_use_for_ar_scale": false,
    "needs_user_confirmation": true,
    "scale_status": "verified_from_listing | listing_approx_needs_user_confirmation | estimated_needs_user_confirmation | low_confidence_blocked",
    "confidence_level": "high | medium | low",
    "inpainting_used": false,
    "masking_family": "string",
    "warnings": []
  },
  "files": {
    "original": "01_original.jpg",
    "measurement": "02_measurement.png",
    "final_cutout": "03_final_cutout.png",
    "raw_mask": "04_raw_mask.png",
    "generation_cutout": "06_generation_cutout.png | null"
  },
  "model_generation": {
    "status": "skipped | not_configured | processing | completed | failed | failed_to_start",
    "trellis_job_id": "string",
    "input_file": "06_generation_cutout.png | 03_final_cutout.png | null",
    "image_url": "string | null",
    "glb_url": "string | null",
    "error": "string | null"
  },
  "debug": { ... }
}
```

---

## 7. 확인된 TRELLIS 연동 방식

- 환경변수: `TRELLIS_BASE_URL` (실제 값 미포함), `BACKEND_PUBLIC_URL`
- 연동 흐름:
  1. `PipelineService.run_pipeline()` 내에서 TRELLIS 입력 파일 결정
     - `06_generation_cutout.png` 우선 (인페인팅 후 SAM3 재실행 결과)
     - 없으면 `03_final_cutout.png` 폴백
  2. `image_url` 자동 계산: `{BACKEND_PUBLIC_URL}/api/furniture/output/{job_id}/{trellis_input_file}`
  3. TRELLIS 서버에 POST 요청: `POST {TRELLIS_BASE_URL}/generate` with `{"job_id": ..., "image_url": ...}`
  4. 상태 polling: `GET {TRELLIS_BASE_URL}/status/{trellis_job_id}`
  5. `completed` 상태에서 `glb_url` (S3 URL) 수신
  6. result.json의 `model_generation.glb_url` 에 저장

---

## 8. Unity 관련 코드 및 확인 사항

| 항목 | 상태 |
|------|------|
| `unity-ar/` 디렉토리 | 존재 확인 (내용 상세 미확인) |
| Unity 자동 연동 코드 | 백엔드 코드에서 확인되지 않음 |
| GLB URL 반환 | 확인 완료 (result.json `model_generation.glb_url`) |
| Unity scale 보정 자동화 | 코드상 자동화 로직 없음 — 시연 시 수동 Unity import 및 스케일 적용 추정 |
| `can_use_for_ar_scale` | result.json에 존재 (판매글 치수가 정확할 때만 true) |

**결론:** Unity 연동은 백엔드가 GLB URL을 반환하면, 이후 Unity에서 GLB를 import하여 스케일을 보정하는 방식으로 시연 단계에서 수동으로 이루어지는 것으로 판단됨 (확인 필요).

---

## 9. 기존 설명과 실제 코드 차이

| 항목 | 기존 설명 | 실제 코드 |
|------|----------|---------|
| 인페인팅 | "nano-banana" 언급 | 코드에서는 **Flux-Fill** (`inpainting_flux.py`)이 실제 인페인팅 엔진. nano-banana는 코드에서 미확인. |
| LaMa | 인페인팅 엔진으로 설명 | `inpainting_service.py`에 `inpaint_with_lama()` 메서드 존재하나, 파이프라인에서 실제 호출되지 않음. `inpaint_with_flux()`가 호출됨. LaMa는 레거시/잔존 코드. |
| Unity 자동 연동 | 자동화 인상 | 백엔드에서 GLB URL만 반환, Unity 자동 import 코드 없음 |
| `pipeline_version` | - | `"service_v3_sam3_only"` 로 확인 |

---

## 10. 추가 확인 필요 사항

| 항목 | 내용 |
|------|------|
| `unity-ar/` 디렉토리 내용 | Unity 프로젝트 존재 여부, GLB import 스크립트 여부 |
| `frontend/` 디렉토리 | 별도 프론트엔드 개발 여부 |
| `ai-pipeline/` 디렉토리 | 별도 파이프라인 존재 여부 |
| nano-banana | 코드에서 미확인 — 향후 도입 예정인지 확인 필요 |
| 실제 output/ 결과 | 현재 output/ 폴더에 결과 없음 — 테스트 결과 없음 |
| `services/generation_service.py` | 파일 존재하나 내용 미확인 (TRELLIS 연동 별도 서비스인지) |
| `lama_inpaint_worker.py` | 상세 내용 미확인 (LaMa 서브프로세스 워커) |
| TRELLIS 서버 실제 운영 여부 | RunPod 기반 TRELLIS 서버가 현재 운영 중인지 확인 필요 |
| S3 권한 설정 | GLB URL 접근 가능 여부 확인 필요 |
