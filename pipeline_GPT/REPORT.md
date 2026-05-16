# 가구 치수 측정 파이프라인 — 기술 보고서 (v5)

## 1. 프로젝트 개요

중고 가구 거래 플랫폼(당근마켓, 중고나라)의 상품 URL을 입력하면, 해당 가구 이미지에서 **누끼(배경 제거) PNG**와 **추정 치수(가로/깊이/높이 cm)**를 자동으로 산출하는 로컬 웹 애플리케이션.

- **실행**: `python pipeline/app.py` → `http://localhost:5001`
- **입력**: 당근마켓 or 중고나라 상품 URL
- **출력**: 원본, SAM 측정용, SAM/BiRefNet/RMBG 누끼, GPT 누끼(참고), 비율 오버레이, 치수 JSON

### v5 주요 변경 — 다중 배경제거 모델 비교 시스템

> **문제**: GroundingDINO+SAM 기반 누끼 품질이 중고 가구 이미지에서 부족. 창문/바닥/수납장이 함께 남고, 얇은 다리 경계가 불안정. SAM은 promptable segmentation 모델이라 alpha matte 생성에는 약함.

> **해결**:
> 1. **BiRefNet** (alpha matte 배경제거 전용 모델) 추가 — 1순위
> 2. **RMBG-1.4** (BriaAI 배경제거 모델) 추가 — 2순위
> 3. SAM faithful cutout 유지 — 3순위 fallback
> 4. GPT cutout은 display preview 전용 (치수 측정에 절대 미사용)
> 5. 모든 모델 결과를 품질 점수로 자동 비교 + 사용자 수동 선택 지원
> 6. 선택된 모델의 마스크로 치수 측정 이미지 재생성

---

## 2. 시스템 구성

```
pipeline/
  app.py                  ← Flask 백엔드 (약 1,920줄)
  static/
    index.html            ← 프론트엔드 UI (약 700줄)
  requirements.txt        ← Python 의존성
  output/
    {job_id}/
      01_original.jpg
      02_measurement.png           ← 치수 측정용 (선택된 모델 마스크 기준)
      02_measurement_{model}.png   ← 모델별 측정용 (사용자 재선택 시)
      03_display_cutout.png        ← SAM faithful cutout
      04_mask.png                  ← SAM 마스크
      05_gpt_cutout.png            ← GPT cutout (display only)
      06_birefnet_cutout.png       ← BiRefNet 누끼 [v5 신규]
      06_birefnet_mask.png         ← BiRefNet 마스크 [v5 신규]
      06_ratio_overlay.png         ← 비율 비교 오버레이
      07_rmbg_cutout.png           ← RMBG 누끼 [v5 신규]
      07_rmbg_mask.png             ← RMBG 마스크 [v5 신규]
      debug/
      result.json
```

### 외부 모듈/모델 의존

| 모듈 | 용도 |
|------|------|
| `nanobanana_ratio_project/segmentation.py` | GroundedSamSegmenter, SAM |
| `zhengpeng7/BiRefNet` (HuggingFace) | Alpha matte 배경제거 [v5 신규] |
| `briaai/RMBG-1.4` (HuggingFace) | Alpha matte 배경제거 [v5 신규] |
| OpenAI API | gpt-4.1-mini (Vision), gpt-image-1 (Image Edit) |

---

## 3. 파이프라인 단계별 상세

### Stage 1: URL 스크래핑 + 이미지 선택 (L56–L233)

| 함수 | 줄 | 역할 |
|------|-----|------|
| `identify_platform(url)` | 69 | 당근/중고나라 분기 |
| `scrape_daangn(url)` | 77 | JSON-LD 스크래핑 |
| `scrape_joongna(url)` | 122 | 중고나라 스크래핑 |
| `select_best_image_gpt(...)` | 172 | GPT Vision 대표 이미지 선택 |
| `download_image(url, path)` | 204 | 이미지 다운로드 |

### Stage 1.5: 가구 타입 분류 (L235–L424) [v3]

| 함수 | 줄 | 역할 |
|------|-----|------|
| `classify_furniture_from_listing(...)` | 256 | 키워드 매칭 |
| `classify_furniture_from_image(...)` | 285 | GPT Vision 분류 |
| `reconcile_furniture_type(...)` | 329 | 통합 판정 |

---

### Stage 2: 다중 모델 배경제거 (L426–L716) [v5 확장]

#### 2A. SAM Faithful Cutout

**`generate_faithful_cutout()`** (L433): 원본 RGB + SAM mask → alpha. AI 생성 없음.

#### 2B. BiRefNet Alpha Matte [v5 신규]

**`generate_birefnet_cutout()`** (L575):

```
원본 이미지 → BiRefNet (1024x1024 추론) → sigmoid → soft alpha matte
→ 원본 해상도로 리사이즈 → 원본 RGB + BiRefNet alpha → RGBA PNG
```

- **모델**: `zhengpeng7/BiRefNet` (AutoModelForImageSegmentation)
- **핵심**: 원본 픽셀 100% 보존, 모델 출력은 alpha 채널로만 사용
- **장점**: 배경제거 전용 학습, 가장자리 품질 우수, 얇은 구조(다리) 보존
- **의존성**: `einops`, `kornia` (BiRefNet 내부 사용)

#### 2C. RMBG-1.4 Alpha Matte [v5 신규]

**`generate_rmbg_cutout()`** (L588):

```
원본 이미지 → RMBG-1.4 (1024x1024 추론) → sigmoid → alpha matte
→ 원본 RGB + RMBG alpha → RGBA PNG
```

- **모델**: `briaai/RMBG-1.4` (BriaRMBG)
- RMBG-2.0은 gated (인증 필요) → 1.4로 fallback

#### 공통 추론 로직 (`_alpha_matte_cutout()`, L505)

```python
transform = Resize(1024) → ToTensor → Normalize(ImageNet mean/std)
result = model(input_tensor)  # BiRefNet: list[-1], RMBG: tuple[0][0]
mask = result.sigmoid()       # soft alpha (0~1)
mask → resize to original → GaussianBlur(3,3) anti-alias
RGBA = original_BGR + alpha
```

#### 2D. GPT Image Edit Cutout (L778, display only)

기존과 동일. RATIO_LOCK_TEXT 프롬프트, n=3 후보, ratio_score 기반 선택.

---

### Stage 2.5: 누끼 품질 비교 평가 [v5 신규]

#### `evaluate_cutout_quality()` (L601)

각 모델 결과에 대해 7개 지표 자동 평가:

| 지표 | 설명 | 좋은 값 |
|------|------|---------|
| `mask_coverage` | 전경 픽셀 비율 | 0.05~0.75 |
| `connected_components_count` | 분리된 영역 수 | 1~3 |
| `cohesion` | 최대 컴포넌트 비율 | >0.7 |
| `edge_smoothness` | 둘레/√면적 비 | <35 |
| `thin_structure_score` | 5x5 erosion 2회 후 잔존율 | >0.5 |
| `background_leakage_warning` | 배경 누수 경고 목록 | 없음 |
| `quality_score` | 종합 품질 (0~100) | >80 |

