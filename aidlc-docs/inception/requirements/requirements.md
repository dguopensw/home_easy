# 요구사항 문서 (Requirements Document)
# 집에 가구 쉽다 (Easy Furniture Fit)

---

## 1. Intent Analysis

| 항목 | 내용 |
|------|------|
| **Request Type** | New Project (Greenfield) |
| **Scope** | System-wide — Frontend, Backend API, AI Pipeline |
| **Complexity** | Complex (AI 파이프라인 + AR 통합 + 멀티 서비스) |
| **Depth Level** | Comprehensive |

**User Request 요약**:
중고 거래 플랫폼(당근마켓, 번개장터, 중고나라)의 가구 게시글 URL을 입력하면
AI가 자동으로 3D 모델을 생성하고, 사용자가 실제 공간에 AR로 배치해볼 수 있는 모바일 웹앱

---

## 2. MVP 범위 정의

### MVP에 포함 (완전 기능 구현)
- 홈 화면
- URL 입력 화면
- 로딩 화면 (AI 파이프라인 진행 상태)
- 3D 미리보기 화면
- AR 배치 화면 (기록/공유 제외)

### MVP에 포함 (UI만, 기능 미구현)
- 배치 기록(History) 화면
- 결과 저장 화면

### Post-MVP (추후 개발)
- 배치 기록 저장 기능 (PostgreSQL + S3 연동)
- 소셜 로그인 (카카오) — 배치 기록 구현 시 함께 도입

---

## 3. 기능 요구사항 (Functional Requirements)

### FR-01: 홈 화면
- 서비스 소개 및 사용법 안내 (How it works)
- "지금 시작하기" 버튼으로 URL 입력 화면 이동
- 최근 배치 기록 섹션 (MVP: UI만, 더미 데이터)
- 배치 기록 전체보기 버튼 (MVP: 화면 이동만)

### FR-02: URL 입력 화면
- 당근마켓 / 번개장터 / 중고나라 게시글 URL 입력 필드
- 지원 플랫폼 표시 칩 (당근마켓, 번개장터, 중고나라)
- 데모용 샘플 링크 제공
- URL 유효성 검사 (빈 값 방지)
- "3D 모델 생성하기" 버튼으로 AI 파이프라인 요청

### FR-03: 로딩 화면
- AI 파이프라인 5단계 진행 상태 표시
  1. 게시글 크롤링
  2. 최적 이미지 선정 (GPT-4o Vision)
  3. 치수 측정 (Metric3D)
  4. 배경 제거·전처리 (SAM + LaMa)
  5. 3D 모델 생성 (TRELLIS)
- 단계별 진행률(%) 및 현재 단계 강조 표시
- 백엔드 완료 시 자동으로 3D 미리보기 화면으로 전환

### FR-04: 3D 미리보기 화면
- Google model-viewer로 생성된 `.glb` 파일 렌더링
- 드래그 회전 / 핀치 확대 제스처 지원
- 치수 탭: 너비(W) / 높이(H) / 깊이(D) 수치 및 다이어그램 표시
- "AR로 방에 배치하기" 버튼으로 AR 화면 이동

### FR-05: AR 배치 화면
- Unity WebGL iframe을 React 앱에 통합
- React ↔ Unity 메시지 통신 (SendMessage API)
- 바닥 평면 인식 후 가구 배치
- 배치된 가구 핀치/회전 제스처 조절
- 복제 / 삭제 / 촬영 버튼
- AR ↔ 3D 뷰 전환 탭

### FR-06: AI 파이프라인 (Backend + RunPod)

**FastAPI 백엔드 (AWS EC2)**:
- 당근마켓 / 번개장터 / 중고나라 게시글 크롤링
- GPT-4o Vision으로 최적 이미지 자동 선정
- Grounding DINO + SAM으로 가구 객체 추출 → LaMa로 인페인팅 전처리
- Metric3D / Depth Pro로 실제 치수(W×H×D) 추정
- UUID로 job_id 생성 후 즉시 반환 (비동기 처리)
- 완료된 결과(job_id, source_url, dimensions, glb_url)를 DB에 저장

**RunPod Serverless (GPU)**:
- TRELLIS로 전처리된 이미지 → `.glb` 3D 모델 생성
- 생성된 `.glb` 파일 S3 업로드 후 URL 반환

---

## 4. 비기능 요구사항 (Non-Functional Requirements)

### NFR-01: 성능
- 3D 모델 생성 목표 시간: 3분 이내 (RunPod GPU 기준)
- API 응답 시간: 일반 엔드포인트 1초 이내
- 프론트엔드 초기 로드: 3초 이내 (PWA)

### NFR-02: 플랫폼
- 모바일 웹 (PWA) — iOS Safari, Android Chrome 지원
- 반응형: 375px 기준 모바일 레이아웃
- AR 기능: 카메라 접근 권한 필요

### NFR-03: 확장성
- MVP 이후 소셜 로그인 및 배치 기록 추가를 고려한 구조 설계
- 인증 없이도 동작하는 API 설계 (Post-MVP 인증 추가 시 최소 변경)

### NFR-04: 보안
- 보안 확장 규칙 생략 (프로토타입/MVP 단계)
- 기본 보안: HTTPS, CORS 설정, API 키 환경변수 관리

---

## 5. 기술 스택 (Tech Stack Decisions)

| 영역 | 기술 | 선택 이유 |
|------|------|-----------|
| **Frontend** | React + Vite + TypeScript + Tailwind CSS | app.html 기반 React, Vite 빌드 속도, TypeScript 타입 안전성, Tailwind 스타일링 |
| **배포 (FE)** | Vercel | PWA 배포 최적, 무료 티어 |
| **Backend API** | Python + FastAPI | AI 라이브러리 호환, 비동기 처리 |
| **API 서버** | AWS EC2 (t3.small) | 저렴, S3 네이티브 연동 |
| **AI Pipeline** | RunPod Serverless GPU | 요청 기반 과금, GPU 비용 절감 |
| **3D 생성** | TRELLIS | 2D-to-3D 생성 모델 |
| **세그멘테이션** | Grounding DINO + SAM | 배경 제거 SOTA |
| **인페인팅** | LaMa | 가림 영역 복원 |
| **치수 추정** | Metric3D / Depth Pro | 단일 이미지 깊이 추정 |
| **3D 뷰어** | Google model-viewer | .glb 웹 렌더링 표준 |
| **AR** | Unity WebGL | app.html 기준, WebGL iframe 통합 |
| **파일 저장** | AWS S3 | .glb 파일 저장 |
| **메타데이터 DB** | PostgreSQL (RDS) | MVP: job 완료 결과 저장 / Post-MVP: 배치 기록 + 로그인 연동 |
| **인증** | 없음 (MVP), 카카오 로그인 (Post-MVP) | 단계적 도입 |

---

## 6. 시스템 아키텍처 개요

```
[사용자 모바일 브라우저]
        |
        v
[React PWA — Vercel]
        |
        v
[FastAPI — AWS EC2]
    |         |         |
    v         v         v
[RunPod  [AWS S3]  [PostgreSQL]
 Serverless] (glb)  (job 결과)
 (3D 생성)
    |
    v
[TRELLIS]

FastAPI 내 AI 처리:
[GPT-4o Vision]
[DINO + SAM + LaMa]
[Metric3D / Depth Pro]
```

---

## 7. 지원 플랫폼 (크롤링 대상)

- 당근마켓 (daangn.com)
- 번개장터 (bunjang.co.kr)
- 중고나라 (junggonara.co.kr)
