---
name: ossp-report
description: >
  home_easy 프로젝트의 OSSP 최종보고서 문서 세트를 생성·개선·업데이트한다.
  레포 분석 → 결함 진단 → 목차 재설계 → Markdown 보고서 확장 → HTML 보고서 확장 → 오픈소스 보강 → 실험 설계 보강 → 검수 → revision_summary 작성까지 전체 파이프라인을 수행한다.
  "OSSP 보고서", "최종보고서", "보고서 작성", "보고서 업데이트", "보고서 개선", "보고서 확장", "다시 작성",
  "HTML 보고서", "레포 분석", "오픈소스 인벤토리", "자료 체크리스트", "보고서 검수", "보고서 보강",
  "예시 보고서 수준", "보고서 이어서", "이전 보고서 작업" 등의 요청 시 반드시 이 스킬을 사용할 것.
  docs/final_report/ 내 파일만 수정하며, 서비스 코드(backend/, unity-ar/)는 절대 수정하지 않는다.
---

# OSSP 최종보고서 오케스트레이터

## 실행 모드
**하이브리드**: 서브 에이전트 순차 파이프라인 (파일 기반 데이터 전달)

---

## Phase 0: 컨텍스트 확인

실행 전 기존 산출물 상태를 먼저 파악한다.

1. `docs/final_report/` 디렉토리 목록 확인
2. `docs/final_report/revision_summary.md` 존재 시 읽고, 이전 검수에서 "여전히 필요"로 남은 항목 식별
3. `docs/final_report/report_gap_analysis.md` 존재 시 읽고, 결함 목록 확인
4. 실행 모드 결정:
   - 파일 없음 → **초기 실행** (Phase 1~9 전체)
   - 일부 있음 + 부분 수정 요청 → **부분 재실행** (해당 Phase만)
   - 있음 + 개선 요청 → **개선 실행** (기존 파일 읽고 보강)

---

## Phase 1 — 레포 분석

**실행 모드:** 서브 에이전트 (repo-analyst)
**산출물:** `docs/final_report/repo_analysis_summary.md`

에이전트: `.claude/agents/repo-analyst.md` 참조

기존 `repo_analysis_summary.md`가 있으면 읽고, 누락된 항목(확인 필요로 남은 것) 위주로 보완 분석한다.
이미 확인된 항목은 재확인 없이 유지한다.

---

## Phase 2 — 기존 보고서 결함 진단

**실행 모드:** 직접 수행 (서브 에이전트 불필요)
**산출물:** `docs/final_report/report_gap_analysis.md`

`repo_analysis_summary.md`와 기존 보고서 파일들을 읽고, 다음 기준으로 결함을 분류한다:

| 결함 유형 | 판단 기준 | 보강 방향 |
|----------|----------|----------|
| 본문 밀도 부족 | 장당 본문 2문단 미만 | 설명형 문단 추가 |
| 근거 없는 구현 완료 | 코드 확인 없이 완료 표기 | 상태 수정 또는 근거 병기 |
| 실험 결과 조작 | 실제 결과 없는데 수치 기재 | 실험 설계로 대체 |
| 기술 설명 부실 | "SAM3 사용"처럼 왜인지 설명 없음 | 선택 이유 + 입출력 추가 |
| 필수 장 누락 | 비교, 유즈케이스, 실험 설계 없음 | 해당 장 신규 추가 |

---

## Phase 3 — 확장 목차 재설계

**실행 모드:** 직접 수행
**산출물:** `docs/final_report/report_gap_analysis.md` (목차 섹션 추가)

`report_gap_analysis.md`에 다음 내용을 추가한다:
- 예시 보고서 대비 누락 장 목록
- 최종 확장 목차 (18장)
- 각 장별 목표 분량 (최소 문단 수)

---

## Phase 4 — Markdown 보고서 확장

**실행 모드:** 서브 에이전트 (report-writer)
**산출물:** `docs/final_report/OSSP_final_report_draft.md`

에이전트: `.claude/agents/report-writer.md` 참조

기존 파일이 있으면 **반드시 먼저 읽고**, `report_gap_analysis.md`의 결함 목록 기준으로 보강이 필요한 장을 식별한 뒤 우선 확장한다.

**필수 확인 항목:**
- 개발동기 5문단 이상 작성 여부
- FR/NFR 표 2개 모두 포함 여부
- 기존 서비스 비교 장 존재 여부
- 시스템 아키텍처 Mermaid 다이어그램 포함 여부
- 실험 설계 장 (실제 결과 없어도 설계·지표·판정 기준 충분히) 존재 여부
- 한계 및 개선방향 10개 이상

---

## Phase 5 — HTML 보고서 확장

**실행 모드:** 서브 에이전트 (report-writer)
**산출물:** `docs/final_report/OSSP_final_report.html`

기존 HTML이 있으면 **반드시 먼저 읽고**, 요약 카드 위주의 구성을 본문 중심으로 확장한다.

**필수 확인 항목:**
- 각 섹션에 설명 문단 + 표 포함 여부
- Hero에 "HTML = 문서 산출물, Unity GLB = 최종 결과물" 배지 포함 여부
- 파이프라인 시각화 (17단계) 포함 여부
- CSS 박스 아키텍처 다이어그램 포함 여부
- 실험 설계 섹션 포함 여부
- 인쇄/PDF 저장용 print CSS 포함 여부
- 전체 스크롤 분량 30~50 화면 페이지 수준

---

## Phase 6 — 오픈소스 인벤토리 보강