**종합 점수 (`quality_score`)** 계산:
```python
score = 100
score -= 20 if coverage > 0.75       # 배경 포함 가능
score -= 30 if coverage < 0.02       # 감지 실패
score -= min(fragments * 3, 20)      # 파편화
score -= (1 - cohesion) * 15         # 응집도
score -= (edge_smooth - 35) * 0.5    # 거친 가장자리 (>35 시)
score -= (0.5 - thin_score) * 20     # 얇은 구조 손실 (<0.5 시)
```

#### 모델 자동 선택 로직

```
1. SAM, BiRefNet, RMBG 각각의 quality_score 계산
2. GPT는 display_only → 순위에서 제외
3. quality_score 최고 모델 = auto_selected
4. 사용자 override 가능 (body.selected_cutout_method)
5. 선택된 모델의 마스크로 치수 측정 이미지 재생성
```

---

### Stage 3: 비율 보존 평가 (L1238–L1488) [v4]

`evaluate_ratio_preservation()`, `generate_ratio_overlay()`, `validate_geometry()` — 기존과 동일.

### Stage 4: 치수 측정 (L1517–L1557)

**`measure_dimensions()`**: 선택된 모델의 마스크 기반 측정 이미지 → GPT-4.1-mini Vision.

- SAM이 아닌 모델 선택 시 → 해당 마스크로 `02_measurement_{model}.png` 재생성
- GPT cutout은 절대 사용하지 않음

---

## 4. API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| GET | `/` | 프론트엔드 HTML |
| POST | `/api/scrape` | URL 스크래핑 |
| POST | `/api/process` | 전체 파이프라인 |
| GET | `/api/output/{job_id}/{filename}` | 결과 파일 |

### `/api/process` 요청 (v5)

```json
{
  "url": "https://www.daangn.com/...",
  "selected_image_index": 0,
  "roi_bbox": [100, 80, 420, 610],
  "selected_cutout_method": "birefnet"
}
```

### `/api/process` 응답 (v5)

```json
{
  "job_id": "a1b2c3d4",
  "furniture_type": "chair",
  "dimensions": { "width_cm": 55, "depth_cm": 50, "height_cm": 80 },
  "selected_cutout_method": "birefnet",
  "auto_selected_cutout": "birefnet",
  "cutout_models_eval": {
    "sam": {
      "quality_score": 62.5,
      "mask_coverage": 0.35,
      "connected_components_count": 4,
      "cohesion": 0.72,
      "edge_smoothness": 28.3,
      "thin_structure_score": 0.68,
      "warnings": ["many_fragments"]
    },
    "birefnet": {
      "quality_score": 88.2,
      "mask_coverage": 0.28,
      "connected_components_count": 1,
      "cohesion": 1.0,
      "edge_smoothness": 18.5,
      "thin_structure_score": 0.82,
      "warnings": []
    },
    "rmbg": {
      "quality_score": 79.1,
      "mask_coverage": 0.26,
      "connected_components_count": 1,
      "cohesion": 1.0,
      "edge_smoothness": 22.1,
      "thin_structure_score": 0.71,
      "warnings": []
    },
    "gpt": {
      "quality_score": 75.0,
      "display_only": true,
      "warnings": []
    }
  },
  "gpt_cutout_eval": { "ratio_score": 87.5, "ratio_grade": "pass" },
  "gpt_candidates_eval": [...]
}
```

---

## 5. 출력 파일 구조

| 파일 | 모델 | 용도 |
|------|------|------|
| `01_original.jpg` | - | 원본 |
| `02_measurement.png` | 선택 모델 | 치수 측정 입력 |
| `03_display_cutout.png` | SAM | SAM 누끼 |
| `04_mask.png` | SAM | SAM 마스크 |
| `05_gpt_cutout.png` | GPT | display only |
| **`06_birefnet_cutout.png`** | **BiRefNet** | **alpha matte 누끼 [v5]** |
| **`06_birefnet_mask.png`** | **BiRefNet** | **alpha matte 마스크 [v5]** |
| `06_ratio_overlay.png` | - | GPT 비율 비교 |
| **`07_rmbg_cutout.png`** | **RMBG** | **alpha matte 누끼 [v5]** |
| **`07_rmbg_mask.png`** | **RMBG** | **alpha matte 마스크 [v5]** |
| `result.json` | - | 전체 메타데이터 |

---

## 6. 프론트엔드 UI (v5)

### 누끼 모델 비교 섹션 [v5 신규]

4개 모델 카드를 그리드로 나란히 표시:

| 카드 | 내용 |
|------|------|
| **SAM Faithful** | SAM 누끼 + 품질점수 + 지표 + 선택 버튼 |
| **BiRefNet** | BiRefNet 누끼 + 품질점수 + 지표 + 선택 버튼 |
| **RMBG-1.4** | RMBG 누끼 + 품질점수 + 지표 + 선택 버튼 |
| **GPT Edit** | GPT 누끼 + 품질점수 (display only 표시, 선택 불가) |

각 카드에 표시되는 지표:
- 품질점수 (0~100, 색상 코딩)
- 마스크 커버리지 (%)
- Connected Components 수
- 얇은구조 보존율 (%)
- 엣지 평활도
- 경고 건수

**자동 추천**: quality_score 최고 모델에 "(자동추천)" 태그
**사용자 선택**: "이 모델 선택" 버튼 → 선택된 모델 마스크로 치수 재측정
**선택 상태**: 파란 테두리 + "(선택됨)" 표시

---

## 7. 핵심 설계 결정

### 7.1 배경제거 모델 비교 전략 (v5)

| | SAM | BiRefNet | RMBG-1.4 | GPT Edit |
|---|---|---|---|---|
| 유형 | Promptable segmentation | Alpha matte 전용 | Alpha matte 전용 | 생성형 편집 |
| 원본 픽셀 보존 | 100% | 100% | 100% | 보장 불가 |
| Alpha 품질 | 이진 마스크 (hard edge) | Soft matte (smooth edge) | Soft matte | N/A |
| 얇은 구조 | 약함 (프롬프트 의존) | 강함 | 중간 | N/A |
| 배경 분리 | DINO prompt 의존 | 자동 (학습 기반) | 자동 | 자동 |
| 치수 측정 사용 | 가능 | **권장** | 가능 | **금지** |
| 우선순위 | 3순위 (fallback) | **1순위** | 2순위 | display only |

### 7.2 치수 측정 마스크 우선순위

```
1. 사용자 선택 모델의 마스크 (body.selected_cutout_method)
2. 자동 추천 모델 (quality_score 최고)
3. SAM 마스크 (fallback)
4. GPT cutout → 절대 사용 금지
```

### 7.3 모델 싱글턴 패턴

BiRefNet과 RMBG는 처음 호출 시 모델을 로드하고 이후 재사용:
- `_get_birefnet()`: `_birefnet_model` 전역 캐시
- `_get_rmbg()`: `_rmbg_model` 전역 캐시
- 첫 번째 요청은 모델 로딩으로 느릴 수 있음 (BiRefNet ~2-5초)

---

## 8. 환경 변수

