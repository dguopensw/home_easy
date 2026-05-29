import type { Dimensions } from '../hooks/useDimensionInput'

interface DimensionPanelProps {
  isOpen: boolean
  draft: Dimensions
  onClose: () => void
  onDraftChange: (dims: Dimensions) => void
  onApply: () => void
}

export default function DimensionPanel({
  isOpen,
  draft,
  onClose,
  onDraftChange,
  onApply,
}: DimensionPanelProps) {
  if (!isOpen) return null

  const fields: { key: keyof Dimensions; label: string }[] = [
    { key: 'w', label: '너비 (W)' },
    { key: 'h', label: '높이 (H)' },
    { key: 'd', label: '깊이 (D)' },
  ]

  return (
    <div
      className="fixed inset-0 z-50 flex items-end"
      onClick={onClose}
    >
      <div
        className="w-full rounded-t-2xl p-6 flex flex-col gap-4"
        style={{ background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(12px)' }}
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-1">
          <span className="text-white font-semibold text-base">치수 조정</span>
          <button onClick={onClose} className="text-white/50 text-sm">닫기</button>
        </div>

        {fields.map(({ key, label }) => (
          <div key={key} className="flex items-center gap-3">
            <span className="text-white/70 text-sm w-20">{label}</span>
            <input
              type="number"
              inputMode="decimal"
              min={1}
              max={999}
              value={draft[key]}
              onChange={e =>
                onDraftChange({ ...draft, [key]: Number(e.target.value) })
              }
              className="flex-1 px-3 py-2 rounded-xl bg-white/10 text-white text-sm outline-none border border-white/20"
            />
            <span className="text-white/50 text-sm">cm</span>
          </div>
        ))}

        <button
          onClick={onApply}
          className="mt-2 w-full py-3 rounded-xl bg-white text-black font-semibold text-sm"
        >
          적용
        </button>
      </div>
    </div>
  )
}
