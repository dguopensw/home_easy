# Domain Entities — Unit 1 Frontend
# 집에 가구 쉽다 (Easy Furniture Fit)

---

## 핵심 데이터 구조

### JobId
```typescript
type JobId = string  // 백엔드에서 발급한 파이프라인 작업 ID
```

### GlbUrl
```typescript
type GlbUrl = string  // S3에 업로드된 .glb 파일의 URL
```

### Dimensions
```typescript
interface Dimensions {
  w: number  // 너비 (cm)
  h: number  // 높이 (cm)
  d: number  // 깊이 (cm)
}
```

### PipelineProgress
```typescript
interface PipelineProgress {
  step: PipelineStep   // 현재 단계
  progress: number     // 전체 진행률 0~100
}

type PipelineStep =
  | 'crawling'          // 0% → 5%
  | 'image_select'      // 5% → 10%
  | 'preprocess'        // 10% → 20%
  | 'dimension'         // 20% → 30%
  | 'model_generate'    // 30% → 95%
  | 'upload'            // 95% → 100%
  | 'complete'
  | 'error'
```

### PipelineResult
```typescript
interface PipelineResult {
  glbUrl: GlbUrl
  dimensions: Dimensions
}
```

### PipelineError
```typescript
interface PipelineError {
  type: 'crawling_failed' | 'generation_failed' | 'unknown'
  message: string
}
```

### SSE 이벤트 (백엔드 → 프론트)
```typescript
// 백엔드가 실제로 보내는 것: step 이름만
interface SSEProgressEvent {
  step: PipelineStep
}
interface SSECompleteEvent {
  status: 'complete'
  glb_url: string
  dimensions: { w: number; h: number; d: number }
}
interface SSEErrorEvent {
  status: 'error'
  type: 'crawling_failed' | 'generation_failed' | 'unknown'
  message: string
}
```

### LoadingPage 내부 State (React useState)
```typescript
// progress는 백엔드에서 받는 게 아니라 프론트에서 step 기반으로 계산
const [currentStep, setCurrentStep] = useState<PipelineStep>('crawling')
const [progress, setProgress] = useState(0)   // 프론트 내부 계산값
const [error, setError] = useState<PipelineError | null>(null)
```

### step → progress 매핑 (프론트 내부 상수)
```typescript
const STEP_PROGRESS: Record<PipelineStep, number> = {
  crawling:       5,
  image_select:   10,
  preprocess:     20,
  dimension:      30,
  model_generate: 95,   // 30%→95% 구간은 시간 기반 애니메이션
  upload:         100,
  complete:       100,
  error:          0,
}
```

### Platform
```typescript
type Platform = 'daangn' | 'bunjang' | 'junggonara' | 'unknown'
```

---

## 화면 간 데이터 전달 (React Router navigate state)

| 출발 | 도착 | 전달 데이터 |
|------|------|------------|
| UrlInputPage | LoadingPage | `{ jobId: JobId }` |
| LoadingPage | ModelPreviewPage | `{ glbUrl: GlbUrl, dimensions: Dimensions }` |
| ModelPreviewPage | ARPage | props: `glbUrl: GlbUrl` |