| 변수 | 필수 | 설명 |
|------|------|------|
| `OPENAI_API_KEY` | 필수 | OpenAI API 인증 |
| `GPT_IMAGE_MODELS` | 선택 | GPT cutout 모델 체인 |
| `SAM_CHECKPOINT` | 자동 | SAM 모델 경로 |

---

## 9. 의존성 (v5 추가)

```
flask, flask-cors            ← 웹 서버
requests, beautifulsoup4     ← URL 스크래핑
openai (>=2.36.0)            ← GPT Vision + Image Edit API
python-dotenv                ← 환경변수
opencv-python, numpy         ← 이미지 처리
Pillow                       ← 이미지 로딩
torch, torchvision           ← 모델 추론
transformers                 ← BiRefNet, RMBG-1.4, GroundingDINO
timm                         ← BiRefNet backbone
einops                       ← BiRefNet 내부 연산 [v5 신규]
kornia                       ← BiRefNet 내부 연산 [v5 신규]
segment-anything             ← SAM (nanobanana 경유)
```

---

## 10. 실행 흐름 다이어그램 (v5)

```
사용자: 당근마켓 URL 입력
  │
  ▼
[1] scrape → [2] select_image → [2.5] classify_furniture
  │
  ▼
[3] generate_measurement_image(furniture_type) → 02_measurement.png + 04_mask.png
  │
  ▼ (병렬 실행 가능)
┌─────────────────────────────────────────────────────────┐
│ [4a]   SAM faithful cutout     → 03_display_cutout.png  │
│ [4a-2] BiRefNet alpha matte   → 06_birefnet_cutout.png  │  [v5]
│ [4a-3] RMBG alpha matte       → 07_rmbg_cutout.png      │  [v5]
│ [4b]   GPT Image Edit (opt)   → 05_gpt_cutout.png       │
└─────────────────────────────────────────────────────────┘
  │
  ▼
[4e] evaluate_cutout_quality() × 4 models → cutout_models_eval  [v5]
  │   → quality_score 최고 모델 자동 선택 (or 사용자 override)
  │
  ▼
[4b-2] evaluate_ratio_preservation() → gpt_cutout_eval
[4b-3] generate_ratio_overlay() → 06_ratio_overlay.png
[4c]   validate_geometry() + ratio_grade 연동
  │
  ▼
[5] measure_dimensions(selected_model_mask)
  │   → 선택된 모델 마스크로 측정 이미지 재생성 (if not SAM)
  │   → GPT-4.1-mini Vision → 치수 JSON
  ▼
결과: result.json (cutout_models_eval, selected_cutout_method 포함)
     + 프론트엔드: 모델 비교 카드 + 품질 점수 + 선택 버튼
```

---

## 11. 함수 목록 (app.py)

| 함수 | 줄 | 역할 |
|------|-----|------|
| `get_openai_client()` | 48 | OpenAI 클라이언트 |
| `identify_platform(url)` | 69 | URL 플랫폼 식별 |
| `scrape_daangn(url)` | 77 | 당근마켓 스크래핑 |
| `scrape_joongna(url)` | 122 | 중고나라 스크래핑 |
| `select_best_image_gpt(...)` | 172 | GPT Vision 이미지 선택 |
| `download_image(url, path)` | 204 | 이미지 다운로드 |
| `get_segmenter(device)` | 220 | SAM+GroundingDINO 로드 |
| `classify_furniture_from_listing(...)` | 256 | 키워드 분류 [v3] |
| `classify_furniture_from_image(...)` | 285 | GPT Vision 분류 [v3] |
| `reconcile_furniture_type(...)` | 329 | 분류 통합 [v3] |
| `_get_part_prompts(ft)` | 389 | 타입별 SAM 프롬프트 [v3] |
| `_build_edit_prompt(ft)` | 406 | GPT 프롬프트 + RATIO_LOCK [v4] |
| `generate_faithful_cutout(...)` | 433 | SAM → RGBA |
| **`_get_birefnet()`** | **471** | **BiRefNet 모델 로드 [v5]** |
| **`_get_rmbg()`** | **488** | **RMBG-1.4 모델 로드 [v5]** |
| **`_alpha_matte_cutout(...)`** | **505** | **공통 alpha matte 추론 [v5]** |
| **`generate_birefnet_cutout(...)`** | **575** | **BiRefNet 배경제거 [v5]** |
| **`generate_rmbg_cutout(...)`** | **588** | **RMBG 배경제거 [v5]** |
| **`evaluate_cutout_quality(...)`** | **601** | **7지표 품질 평가 [v5]** |
| `_select_edit_size(image_path)` | 718 | GPT edit 사이즈 |
| `_create_edit_mask_from_sam(...)` | 731 | SAM→edit mask |
| `_call_images_edit(client, **kw)` | 758 | SDK 호환 호출 |
| `generate_gpt_cutout(...)` | 778 | GPT Image Edit |
| `_pick_best_candidate(...)` | 920 | ratio_score 후보 선택 [v4] |
| `_multi_prompt_segment(...)` | 974 | 타입별 GroundingDINO+SAM |
| `_merge_and_filter_masks(...)` | 1055 | CC 필터링 |
| `generate_measurement_image(...)` | 1182 | 측정 이미지 생성 |
| `evaluate_ratio_preservation(...)` | 1269 | 5지표 비율 평가 [v4] |
| `generate_ratio_overlay(...)` | 1368 | bbox 오버레이 [v4] |
| `validate_geometry(...)` | 1430 | 형상 검증 |
| `measure_dimensions(...)` | 1517 | GPT Vision 치수 |
| `api_process()` | 1585 | 전체 파이프라인 (**모델 비교 포함**) [v5] |
| `serve_output(...)` | 1901 | 파일 서빙 |

---

## 12. 알려진 한계 및 향후 과제

| 한계 | 원인 | 현재 완화 | 향후 |
|------|------|----------|------|
| 첫 요청 시 모델 로딩 느림 | BiRefNet/RMBG lazy load | 싱글턴 캐시 | 서버 시작 시 사전 로드 옵션 |
| RMBG-2.0 접근 불가 | gated repo | RMBG-1.4 사용 | HuggingFace 인증 후 전환 |
| BiRefNet 메모리 사용 | 대형 모델 | CPU 추론 | GPU 가용 시 자동 전환 |
| GPT cutout 재생성 위험 | 생성 모델 본질 | RATIO_LOCK + 비율 검증 + display only | - |
| SAM 배경 누수 | promptable segmentation 한계 | BiRefNet/RMBG fallback | SAM 2 |
| 사용자 ROI 미구현 | 프론트 미개발 | SAM bbox fallback | ROI 드래그 UI |

---

## 13. 버전 이력

| 버전 | 변경 |
|------|------|
| v1 | 기본 파이프라인: 단일 프롬프트 SAM + GPT cutout |
| v2 | Dual-output, multi-prompt SAM, AR 기반, n=3 후보, geometry 검증 |
| v3 | Category-aware: 가구 분류, 타입별 프롬프트 |
| v4 | 비율 보존 평가: ratio_score, 5지표, 오버레이, 후보 선택 개선 |
| **v5** | **다중 배경제거 모델: BiRefNet + RMBG-1.4 추가, 7지표 품질 평가, quality_score 자동 선택, 모델 비교 UI, 선택 모델 기반 치수 재측정** |

