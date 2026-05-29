//현준님 여기서 작업하시면 됩니다! 아래 코드들은 현준님 상황에 맞춰 수정하셔도 됩니다







import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import NavBar from '@/components/NavBar'
import Toast from '@/components/Toast'
import ARHint from './components/ARHint'
import ARControls from './components/ARControls'






declare global {
  interface Window {
    unityInstance?: {
      SendMessage: (obj: string, method: string, param?: string) => void
    }
  }
}

interface Dimensions {
  width: number
  height: number
  depth: number
}

const HINT_TIMEOUT_MS = 10_000

export default function ARPage() {
  const navigate = useNavigate()
  const { state } = useLocation()
  const glbUrl: string = state?.glbUrl ?? ''
  const sourceUrl: string = state?.sourceUrl ?? ''
  // AI가 측정한 가구 치수 (PreviewPage에서 state로 전달받음)
  const dimensions: Dimensions = useMemo(
    () => state?.dimensions ?? { width: 0, height: 0, depth: 0 },
    [state],
  )

  const iframeRef = useRef<HTMLIFrameElement>(null)
  const [unityReady, setUnityReady] = useState(false)
  const [showHint, setShowHint] = useState(true)
  const [toastVisible, setToastVisible] = useState(false)

  useEffect(() => {
    const handleUnityReady = () => {
      setUnityReady(true)
      window.unityInstance?.SendMessage('ARController', 'LoadModel', glbUrl)
      // dimensions(AI 측정 치수)는 state로 전달받아 둠 — Unity 스케일 적용 연동은 이후 단계
    }
    const handlePlaneFound = () => setShowHint(false)

    window.addEventListener('unity:ready', handleUnityReady)
    window.addEventListener('unity:planeFound', handlePlaneFound)

    const hintTimer = setTimeout(() => setShowHint(true), HINT_TIMEOUT_MS)

    return () => {
      window.removeEventListener('unity:ready', handleUnityReady)
      window.removeEventListener('unity:planeFound', handlePlaneFound)
      clearTimeout(hintTimer)
    }
  }, [glbUrl, dimensions, unityReady])

  const handleDuplicate = () => {
    window.unityInstance?.SendMessage('PlacementManager', 'DuplicateSelected')
  }

  const handleDelete = () => {
    window.unityInstance?.SendMessage('PlacementManager', 'DeleteSelected')
  }

  const handleCapture = () => {
    window.unityInstance?.SendMessage('ARController', 'CaptureScreen')
    setToastVisible(true)
    setTimeout(() => {
      setToastVisible(false)
      navigate('/result', { state: { sourceUrl } })
    }, 1200)
  }

  return (
    <div className="min-h-screen bg-black flex flex-col">
      <div className="absolute top-0 left-0 right-0 z-10">
        <NavBar title="AR 배치" onBack={() => navigate(-1)} />
      </div>

      {/* Unity WebGL iframe */}
      <iframe
        ref={iframeRef}
        src="/unity/index.html"
        data-testid="ar-unity-iframe"
        className="w-full flex-1 border-none"
        style={{ minHeight: '100vh' }}
        allow="camera; gyroscope; accelerometer"
        title="AR 배치 화면"
      />

      {showHint && <ARHint />}

      <ARControls
        onDuplicate={handleDuplicate}
        onDelete={handleDelete}
        onCapture={handleCapture}
      />

      <Toast message="저장 완료!" visible={toastVisible} />
    </div>
  )
}
