interface NavBarProps {
  title: string
  onBack?: () => void
}

export default function NavBar({ title, onBack }: NavBarProps) {
  return (
    <div className="flex items-center px-[16px] py-[12px]">
      {onBack && (
        <button
          onClick={onBack}
          data-testid="navbar-back-button"
          className="mr-[12px] p-[4px] -ml-[4px] text-text-primary"
          aria-label="뒤로가기"
        >
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>
      )}
      <h1 className="text-[16px] font-semibold text-text-primary">{title}</h1>
    </div>
  )
}