---

## 14. 2026-05-14 수정 보고 — FastAPI 전환

### 14.1 수정 목적

기존 `app.py`는 Flask 앱으로 작성되어 있었고, 실행 포트도 `5001`로 고정되어 있었다. 사용 요청에 따라 서버 레이어를 FastAPI 기반으로 전환하고, 기존 포트와 충돌하지 않도록 `5003`에서 실행하도록 변경했다.

### 14.2 변경 파일

| 파일 | 변경 내용 |
|------|-----------|
| `fastapi_app.py` | FastAPI 엔트리포인트 신규 추가 |
| `requirements.txt` | `fastapi`, `uvicorn` 의존성 추가 |

### 14.3 현재 서버 구조

현재 구조는 완전한 로직 이관이 아니라, **FastAPI HTTP 레이어 + 기존 `app.py` 파이프라인 함수 재사용** 방식이다.

```
Browser
  │
  ▼
FastAPI app (`fastapi_app.py`)
  │
  ├─ GET  /                         → static/index.html
  ├─ GET  /api/health               → FastAPI 상태 확인
  ├─ POST /api/scrape               → 기존 `app.py`의 `api_scrape()` 재사용
  ├─ POST /api/process              → 기존 `app.py`의 `api_process()` 재사용
  └─ GET  /api/output/{job}/{file}  → output 파일 서빙
```

기존 프론트엔드 `static/index.html`은 `/api/scrape`, `/api/process`, `/api/output/...` 경로를 그대로 사용하므로 수정 없이 FastAPI 서버에서 동작한다.

### 14.4 FastAPI 엔드포인트

| Method | Path | 역할 |
|--------|------|------|
| `GET` | `/` | 프론트엔드 HTML 반환 |
| `GET` | `/api/health` | 서버 상태 확인 |
| `POST` | `/api/scrape` | 당근/중고나라 URL 메타데이터 및 이미지 목록 스크래핑 |
| `POST` | `/api/process` | 전체 파이프라인 실행 |
| `GET` | `/api/output/{job_id}/{filename}` | 결과 이미지/파일 반환 |

### 14.5 실행 방법

```bash
cd /Users/dahoo/OSS-Project/pipeline_GPT
../.venv/bin/python -m uvicorn fastapi_app:app --host 127.0.0.1 --port 5003
```

접속 주소:

```text
http://127.0.0.1:5003/
```

상태 확인:

```text
http://127.0.0.1:5003/api/health
```

### 14.6 검증 결과

다음 항목을 확인했다.

| 검증 | 결과 |
|------|------|
| `fastapi_app.py`, `app.py` 문법 컴파일 | 성공 |
| FastAPI 앱 import | 성공 |
| `GET /` | `200 OK` |
| `GET /api/health` | `{"status":"ok","framework":"fastapi"}` |
| 빈 URL로 `POST /api/scrape` | 기존과 동일하게 `400 URL을 입력해주세요.` 반환 |

### 14.7 현재 코드 상태

- `app.py`는 아직 Flask 객체와 route를 포함한다.
- `fastapi_app.py`는 기존 Flask route 함수를 `test_request_context()`로 감싸 재사용한다.
- 따라서 파이프라인 핵심 로직은 한 벌만 유지된다.
- 향후 안정화 단계에서는 `api_process()` 내부 로직을 route 함수에서 분리해 `run_pipeline(payload)` 같은 순수 함수로 옮기고, Flask 의존을 제거하는 것이 좋다.

### 14.8 남은 리스크 및 다음 개선안

| 항목 | 설명 | 권장 조치 |
|------|------|-----------|
| Flask 의존 잔존 | `fastapi_app.py`가 기존 Flask route 함수를 호출함 | `app.py`의 route와 pipeline core 분리 |
| 동기 처리 | `/api/process`가 긴 작업을 HTTP 요청 하나에서 동기 실행 | Background task/job status API 분리 |
| 모델 로딩 시간 | GroundingDINO/SAM/BiRefNet/RMBG lazy load로 첫 요청이 느림 | startup preload 옵션 추가 |
| 에러 타입 | 기존 Flask 응답을 JSONResponse로 변환 | FastAPI 예외 모델로 정리 |

### 14.9 변경 원칙

앞으로 기능 수정이 끝날 때마다 이 `REPORT.md`에 다음 내용을 갱신한다.

- 수정 목적
- 변경 파일
- 현재 코드 구조
- 실행 방법
- 검증 결과
- 남은 리스크

---

## 15. 2026-05-14 수정 보고 — FastAPI 직접 호출 구조로 리팩터링

### 15.1 수정 목적

14번 수정에서는 FastAPI 서버를 추가했지만, 내부적으로 기존 Flask route 함수를 `test_request_context()`로 감싸 호출하고 있었다. 이는 FastAPI 서버를 사용하더라도 Flask request context 의존이 남는 구조였다.

이번 수정의 목적은 다음과 같다.

- `/api/scrape`, `/api/process`의 핵심 로직을 framework-neutral 함수로 분리
- FastAPI가 Flask route를 우회하지 않고 core 함수를 직접 호출
- 기존 Flask 실행 호환성은 유지
- 프론트엔드 API 경로는 그대로 유지

### 15.2 변경 파일

| 파일 | 변경 내용 |
|------|-----------|
| `app.py` | `scrape_listing(body)`, `run_pipeline(body)` 순수 함수 추가 및 Flask route wrapper로 변경 |
| `fastapi_app.py` | Flask `test_request_context()` 제거, core 함수 직접 호출 |
| `REPORT.md` | 현재 수정 보고 추가 |

### 15.3 현재 코드 구조

```
static/index.html
  │
  ▼
FastAPI (`fastapi_app.py`)
  │
  ├─ POST /api/scrape
  │    └─ app.scrape_listing(body)
  │
  └─ POST /api/process
       └─ app.run_pipeline(body)

Flask legacy route (`app.py`)
  │
  ├─ /api/scrape  → scrape_listing(body) 결과를 jsonify
  └─ /api/process → run_pipeline(body) 결과를 jsonify
```

핵심 파이프라인은 `run_pipeline(body)`에 있고, Flask와 FastAPI는 모두 이 함수를 호출하는 얇은 HTTP wrapper 역할만 한다.

### 15.4 변경 상세

#### `app.py`

새 함수:

```python
def scrape_listing(body: dict) -> tuple[dict, int]:
    ...

def run_pipeline(body: dict) -> tuple[dict, int]:
    ...
```

기존 Flask route:

```python
@app.route("/api/process", methods=["POST"])
def api_process():
    body = request.get_json(force=True)
    data, status_code = run_pipeline(body)
    return jsonify(data), status_code
```

#### `fastapi_app.py`

이전:

```python
with legacy_pipeline.app.test_request_context(...):
    return _flask_response_to_fastapi(legacy_pipeline.api_process())
```

현재:

```python
data, status_code = legacy_pipeline.run_pipeline(body.model_dump(exclude_none=True))
return JSONResponse(content=data, status_code=status_code)
```

