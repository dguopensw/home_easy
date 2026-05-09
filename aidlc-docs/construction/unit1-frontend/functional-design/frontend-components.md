# Frontend Components — Unit 1 Frontend
# 집에 가구 쉽다 (Easy Furniture Fit)

---

## HomePage

**Props**: 없음

**State**:
```typescript
// 없음 (더미 데이터로 최근 기록 표시, MVP)
```

**주요 상호작용**:
- "지금 시작하기" 버튼 → `navigate('/UrlInputPage')`
- "전체보기" 버튼 → `navigate('/HistoryPage')`

---

## UrlInputPage

**Props**: 없음

**State**:
```typescript
const [url, setUrl] = useState('')
const [error, setError] = useState<string | null>(null)
const [isLoading, setIsLoading] = useState(false)
const [shake, setShake] = useState(false)
```

**주요 상호작용**:
- URL 입력 → `setUrl`
- 데모 링크 탭 → `setUrl(demoUrl)`
- "3D 모델 생성하기" 탭:
  1. 빈 URL → `setShake(true)` (애니메이션 후 false 복귀)
  2. 미지원 플랫폼 → `setError('현재 당근마켓, 번개장터, 중고나라만 지원합니다')`
  3. 유효 URL → `POST /furniture/gen/start` → `navigate('/LoadingPage', { state: { jobId } })`

**전용 컴포넌트** (`UrlInputPage/components/`):
- `PlatformChip` — 당근/번개/중고나라 플랫폼 칩
- `DemoLinkButton` — 당근마켓 데모 링크 버튼 (1개)

---

## LoadingPage

**Props**: 없음 (jobId는 `useLocation().state`에서 수신)

**State**:
```typescript
const [progress, setProgress] = useState(0)
const [currentStep, setCurrentStep] = useState<PipelineStep>('crawling')
const [error, setError] = useState<PipelineError | null>(null)
```

**STEPS 정의** (app_init.html 기준):
```typescript
const STEPS = [
  { key: 'crawling',        label: '게시글 크롤링',      sub: '이미지·텍스트·치수 정보 수집',      icon: '🔍' },
  { key: 'image_select',    label: '최적 이미지 선정',   sub: 'GPT-4o Vision 분석 중',             icon: '🤖' },
  { key: 'dimension',       label: '치수 측정',           sub: 'Metric3D 깊이 추정 · W×H×D 계산',  icon: '📐' },
  { key: 'preprocess',      label: '배경 제거·전처리',   sub: 'SAM 세그멘테이션 · LaMa 인페인팅',  icon: '✂️' },
  { key: 'model_generate',  label: '3D 모델 생성',        sub: 'TRELLIS 변환 중…',                  icon: '🧊' },
]
```

**주요 상호작용**:
- 마운트 시 SSE 연결 시작
- progress 이벤트 → `setProgress`, `setCurrentStep`
- complete 이벤트 → `navigate('/PreviewPage', { state: { glbUrl, dimensions } })`
- error 이벤트 → `setError`
- 언마운트 시 SSE 연결 종료

**전용 컴포넌트** (`LoadingPage/components/`):
- `StepList` — 단계 리스트 (완료/현재/대기 상태별 UI)
- `BouncingDots` — 현재 단계 바운싱 dot 애니메이션

---

## ModelPreviewPage

**Props**: 없음 (glbUrl, dimensions는 `useLocation().state`에서 수신)

**State**:
```typescript
const [activeTab, setActiveTab] = useState<'3d' | 'dimensions'>('3d')
```

**주요 상호작용**:
- 탭 전환 → `setActiveTab`
- "AR로 배치하기" 버튼 → `navigate('/ARPage', { state: { glbUrl } })`

**전용 컴포넌트** (`PreviewPage/components/`):
- `TabBar` — 3D / 치수 탭 전환
- `DimensionsView` — W·H·D 수치 + 다이어그램

---

## ARPage

**Props**: 없음 (glbUrl은 `useLocation().state`에서 수신)

**State**:
```typescript
const [unityReady, setUnityReady] = useState(false)
const [modelLoaded, setModelLoaded] = useState(false)
const [showHint, setShowHint] = useState(true)    // AR 인식 실패 안내
```

**주요 상호작용**:
- Unity `ready` 이벤트 → `sendGlbToUnity(glbUrl)`
- Unity `modelLoaded` 이벤트 → `setModelLoaded(true)`
- Unity `planeFound` 이벤트 → `setShowHint(false)`
- 10초 후 planeFound 없으면 `setShowHint(true)` 유지 → 안내 메시지 표시
- "촬영" 버튼 → 화면 캡처 + 저장 완료 토스트

**전용 컴포넌트** (`ARPage/components/`):
- `ARHint` — 바닥 인식 안내 오버레이
- `ARControls` — 복제/삭제 버튼 오버레이

---

## 공통 컴포넌트 (`src/components/`)

| 컴포넌트 | Props | 역할 |
|---------|-------|------|
| `Button` | `variant: 'accent' \| 'outline'`, `onClick`, `children` | 공통 버튼 |
| `ProgressBar` | `progress: number` | AI 진행률 바 |
| `Toast` | `message: string`, `visible: boolean` | 일회성 알림 |
| `NavBar` | `title: string`, `onBack?: () => void` | 뒤로가기 + 제목 |
