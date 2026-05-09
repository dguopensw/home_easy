interface ButtonProps {
  variant?: 'accent' | 'outline'
  onClick?: () => void
  disabled?: boolean
  children: React.ReactNode
  className?: string
  'data-testid'?: string
}

export default function Button({
  variant = 'accent',
  onClick,
  disabled,
  children,
  className = '',
  'data-testid': testId,
}: ButtonProps) {
  const base =
    'w-full py-[16px] rounded-[16px] font-semibold text-[16px] transition-opacity active:opacity-70'
  const variants = {
    accent: 'bg-accent text-white',
    outline: 'border border-accent text-accent bg-transparent',
  }

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      data-testid={testId}
      className={`${base} ${variants[variant]} ${disabled ? 'opacity-40' : ''} ${className}`}
    >
      {children}
    </button>
  )
}
