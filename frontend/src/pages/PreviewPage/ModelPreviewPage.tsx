import { useEffect, useRef, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'

declare global {
  namespace JSX {
    interface IntrinsicElements {
      'model-viewer': React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement>, HTMLElement> & {
        src?: string
        alt?: string
        'auto-rotate'?: string | boolean
        'auto-rotate-delay'?: string
        'rotation-per-second'?: string
        'camera-controls'?: string | boolean
        'shadow-intensity'?: string
        exposure?: string
        'environment-image'?: string
      }
    }
  }
}

interface Dimensions {
  width: number
  height: number
  depth: number
}

export default function ModelPreviewPage() {
  const navigate = useNavigate()
  const { state } = useLocation()
  const glbUrl: string = state?.glbUrl ?? ''
  const dimensions: Dimensions = state?.dimensions ?? { width: 120, height: 85, depth: 60 }
  const sourceUrl: string = state?.sourceUrl ?? ''

  const [tab, setTab] = useState<'3d' | '치수'>('3d')
  const [loaded, setLoaded] = useState(false)
  const mvRef = useRef<HTMLElement>(null)

  useEffect(() => {
    const el = mvRef.current
    if (!el || tab !== '3d') return
    setLoaded(false)
    const onLoad = () => setLoaded(true)
    const onError = () => setLoaded(true)
    el.addEventListener('load', onLoad)
    el.addEventListener('error', onError)
    const fallback = setTimeout(() => setLoaded(true), 6000)
    return () => {
      el.removeEventListener('load', onLoad)
      el.removeEventListener('error', onError)
      clearTimeout(fallback)
    }
  }, [tab, glbUrl])

  return (
    <div className="min-h-screen bg-bg flex flex-col">
      {/* 헤더 */}
      <div className="flex items-center px-[16px] py-[12px] gap-[8px] flex-shrink-0">
        <button
          onClick={() => navigate(-1)}
          data-testid="navbar-back-button"
          className="w-[38px] h-[38px] rounded-full bg-surface-2 flex items-center justify-center text-text-primary flex-shrink-0"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
            <path d="m15 18-6-6 6-6" />
          </svg>
        </button>
        <span className="text-[17px] font-bold text-text-primary">3D 미리보기</span>

        {/* 탭 스위처 */}
        <div className="ml-auto flex gap-[2px] bg-surface-2 rounded-[10px] p-[3px]">
          {(['3d', '치수'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              data-testid={`preview-tab-${t}`}
              className="px-[12px] py-[5px] rounded-[8px] text-[12px] font-bold transition-all duration-200"
              style={{
                background: tab === t ? 'var(--color-surface)' : 'transparent',
                color: tab === t ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
              }}
            >
              {t.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {tab === '3d' ? (
        <>
          {/* model-viewer 뷰포트 */}
          <div
            className="mx-[20px] rounded-[24px] overflow-hidden relative"
            style={{ background: 'var(--color-surface-2)', height: 320 }}
          >
            {/* @ts-ignore model-viewer 웹 컴포넌트 */}
            <model-viewer
              ref={mvRef}
              src={glbUrl}
              alt="3D 가구 모델"
              camera-controls=""
              auto-rotate=""
              auto-rotate-delay="500"
              rotation-per-second="20deg"
              shadow-intensity="1"
              exposure="1"
              environment-image="neutral"
              data-testid="preview-model-viewer"
              style={{ width: '100%', height: '100%', background: 'transparent' } as React.CSSProperties}
            />

            {/* 로딩 오버레이 */}
            {!loaded && (
              <div
                className="absolute inset-0 flex flex-col items-center justify-center gap-[10px]"
                style={{ background: 'rgba(237,231,222,0.85)', backdropFilter: 'blur(2px)' }}
              >
                <div
                  className="w-[32px] h-[32px] rounded-full border-[3px] border-t-accent"
                  style={{ borderColor: 'color-mix(in srgb, var(--color-accent) 25%, transparent)', borderTopColor: 'var(--color-accent)', animation: 'spin 0.9s linear infinite' }}
                />
                <span className="text-[12px] text-text-secondary font-semibold">3D 모델 불러오는 중…</span>
              </div>
            )}

            {/* 드래그 힌트 */}
            <div className="absolute bottom-[14px] left-0 right-0 flex justify-center pointer-events-none">
              <div
                className="flex items-center gap-[5px] px-[12px] py-[5px] rounded-[20px]"
                style={{ background: 'rgba(0,0,0,0.45)', backdropFilter: 'blur(6px)' }}
              >
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.8)" strokeWidth="2">
                  <path d="M18 11V6a2 2 0 0 0-4 0v5" />
                  <path d="M14 10V4a2 2 0 0 0-4 0v6" />
                  <path d="M10 10.5V6a2 2 0 0 0-4 0v8" />
                  <path d="M6 14v-3a2 2 0 0 0-4 0v4c0 4 4 7 8 7s8-3 8-7v-3" />
                </svg>
                <span className="text-[11px]" style={{ color: 'rgba(255,255,255,0.85)' }}>드래그하여 회전 · 핀치하여 확대</span>
              </div>
            </div>
          </div>

          {/* 정보 카드 */}
          <div className="mx-[20px] mt-[16px] bg-surface rounded-[20px] p-[16px] border border-border flex-shrink-0">
            <div className="flex justify-between items-start mb-[14px]">
              <div>
                <p className="text-[17px] font-extrabold text-text-primary mb-[4px]">소파 (원목 2인)</p>
                <p className="text-[12px] text-text-secondary">당근마켓 게시글 · 3D 생성 완료</p>
              </div>
              <div
                className="px-[10px] py-[4px] rounded-[20px] text-[11px] font-bold text-accent border flex-shrink-0"
                style={{ background: 'color-mix(in srgb, var(--color-accent) 10%, transparent)', borderColor: 'color-mix(in srgb, var(--color-accent) 33%, transparent)' }}
              >
                3D 완성
              </div>
            </div>
            <div className="flex gap-[8px]">
              {([['W', dimensions.width], ['H', dimensions.height], ['D', dimensions.depth]] as const).map(([k, v]) => (
                <div key={k} className="flex-1 bg-surface-2 rounded-[12px] py-[10px] text-center">
                  <p className="text-[11px] text-text-secondary mb-[2px]">{k}</p>
                  <p className="text-[15px] font-bold text-text-primary">{v}cm</p>
                </div>
              ))}
            </div>
          </div>
        </>
      ) : (
        /* 치수 탭 */
        <div className="flex-1 overflow-y-auto px-[20px]">
          {/* SVG 도식 */}
          <div className="bg-surface-2 rounded-[20px] overflow-hidden mb-[16px]">
            <div className="aspect-video flex items-center justify-center" style={{ background: '#D4C5B2' }}>
              <svg viewBox="0 0 280 160" style={{ width: '80%', maxWidth: 260 }}>
                <rect x="40" y="60" width="200" height="60" rx="6" fill="var(--color-accent)" opacity="0.8" />
                <rect x="38" y="48" width="22" height="74" rx="5" fill="var(--color-accent)" />
                <rect x="220" y="48" width="22" height="74" rx="5" fill="var(--color-accent)" />
                <rect x="40" y="82" width="200" height="20" rx="4" fill="var(--color-accent)" opacity="0.5" />
                {/* 너비 화살표 */}
                <line x1="38" y1="140" x2="242" y2="140" stroke="#E07A5F" strokeWidth="1.5" />
                <line x1="38" y1="135" x2="38" y2="145" stroke="#E07A5F" strokeWidth="1.5" />
                <line x1="242" y1="135" x2="242" y2="145" stroke="#E07A5F" strokeWidth="1.5" />
                <text x="140" y="155" textAnchor="middle" fill="#E07A5F" fontSize="11" fontWeight="700">W · {dimensions.width}cm</text>
                {/* 높이 화살표 */}
                <line x1="14" y1="48" x2="14" y2="122" stroke="#3B82F6" strokeWidth="1.5" />
                <line x1="9" y1="48" x2="19" y2="48" stroke="#3B82F6" strokeWidth="1.5" />
                <line x1="9" y1="122" x2="19" y2="122" stroke="#3B82F6" strokeWidth="1.5" />
                <text x="8" y="90" textAnchor="middle" fill="#3B82F6" fontSize="10" fontWeight="700" transform="rotate(-90,8,88)">H · {dimensions.height}</text>
                {/* 깊이 라벨 */}
                <text x="140" y="105" textAnchor="middle" fill="rgba(255,255,255,0.6)" fontSize="10">D · {dimensions.depth}cm</text>
              </svg>
            </div>
          </div>

          {/* 치수 목록 */}
          <div className="flex flex-col gap-[10px] pb-[24px]">
            {[
              { label: '너비 (W)', value: `${dimensions.width} cm`, color: '#E07A5F' },
              { label: '높이 (H)', value: `${dimensions.height} cm`, color: '#3B82F6' },
              { label: '깊이 (D)', value: `${dimensions.depth} cm`, color: '#10B981' },
            ].map((row) => (
              <div key={row.label} className="flex justify-between items-center px-[16px] py-[12px] bg-surface rounded-[12px] border border-border">
                <span className="text-[14px] text-text-secondary">{row.label}</span>
                <span className="text-[14px] font-bold" style={{ color: row.color }}>{row.value}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* CTA */}
      <div className="px-[20px] pb-[36px] pt-[16px] flex-shrink-0">
        <button
          onClick={() => navigate('/ar', { state: { glbUrl, dimensions: { w: dimensions.width, h: dimensions.height, d: dimensions.depth }, sourceUrl } })}
          data-testid="preview-ar-button"
          className="w-full py-[17px] rounded-[18px] text-white text-[16px] font-bold flex items-center justify-center gap-[10px]"
          style={{
            background: 'linear-gradient(135deg, var(--color-accent), #E8A070)',
            boxShadow: '0 6px 24px color-mix(in srgb, var(--color-accent) 33%, transparent)',
          }}
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.8" strokeLinecap="round">
            <path d="M12 2l8 4v6c0 4-3.5 7.7-8 9-4.5-1.3-8-5-8-9V6z" />
            <path d="M12 8v8M8 10l4-2 4 2" />
          </svg>
          AR로 방에 배치하기
        </button>
      </div>
    </div>
  )
}
