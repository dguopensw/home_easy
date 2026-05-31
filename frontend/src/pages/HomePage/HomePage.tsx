import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

const HOW_TO = [
  { icon: '🔗', title: '링크 붙여넣기',   desc: '당근·번개장터 게시글 URL만 입력하세요' },
  { icon: '✨', title: 'AI 3D 모델 생성', desc: 'AI가 자동으로 3D 모델을 만들어드려요' },
  { icon: '🛋️', title: '내 방에 AR 배치', desc: '실제 공간에 가구를 가상으로 배치해요' },
]

const RECENT_ITEMS = [
  { label: '소파',  color: '#C4A882' },
  { label: '책상',  color: '#7D5C3C' },
  { label: '의자',  color: '#B09070' },
]

const CUBE_FACES = [
  { transform: 'translateZ(32px)',                 opacity: 1    },
  { transform: 'rotateY(180deg) translateZ(32px)', opacity: 0.45 },
  { transform: 'rotateY(90deg) translateZ(32px)',  opacity: 0.7  },
  { transform: 'rotateY(-90deg) translateZ(32px)', opacity: 0.55 },
  { transform: 'rotateX(90deg) translateZ(32px)',  opacity: 0.35 },
  { transform: 'rotateX(-90deg) translateZ(32px)', opacity: 0.85 },
]

const DECO_RECTS = [
  { w: 90, h: 90, top: -10, right: 120, rot: 25,  op: 0.18 },
  { w: 70, h: 70, top:  30, right:  20, rot: 15,  op: 0.22 },
  { w: 50, h: 50, top: 120, right:  60, rot: -10, op: 0.14 },
]

export default function HomePage() {
  const navigate = useNavigate()
  const [angle, setAngle] = useState(0)

  useEffect(() => {
    const id = setInterval(() => setAngle((a) => a + 1.2), 40)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="min-h-screen bg-bg flex flex-col overflow-y-auto">
      {/* Hero */}
      <div className="relative overflow-hidden flex-shrink-0" style={{ background: '#2C1810', minHeight: 300 }}>
        {/* 장식 사각형 */}
        {DECO_RECTS.map((r, i) => (
          <div
            key={i}
            className="absolute rounded-[18px]"
            style={{
              top: r.top, right: r.right,
              width: r.w, height: r.h,
              border: '2px solid rgba(255,255,255,0.5)',
              transform: `rotate(${r.rot}deg)`,
              opacity: r.op,
            }}
          />
        ))}

        {/* 회전 큐브 */}
        <div className="absolute" style={{ top: 18, right: 16, width: 100, height: 100, perspective: 380 }}>
          <div
            style={{
              width: 64, height: 64,
              margin: '18px auto',
              transformStyle: 'preserve-3d',
              transform: `rotateY(${angle}deg) rotateX(20deg)`,
              position: 'relative',
            }}
          >
            {CUBE_FACES.map((face, i) => (
              <div
                key={i}
                style={{
                  position: 'absolute', width: 64, height: 64,
                  background: 'var(--color-accent)',
                  opacity: face.opacity,
                  border: '1px solid rgba(255,255,255,0.15)',
                  transform: face.transform,
                }}
              />
            ))}
          </div>
        </div>

        {/* 텍스트 + CTA */}
        <div className="px-[24px] pt-[48px] pb-[36px]">
          <h1 className="text-[36px] font-extrabold text-white leading-[1.15] mb-[12px]">
            집에<br />가구 쉽다
          </h1>
          <p className="text-[14px] leading-[1.65] mb-[28px]" style={{ color: 'rgba(255,255,255,0.6)', maxWidth: 210 }}>
            사진 한 장으로 중고 가구를<br />내 방에 3D로 배치해보세요
          </p>
          <button
            onClick={() => navigate('/url-input')}
            data-testid="home-start-button"
            className="flex items-center gap-[8px] text-white text-[15px] font-bold px-[22px] py-[13px] rounded-full border-none"
            style={{
              background: 'var(--color-accent)',
              boxShadow: '0 4px 20px color-mix(in srgb, var(--color-accent) 40%, transparent)',
            }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.8" strokeLinecap="round">
              <line x1="5" y1="12" x2="19" y2="12" />
              <polyline points="12 5 19 12 12 19" />
            </svg>
            지금 시작하기
          </button>
        </div>
      </div>

      {/* How it works */}
      <div className="px-[24px] pt-[28px]">
        <p className="text-[12px] font-bold text-text-secondary uppercase tracking-[0.12em] mb-[20px]">
          How it works
        </p>
        <div className="flex flex-col">
          {HOW_TO.map((item, i) => (
            <div key={i} className="flex gap-[16px] relative" style={{ paddingBottom: i < HOW_TO.length - 1 ? 26 : 0 }}>
              {/* 수직 연결선 */}
              {i < HOW_TO.length - 1 && (
                <div
                  className="absolute"
                  style={{ left: 19, top: 42, width: 2, height: 'calc(100% - 18px)', background: 'var(--color-border)' }}
                />
              )}
              {/* 아이콘 원 */}
              <div
                className="w-[40px] h-[40px] rounded-full bg-surface-2 border border-border flex items-center justify-center flex-shrink-0 relative z-10"
              >
                <span className="text-[18px]">{item.icon}</span>
              </div>
              <div className="pt-[8px]">
                <p className="text-[11px] font-bold text-accent mb-[3px]">0{i + 1}</p>
                <p className="text-[15px] font-bold text-text-primary mb-[3px]">{item.title}</p>
                <p className="text-[13px] text-text-secondary leading-[1.55]">{item.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
      

    </div>
  )
}
