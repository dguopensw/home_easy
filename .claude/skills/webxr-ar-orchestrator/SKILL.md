---
name: webxr-ar-orchestrator
description: |
  home_easy 프로젝트의 WebAR 기능을 처음부터 끝까지 빌드하는 오케스트레이터. Unity iframe을 Three.js + WebXR로 교체하며, 바닥 감지(hit-test), reticle, GLB 배치, 치수 기반 스케일, 드래그/핀치/버튼 인터랙션, iOS 폴백까지 전체 파이프라인을 조율한다.
  "WebAR 만들어줘", "Unity 대신 WebXR", "AR 페이지 구현", "GLB AR 배치", "Three.js AR", "reticle 바닥 감지", "AR 하네스 실행", "AR 빌드 시작", "이전 AR 작업 이어서", "AR 업데이트"  등의 요청 시 반드시 이 스킬을 사용할 것.
---

# WebXR AR Orchestrator

## 목표

`frontend/src/pages/ARPage/`를 Unity 의존성 없이 Three.js + WebXR 기반으로 완전히 구현한다.

## 실행 모드

**하이브리드 파이프라인**:
- Phase 1 (Planner): 서브 에이전트
- Phase 2 (Core + Interaction): 팬아웃 서브 에이전트 (병렬)
- Phase 3 (React Builder): 서브 에이전트
- Phase 4 (QA): 서브 에이전트

---

## Phase 0: 컨텍스트 확인

시작 전에 반드시 다음을 확인한다:

1. `_workspace/` 디렉토리가 존재하는지 확인한다
2. 기존 `_workspace/*.md` 파일 목록을 확인한다
3. 실행 모드를 결정한다:
   - `_workspace/05_qa_report.md` 존재 → 이전 빌드 완료, 부분 수정 또는 재QA 모드
   - `_workspace/04_react_builder_done.md` 존재 → React 빌더까지 완료, QA만 실행
   - `_workspace/02_core_builder_done.md` 또는 `03_interaction_builder_done.md` 존재 → 미완료 Phase부터 재개
   - 없음 → 전체 초기 실행
4. 사용자에게 실행 모드를 보고하고, 확인을 받는다 (단, 명시적으로 "전체 다시"를 요청했으면 기존 _workspace를 `_workspace_prev/`로 이동 후 초기 실행)

---

## Phase 1: 아키텍처 계획 (서브 에이전트)

```
Agent(
  agent: "ar-planner",
  model: "opus",
  prompt: "webxr-ar-core 스킬을 읽고, 다음 컨텍스트로 WebAR 아키텍처를 설계하라:
    - 프로젝트: /Users/dahoo/home_easy/frontend
    - 기존 ARPage: frontend/src/pages/ARPage/ARPage.tsx
    - 기존 스택: React 18 + TypeScript + Vite + TailwindCSS v4
    - 요구사항: S3 GLB URL → 카메라 → 바닥감지+reticle → 탭배치 → 치수스케일 → 드래그회전/핀치스케일 → 버튼(회전/리프트/스케일/재배치)
    - 산출물: _workspace/01_planner_architecture.md"
)
```

Phase 1 완료 조건: `_workspace/01_planner_architecture.md` 파일 생성 확인

---

## Phase 2: Core + Interaction 병렬 빌드 (팬아웃 서브 에이전트)

Phase 1 완료 후 두 에이전트를 병렬로 실행한다:

**2-A: AR Core Builder** (run_in_background: true)
```
Agent(
  agent: "ar-core-builder",
  model: "opus",
  run_in_background: true,
  prompt: "_workspace/01_planner_architecture.md를 읽고, webxr-ar-core 스킬을 참조하여
    Three.js + WebXR 세션/히트테스트/reticle/GLB로더/치수스케일을 구현하라.
    작업 디렉토리: /Users/dahoo/home_easy/frontend/src/pages/ARPage/"
)
```

**2-B: AR Interaction Builder** (run_in_background: true)
```
Agent(
  agent: "ar-interaction-builder",
  model: "opus",
  run_in_background: true,
  prompt: "_workspace/01_planner_architecture.md를 읽고, ar-interaction 스킬을 참조하여
    터치 드래그 회전, 핀치 스케일, 버튼 제어를 구현하라.
    작업 디렉토리: /Users/dahoo/home_easy/frontend/src/pages/ARPage/"
)
```

두 에이전트의 완료를 대기한다. 완료 조건:
- `_workspace/02_core_builder_done.md` 존재
- `_workspace/03_interaction_builder_done.md` 존재

---

## Phase 3: React 통합 (서브 에이전트)

```
Agent(
  agent: "ar-react-builder",
  model: "opus",
  prompt: "_workspace/의 01, 02, 03 문서를 모두 읽고, ar-react-integration 스킬을 참조하여
    ARPage.tsx를 WebXR 기반으로 재작성하고 ARControls.tsx를 확장하라.
    기존 파일을 먼저 Read한 뒤 수정한다.
    작업 디렉토리: /Users/dahoo/home_easy/frontend/src/pages/ARPage/"
)
```

완료 조건: `_workspace/04_react_builder_done.md` 존재

---

## Phase 4: QA 검증 (서브 에이전트)

```
Agent(
  agent: "ar-qa",
  model: "opus",
  prompt: "7가지 요구사항(R1~R7)에 대해 구현된 코드를 검증하라.
    대상 디렉토리: /Users/dahoo/home_easy/frontend/src/pages/ARPage/
    결과: _workspace/05_qa_report.md"
)
```

---

## Phase 5: 결과 보고 및 후속 안내

QA 보고서(`_workspace/05_qa_report.md`)를 읽고 사용자에게 요약한다:

1. **PASS인 경우**: 다음 단계 안내
   ```
   패키지 설치: cd frontend && pnpm add three @types/three
   개발 서버: pnpm dev
   Android Chrome에서 https://localhost:5173/ar 접속 (HTTPS 필요 — WebXR 요구사항)
   ```

2. **FAIL인 경우**: 실패 항목을 목록화하고, 해당 빌더 에이전트를 부분 재실행할지 묻는다

---

## 에러 핸들링

| 상황 | 처리 |
|------|------|
| Phase 1 실패 (파일 미생성) | 오류 보고 후 중단 |
| Phase 2-A 또는 2-B 중 하나 실패 | 실패 에이전트만 재실행 |
| Phase 3 실패 | Phase 3만 재실행 |
| Phase 4 FAIL | 실패 항목에 해당하는 빌더만 부분 재실행 후 Phase 4 재실행 |

---

## 테스트 시나리오

### 정상 흐름
1. "WebAR 만들어줘" 입력
2. Phase 0에서 _workspace 없음 확인 → 전체 초기 실행 보고
3. Phase 1~4 순차 실행
4. QA PASS → 패키지 설치 안내

### 에러 흐름
1. "AR 빌드 이어서" 입력 + _workspace/02_core_builder_done.md 존재
2. Phase 0에서 Phase 3부터 재개 결정
3. React 빌더 → QA 순으로만 실행