### 15.5 실행 방법

```bash
cd /Users/dahoo/OSS-Project/pipeline_GPT
../.venv/bin/python -m uvicorn fastapi_app:app --host 127.0.0.1 --port 5003
```

현재 접속 주소:

```text
http://127.0.0.1:5003/
```

### 15.6 검증 결과

| 검증 | 결과 |
|------|------|
| `app.py`, `fastapi_app.py` 문법 컴파일 | 성공 |
| FastAPI 앱 import | 성공 |
| 기존 FastAPI 서버 재시작 | 성공 |
| `GET /` | `200 OK` |
| `GET /api/health` | `{"status":"ok","framework":"fastapi"}` |
| 빈 URL로 `POST /api/scrape` | `400 URL을 입력해주세요.` 정상 반환 |

### 15.7 현재 남은 리스크

| 항목 | 현재 상태 | 다음 개선 |
|------|-----------|-----------|
| Flask import 의존 | `app.py` 상단에 Flask 객체와 route는 아직 존재 | 완전 FastAPI 전환 시 별도 `pipeline_core.py`로 로직 이동 |
| 긴 동기 요청 | `/api/process`는 여전히 요청 중 전체 파이프라인을 동기 실행 | job queue/status polling API 추가 |
| 대형 단일 파일 | `app.py`가 여전히 매우 큼 | scraper, segmentation, cutout, evaluation, dimension 모듈로 분리 |
| Flask 호환 유지 | 현재는 의도적으로 유지 | 안정화 후 Flask route 제거 가능 |

### 15.8 현재 판단

이번 수정으로 FastAPI 서버는 더 이상 Flask request context에 의존하지 않는다. 다만 `app.py` 파일 자체는 Flask legacy route와 pipeline core를 함께 갖고 있으므로, 다음 큰 정리는 `pipeline_core.py` 분리 작업이 적절하다.

---

## 16. 2026-05-14 수정 보고 — GPT Vision 장애물 판단 로직 추가

### 16.1 수정 목적

기존 파이프라인은 SAM/BiRefNet/RMBG/GPT cutout을 생성하고 품질 점수로 비교했지만, “이미지 속 장애물을 제거해야 하는지”에 대한 의미론적 판단은 명확히 분리되어 있지 않았다.

이번 수정의 목적은 다음과 같다.

- 장애물 판단은 **GPT Vision 전담**으로 분리
- BiRefNet은 장애물 판단에 사용하지 않고, **누끼와 bbox 검증 전용**으로 제한
- GPT Image Edit는 항상 실행하지 않고, `surface_obstacle`일 때만 실행
- `structural_occlusion`은 복원 가능성은 있어도 치수/스케일 신뢰도를 낮게 표시
- `result.json`과 UI에 장애물 판단 결과를 명시

### 16.2 변경 파일

| 파일 | 변경 내용 |
|------|-----------|
| `app.py` | GPT Vision 장애물 판단 함수, surface obstacle 전용 inpainting 함수, 파이프라인 분기 추가 |
| `static/index.html` | 장애물 판단 결과 표시, 단계 표시, preview panel 문구 수정 |
| `REPORT.md` | 현재 수정 보고 추가 |

### 16.3 신규 장애물 판단 함수

#### `analyze_obstacles_with_gpt(...)`

위치: `app.py`

역할:

- 원본 이미지와 가능하면 BiRefNet cutout 이미지를 GPT Vision에 함께 전달
- BiRefNet cutout은 시각 보조 자료일 뿐, 판단 주체가 아님을 프롬프트에 명시
- GPT Vision이 아래 JSON 형태로만 응답하도록 요구

```json
{
  "main_furniture": "desk | chair | sofa | cabinet | table | bed | unknown",
  "obstacle_status": "none | background_only | surface_obstacle | structural_occlusion",
  "needs_inpainting": true,
  "occlusion_affects_outline": true,
  "confidence": "high | medium | low",
  "obstacles": [
    {
      "name": "book",
      "location": "on tabletop",
      "removal_needed": true,
      "affects_measurement": false
    }
  ],
  "reason": "..."
}
```

#### `_normalize_obstacle_analysis(...)`

역할:

- GPT 응답이 허용값 밖으로 나가면 안전한 값으로 정규화
- `needs_inpainting`은 `surface_obstacle`일 때만 `true`로 강제
- `structural_occlusion`이면 `confidence`를 `low`로 강제

### 16.4 신규 GPT Image Edit 함수

#### `generate_obstacle_removed_image(...)`

역할:

- `obstacle_status == "surface_obstacle"`일 때만 GPT Image Edit 실행
- 표면 위 책, 컵, 잡동사니 등 removable object만 제거
- 가구의 실루엣, 폭/높이, 다리/프레임 위치, 원근, 재질, 외곽선 보존을 프롬프트에 명시
- 결과 파일:

```text
output/{job_id}/05_obstacle_removed.png
```

이 함수는 기존 GPT cutout처럼 배경 제거/누끼를 만들지 않는다. 목적은 **장애물 제거된 일반 이미지 생성**이다.

### 16.5 처리 분기

현재 `obstacle_status`별 분기는 다음과 같다.

| obstacle_status | 처리 |
|-----------------|------|
| `none` | GPT inpainting 미사용. 원본 + BiRefNet 누끼 사용 |
| `background_only` | GPT inpainting 미사용. BiRefNet 누끼 사용 |
| `surface_obstacle` | GPT로 표면 장애물만 제거 → 제거 이미지에 BiRefNet 재적용 → bbox/비율 검증. 치수 측정은 원본 기준 유지 |
| `structural_occlusion` | GPT inpainting 미사용. `structural_occlusion_low_confidence` warning 추가. 치수/3D/AR 신뢰도 낮게 처리 |

### 16.6 추가 output 파일

`surface_obstacle`일 때만 다음 파일이 생성될 수 있다.

```text
05_obstacle_removed.png
05_obstacle_removed_birefnet_cutout.png
05_obstacle_removed_birefnet_mask.png
```

`05_obstacle_removed.png`는 GPT가 장애물을 제거한 이미지다.  
`05_obstacle_removed_birefnet_*`는 그 결과에 BiRefNet을 다시 적용한 누끼/마스크다.

### 16.7 result.json 변경

새로 추가되는 주요 필드:

```json
{
  "obstacle_analysis": {...},
  "obstacle_status": "surface_obstacle",
  "inpainting_used": true,
  "warnings": [...]
}
```

`final_decision`에도 다음 필드가 추가된다.

```json
{
  "obstacle_status": "surface_obstacle",
  "inpainting_used": true
}
```

`structural_occlusion`이면 다음 warning이 추가된다.

```text
structural_occlusion_low_confidence
```

### 16.8 UI 변경

프론트엔드에 장애물 판단 결과를 간단히 표시한다.

| 상태 | 표시 문구 |
|------|-----------|
| `none` | 장애물 없음 |
| `background_only` | 배경만 복잡함 |
| `surface_obstacle` | 표면 장애물 제거 필요 |
| `structural_occlusion` | 구조 가림으로 신뢰도 낮음 |

