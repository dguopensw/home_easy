# Business Logic Model — Unit 1 Frontend
# 집에 가구 쉽다 (Easy Furniture Fit)

---

## 전체 사용자 흐름

```
HomePage
  → "지금 시작하기" 탭
  → UrlInputPage

UrlInputPage
  → URL 입력
  → [BR-01-1] 빈 URL → 흔들림 애니메이션, 중단
  → [BR-01-2] 미지원 플랫폼 → 에러 메시지, 중단
  → POST /furniture/gen/start → { jobId }
  → navigate('/LoadingPage', { state: { jobId } })

LoadingPage
  → useLocation().state에서 jobId 수신
  → SSE 연결: GET /furniture/gen/status/{jobId}
  → progress 이벤트 → progress/currentStep 업데이트
  → complete 이벤트 → navigate('/PreviewPage', { state: { glbUrl, dimensions } })
  → error 이벤트 → [BR-04] 에러 UI 표시

ModelPreviewPage
  → useLocation().state에서 glbUrl, dimensions 수신
  → 기본 탭: 3D → model-viewer에 glbUrl 로드
  → 치수 탭 → dimensions 표시
  → "AR로 배치하기" 탭 → navigate('/ARPage')에 glbUrl props 전달

ARPage
  → glbUrl props 수신
  → Unity WebGL iframe 로드
  → Unity 준비 완료 → sendGlbToUnity(glbUrl)
  → Unity 이벤트 수신 (planeFound, placed 등)
```

---

## UrlInputPage 로직

```
사용자 URL 입력
  │
  ▼
"3D 모델 생성하기" 탭
  │
  ├─ [빈 URL] → 흔들림 애니메이션 + 포커스 이동
  │
  ├─ [미지원 플랫폼] → 에러 메시지 표시
  │
  └─ [유효한 URL] → POST /furniture/gen/start
                      │
                      ├─ 성공 → jobId 수신 → navigate('/LoadingPage')
                      └─ 실패 → 에러 토스트
```

---

## LoadingPage SSE 처리 로직

```
마운트
  │
  ▼
EventSource('/furniture/gen/status/{jobId}') 생성
  │
  ├─ onmessage (progress) → { step, progress } → 상태 업데이트
  │     └─ 단계별 UI: 완료(✓) / 현재(바운싱 dot) / 대기(흐린 아이콘)
  │
  ├─ onmessage (complete) → { glbUrl, dimensions }
  │     └─ EventSource.close()
  │     └─ navigate('/PreviewPage', { state: { glbUrl, dimensions } })
  │
  ├─ onmessage (error) → { type, message }
  │     └─ EventSource.close()
  │     └─ 에러 UI 표시 [BR-04]
  │
  └─ 언마운트 → EventSource.close() (cleanup)
```

---

## ARPage Unity 브리지 로직

```
마운트
  │
  ▼
Unity WebGL iframe 로드 (public/unity/index.html)
  │
  ▼
window.addEventListener('unity:ready')
  │
  ▼
unityInstance.SendMessage('ARController', 'LoadModel', glbUrl)
  │
  ├─ window.addEventListener('unity:modelLoaded') → 배치 UI 활성화
  ├─ window.addEventListener('unity:planeFound')  → 바닥 인식 안내 해제
  └─ window.addEventListener('unity:placed')      → 조작 UI 표시
```
