# Unit of Work 의존성
# 집에 가구 쉽다 (Easy Furniture Fit)

---

## Unit 간 의존성 매트릭스

| 호출자 \ 피호출자 | Unit 1 Frontend | Unit 2 Backend | Unit 3 AI Pipeline | Unit 4 Unity AR |
|-----------------|:--------------:|:--------------:|:------------------:|:---------------:|
| **Unit 1 Frontend** | — | ✅ REST/SSE | ❌ 직접 없음 | ✅ SendMessage |
| **Unit 2 Backend** | ❌ | — | ✅ RunPod API | ❌ |
| **Unit 3 AI Pipeline** | ❌ | ❌ | — | ❌ |
| **Unit 4 Unity AR** | ✅ CustomEvent | ❌ | ❌ | — |

> ✅ 의존 있음 / ❌ 의존 없음

---

## 통신 상세

### Unit 1 → Unit 2 (REST / SSE)
| 호출 | 방식 | 엔드포인트 |
|------|------|-----------|
| 파이프라인 시작 | HTTP POST | `/furniture/gen/start` |
| 진행 상태 수신 | SSE (GET) | `/furniture/gen/status/{job_id}` |
| 모델 정보 조회 | HTTP GET | `/furniture/{job_id}` |
| 크롤링 테스트 | HTTP POST | `/furniture/crawl/test` |

### Unit 2 → Unit 3 (RunPod REST API)
| 호출 | 방식 | 내용 |
|------|------|------|
| 작업 시작 | RunPod API | 전처리된 이미지 전달 (크롤링·이미지선정·전처리·치수추정은 Unit 2에서 완료) |
| 상태 폴링 | RunPod API | 2초마다 상태 확인 (runpod_job_id 사용, 메모리에만 저장) |
| 결과 수신 | RunPod API | glb_url 반환 (dimensions는 Unit 2에서 이미 계산) |

### Unit 1 ↔ Unit 4 (JSBridge)
| 방향 | 방식 | 내용 |
|------|------|------|
| Frontend → Unity | `unityInstance.SendMessage()` | glbUrl 전달 |
| Unity → Frontend | `window.dispatchEvent(CustomEvent)` | 이벤트 알림 |

---

## 외부 의존성

| Unit | 외부 서비스 | 용도 |
|------|-----------|------|
| Unit 2 Backend | 당근마켓 / 번개장터 / 중고나라 | 크롤링 대상 |
| Unit 2 Backend | OpenAI GPT-4o Vision | 최적 이미지 선정 |
| Unit 2 Backend | Grounding DINO + SAM | 배경 제거 |
| Unit 2 Backend | LaMa | 인페인팅 |
| Unit 2 Backend | Metric3D / Depth Pro | 치수 추정 |
| Unit 2 Backend | PostgreSQL (AWS RDS) | 완료 결과 저장 |
| Unit 3 AI Pipeline | AWS S3 | .glb 파일 저장 |
