import { useNavigate } from 'react-router-dom'
import NavBar from '@/components/NavBar'

const DUMMY_HISTORY = [
  { id: 1, name: '원목 소파', platform: '당근마켓', date: '2024.01.15' },
  { id: 2, name: '책상 의자', platform: '번개장터', date: '2024.01.12' },
  { id: 3, name: '침대 프레임', platform: '중고나라', date: '2024.01.10' },
  { id: 4, name: '책장', platform: '당근마켓', date: '2024.01.08' },
  { id: 5, name: '식탁', platform: '번개장터', date: '2024.01.05' },
  { id: 6, name: '옷장', platform: '중고나라', date: '2024.01.03' },
]

export default function HistoryPage() {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen bg-bg flex flex-col">
      <NavBar title="배치 기록" onBack={() => navigate(-1)} />

      <div className="flex-1 px-[16px] pt-[16px]">
        <div className="grid grid-cols-2 gap-[12px]">
          {DUMMY_HISTORY.map((item) => (
            <div
              key={item.id}
              data-testid={`history-item-${item.id}`}
              className="bg-surface rounded-[16px] overflow-hidden"
            >
              <div className="aspect-square bg-surface-2 flex items-center justify-center text-[40px]">
                🛋️
              </div>
              <div className="p-[12px]">
                <p className="text-[14px] font-semibold text-text-primary truncate">{item.name}</p>
                <p className="text-[12px] text-text-secondary mt-[2px]">{item.platform} · {item.date}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
