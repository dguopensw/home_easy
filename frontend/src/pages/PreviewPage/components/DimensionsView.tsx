interface Dimensions {
  w: number
  h: number
  d: number
}

interface DimensionsViewProps {
  dimensions: Dimensions
}

const DIM_LABELS = [
  { key: 'w' as const, label: '너비 (W)', color: '#E57373' },
  { key: 'h' as const, label: '높이 (H)', color: '#64B5F6' },
  { key: 'd' as const, label: '깊이 (D)', color: '#81C784' },
]

export default function DimensionsView({ dimensions }: DimensionsViewProps) {
  return (
    <div className="flex flex-col gap-[16px]">
      <p className="text-[13px] text-text-secondary">AI가 추정한 실제 치수예요</p>
      <div className="flex flex-col gap-[12px]">
        {DIM_LABELS.map(({ key, label, color }) => (
          <div key={key} className="flex items-center justify-between bg-surface rounded-[14px] px-[18px] py-[14px]">
            <div className="flex items-center gap-[10px]">
              <div className="w-[10px] h-[10px] rounded-full" style={{ background: color }} />
              <span className="text-[14px] text-text-secondary">{label}</span>
            </div>
            <span className="text-[20px] font-bold text-text-primary">
              {dimensions[key]}
              <span className="text-[13px] font-normal text-text-secondary ml-[4px]">cm</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