추가 변경:

- 진행 단계에 `GPT Vision 장애물 판단` 추가
- 기존 `GPT 누끼` 문구를 `표면 장애물 제거` 중심으로 변경
- 미리보기 패널은 inpainting이 있으면 `05_obstacle_removed.png`, 없으면 BiRefNet cutout을 표시
- 디버그 모델 비교에 `GPT 제거 + BiRefNet` 항목 추가 가능
- GPT 기반 preview 모델은 프론트와 백엔드 양쪽에서 치수 측정 소스로 선택할 수 없도록 차단

### 16.9 검증 결과

| 검증 | 결과 |
|------|------|
| `app.py`, `fastapi_app.py` 문법 컴파일 | 성공 |
| FastAPI 앱 import | 성공 |
| 신규 함수 존재 확인 | `analyze_obstacles_with_gpt`, `generate_obstacle_removed_image` 확인 |
| 서버 재시작 | 성공, 최종 PID 51312 |
| `GET /` | `200 OK` |
| `GET /api/health` | `{"status":"ok","framework":"fastapi"}` |
| 빈 URL로 `POST /api/scrape` | `400 URL을 입력해주세요.` 정상 반환 |

### 16.10 현재 남은 리스크

| 항목 | 설명 | 다음 개선 |
|------|------|-----------|
| GPT Vision 판단 오차 | 장애물/가구 구조 판단은 생성 모델의 시각 추론에 의존 | 실제 샘플 로그를 모아 status별 정확도 확인 |
| surface_obstacle edit 실패 가능 | OpenAI image edit 모델/파라미터 지원 여부에 따라 실패 가능 | 실패 시 result warning과 UI 표시 유지 |
| structural_occlusion 처리 | 현재는 low confidence로 막는 보수적 정책 | 필요 시 별도 “복원 미리보기만 생성” 옵션 추가 |
| BiRefNet 재누끼 품질 | 장애물 제거 후 BiRefNet 마스크가 흔들릴 수 있음 | inpainted mask와 original mask dense contour 비교 추가 |

### 16.11 현재 판단

이번 수정으로 “판단 주체”와 “누끼 도구”가 분리되었다.

- 장애물 판단: GPT Vision
- 누끼/마스크/bbox 검증: BiRefNet 중심, SAM/RMBG fallback
- 실제 이미지 편집: `surface_obstacle`일 때만 GPT Image Edit
- 치수 측정: GPT로 복원한 이미지가 아니라 원본 기준 마스크 유지

---

## 17. 2026-05-14 수정 보고 — FastAPI 환경변수 로딩 누락 수정

### 17.1 문제

FastAPI 서버에서 OpenAI 호출 시 다음 오류가 발생했다.

```text
Missing credentials. Please pass an api_key, workload_identity, admin_api_key, or set the OPENAI_API_KEY or OPENAI_ADMIN_KEY environment variable.
```

원인은 Flask 실행 경로에서는 `if __name__ == "__main__"` 블록에서 `.env`를 읽었지만, FastAPI/uvicorn 실행에서는 해당 블록이 실행되지 않는다는 점이었다.

### 17.2 변경 파일

| 파일 | 변경 내용 |
|------|-----------|
| `app.py` | `load_runtime_environment()` 공통 함수 추가 |
| `fastapi_app.py` | import 직후 `legacy_pipeline.load_runtime_environment()` 호출 |
| `REPORT.md` | 현재 수정 보고 추가 |

### 17.3 현재 환경 로딩 순서

```python
load_dotenv(PROJECT_ROOT / "nanobanana_ratio_project" / ".env")
load_dotenv(PROJECT_ROOT / "furniture_dimension_eval" / ".env")
load_dotenv(PIPELINE_DIR / ".env")
load_dotenv()
```

따라서 기존 실험 프로젝트나 치수 측정 프로젝트의 `.env`에 있는 `OPENAI_API_KEY`를 FastAPI 서버에서도 사용할 수 있다.

### 17.4 검증 결과

| 검증 | 결과 |
|------|------|
| `app.py`, `fastapi_app.py` 문법 컴파일 | 성공 |
| FastAPI import 후 OpenAI key 존재 여부 확인 | `True` |
| FastAPI 서버 재시작 | 성공, PID 53207 |
| `GET /` | `200 OK` |
| `GET /api/health` | `{"status":"ok","framework":"fastapi"}` |

### 17.5 현재 판단

이번 수정으로 uvicorn 실행에서도 OpenAI SDK가 필요한 환경변수를 읽을 수 있다. 앞으로 서버 실행 방식이 Flask든 FastAPI든 동일한 `load_runtime_environment()`를 사용한다.

---

## 18. 2026-05-14 수정 보고 — DINO+SAM / DINO+BiRefNet 비교 및 DINO 박스 기반 누끼

### 18.1 목표

소파 위 인형처럼 작은 전경 물체가 있을 때 BiRefNet 단독 누끼가 해당 물체를 주 피사체로 잡아 가구를 놓치는 문제가 있었다. 이번 수정은 판매글/이미지에서 파악한 가구 타입을 기준으로 GroundingDINO가 먼저 목표 가구 영역을 잡고, 그 박스 안에서 SAM 또는 BiRefNet 누끼를 비교할 수 있게 만드는 것이다.

### 18.2 변경 파일

| 파일 | 변경 내용 |
|------|-----------|
| `app.py` | 판매글 기반 가구 타입 우선 정책 강화, DINO bbox 메타데이터 저장, DINO 박스 내부 BiRefNet 누끼 추가, 모델 비교/자동 선택 로직 변경 |
| `static/index.html` | DINO+SAM / DINO+BiRefNet 비교 표시, 선택 모델별 측정/미리보기 이미지 매핑 추가 |
| `REPORT.md` | 현재 수정 보고 추가 |

### 18.3 핵심 로직

1. 판매글 텍스트 분류가 `high` confidence면 이미지 분류가 다른 물체에 흔들려도 판매글의 가구 타입을 DINO 프롬프트 기준으로 사용한다.
2. `generate_measurement_image()`가 GroundingDINO 검출 박스들을 union해서 `dino_bbox`를 저장한다.
3. `generate_dino_birefnet_cutout()`이 원본 전체가 아니라 `dino_bbox`를 padding한 crop 안에서 BiRefNet을 실행한다.
4. boxed BiRefNet 결과가 SAM 기준 가구 마스크보다 지나치게 작으면 `dino_birefnet_undercovered_target_used_sam_guard` 경고와 함께 SAM support mask를 합쳐 가구가 통째로 사라지는 것을 막는다.
5. 비교 후보는 `dino_sam`, `dino_birefnet`, `birefnet`, `rmbg`로 저장된다.
6. 자동 선택 기본값은 `dino_birefnet`이며, 실패하면 `dino_sam`으로 fallback한다.

### 18.4 산출물

