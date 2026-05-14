# User Story → Unit 매핑
# 집에 가구 쉽다 (Easy Furniture Fit)

---

## Unit 1 — Frontend

| 스토리 | 제목 | 우선순위 |
|--------|------|---------|
| US-01 | 서비스 소개 확인 | 🔴 MVP |
| US-02 | 가구 탐색 시작 | 🔴 MVP |
| US-03 | 최근 배치 기록 미리보기 | 🟡 MVP UI만 |
| US-04 | 중고 가구 URL 입력 | 🔴 MVP |
| US-05 | 데모 링크로 체험 | 🔴 MVP |
| US-06 | 빈 URL 입력 에러 처리 | 🔴 MVP |
| US-07 | 지원하지 않는 플랫폼 URL 에러 | 🔴 MVP |
| US-08 | AI 처리 진행 상태 확인 | 🔴 MVP |
| US-09 | 크롤링 실패 에러 처리 (UI) | 🔴 MVP |
| US-10 | 3D 생성 실패 에러 처리 (UI) | 🔴 MVP |
| US-11 | 3D 모델 인터랙션 | 🔴 MVP |
| US-12 | 가구 치수 확인 | 🔴 MVP |
| US-13 | AR 배치로 이동 | 🔴 MVP |
| US-18 | AR 결과 촬영 | 🔴 MVP |
| US-19 | 배치 기록 목록 조회 (UI) | 🟢 Post-MVP |
| US-20 | AR 배치 결과 공유 (UI) | 🟢 Post-MVP |
| US-21 | 카카오 로그인 (UI) | 🟢 Post-MVP |

---

## Unit 2 — Backend API

| 스토리 | 제목 | 우선순위 |
|--------|------|---------|
| US-04 | 중고 가구 URL 입력 (UUID job_id 즉시 반환, 비동기 처리 시작) | 🔴 MVP |
| US-07 | 지원하지 않는 플랫폼 감지 | 🔴 MVP |
| US-08 | AI 진행 상태 SSE 스트리밍 (크롤링 ~ 치수 추정 구간 포함) | 🔴 MVP |
| US-08 | 최적 이미지 선정 (GPT-4o Vision) | 🔴 MVP |
| US-08 | 이미지 전처리 (DINO+SAM 배경 제거, LaMa 인페인팅) | 🔴 MVP |
| US-12 | 가구 치수 추정 (Metric3D) | 🔴 MVP |
| US-09 | 크롤링 / 전처리 실패 SSE error 이벤트 반환 | 🔴 MVP |
| US-10 | 3D 생성 실패 SSE error 이벤트 반환 | 🔴 MVP |
| —     | DB 구축 (PostgreSQL 연결 설정, Job 테이블 생성) | 🔴 MVP |
| —     | 완료 결과 DB 저장 (job_id, source_url, dimensions, glb_url) | 🔴 MVP |

---

## Unit 3 — AI Pipeline (RunPod)

| 스토리 | 제목 | 우선순위 |
|--------|------|---------|
| US-08 | 전처리된 이미지로 3D 모델 생성 (TRELLIS) | 🔴 MVP |
| US-08 | 생성된 .glb 파일 S3 업로드 후 glb_url 반환 | 🔴 MVP |
| US-10 | 3D 생성 실패 처리 (RunPod handler 내 에러 반환) | 🔴 MVP |

---

## Unit 4 — Unity AR

| 스토리 | 제목 | 우선순위 |
|--------|------|---------|
| US-14 | AR 가구 배치 및 위치 조작 | 🔴 MVP |
| US-15 | 배치된 가구 회전 | 🔴 MVP |
| US-16 | 가구 복제 및 삭제 | 🔴 MVP |
| US-17 | AR 인식 실패 안내 | 🔴 MVP |

---

## 전체 커버리지 요약

| Unit | MVP 필수 | MVP UI만 | Post-MVP |
|------|---------|---------|---------|
| Unit 1 Frontend | 13개 | 1개 | 3개 |
| Unit 2 Backend | 10개 | — | — |
| Unit 3 AI Pipeline | 3개 | — | — |
| Unit 4 Unity AR | 4개 | — | — |

> 일부 스토리(US-04, US-08, US-09, US-10, US-12)는 여러 Unit에 걸쳐 구현됩니다.
> Unit 2는 크롤링·AI 전처리·치수 추정·DB 구축까지 포함하며, Unit 3(RunPod)은 3D 생성과 S3 업로드만 담당합니다.
