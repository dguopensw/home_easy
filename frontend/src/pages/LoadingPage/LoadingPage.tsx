import { useEffect, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import StepList, { PipelineStep, STEP_ORDER, STEPS } from './components/StepList'

const STEP_PROGRESS: Record<PipelineStep, number> = {
  crawling:       5,
  image_select:   10,
  preprocess:     20,
  dimension:      30,
  model_generate: 95,
  upload:         100,
  complete:       100,
  error:          0,
}

const MOCK_STEPS: PipelineStep[] = ['crawling', 'image_select', 'preprocess', 'dimension', 'model_generate', 'complete']
const STEP_INTERVAL_MS = 1200

const CUBE_FACES = [
  { transform: 'translateZ(44px)',                 opacity: 1    },
  { transform: 'rotateY(180deg) translateZ(44px)', opacity: 0.45 },
  { transform: 'rotateY(90deg) translateZ(44px)',  opacity: 0.7  },
  { transform: 'rotateY(-90deg) translateZ(44px)', opacity: 0.55 },
  { transform: 'rotateX(90deg) translateZ(44px)',  opacity: 0.35 },
  { transform: 'rotateX(-90deg) translateZ(44px)', opacity: 0.85 },
]

export default function LoadingPage() {
  const navigate = useNavigate()
  const { state } = useLocation()
  const jobId: string = state?.jobId ?? ''
  const sourceUrl: string = state?.sourceUrl ?? ''

  const [stepIdx, setStepIdx] = useState(0)
  const [angle, setAngle] = useState(0)

  const currentStep = MOCK_STEPS[Math.min(stepIdx, MOCK_STEPS.length - 1)]
  const progress = STEP_PROGRESS[currentStep] ?? 0
  const currentStepData = STEPS.find((s) => s.key === currentStep)

  // 큐브 회전
  useEffect(() => {
    const id = setInterval(() => setAngle((a) => a + 2), 30)
    return () => clearInterval(id)
  }, [])

  // 단계 진행
  useEffect(() => {
    if (!jobId) {
      navigate('/home', { replace: true })
      return
    }
    if (stepIdx >= MOCK_STEPS.length - 1) {
      const timer = setTimeout(() => {
        navigate('/preview', {
          state: {
            glbUrl: '/example.glb',
            dimensions: { width: 120, height: 85, depth: 60 },
            sourceUrl,
          },
        })
      }, 600)
      return () => clearTimeout(timer)
    }
    const timer = setTimeout(() => setStepIdx((i) => i + 1), STEP_INTERVAL_MS)
    return () => clearTimeout(timer)
  }, [stepIdx, jobId, navigate])

  return (
    <div className="min-h-screen bg-[#1A130C] flex flex-col items-center justify-center px-[28px] relative overflow-hidden">
      {/* 앰비언트 글로우 */}
      <div
        className="absolute top-[35%] left-1/2 -translate-x-1/2 -translate-y-1/2 w-[280px] h-[280px] rounded-full pointer-events-none"
        style={{ background: 'var(--color-accent)', opacity: 0.07, filter: 'blur(70px)' }}
      />

      <div className="w-full flex flex-col items-center gap-[32px] relative z-10">
        {/* 3D 큐브 */}
        <div className="flex-shrink-0 flex flex-col items-center" style={{ width: 150, height: 150, perspective: 500 }}>
          <div
            style={{
              width: 88,
              height: 88,
              margin: '31px auto 0',
              transformStyle: 'preserve-3d',
              transform: `rotateY(${angle}deg) rotateX(22deg)`,
              position: 'relative',
            }}
          >
            {CUBE_FACES.map((face, i) => (
              <div
                key={i}
                style={{
                  position: 'absolute',
                  width: 88,
                  height: 88,
                  background: 'var(--color-accent)',
                  opacity: face.opacity,
                  border: '1px solid rgba(255,255,255,0.12)',
                  transform: face.transform,
                }}
              />
            ))}
          </div>
          {/* 그림자 */}
          <div
            style={{
              width: 60,
              height: 10,
              borderRadius: '50%',
              background: 'rgba(0,0,0,0.35)',
              filter: 'blur(8px)',
              marginTop: 4,
            }}
          />
        </div>

        {/* 타이틀 */}
        <div className="text-center">
          <h2 className="text-[22px] font-extrabold text-white mb-[6px]">3D 모델 생성 중</h2>
          <p className="text-[13px]" style={{ color: 'rgba(255,255,255,0.4)' }}>
            게시글 분석 중…
          </p>
        </div>

        {/* 진행률 */}
        <div className="w-full">
          <div className="flex justify-between items-center mb-[8px]">
            <span className="text-[13px] font-semibold" style={{ color: 'rgba(255,255,255,0.7)' }}>
              {currentStepData?.icon}&nbsp;{currentStepData?.label}
            </span>
            <span className="text-[14px] font-bold text-accent">{progress}%</span>
          </div>

          {/* 그라디언트 진행바 */}
          <div className="w-full h-[7px] rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.08)' }}>
            <div
              className="h-full rounded-full transition-[width] duration-150 ease-linear"
              style={{
                width: `${progress}%`,
                background: 'linear-gradient(90deg, var(--color-accent), #E8B070)',
                boxShadow: '0 0 16px color-mix(in srgb, var(--color-accent) 50%, transparent)',
              }}
            />
          </div>

          <p className="text-[12px] mt-[6px]" style={{ color: 'rgba(255,255,255,0.3)' }}>
            {currentStepData?.sub}
          </p>
        </div>

        {/* 단계 리스트 */}
        <div className="w-full">
          <StepList currentStep={currentStep} />
        </div>
      </div>
    </div>
  )
}