| 파일 | 의미 |
|------|------|
| `03_display_cutout.png` | DINO+SAM 기반 원본 픽셀 누끼 |
| `06_dino_birefnet_cutout.png` | DINO 박스 내부 BiRefNet 누끼 |
| `06_dino_birefnet_mask.png` | DINO+BiRefNet 마스크 |
| `06_birefnet_cutout.png` | BiRefNet 단독 누끼, 비교용 |
| `result.json` | `segmentation_info`, `dino_birefnet_info`, `cutout_models_eval` 포함 |

### 18.5 검증 결과

| 검증 | 결과 |
|------|------|
| `app.py`, `fastapi_app.py` 문법 컴파일 | 성공 |
| FastAPI 앱 import | 성공 |
| FastAPI 서버 실행 | 성공, PID 57407 |
| `GET /api/health` | `{"status":"ok","framework":"fastapi"}` |

### 18.6 현재 판단

이제 BiRefNet은 “전체 이미지에서 주 피사체 찾기”가 아니라 “DINO가 잡은 목표 가구 박스 안에서 alpha matte를 다듬는 도구”로 동작한다. 따라서 소파 위 인형, 책상 위 물건처럼 작은 물체가 있어도 판매 대상 가구를 기준으로 DINO+SAM과 DINO+BiRefNet 결과를 나란히 비교할 수 있다.

---

## 19. 2026-05-14 수정 보고 — OpenAI 429 쿼터 초과 fallback 처리

### 19.1 문제

OpenAI API 호출 중 다음 오류가 발생하면 기존 서버는 치수 측정 단계에서 전체 파이프라인을 `500`으로 종료했다.

```text
Error code: 429 - insufficient_quota
```

### 19.2 변경 파일

| 파일 | 변경 내용 |
|------|-----------|
| `app.py` | OpenAI quota/credential/rate-limit 오류 감지, 이후 GPT 호출 생략, 치수 로컬 fallback 추가 |
| `static/index.html` | fallback warning 문구 추가 |
| `REPORT.md` | 현재 수정 보고 추가 |

### 19.3 변경 내용

1. `_openai_error_reason()`, `_mark_openai_unavailable()`, `_openai_skip_reason()`을 추가했다.
2. 이미지 대표 선택, 이미지 기반 가구 분류, 장애물 판단, 장애물 제거 이미지 생성은 OpenAI가 unavailable이면 바로 skip 또는 기본값을 반환한다.
3. `measure_dimensions()`는 OpenAI 429가 발생해도 실패하지 않고 `local_category_fallback`을 반환한다.
4. 로컬 fallback 치수는 가구 타입별 일반값이며 항상 `confidence: low`로 표시한다.
5. 최종 경고에 `openai_insufficient_quota`, `dimension_local_fallback_used`를 추가해 UI에서 사용자가 원인을 볼 수 있게 했다.

### 19.4 fallback 치수 정책

| 가구 타입 | 기본값 |
|-----------|--------|
| chair | 50 × 55 × 85 cm |
| desk | 120 × 60 × 75 cm |
| table | 120 × 75 × 74 cm |
| sofa | 180 × 85 × 80 cm |
| cabinet | 80 × 45 × 120 cm |
| shelf | 80 × 30 × 160 cm |
| bed | 200 × 100 × 50 cm |
| dresser | 90 × 45 × 140 cm |

이 값은 실제 치수 검증용이 아니라 파이프라인을 계속 진행하기 위한 낮은 신뢰도 placeholder다.

### 19.5 검증 결과

| 검증 | 결과 |
|------|------|
| `app.py`, `fastapi_app.py` 문법 컴파일 | 성공 |
| 로컬 fallback 함수 직접 호출 | 성공 |
| FastAPI 서버 재시작 | 성공, PID 58093 |
| `GET /api/health` | `{"status":"ok","framework":"fastapi"}` |

### 19.6 현재 판단

OpenAI 계정 쿼터가 없으면 GPT Vision 기반 판단과 치수 추정은 정확히 수행할 수 없다. 하지만 DINO+SAM, DINO+BiRefNet 누끼 비교와 마스크/bbox 기반 전처리 검증은 계속 실행되며, 치수는 낮은 신뢰도의 카테고리 기본값으로만 표시된다.

---

## 20. 2026-05-14 수정 보고 — 서비스용 단일 플로우 `clean_pipeline.py` 추가

### 20.1 목표

실험용 v5 구조는 SAM, BiRefNet, RMBG, GPT 후보를 비교하는 코드가 많이 섞여 있었다. 이번 수정은 기존 `app.py`를 보존하면서, 서비스에 쓸 단일 최적 플로우를 `clean_pipeline.py`로 분리하는 것이다.

핵심 정책은 다음 한 줄이다.

```text
DINO로 가구를 찾고, BiRefNet으로 누끼를 따고, GPT는 장애물 제거가 필요할 때만 쓰고, 치수는 원본 기준으로만 잰다.
```

### 20.2 변경 파일

| 파일 | 변경 내용 |
|------|-----------|
| `clean_pipeline.py` | FastAPI 기반 서비스용 단일 파이프라인 신규 추가 |
| `REPORT.md` | 현재 수정 보고 추가 |

기존 `app.py`, `fastapi_app.py`, 실험용 UI는 삭제하거나 대규모 수정하지 않고 그대로 보존했다.

### 20.3 단일 플로우

1. URL 또는 local image path 입력
2. URL이면 기존 당근/중고나라 scraper 재사용
3. 대표 이미지 선택
4. 판매글 기반 가구 타입 판단 우선
5. DINO+SAM 기존 로직으로 목표 가구 bbox 확보
6. DINO bbox 내부에서 BiRefNet 누끼
7. undercoverage 또는 실패 시 DINO+SAM fallback
8. GPT Vision 장애물 판단
9. `surface_obstacle`일 때만 GPT image edit 실행
10. GPT 제거 결과는 3D 생성 후보로만 사용
11. 치수 측정 이미지는 항상 원본 기반 `04_final_mask.png`로 생성
12. 치수는 listing text dimensions, user input dimensions, vision estimate 순으로 선택
13. 최종 `result.json` 저장

### 20.4 제거된 서비스 UI 요소

`clean_pipeline.py`의 UI에는 아래 실험용 요소를 노출하지 않는다.

| 제거 대상 |
|-----------|
| SAM/BiRefNet/RMBG/GPT 모델 비교 카드 |
| quality_score 순위표 |
| 모델 선택 버튼 |
| GPT 후보 비교 |
| 복잡한 디버그 지표 기본 노출 |

디버그 정보는 `result.json`과 UI의 접이식 debug section에만 남긴다.

### 20.5 주요 산출물

| 파일 | 의미 |
|------|------|
| `01_original.jpg` | 원본 이미지 |
| `02_detection_bbox.png` | DINO bbox 표시 이미지 |
| `02_measurement.png` | 원본 이미지 + 최종 mask 기반 측정 이미지 |
| `03_final_cutout.png` | DINO+BiRefNet 또는 fallback 최종 누끼 |
| `04_final_mask.png` | 치수 측정 기준 mask |
| `05_obstacle_removed.png` | surface obstacle일 때만 생성되는 GPT 장애물 제거 이미지 |
| `06_generation_cutout.png` | 장애물 제거 후 3D 생성 후보 cutout |
| `result.json` | clean_v1 최종 판단 |

### 20.6 API

