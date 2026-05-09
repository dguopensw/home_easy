# Unit of Work Plan
# 집에 가구 쉽다 (Easy Furniture Fit)

---

## 확인된 Units (Application Design 기반)

Application Design에서 4개 Unit이 이미 정의되었습니다.

| Unit | 기술 스택 | 배포 환경 |
|------|----------|----------|
| Unit 1: Frontend | React + Vite + TypeScript + Tailwind CSS | Vercel |
| Unit 2: Backend API | Python + FastAPI | AWS EC2 |
| Unit 3: AI Pipeline | Python + RunPod Serverless | RunPod |
| Unit 4: Unity AR | Unity WebGL | Vercel (Frontend 내 포함) |

---

## 질문

### Question 1
레포지토리 구조를 어떻게 할까요?

A) 모노레포 — 하나의 git repo 안에 모든 Unit을 폴더로 관리
   ```
   opensw/
   ├── frontend/
   ├── backend/
   ├── ai-pipeline/
   └── unity-ar/
   ```
B) 멀티레포 — Unit마다 별도 git repo
C) Other (please describe after [Answer]: tag below)

[Answer]:A

---

### Question 2
Unit 3 AI Pipeline은 RunPod에서 실행되는 별도 서버리스 코드입니다.
이 코드를 Unit 2 Backend API와 같은 repo/폴더에 둘까요, 아니면 분리할까요?

A) 분리 — `ai-pipeline/` 폴더를 별도로 관리 (RunPod에 독립 배포)
B) 통합 — `backend/` 안의 서브폴더로 관리 (`backend/ai_pipeline/`)
C) Other (please describe after [Answer]: tag below)

[Answer]:A

---

### Question 3
Unit 4 Unity AR은 빌드 결과물(WebGL)이 Frontend에 포함되어 배포됩니다.
Unity 소스코드는 어디에 둘까요?

A) Frontend 폴더 내부 — `frontend/unity/` 에 Unity 프로젝트 배치
B) 별도 폴더 — `unity-ar/` 로 분리하고, 빌드 결과만 frontend에 복사
C) Other (please describe after [Answer]: tag below)

[Answer]:B

---

## 생성 체크리스트 (답변 후 자동 실행)

- [x] `unit-of-work.md` — Unit 정의 및 책임
- [x] `unit-of-work-dependency.md` — Unit 간 의존성 매트릭스
- [x] `unit-of-work-story-map.md` — User Story → Unit 매핑
