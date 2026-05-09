interface ProgressBarProps {
  progress: number // 0~100
}

export default function ProgressBar({ progress }: ProgressBarProps) {
  return (
    <div className="h-[7px] bg-black/8 rounded-[7px] overflow-hidden">
      <div
        className="h-full rounded-[7px] transition-[width] duration-150 ease-linear bg-accent"
        style={{ width: `${progress}%` }}
      />
    </div>
  )
}
