# 프론트-백엔드 연동 가이드

이 문서는 프론트 개발자가 백엔드와 통신할 때 필요한 API 호출 순서와 화면에 표시할 값을 정리한 문서입니다.

프론트가 받아야 하는 핵심 데이터는 세 가지입니다.

1. 게시글에서 가져온 이미지 후보 목록
2. AI가 선택한 추천 이미지
3. 처리 진행상황과 최종 3D 모델 URL

## 전체 흐름

```text
1. 사용자가 게시글 URL 입력
2. POST /api/scrape 호출
3. 이미지 후보와 AI 추천 이미지 표시
4. 사용자가 이미지 선택 후 POST /api/process/start 호출
5. 받은 job_id로 GET /api/process/status/{job_id} SSE 연결
6. 단계별 진행상황 표시
7. 완료 또는 실패 후 GET /api/furniture/job/{job_id}로 상세 결과 조회
```

로컬 개발 기본 주소:

```text
http://localhost:8000/api
```

프론트 환경변수 예시:

```text
VITE_API_URL=http://localhost:8000/api
```

## 1. URL 스크래핑 및 이미지 후보 조회

사용자가 URL을 입력하고 `스크래핑` 버튼을 누르면 이 API를 호출합니다.

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
  "image_urls": ["https://image-0", "https://image-1"],
  "ai_recommended_image_index": 0,
  "ranked_candidate_indices": [0, 2, 1],
  "furniture_guess": {
    "type": "chair",
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

- `image_urls`: 화면에 보여줄 전체 후보 이미지 목록
- `ai_recommended_image_index`: AI가 고른 대표 이미지 인덱스
- `ranked_candidate_indices`: AI 추천 순위 표시용
- `title`, `description`, `price`: 게시글 정보 표시용
- `dimensions_from_listing`: 게시글에서 바로 찾은 치수 정보가 있으면 표시

백엔드 임시 프론트에서는 `/api/scrape` 요청 중 아래 진행상황을 먼저 보여줍니다.

```json
{
  "step": "crawling",
  "status": "processing",
  "progress": 5,
  "message": "게시글 크롤링 중..."
}
```

`/api/scrape`가 성공하면 아래 두 단계가 완료된 것으로 표시합니다.

```json
{
  "step": "crawling",
  "status": "completed",
  "progress": 20,
  "message": "게시글 크롤링 완료"
}
```

```json
{
  "step": "image_selection",
  "status": "completed",
  "progress": 35,
  "message": "최적 이미지 선정 완료"
}
```

## 2. 처리 시작

사용자가 후보 이미지 중 하나를 선택하고 `이 이미지로 처리하기`를 누르면 이 API를 호출합니다.

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

프론트는 `job_id`를 받은 직후 SSE에 연결합니다.

## 3. 진행상황 SSE

SSE는 서버가 프론트로 진행상황을 계속 보내주는 연결입니다. 프론트에서는 `EventSource`를 사용합니다.

```http
GET /api/process/status/{job_id}
Accept: text/event-stream
```

Event data 기본 형태:

```json
{
  "job_id": "abc12345",
  "step": "preprocessing",
  "status": "completed",
  "progress": 70,
  "message": "배경 제거 및 전처리 완료"
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

단계별 이벤트 예시:

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

최종 완료 이벤트:

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

## 4. 결과 상세 조회

SSE에서 `completed` 또는 `error` 이벤트를 받은 뒤, 상세 결과를 확인하고 싶으면 이 API를 호출합니다.

```http
GET /api/furniture/job/{job_id}
```

용도:

- 처리 결과 이미지 파일명 확인
- 치수 결과 확인
- `model_generation.glb_url` 확인
- 디버그 정보 확인

주의할 점:

- 실패했더라도 `result.json`이 만들어진 상태라면 이 API로 중간 결과를 볼 수 있습니다.
- 예를 들어 트릴리스 서버가 꺼져 있어도 배경 제거, 치수 측정, 컷아웃 이미지는 확인할 수 있습니다.

결과 이미지 URL은 아래 규칙으로 만듭니다.

```text
/api/furniture/output/{job_id}/{filename}
```

예시:

```text
/api/furniture/output/abc12345/03_final_cutout.png
```

## 5. 트릴리스 서버가 꺼져 있는 경우

현재 3D 모델 생성은 트릴리스 서버 설정에 의존합니다.

아래 메시지가 나오면 트릴리스 관련 설정이 없거나 서버가 꺼져 있는 상태입니다.

```text
TRELLIS_BASE_URL or BACKEND_PUBLIC_URL is missing
```

이 경우 의미:

- 게시글 크롤링은 성공
- 이미지 선정은 성공
- 배경 제거 및 전처리는 성공 가능
- 치수 측정은 성공 가능
- 최종 `glb_url`만 없음
- 화면에서는 `model_generation` 단계만 실패로 표시하면 됨

프론트 처리 권장:

- 전체 진행상황 카드를 지우지 말 것
- 이전 성공 단계는 완료 상태로 유지할 것
- `3D 모델 생성` 단계만 오류로 표시할 것
- `/api/furniture/job/{job_id}`로 결과를 조회해 이미지/치수 결과는 보여줄 것

## 6. 프론트 구현 예시

아래 코드는 흐름 이해용 예시입니다.

```js
const API = 'http://localhost:8000/api';

async function scrape(url) {
  const res = await fetch(`${API}/scrape`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) throw new Error('스크래핑 실패');
  return res.json();
}

async function startProcess(url, selectedImageIndex) {
  const res = await fetch(`${API}/process/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      url,
      selected_image_index: selectedImageIndex,
    }),
  });
  if (!res.ok) throw new Error('처리 시작 실패');
  return res.json();
}

function connectProgress(jobId) {
  const events = new EventSource(`${API}/process/status/${jobId}`);

  events.onmessage = async (event) => {
    const data = JSON.parse(event.data);
    console.log('progress event:', data);

    if (data.step === 'completed' || data.step === 'error') {
      events.close();

      const resultRes = await fetch(`${API}/furniture/job/${jobId}`);
      const result = await resultRes.json();
      console.log('final result:', result);
    }
  };

  events.onerror = () => {
    events.close();
    console.error('SSE 연결 오류');
  };
}
```

## 7. 백엔드 임시 프론트에서 확인하는 방법

백엔드 서버 실행:

```bash
uvicorn main:app --host 0.0.0.0 --port 4001
```

브라우저 접속:

```text
http://localhost:4001/
```

확인 순서:

1. 게시글 URL 입력
2. `스크래핑` 클릭
3. `게시글 크롤링`, `최적 이미지 선정` 진행 카드 확인
4. 이미지 후보와 AI 추천 이미지 확인
5. `이 이미지로 처리하기` 클릭
6. Network 탭에서 아래 요청 확인
   - `POST /api/process/start`
   - `GET /api/process/status/{job_id}`
7. 처리 단계 카드 확인
8. 트릴리스가 꺼져 있으면 `3D 모델 생성` 단계만 오류로 표시되는지 확인
9. 이전 단계 카드와 처리 결과 이미지가 화면에 유지되는지 확인

## 8. 기존 호환 API

아래 API는 기존 임시 UI 또는 이전 코드 호환용으로 남아 있습니다.

- `POST /api/process`
- `POST /api/gen/start`
- `GET /api/gen/status/{job_id}`

신규 프론트 개발에서는 `POST /api/process/start`와 `GET /api/process/status/{job_id}` 조합을 사용하는 것을 권장합니다.