FastAPI 엔드포인트는 단순하게 유지했다.

| 엔드포인트 | 역할 |
|------------|------|
| `GET /` | 단순 서비스 UI |
| `GET /api/health` | 서버 상태 |
| `POST /api/process` | 단일 파이프라인 실행 |
| `GET /api/output/{job_id}/{filename}` | 결과 파일 제공 |

비교용 API와 모델 선택 API는 추가하지 않았다.

### 20.7 검증 결과

| 검증 | 결과 |
|------|------|
| `clean_pipeline.py` 문법 컴파일 | 성공 |
| `import clean_pipeline` | 성공 |
| `GET /api/health` | `{"status":"ok","framework":"fastapi","pipeline_version":"clean_v1"}` |
| `GET /` | HTML UI 정상 응답 |
| 서버 실행 | 성공, PID 58384 |

### 20.8 실행 명령

```bash
python -m uvicorn clean_pipeline:app --host 127.0.0.1 --port 5004
```

현재 서버는 다음 주소에서 실행 중이다.

```text
http://127.0.0.1:5004
```

---

## 21. 2026-05-14 수정 보고 — `clean_v2_speed` SAM 제거 및 DINO+BiRefNet 단일화

### 21.1 목표

서비스용 플로우를 속도 우선으로 다시 정리했다.

이전 `clean_v1`은 DINO bbox 확보 과정에서 기존 `generate_measurement_image()`를 재사용했고, 이 함수 내부에서 SAM을 사용했다. 또한 DINO+BiRefNet undercoverage가 발생하면 DINO+SAM fallback을 허용했다.

이번 수정에서는 SAM을 서비스 플로우에서 제거했다.

### 21.2 변경 파일

| 파일 | 변경 내용 |
|------|-----------|
| `clean_pipeline.py` | GroundingDINO-only bbox 검출 추가, SAM fallback 제거, BiRefNet 결과가 bbox 대비 너무 작으면 실패 처리 |
| `REPORT.md` | 현재 수정 보고 추가 |

### 21.3 새 흐름

```text
URL 또는 이미지 입력
↓
상품 정보/대표 이미지
↓
가구 타입 판단
↓
GroundingDINO만으로 목표 bbox 검출
↓
DINO bbox crop 안에서 BiRefNet 누끼
↓
BiRefNet mask가 bbox 대비 너무 작으면 failed
↓
정상일 때만 measurement image 생성
↓
GPT Vision 장애물 판단
↓
surface_obstacle일 때만 GPT image edit
↓
치수는 원본 기반 DINO+BiRefNet mask로만 측정
```

### 21.4 제거된 동작

| 제거 항목 |
|-----------|
| `generate_measurement_image()` 호출 |
| DINO bbox 단계의 SAM mask 생성 |
| DINO+SAM fallback |
| `dino_birefnet_failed_used_dino_sam` warning |
| generation cutout에서 SAM/기존 mask support guard 사용 |

### 21.5 추가된 검증

`_validate_birefnet_mask_against_bbox()`를 추가했다.

검증 기준:

| 조건 | 처리 |
|------|------|
| BiRefNet mask가 없음 | failed |
| mask bbox width가 DINO bbox width의 40% 미만 | failed |
| mask bbox height가 DINO bbox height의 40% 미만 | failed |
| mask area가 DINO bbox area의 3% 미만 | failed |

실패 시 fallback하지 않고 `pipeline_status = failed`, HTTP `422`로 반환한다.

### 21.6 버전

새 pipeline version은 다음과 같다.

```text
clean_v2_speed
```

### 21.7 검증 결과

| 검증 | 결과 |
|------|------|
| `clean_pipeline.py` 문법 컴파일 | 성공 |
| `import clean_pipeline` | 성공 |
| `GET /api/health` | `{"status":"ok","framework":"fastapi","pipeline_version":"clean_v2_speed"}` |
| 서버 재시작 | 성공, PID 59189 |

### 21.8 현재 판단

이제 서비스용 `clean_pipeline.py`는 SAM을 쓰지 않는다. 타깃 위치는 GroundingDINO bbox만 사용하고, 누끼는 DINO bbox 내부 BiRefNet만 사용한다. BiRefNet이 인형이나 작은 전경 물체만 잡는 상황은 fallback으로 숨기지 않고 명시적 실패로 처리한다.

---

## 22. 2026-05-14 수정 보고 — 낮은 영향 소품/쿠션류 GPT edit 방지

### 22.1 문제

소파 이미지에서 쿠션, 볼스터, 작은 인형처럼 실제 가구 외형이나 치수에 거의 영향을 주지 않는 항목이 GPT Vision에 의해 `surface_obstacle`로 분류되었다. 이 경우 서비스 UI에서는 장애물 제거가 필요한 것으로 보이고, GPT image edit가 실행되어 불필요하게 생성 이미지가 만들어질 수 있었다.

### 22.2 변경 파일

| 파일 | 변경 내용 |
|------|-----------|
| `app.py` | GPT Vision 장애물 판단 프롬프트를 보수적으로 수정 |
| `clean_pipeline.py` | 낮은 영향 accessory policy 추가 |
| `REPORT.md` | 현재 수정 보고 추가 |

### 22.3 정책 변경

이제 아래 항목은 가구 외곽/구조/측정에 영향을 주지 않으면 장애물 제거 대상으로 보지 않는다.

| 낮은 영향 항목 |
|----------------|
| sofa cushion |
| pillow |
| bolster |
| included back/seat cushion |
| seams/wrinkles |
| small plush toy |
| doll/teddy |
| product accessory |

GPT Vision이 그래도 `surface_obstacle`로 반환하더라도 `clean_pipeline.py`의 `_apply_service_obstacle_policy()`가 한 번 더 판단한다.

### 22.4 동작 방식

```text
GPT Vision raw result = surface_obstacle
↓
obstacles가 cushion/pillow/bolster/plush/doll/toy 계열인지 확인
↓
affects_measurement=false 이고 occlusion_affects_outline=false 이면
↓
service obstacle_status를 none으로 downgrade
↓
GPT image edit 실행하지 않음
```

raw GPT 결과는 `result.json > debug.raw_obstacle_analysis`에 남긴다. 실제 서비스 판단은 `result.json > obstacle_analysis`에 저장된다.

### 22.5 검증 결과

| 검증 | 결과 |
|------|------|
| `app.py`, `clean_pipeline.py` 문법 컴파일 | 성공 |
| low-impact accessory policy 직접 호출 | `surface_obstacle` → `none` downgrade 확인 |
| 서버 재시작 | 성공, PID 59540 |
| `GET /api/health` | `{"status":"ok","framework":"fastapi","pipeline_version":"clean_v2_speed"}` |

### 22.6 현재 판단

스크린샷처럼 쿠션/작은 인형이 보이지만 가구 구조와 치수를 가리지 않는 경우에는 GPT image edit를 실행하지 않는 쪽이 맞다. 장애물 제거는 책, 컵, 옷, 가방, 잡동사니처럼 명확한 비가구 clutter가 표면을 차지하거나 측정/형상 판단을 방해할 때만 실행한다.
