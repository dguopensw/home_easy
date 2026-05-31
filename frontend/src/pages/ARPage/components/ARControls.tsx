import RotationSlider from './RotationSlider'

interface ARControlsProps {
  onRotateLeft: () => void
  onRotateRight: () => void
  onLiftUp: () => void
  onLiftDown: () => void
  onScaleUp: () => void
  onScaleDown: () => void
  onReset: () => void
  onCapture: () => void
  onDimensionAdjust: () => void
  onShare?: () => void
  rotationDeg: number
  onRotationSliderChange: (deg: number) => void
}

const btnClass = 'w-[44px] h-[44px] rounded-full flex items-center justify-center text-white text-[18px]'
const btnStyle = { background: 'rgba(255,255,255,0.15)', backdropFilter: 'blur(8px)' } as const

export default function ARControls({
  onRotateLeft,
  onRotateRight,
  onLiftUp,
  onLiftDown,
  onScaleUp,
  onScaleDown,
  onReset,
  onCapture,
  onDimensionAdjust,
  onShare,
  rotationDeg,
  onRotationSliderChange,
}: ARControlsProps) {
  return (
    <div className="absolute bottom-[40px] left-[16px] right-[16px] z-20 pointer-events-auto flex flex-col gap-[12px]">
      {/* Rotation slider */}
      <RotationSlider rotationDeg={rotationDeg} onChange={onRotationSliderChange} />

      {/* Top row: rotation, lift, scale, reset, dimension */}
      <div className="flex justify-center gap-[10px]">
        <button onClick={onRotateLeft} style={btnStyle} className={btnClass} aria-label="좌회전">
          <span>↺</span>
        </button>
        <button onClick={onRotateRight} style={btnStyle} className={btnClass} aria-label="우회전">
          <span>↻</span>
        </button>
        <button onClick={onLiftUp} style={btnStyle} className={btnClass} aria-label="위로">
          <span>↑</span>
        </button>
        <button onClick={onLiftDown} style={btnStyle} className={btnClass} aria-label="아래로">
          <span>↓</span>
        </button>
        <button onClick={onScaleUp} style={btnStyle} className={btnClass} aria-label="크게">
          <span>+</span>
        </button>
        <button onClick={onScaleDown} style={btnStyle} className={btnClass} aria-label="작게">
          <span>-</span>
        </button>
        <button onClick={onReset} style={btnStyle} className={btnClass} aria-label="재배치">
          <span>⟳</span>
        </button>
        <button onClick={onDimensionAdjust} style={btnStyle} className={btnClass} aria-label="치수 조정">
          <span style={{ fontSize: 14 }}>cm</span>
        </button>
      </div>

      {/* Bottom row: capture + share */}
      <div className="flex justify-center items-center gap-[16px]">
        {onShare && (
          <button
            onClick={onShare}
            style={btnStyle}
            className={btnClass}
            aria-label="공유"
          >
            <span>⬆</span>
          </button>
        )}
        <button
          onClick={onCapture}
          data-testid="ar-capture-button"
          className="w-[64px] h-[64px] rounded-full border-[3px] border-white flex items-center justify-center"
          style={{ background: 'rgba(255,255,255,0.2)', backdropFilter: 'blur(8px)' }}
          aria-label="캡처"
        >
          <div className="w-[48px] h-[48px] rounded-full bg-white" />
        </button>
      </div>
    </div>
  )
}
