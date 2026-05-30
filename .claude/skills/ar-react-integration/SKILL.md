---
name: ar-react-integration
description: |
  useWebXR과 useARGestures 훅을 React 컴포넌트로 통합하는 가이드. Unity iframe 제거, WebXR canvas + DOM overlay 구조 설정, 기존 라우터 state 연동, TailwindCSS v4 기반 버튼 UI 확장 방법을 다룬다. ar-react-builder 에이전트가 사용한다.
---

# AR React 통합 가이드

## React + WebXR 마운트 패턴

WebXR은 명령형 API다. React의 선언형 모델과 충돌하지 않으려면:
- WebXR 세션 객체는 `useRef`에 보관 (리렌더링 없이 유지)
- `isSessionActive`, `isModelPlaced` 같은 UI 상태만 `useState`로 관리
- 세션 시작/종료는 사용자 gesture 이벤트(버튼 클릭)에서만 호출

---

## ARPage.tsx 전체 구조

```tsx
import { useEffect, useRef, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import NavBar from '@/components/NavBar'
import Toast from '@/components/Toast'
import ARHint from './components/ARHint'
import ARControls from './components/ARControls'
import IOSFallback from './components/IOSFallback'
import { useWebXR } from './hooks/useWebXR'
import { useARGestures } from './hooks/useARGestures'

function isIOSDevice(): boolean {
  return /iPad|iPhone|iPod/.test(navigator.userAgent) && !(window as any).MSStream
}

export default function ARPage() {
  const navigate = useNavigate()
  const { state } = useLocation()

  // 라우터 state 계약: 변경 금지
  const glbUrl: string = state?.glbUrl ?? ''
  const dimensions = state?.dimensions ?? { w: 60, h: 80, d: 40 }  // cm 단위 기본값
  const sourceUrl: string = state?.sourceUrl ?? ''

  const canvasRef = useRef<HTMLCanvasElement>(null)
  const overlayRef = useRef<HTMLDivElement>(null)
  const [toastVisible, setToastVisible] = useState(false)

  const {
    isSupported,
    isSessionActive,
    isModelPlaced,
    error,
    startSession,
    endSession,
    placeModel,
    resetModel,
    getPlacedModel,
  } = useWebXR({ canvasRef, overlayRef, glbUrl, dimensions })

  const {
    rotateLeft, rotateRight,
    liftUp, liftDown,
    scaleUp, scaleDown,
  } = useARGestures({ overlayRef, getPlacedModel, isModelPlaced })

  const handleCapture = () => {
    // WebXR에서는 canvas.toDataURL() 또는 스크린샷 API 사용
    setToastVisible(true)
    setTimeout(() => {
      setToastVisible(false)
      navigate('/result', { state: { sourceUrl } })
    }, 1200)
  }

  // iOS: model-viewer 폴백
  if (isIOSDevice()) {
    return <IOSFallback glbUrl={glbUrl} onBack={() => navigate(-1)} />
  }

  // WebXR 미지원
  if (!isSupported && !isSessionActive) {
    return (
      <div className="min-h-screen bg-black flex flex-col items-center justify-center text-white p-6 text-center">
        <NavBar title="AR 배치" onBack={() => navigate(-1)} />
        <p className="text-lg mt-20">
          이 브라우저는 WebAR을 지원하지 않습니다.<br />
          Android Chrome을 사용해 주세요.
        </p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-black flex flex-col relative overflow-hidden">
      {/* NavBar는 WebXR 세션 중에도 overlay 위에 표시 */}
      <div className="absolute top-0 left-0 right-0 z-20">
        <NavBar title="AR 배치" onBack={() => { endSession(); navigate(-1) }} />
      </div>

      {/* WebXR 렌더링 canvas */}
      <canvas
        ref={canvasRef}
        className="w-full flex-1"
        style={{ minHeight: '100vh', display: 'block' }}
      />

      {/* DOM overlay: WebXR 세션 중 위에 그려지는 레이어 */}
      <div
        ref={overlayRef}
        className="absolute inset-0 z-10"
        style={{ pointerEvents: isModelPlaced ? 'auto' : 'none' }}
      >
        {/* 배치 전: 투명 탭 영역 — reticle 위치에 배치 */}
        {!isModelPlaced && isSessionActive && (
          <div
            className="absolute inset-0"
            style={{ pointerEvents: 'auto' }}
            onClick={placeModel}
          />
        )}
      </div>

      {/* AR 시작 버튼 (세션 전) */}
      {!isSessionActive && (
        <div className="absolute inset-0 flex items-center justify-center z-30">
          <button
            onClick={startSession}
            className="px-8 py-4 bg-white text-black rounded-full text-lg font-semibold shadow-lg"
          >
            AR 시작
          </button>
        </div>
      )}

      {/* 힌트: 배치 전에만 표시 */}
      {isSessionActive && !isModelPlaced && <ARHint />}

      {/* 에러 표시 */}
      {error && (
        <div className="absolute bottom-24 left-4 right-4 z-30 bg-red-500 text-white p-3 rounded-xl text-sm text-center">
          {error}
        </div>
      )}

      {/* 인터랙션 컨트롤: 배치 후에만 표시 */}
      {isModelPlaced && (
        <ARControls
          onRotateLeft={rotateLeft}
          onRotateRight={rotateRight}
          onLiftUp={liftUp}
          onLiftDown={liftDown}
          onScaleUp={scaleUp}
          onScaleDown={scaleDown}
          onReset={resetModel}
          onCapture={handleCapture}
        />
      )}

      <Toast message="저장 완료!" visible={toastVisible} />
    </div>
  )
}
```

