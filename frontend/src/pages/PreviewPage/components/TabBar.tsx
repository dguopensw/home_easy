interface TabBarProps {
  activeTab: '3d' | 'dimensions'
  onChange: (tab: '3d' | 'dimensions') => void
}

export default function TabBar({ activeTab, onChange }: TabBarProps) {
  return (
    <div className="flex bg-surface-2 rounded-[12px] p-[4px]">
      {(['3d', 'dimensions'] as const).map((tab) => (
        <button
          key={tab}
          onClick={() => onChange(tab)}
          data-testid={`preview-tab-${tab}`}
          className="flex-1 py-[8px] rounded-[10px] text-[14px] font-medium transition-all duration-200"
          style={{
            background: activeTab === tab ? 'white' : 'transparent',
            color: activeTab === tab ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
            boxShadow: activeTab === tab ? '0 1px 4px rgba(0,0,0,0.08)' : 'none',
          }}
        >
          {tab === '3d' ? '3D 보기' : '치수 정보'}
        </button>
      ))}
    </div>
  )
}
