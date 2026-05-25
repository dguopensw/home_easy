import BouncingDots from './BouncingDots'

export type PipelineStep =
  | 'crawling'
  | 'image_select'
  | 'preprocess'
  | 'dimension'
  | 'model_generate'
  | 'upload'
  | 'complete'
  | 'error'

export const STEPS: { key: PipelineStep; label: string; icon: string; sub: string }[] = [
  { key: 'crawling',       label: '게시글 크롤링',    icon: '🔍', sub: '이미지 · 텍스트 · 치수 정보 수집' },
  { key: 'image_select',   label: '최적 이미지 선정', icon: '🤖', sub: 'GPT-4o Vision 분석 중' },
  { key: 'preprocess',     label: '배경 제거·전처리', icon: '✂️', sub: 'SAM 세그멘테이션 · LaMa 인페인팅' },
  { key: 'dimension',      label: '치수 측정',        icon: '📐', sub: 'Metric3D 깊이 추정 · W×H×D 계산' },
  { key: 'model_generate', label: '3D 모델 생성',     icon: '🧊', sub: 'TRELLIS 변환 중…' },
]

export const STEP_ORDER = STEPS.map((s) => s.key)

interface StepListProps {
  currentStep: PipelineStep
}

export default function StepList({ currentStep }: StepListProps) {
  const currentIdx = STEP_ORDER.indexOf(currentStep)

  return (
    <div className="flex flex-col gap-[12px]">
      {STEPS.map((step, i) => {
        const done   = i < currentIdx
        const active = i === currentIdx
        const future = i > currentIdx

        return (
          <div
            key={step.key}
            className="flex items-center gap-[12px]"
            style={{ opacity: future ? 0.28 : 1, transition: 'opacity 0.4s' }}
          >
            {/* 상태 인디케이터 */}
            <div
              className="w-[34px] h-[34px] rounded-full flex-shrink-0 flex items-center justify-center transition-all duration-300"
              style={{
                background: done ? 'var(--color-accent)' : active ? 'transparent' : 'rgba(255,255,255,0.05)',
                border: active ? '1.5px solid var(--color-accent)' : 'none',
              }}
            >
              {done ? (
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              ) : active ? (
                <BouncingDots />
              ) : (
                <span className="text-[14px]">{step.icon}</span>
              )}
            </div>

            {/* 레이블 */}
            <div className="flex-1">
              <p
                className="text-[13px] leading-none"
                style={{
                  fontWeight: active || done ? 600 : 400,
                  color: done ? 'rgba(255,255,255,0.55)' : active ? 'white' : 'rgba(255,255,255,0.3)',
                }}
              >
                {step.label}
              </p>
              {active && (
                <p className="text-[11px] mt-[3px]" style={{ color: 'rgba(255,255,255,0.3)' }}>
                  {step.sub}
                </p>
              )}
            </div>

            {done && (
              <span className="text-[11px] font-bold text-accent">완료</span>
            )}
          </div>
        )
      })}
    </div>
  )
}
