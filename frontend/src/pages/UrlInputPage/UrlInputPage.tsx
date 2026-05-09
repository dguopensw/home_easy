import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import NavBar from '@/components/NavBar'

const SAMPLES = [
  { label: '당근마켓 예시', icon: '🥕', url: 'https://www.daangn.com/articles/12345678' },
]

export default function UrlInputPage() {
  const navigate = useNavigate()
  const [url, setUrl] = useState('')
  const [focused, setFocused] = useState(false)
  const [shake, setShake] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const triggerShake = () => {
    setShake(true)
    setTimeout(() => setShake(false), 400)
  }

  const handleSubmit = () => {
    if (!url.trim()) {
      triggerShake()
      inputRef.current?.focus()
      return
    }
    navigate('/loading', { state: { jobId: 'mock-job-id', sourceUrl: url } })
  }

  return (
    <div className="min-h-screen bg-bg flex flex-col">
      <NavBar title="링크 입력" onBack={() => navigate('/home')} />

      <div className="flex-1 px-[24px] pt-[28px] flex flex-col">
        <p className="text-[14px] text-text-secondary leading-[1.65] mb-[28px]">
          당근마켓·번개장터·중고나라 게시글 URL을<br />
          붙여넣으면 나머지는 AI가 다 해드려요
        </p>

        {/* Input */}
        <div
          className={`flex items-center gap-[8px] pl-[16px] pr-[4px] rounded-[18px] bg-surface border transition-all mb-[16px] ${shake ? 'animate-shake' : ''}`}
          style={{
            borderColor: focused ? 'var(--color-accent)' : 'var(--color-border)',
            borderWidth: '1.5px',
            boxShadow: focused ? '0 0 0 3px color-mix(in srgb, var(--color-accent) 12%, transparent)' : 'none',
          }}
        >
          <svg
            width="17" height="17" viewBox="0 0 24 24" fill="none"
            stroke={focused ? 'var(--color-accent)' : 'var(--color-text-secondary)'}
            strokeWidth="2" strokeLinecap="round"
            style={{ flexShrink: 0 }}
          >
            <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
          </svg>
          <input
            ref={inputRef}
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
            placeholder="https://www.daangn.com/articles/..."
            data-testid="url-input-field"
            className="flex-1 py-[12px] text-[13px] text-text-primary placeholder:text-text-secondary bg-transparent border-none outline-none"
          />
          {url && (
            <button
              onClick={() => { setUrl(''); inputRef.current?.focus() }}
              className="w-[30px] h-[30px] rounded-[8px] bg-surface-2 flex items-center justify-center flex-shrink-0 mr-[4px]"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--color-text-secondary)" strokeWidth="2.5">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          )}
        </div>

        {/* Platform chips */}
        <div className="flex gap-[8px] mb-[28px]">
          {[{ n: '당근마켓', e: '🥕' }, { n: '번개장터', e: '⚡' }, { n: '중고나라', e: '🛍️' }].map((p) => (
            <div
              key={p.n}
              className="flex items-center gap-[5px] px-[11px] py-[5px] rounded-[20px] bg-surface-2 border border-border"
            >
              <span className="text-[12px]">{p.e}</span>
              <span className="text-[11px] text-text-secondary font-medium">{p.n}</span>
            </div>
          ))}
        </div>

        {/* Demo card */}
        <div className="bg-surface-2 rounded-[16px] p-[14px] p-[16px]">
          <p className="text-[11px] font-bold text-text-secondary uppercase tracking-[0.08em] mb-[10px]">
            데모 링크로 체험
          </p>
          <div className="flex flex-col gap-[8px]">
            {SAMPLES.map((s) => (
              <button
                key={s.label}
                onClick={() => { setUrl(s.url); setTimeout(() => inputRef.current?.focus(), 50) }}
                className="flex items-center gap-[10px] px-[12px] py-[10px] bg-surface rounded-[10px] border border-border text-left"
              >
                <span className="text-[14px]">{s.icon}</span>
                <span className="flex-1 text-[12px] text-text-secondary truncate">{s.url}</span>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--color-accent)" strokeWidth="2.5">
                  <polyline points="9 18 15 12 9 6" />
                </svg>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* CTA */}
      <div className="px-[24px] pb-[40px] pt-[24px] flex-shrink-0">
        <button
          onClick={handleSubmit}
          data-testid="url-input-submit-button"
          className="w-full py-[17px] rounded-[18px] text-white text-[16px] font-bold flex items-center justify-center gap-[8px] transition-opacity"
          style={{
            background: 'linear-gradient(135deg, var(--color-accent), #E8A070)',
            boxShadow: '0 6px 24px color-mix(in srgb, var(--color-accent) 33%, transparent)',
            opacity: url.trim() ? 1 : 0.5,
          }}
        >
          3D 모델 생성하기
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round">
            <line x1="5" y1="12" x2="19" y2="12" />
            <polyline points="12 5 19 12 12 19" />
          </svg>
        </button>
      </div>
    </div>
  )
}
