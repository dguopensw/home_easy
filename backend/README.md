# Backend — 집에 가구 쉽다

FastAPI + PostgreSQL 백엔드 초기 세팅 가이드입니다.

---

## 사전 준비 (필수 설치)

| 도구 | 설치 링크 | 확인 명령어 |
|------|----------|------------|
| Docker Desktop | https://www.docker.com/products/docker-desktop | `docker --version` |
| Git | https://git-scm.com | `git --version` |

> Python, PostgreSQL은 **직접 설치하지 않아도 됩니다.** Docker가 대신합니다.

---

## 시작 방법



# 2. 환경변수 파일 생성
cp .env.example .env
```

`.env` 파일을 열어서 아래 항목에 키를 입력합니다. 현재는 AWS에 배포하지 않았으므로 DATABASE_URL만 기입해주시면 됩니다

```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/furniture_db
OPENAI_API_KEY=sk-...
RUNPOD_API_KEY=...
RUNPOD_ENDPOINT_ID=...
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_S3_BUCKET=...
AWS_REGION=ap-northeast-2
```


```bash
# 3. 서버 실행(즉 도커를 실행하면 도커가 api 서버 컨테이너랑 DB가 돌아가는 컨테이너 두개를 띄워줍니다)
docker-compose up
```

정상 실행되면:
- API 서버: http://localhost:8000
- API 문서 (Swagger): http://localhost:8000/docs
- DB: localhost:5432

---

## DB 구조

### jobs 테이블(현재는 jobs 테이블 하나만 있습니다)

처리가 **완료된 결과만** 저장합니다. 진행 중 상태는 SSE가 담당하므로 DB에 저장하지 않습니다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `job_id` | String (PK) | UUID, 백엔드가 생성 |
| `source_url` | String | 사용자가 입력한 원본 게시글 URL |
| `dimensions` | JSON | 가구 치수 `{"w": 80, "h": 60, "d": 40}` (단위: cm) |
| `glb_url` | String | S3에 업로드된 3D 모델 파일 URL |
| `created_at` | DateTime | 저장 시각 (UTC) |

> 에러가 발생하면 DB에 저장하지 않고 SSE `error` 이벤트만 프론트엔드에 전송합니다.

### 테이블 확인 방법

```bash
# DB 접속
docker exec -it furniture_easy_db psql -U postgres -d furniture_db

# 테이블 목록
\dt

# jobs 테이블 컬럼 상세
\d jobs

# 저장된 데이터 조회
SELECT * FROM jobs;
```

---

## 코드 구조

```
backend/
├── main.py              # FastAPI 앱 진입점, 서버 시작 시 DB 테이블 자동 생성
├── database.py          # PostgreSQL 연결 설정
├── models/
│   └── job.py           # jobs 테이블 정의
├── routers/             # API 엔드포인트
│   ├── generation.py    # POST /furniture/gen/start, GET /furniture/gen/status/{job_id}
│   ├── crawling.py      # GET /furniture/crawl/test (개발용)
│   └── furniture.py     # GET /furniture/{job_id}
├── services/            # 비즈니스 로직 (팀원이 구현할 부분)
│   ├── crawling_service.py      # 플랫폼별 크롤링(이거는 그냥 만들어 놓긴 했는데 굳이 안채워도될듯 합니다)
│   ├── image_selector.py        # GPT-4o Vision 이미지 선정
│   ├── preprocessor.py          # 배경 제거 / 인페인팅
│   ├── dimension_estimator.py   # 치수 추정
│   └── generation_service.py    # 파이프라인 조합 + RunPod 폴링 + SSE
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

### 구현해야 할 파일

`services/` 하위 파일들은 뼈대만 잡혀 있습니다. `# TODO:` 주석은 참고만하여 구현하시면 됩니다 
전체 흐름은 `docs/feature-flow/request-flow.md`를 참고하세요+ 다후님 설계변경 사항에 맞게 구현하시면 됩니다

---

## Docker 컨테이너 구성

`docker-compose up` 실행 시 컨테이너 두 개가 뜹니다:

| 컨테이너 이름 | 역할 | 포트 |
|-------------|------|------|
| `furniture_easy_api` | FastAPI 서버 | 8000 |
| `furniture_easy_db` | PostgreSQL 16 | 5432 |

로컬 코드(`backend/`)가 컨테이너에 마운트되어 있어서 **코드를 수정하면 서버가 자동으로 재시작**됩니다.

---

## 자주 쓰는 명령어

```bash
# 서버 시작
docker-compose up

# 백그라운드 실행
docker-compose up -d

# 서버 종료
docker-compose down

# DB 데이터까지 초기화 (스키마 변경 시)
docker-compose down -v
docker-compose up


# DB 접속
docker exec -it furniture_easy_db psql -U postgres -d furniture_db
```

---

## 스키마 변경 시(그니까 디비 구조 바꿀때)

개발 중에는 볼륨째 삭제 후 재시작하면 됩니다 (데이터 초기화됨):

```bash
docker-compose down -v
docker-compose up
```
