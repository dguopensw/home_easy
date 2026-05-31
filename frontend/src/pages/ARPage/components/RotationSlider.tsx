interface RotationSliderProps {
  rotationDeg: number
  onChange: (deg: number) => void
}

export default function RotationSlider({ rotationDeg, onChange }: RotationSliderProps) {
  return (
    <div className="flex items-center gap-2 px-2">
      <span className="text-white/60 text-xs">0°</span>
      <input
        type="range"
        min={0}
        max={360}
        step={1}
        value={rotationDeg}
        onChange={e => onChange(Number(e.target.value))}
        onTouchStart={e => e.stopPropagation()}
        className="flex-1 accent-white h-1 cursor-pointer"
        aria-label="회전 슬라이더"
      />
      <span className="text-white/60 text-xs">360°</span>
    </div>
  )
}
