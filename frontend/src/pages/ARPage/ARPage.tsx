import { useRef, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import NavBar from '@/components/NavBar'
import Toast from '@/components/Toast'
import ARHint from './components/ARHint'
import ARControls from './components/ARControls'
import DimensionPanel from './components/DimensionPanel'
import IOSFallback from './components/IOSFallback'
import { useWebXR } from './hooks/useWebXR'
import { useARGestures } from './hooks/useARGestures'
import { useDimensionInput } from './hooks/useDimensionInput'
import { useRotationSync } from './hooks/useRotationSync'

function isIOSDevice(): boolean {
  return /iPad|iPhone|iPod/.test(navigator.userAgent) && !(window as unknown as { MSStream?: unknown }).MSStream
}

export default function ARPage() {
  // ── 1. 라우터 ──────────────────────────────────────────────────────────────
  const navigate = useNavigate()
  const { state } = useLocation()

  // ── 2. 파생 값 (Hook 아님, 항상 동일하게 계산) ──────────────────────────
  const sourceUrl: string = state?.sourceUrl ?? ''
  const rawDims = state?.dimensions
  const dimensions: { w: number; h: number; d: number } = rawDims
    ? rawDims.w !== undefined
      ? { w: rawDims.w, h: rawDims.h, d: rawDims.d }
      : { w: rawDims.width ?? 60, h: rawDims.height ?? 80, d: rawDims.depth ?? 40 }
    : { w: 60, h: 80, d: 40 }

  // ── 3. 모든 useState — 항상, 조건 없이 ────────────────────────────────────
  const [glbUrl, setGlbUrl] = useState<string>(state?.glbUrl ?? '')
  const [inputUrl, setInputUrl] = useState('')
  const [toastVisible, setToastVisible] = useState(false)
  const [inputDimensions, setInputDimensions] = useState(dimensions)

  // ── 4. 모든 useRef — 항상, 조건 없이 ─────────────────────────────────────
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const overlayRef = useRef<HTMLDivElement>(null)

  // ── 5. 커스텀 Hook — 항상, 조건 없이 (빈 glbUrl은 훅 내부에서 처리) ──────
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
    applyNewDimensions,
    captureAndShare,
  } = useWebXR({ canvasRef, overlayRef, glbUrl, dimensions: inputDimensions })

  const { rotationDeg, setRotationY, onRotationChange } = useRotationSync(getPlacedModel)

  const {
    rotateLeft,
    rotateRight,
    liftUp,
    liftDown,
    scaleUp,
    scaleDown,
  } = useARGestures({ overlayRef, getPlacedModel, isModelPlaced, onRotationChange })

  const {
    isPanelOpen,
    openPanel,
    setIsPanelOpen,
    draft,
    setDraft,
    applyDimensions,
  } = useDimensionInput(inputDimensions, applyNewDimensions)

  // ── 6. 이벤트 핸들러 (Hook 아님) ──────────────────────────────────────────
  const handleCapture = () => {
    setToastVisible(true)
    setTimeout(() => {
      setToastVisible(false)
      navigate('/result', { state: { sourceUrl } })
    }, 1200)
  }

  const handleBack = () => {
    endSession()
    navigate(-1)
  }

  const handleRotationSliderChange = (deg: number) => {
    setRotationY(deg)
  }

  // ── 7. 조건부 return — 모든 Hook 선언 이후 ────────────────────────────────

  // GLB URL 없음 → 입력 화면
  if (!glbUrl) {
    return (
      <div className="min-h-screen bg-black flex flex-col items-center justify-center p-6 gap-4">
        <div className="absolute top-0 left-0 right-0 z-10">
          <NavBar title="AR 배치" onBack={() => navigate(-1)} />
        </div>

        <p className="text-white text-base font-semibold mt-16">GLB 파일 URL을 입력하세요</p>
        <input
          type="url"
          value={inputUrl}
          onChange={e => setInputUrl(e.target.value)}
          placeholder="https://example.com/model.glb"
          className="w-full max-w-sm px-4 py-3 rounded-xl bg-white/10 text-white placeholder-white/40 border border-white/20 text-sm outline-none"
        />

        <p className="text-white/70 text-sm font-semibold self-start w-full max-w-sm">가구 치수 (cm)</p>
        <div className="w-full max-w-sm flex gap-2">
          {(['w', 'h', 'd'] as const).map((key, i) => (
            <div key={key} className="flex-1 flex flex-col gap-1">
              <label className="text-white/50 text-xs text-center">
                {['너비', '높이', '깊이'][i]}
              </label>
              <input
                type="number"
                inputMode="decimal"
                min={1}
                max={999}
                value={inputDimensions[key]}
                onChange={e =>
                  setInputDimensions(prev => ({ ...prev, [key]: Number(e.target.value) }))
                }
                className="w-full px-3 py-2 rounded-xl bg-white/10 text-white text-sm text-center outline-none border border-white/20"
              />
            </div>
          ))}
        </div>

        <button
          onClick={() => inputUrl.trim() && setGlbUrl(inputUrl.trim())}
          className="px-8 py-3 bg-white text-black rounded-full text-sm font-semibold"
        >
          AR 시작
        </button>
        <button
          onClick={() => setGlbUrl('/example.glb')}
          className="text-white/50 text-xs underline"
        >
          예제 모델로 테스트
        </button>
      </div>
    )
  }

  // iOS → Quick Look 폴백
  if (isIOSDevice()) {
    return <IOSFallback glbUrl={glbUrl} onBack={() => navigate(-1)} />
  }

  // WebXR 미지원
  if (!isSupported && !isSessionActive) {
    return (
      <div className="min-h-screen bg-black flex flex-col items-center justify-center text-white p-6 text-center">
        <div className="absolute top-0 left-0 right-0 z-10">
          <NavBar title="AR 배치" onBack={() => navigate(-1)} />
        </div>
        <p className="text-lg mt-20">
          이 브라우저는 WebAR을 지원하지 않습니다.<br />
          Android Chrome을 사용해 주세요.
        </p>
        <button
          onClick={() => navigate(-1)}
          className="mt-6 px-6 py-3 bg-white text-black rounded-full text-sm font-semibold"
        >
          뒤로 가기
        </button>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-black flex flex-col relative overflow-hidden">
      {/* NavBar: visible on top of WebXR session via z-index */}
      <div className="absolute top-0 left-0 right-0 z-20">
        <NavBar title="AR 배치" onBack={handleBack} />
      </div>

      {/* WebXR rendering canvas */}
      <canvas
        ref={canvasRef}
        className="w-full flex-1"
        style={{ minHeight: '100vh', display: 'block' }}
      />

      {/* DOM overlay: rendered on top of WebXR session */}
      <div
        ref={overlayRef}
        className="absolute inset-0 z-10"
        style={{ pointerEvents: isModelPlaced ? 'auto' : 'none' }}
      >
        {/* Pre-placement: full-screen transparent tap area */}
        {!isModelPlaced && isSessionActive && (
          <div
            className="absolute inset-0"
            style={{ pointerEvents: 'auto' }}
            onClick={placeModel}
          />
        )}
      </div>

      {/* AR start button (before session) */}
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

      {/* Hint: shown before model placement */}
      {isSessionActive && !isModelPlaced && <ARHint />}

      {/* Error display */}
      {error && (
        <div className="absolute bottom-24 left-4 right-4 z-30 bg-red-500 text-white p-3 rounded-xl text-sm text-center">
          {error}
        </div>
      )}

      {/* Interaction controls: shown after model placement */}
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
          onDimensionAdjust={openPanel}
          onShare={captureAndShare}
          rotationDeg={rotationDeg}
          onRotationSliderChange={handleRotationSliderChange}
        />
      )}

      {/* Dimension input panel */}
      <DimensionPanel
        isOpen={isPanelOpen}
        draft={draft}
        onClose={() => setIsPanelOpen(false)}
        onDraftChange={setDraft}
        onApply={applyDimensions}
      />

      <Toast message="저장 완료!" visible={toastVisible} />
    </div>
  )
}