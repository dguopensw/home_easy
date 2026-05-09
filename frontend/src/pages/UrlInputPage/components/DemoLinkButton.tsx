interface DemoLinkButtonProps {
  onClick: () => void
}

const DEMO_URL = 'https://www.daangn.com/articles/example'

export default function DemoLinkButton({ onClick }: DemoLinkButtonProps) {
  return (
    <button
      onClick={onClick}
      data-testid="url-input-demo-button"
      className="flex items-center gap-[6px] px-[14px] py-[8px] rounded-full bg-surface border border-border"
    >
      <span className="text-[14px]">🥕</span>
      <span className="text-[13px] text-text-secondary">당근마켓 예시</span>
    </button>
  )
}

export { DEMO_URL }