---

## ARControls.tsx 확장 패턴

기존 파일을 읽은 뒤, props 인터페이스를 확장하고 새 버튼을 추가한다.

```tsx
interface ARControlsProps {
  onRotateLeft: () => void
  onRotateRight: () => void
  onLiftUp: () => void
  onLiftDown: () => void
  onScaleUp: () => void
  onScaleDown: () => void
  onReset: () => void
  onCapture: () => void
}

const BtnStyle = "w-[44px] h-[44px] rounded-full flex items-center justify-center text-white text-[18px]"
const BtnBg = { background: 'rgba(255,255,255,0.15)', backdropFilter: 'blur(8px)' }

export default function ARControls({ ... }: ARControlsProps) {
  return (
    <div className="absolute bottom-[40px] left-[16px] right-[16px] z-20">
      {/* 상단 행: 회전 + 리프트 + 스케일 */}
      <div className="flex justify-center gap-[10px] mb-[16px]">
        <button onClick={onRotateLeft}  style={BtnBg} className={BtnStyle}>↺</button>
        <button onClick={onRotateRight} style={BtnBg} className={BtnStyle}>↻</button>
        <button onClick={onLiftUp}      style={BtnBg} className={BtnStyle}>↑</button>
        <button onClick={onLiftDown}    style={BtnBg} className={BtnStyle}>↓</button>
        <button onClick={onScaleUp}     style={BtnBg} className={BtnStyle}>+</button>
        <button onClick={onScaleDown}   style={BtnBg} className={BtnStyle}>-</button>
        <button onClick={onReset}       style={BtnBg} className={BtnStyle}>⟳</button>
      </div>
      {/* 하단: 캡처 버튼 (중앙) */}
      <div className="flex justify-center">
        <button
          onClick={onCapture}
          className="w-[64px] h-[64px] rounded-full border-[3px] border-white flex items-center justify-center"
          style={{ background: 'rgba(255,255,255,0.2)', backdropFilter: 'blur(8px)' }}
        >
          <div className="w-[48px] h-[48px] rounded-full bg-white" />
        </button>
      </div>
    </div>
  )
}
```

---

## IOSFallback.tsx

```tsx
interface IOSFallbackProps {
  glbUrl: string
  onBack: () => void
}

export default function IOSFallback({ glbUrl, onBack }: IOSFallbackProps) {
  // model-viewer 커스텀 엘리먼트 선언
  // @ts-ignore
  if (!customElements.get('model-viewer')) {
    const script = document.createElement('script')
    script.type = 'module'
    script.src = 'https://ajax.googleapis.com/ajax/libs/model-viewer/3.5.0/model-viewer.min.js'
    document.head.appendChild(script)
  }

  return (
    <div className="min-h-screen bg-black flex flex-col">
      <NavBar title="AR 배치 (iOS)" onBack={onBack} />
      <div className="flex-1 flex flex-col items-center justify-center p-6 text-white text-center gap-4">
        <p className="text-sm text-gray-400">
          iOS에서는 AR Quick Look을 통해 AR 배치를 지원합니다.
        </p>
        {/* @ts-ignore — model-viewer는 웹 컴포넌트 */}
        <model-viewer
          src={glbUrl}
          ar
          ar-modes="quick-look"
          camera-controls
          style={{ width: '100%', height: '60vh' }}
        />
      </div>
    </div>
  )
}
```

---

## 라우터 state 계약 (변경 금지)

기존 PreviewPage/ResultPage와의 연동 계약:

```typescript
// ARPage로 navigate할 때 전달하는 state
interface ARPageState {
  glbUrl: string        // S3 GLB URL
  dimensions?: {        // cm 단위, 선택적
    w: number
    h: number
    d: number
  }
  sourceUrl: string     // 원본 상품 URL (결과 페이지용)
}
```

`dimensions`가 없는 경우 기본값 `{ w: 60, h: 80, d: 40 }`을 사용한다.

---

## 주의사항

- **canvas display:block**: `canvas`의 기본 display는 inline이라 하단에 여백이 생긴다. `display: block` 명시 필요
- **overlay pointer-events**: 배치 전 탭 영역만 `pointer-events: auto`, 나머지는 `none`
- **endSession on back**: NavBar의 onBack에서 `endSession()`을 호출해야 카메라 리소스가 해제됨
- **HTTPS**: `vite --https`나 ngrok 없이는 로컬에서 WebXR 테스트 불가
