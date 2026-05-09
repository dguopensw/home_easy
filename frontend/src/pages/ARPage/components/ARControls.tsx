interface ARControlsProps {
  onDuplicate: () => void
  onDelete: () => void
  onCapture: () => void
}

export default function ARControls({ onDuplicate, onDelete, onCapture }: ARControlsProps) {
  return (
    <div className="absolute bottom-[40px] left-[24px] right-[24px] z-20 flex justify-between items-center">
      <div className="flex gap-[12px]">
        <button
          onClick={onDuplicate}
          data-testid="ar-duplicate-button"
          className="w-[52px] h-[52px] rounded-full flex items-center justify-center"
          style={{ background: 'rgba(255,255,255,0.15)', backdropFilter: 'blur(8px)' }}
        >
          <span className="text-[22px]">⊕</span>
        </button>
        <button
          onClick={onDelete}
          data-testid="ar-delete-button"
          className="w-[52px] h-[52px] rounded-full flex items-center justify-center"
          style={{ background: 'rgba(255,255,255,0.15)', backdropFilter: 'blur(8px)' }}
        >
          <span className="text-[22px]">🗑️</span>
        </button>
      </div>

      <button
        onClick={onCapture}
        data-testid="ar-capture-button"
        className="w-[64px] h-[64px] rounded-full border-[3px] border-white flex items-center justify-center"
        style={{ background: 'rgba(255,255,255,0.2)', backdropFilter: 'blur(8px)' }}
      >
        <div className="w-[48px] h-[48px] rounded-full bg-white" />
      </button>
    </div>
  )
}
