# Frontend Integration Contract

프론트 연동 시 백엔드가 제공하는 값은 크게 세 가지입니다.

1. 크롤링된 이미지 후보와 AI 추천 이미지
2. 파이프라인 단계별 완료 시그널
3. 최종 3D 모델 GLB URL

## Base URL

로컬 개발 기본값:

```text
http://localhost:8000/api
```

프론트 환경변수 예시:

```text
VITE_API_URL=http://localhost:8000/api
```

## 1. 이미지 후보 조회

```http
POST /api/scrape
Content-Type: application/json
```

Request:

```json
{
  "url": "https://..."
}
```

Response 주요 키:

```json
{
  "title": "게시글 제목",
  "description": "게시글 설명",
  "price": "가격",
  "platform": "daangn",
  "image_urls": ["https://...", "https://..."],
  "ai_recommended_image_index": 0,
  "ranked_candidate_indices": [0, 2, 1],
  "furniture_guess": {
    "type": "sofa",
    "confidence": "high"
  },
  "dimensions_from_listing": {
    "width_cm": 120,
    "depth_cm": 60,
    "height_cm": 85
  }
}
```

프론트 표시 기준:

- `image_urls`: 후보 이미지 전체 목록
- `ai_recommended_image_index`: AI가 선택한 대표 이미지 인덱스
- `ranked_candidate_indices`: AI 추천 순위 표시용

## 2. 파이프라인 시작

```http
POST /api/process/start
Content-Type: application/json
```

Request:

```json
{
  "url": "https://...",
  "selected_image_index": 0
}
```

Response:

```json
{
  "job_id": "abc12345"
}
```

`job_id`를 받은 뒤 SSE에 연결합니다.

## 3. 진행 상태 SSE

```http
GET /api/process/status/{job_id}
Accept: text/event-stream
```

Event data:

```json
{
  "job_id": "abc12345",
  "step": "crawling",
  "status": "completed",
  "progress": 20,
  "message": "게시글 크롤링 완료"
}
```

`step` 값:

```ts
type ProgressStep =
  | "crawling"
  | "image_selection"
  | "preprocessing"
  | "dimension"
  | "model_generation"
  | "completed"
  | "error"
```

현재 백엔드 진행 순서:

```text
crawling -> image_selection -> preprocessing -> dimension -> model_generation -> completed
```

단계별 완료 이벤트 예시:

```json
{
  "job_id": "abc12345",
  "step": "crawling",
  "status": "completed",
  "progress": 20,
  "message": "게시글 크롤링 완료"
}
```

```json
{
  "job_id": "abc12345",
  "step": "image_selection",
  "status": "completed",
  "progress": 35,
  "message": "최적 이미지 선정 완료"
}
```

```json
{
  "job_id": "abc12345",
  "step": "preprocessing",
  "status": "completed",
  "progress": 70,
  "message": "배경 제거 및 전처리 완료"
}
```

```json
{
  "job_id": "abc12345",
  "step": "dimension",
  "status": "completed",
  "progress": 80,
  "message": "치수 측정 완료"
}
```

```json
{
  "job_id": "abc12345",
  "step": "model_generation",
  "status": "completed",
  "progress": 95,
  "message": "3D 모델 생성 완료",
  "glb_url": "https://.../model.glb"
}
```

완료 이벤트:

```json
{
  "job_id": "abc12345",
  "step": "completed",
  "status": "completed",
  "progress": 100,
  "glb_url": "https://.../model.glb",
  "dimensions": {
    "width": 120,
    "height": 85,
    "depth": 60,
    "unit": "cm"
  }
}
```

에러 이벤트:

```json
{
  "job_id": "abc12345",
  "step": "error",
  "status": "error",
  "progress": 0,
  "message": "오류 메시지"
}
```

## Existing Compatibility APIs

기존 임시 UI 호환을 위해 아래 API는 유지됩니다.

- `POST /api/scrape`
- `POST /api/process`
- `GET /api/gen/status/{job_id}`

신규 프론트 로딩 화면은 `POST /api/process/start`와 `GET /api/process/status/{job_id}`를 사용하는 것을 권장합니다.
