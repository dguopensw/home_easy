import { useEffect } from 'react'
import NavBar from '@/components/NavBar'

interface IOSFallbackProps {
  glbUrl: string
  onBack: () => void
}

export default function IOSFallback({ glbUrl, onBack }: IOSFallbackProps) {
  // Dynamically load model-viewer script
  useEffect(() => {
    if (customElements.get('model-viewer')) return
    const script = document.createElement('script')
    script.type = 'module'
    script.src = 'https://ajax.googleapis.com/ajax/libs/model-viewer/3.5.0/model-viewer.min.js'
    document.head.appendChild(script)
  }, [])

  return (
    <div className="min-h-screen bg-black flex flex-col">
      <NavBar title="AR 배치 (iOS)" onBack={onBack} />
      <div className="flex-1 flex flex-col items-center justify-center p-6 text-white text-center gap-4">
        <p className="text-sm text-gray-400">
          iOS에서는 AR Quick Look을 통해 AR 배치를 지원합니다.
        </p>
        {/* @ts-ignore model-viewer web component */}
        <model-viewer
          src={glbUrl}
          ar
          ar-modes="quick-look"
          camera-controls
          alt="3D 가구 모델"
          style={{ width: '100%', height: '60vh' }}
        />
      </div>
    </div>
  )
}