**실행 모드:** 직접 수행
**산출물:** `docs/final_report/open_source_inventory.md`

기존 파일이 있으면 읽고, 누락 항목을 추가한다.

**필수 분류 기준:**
- 표 1. 오픈소스 라이브러리/모델 (OpenAI API, RunPod, AWS S3 절대 포함 금지)
- 표 2. 외부 API/상용 서비스 (OpenAI API, TRELLIS RunPod)
- 표 3. 인프라/배포 도구 (RunPod, AWS S3, Docker)
- 라이선스가 requirements.txt에서 확인 안 되면 "확인 필요" 명시

---

## Phase 7 — 실험 설계 및 자료 체크리스트 보강

**실행 모드:** 직접 수행
**산출물:** `docs/final_report/assets_checklist.md`

기존 파일이 있으면 읽고 업데이트한다.

실제 output 결과가 없으면:
- 테스트 케이스 계획 (가구 유형별 5~10개)
- 평가 지표 정의 (마스킹 품질, 치수 오차 비율, 3D 생성 성공률 등)
- 성공/부분성공/실패 판정 기준 표
- 테스트 실행 절차 (백엔드 실행 → URL 입력 → 결과 캡처 → 비교)

---

## Phase 8 — 자체 검수

**실행 모드:** 서브 에이전트 (report-reviewer)
**산출물:** 수정된 문서들

에이전트: `.claude/agents/report-reviewer.md` 참조

이전 `revision_summary.md`가 있으면 읽고, 이전 검수에서 "여전히 필요"로 표시된 항목부터 재확인한다.
검수는 항목 체크에 그치지 않고, 문제 발견 시 즉시 해당 파일을 직접 수정한다.

---

## Phase 9 — revision_summary 작성

**실행 모드:** 직접 수행
**산출물:** `docs/final_report/revision_summary.md`

```markdown
## 검수 결과 요약

### 1. 이번 작업에서 생성/수정한 파일 목록
### 2. 보강 전 주요 문제점
### 3. 보강한 장 목록 및 내용
### 4. 여전히 필요한 자료 목록 (TODO)
### 5. 사용자가 다음에 해야 할 실행 작업
```

---

## 데이터 전달 프로토콜

| Phase | 입력 | 출력 |
|-------|-----|------|
| 1 (레포 분석) | backend/ 코드 | repo_analysis_summary.md |
| 2 (결함 진단) | repo_analysis_summary.md + 기존 보고서 | report_gap_analysis.md |
| 3 (목차 재설계) | report_gap_analysis.md | report_gap_analysis.md (목차 섹션 추가) |
| 4 (MD 확장) | repo_analysis_summary.md + report_gap_analysis.md | OSSP_final_report_draft.md |
| 5 (HTML 확장) | OSSP_final_report_draft.md | OSSP_final_report.html |
| 6 (오픈소스) | requirements.txt + 기존 inventory | open_source_inventory.md |
| 7 (실험 설계) | 기존 assets_checklist.md | assets_checklist.md (업데이트) |
| 8 (검수) | 모든 보고서 파일 | 수정된 파일들 |
| 9 (summary) | 전체 작업 결과 | revision_summary.md |

---

## 보고서 작성 원칙 (전체 Phase 공통)

1. **서비스 코드 수정 금지** — backend/, unity-ar/ 절대 수정하지 않는다
2. `docs/final_report/` 내부 파일만 생성/수정 가능
3. API 키, AWS 키, HuggingFace 토큰, OpenAI 키, RunPod URL 실제 값 포함 금지
4. 환경변수 이름(TRELLIS_BASE_URL, OPENAI_API_KEY 등)은 작성 가능
5. **구현 완료 / 실험 적용 / 선택 예정 / 향후 개선 / 확인 필요** 명확히 구분
6. 최종 결과물 = **Unity 기반 GLB 배치** (일관 유지)
7. HTML = **보고서 문서 산출물** (서비스 결과물 아님, 일관 명시)
8. **WebAR 표현 금지**
9. 인페인팅 = **Flux 또는 nano-banana 중 선택 예정** (확정 금지)
10. LaMa = **기존 실험 후보/코드상 잔존 요소로만** 설명
11. 실제 결과 없는 부분은 결과를 만들지 않고, 실험 설계·평가 지표·판정 기준을 자세히 작성
12. 과장 표현 금지 ("완전히 해결한다", "혁신적" 등)
13. OpenAI API, RunPod, AWS S3를 오픈소스 표에 분류 금지
14. 참고문헌을 임의로 생성하여 URL 없이 추가 금지

---

## 에러 핸들링

- 서브 에이전트 실패 시 1회 재시도, 재실패 시 해당 Phase 누락으로 표시하고 진행
- 민감정보(API 키, 실제 URL, 토큰) 감지 시 즉시 제거
- 상충 정보(코드 vs 보고서)는 삭제하지 않고 "코드 확인 결과: ..." 형태로 출처 병기

---

## 테스트 시나리오

**정상 흐름:** "OSSP 최종보고서 작성해줘" → Phase 0~9 전체 실행 → 7개 문서 생성/갱신
**부분 재실행:** "HTML 보고서만 다시 만들어줘" → Phase 0 확인 후 Phase 5만 실행
**개선 실행:** "보고서 보강해줘" → Phase 0에서 기존 파일 감지 → 결함 진단 후 보강 필요 Phase 실행
**에러 흐름:** repo_analysis_summary.md 없이 보고서 작성 요청 → Phase 1부터 전체 실행
