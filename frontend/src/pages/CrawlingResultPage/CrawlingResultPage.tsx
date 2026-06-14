import { useEffect, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import NavBar from '@/components/NavBar'
import { ScrapeResponse, scrapeUrl, startProcess } from '@/api/furniture'

type Phase = 'loading' | 'error' | 'result'

const SCRAPE_STEPS = [
  { key: 'crawling', label: '게시글 크롤링', icon: '🔍' },
  { key: 'image_selection', label: '최적 이미지 선정', icon: '🤖' },
]

export default function CrawlingResultPage() {
  const navigate = useNavigate()
  const { state } = useLocation()
  const sourceUrl = (state?.sourceUrl as string) ?? ''

  const [phase, setPhase] = useState<Phase>('loading')
  const [scrapeData, setScrapeData] = useState<ScrapeResponse | null>(null)
  const [errorMessage, setErrorMessage] = useState('')
  const [progress, setProgress] = useState(0)
  const [currentScrapeStep, setCurrentScrapeStep] = useState(0)
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!sourceUrl) {
      navigate('/url-input', { replace: true })
      return
    }

    let cancelled = false

    const fakeProgress = setInterval(() => {
      setProgress((p) => {
        if (p < 15) { setCurrentScrapeStep(0); return p + 1 }
        if (p < 30) { setCurrentScrapeStep(1); return p + 1 }
        return p
      })
    }, 120)

    scrapeUrl(sourceUrl)
      .then((data) => {
        if (cancelled) return
        clearInterval(fakeProgress)
        setProgress(100)
        setCurrentScrapeStep(SCRAPE_STEPS.length)
        setScrapeData(data)
        setSelectedIndex(data.ai_recommended_image_index)
        setTimeout(() => { if (!cancelled) setPhase('result') }, 400)
      })
      .catch(() => {
        if (cancelled) return
        clearInterval(fakeProgress)
        const mock: ScrapeResponse = {
          scrape_id: 'mock_scrape_001',
          title: '소파',
          description: '상태 좋은 원목 소파입니다. 직접 수령 부탁드립니다.',
          price: '150,000원',
          platform: 'daangn',
          image_urls: [
            'https://placehold.co/400x300/D4845A/white?text=Image+1',
            'https://placehold.co/400x300/E8A070/white?text=Image+2',
            'https://placehold.co/400x300/8A7460/white?text=Image+3',
            'https://placehold.co/400x300/C4A882/white?text=Image+4',
          ],
          ai_recommended_image_index: 0,
          ranked_candidate_indices: [0, 2, 1, 3],
          furniture_guess: { type: 'sofa', confidence: 'high' },
          dimensions_from_listing: { width_cm: 120, depth_cm: 60, height_cm: 85 },
        }
        setProgress(100)
        setCurrentScrapeStep(SCRAPE_STEPS.length)
        setScrapeData(mock)
        setSelectedIndex(mock.ai_recommended_image_index)
        setTimeout(() => { if (!cancelled) setPhase('result') }, 400)
      })

    return () => { cancelled = true; clearInterval(fakeProgress) }
  }, [sourceUrl, navigate])

  const handleProcess = async () => {
    if (!scrapeData || submitting) return
    setSubmitting(true)
    const furnitureType = scrapeData.furniture_guess?.type
    try {
      const { job_id } = await startProcess(scrapeData.scrape_id, selectedIndex)
      navigate('/loading', { state: { jobId: job_id, sourceUrl, furnitureType } })
    } catch {
      navigate('/loading', { state: { jobId: 'mock_job_001', sourceUrl, furnitureType } })
    }
  }

  /* ── 로딩 화면 ── */
  if (phase === 'loading') {
    return (
      <div className="min-h-screen bg-bg flex flex-col">
        <NavBar title="스크래핑" onBack={() => navigate('/url-input')} />
        <div className="flex-1 flex flex-col items-center justify-center px-[28px]">
          {/* 스피너 */}
          <div
            className="w-[48px] h-[48px] rounded-full border-[3px] mb-[24px]"
            style={{
              borderColor: 'var(--color-border)',
              borderTopColor: 'var(--color-accent)',
              animation: 'spin 0.8s linear infinite',
            }}
          />
          <p className="text-[15px] font-semibold text-text-primary mb-[4px]">
            상품 정보를 가져오는 중...
          </p>
          <p className="text-[12px] text-text-secondary mb-[24px]">{sourceUrl}</p>

          {/* 프로그레스 바 */}
          <div className="w-full max-w-[320px] mb-[20px]">
            <div className="flex justify-between items-center mb-[6px]">
              <span className="text-[12px] font-semibold text-text-secondary">
                {currentScrapeStep < SCRAPE_STEPS.length
                  ? SCRAPE_STEPS[currentScrapeStep].label
                  : '완료'}
              </span>
              <span className="text-[13px] font-bold text-accent">{progress}%</span>
            </div>
            <div className="w-full h-[6px] rounded-full overflow-hidden bg-surface-2">
              <div
                className="h-full rounded-full transition-[width] duration-150"
                style={{
                  width: `${progress}%`,
                  background: 'linear-gradient(90deg, var(--color-accent), #E8A070)',
                }}
              />
            </div>
          </div>

          {/* 단계 리스트 */}
          <div className="w-full max-w-[320px] flex flex-col gap-[10px]">
            {SCRAPE_STEPS.map((step, i) => {
              const done = i < currentScrapeStep
              const active = i === currentScrapeStep
              return (
                <div
                  key={step.key}
                  className="flex items-center gap-[10px]"
                  style={{ opacity: !done && !active ? 0.35 : 1 }}
                >
                  <div
                    className="w-[28px] h-[28px] rounded-full flex items-center justify-center flex-shrink-0"
                    style={{
                      background: done
                        ? 'var(--color-accent)'
                        : active
                          ? 'var(--color-surface-2)'
                          : 'var(--color-surface-2)',
                      border: active ? '1.5px solid var(--color-accent)' : 'none',
                    }}
                  >
                    {done ? (
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3" strokeLinecap="round">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    ) : (
                      <span className="text-[12px]">{step.icon}</span>
                    )}
                  </div>
                  <span
                    className="text-[13px]"
                    style={{
                      fontWeight: active || done ? 600 : 400,
                      color: done
                        ? 'var(--color-text-secondary)'
                        : active
                          ? 'var(--color-text-primary)'
                          : 'var(--color-text-secondary)',
                    }}
                  >
                    {step.label}
                  </span>
                  {done && (
                    <span className="ml-auto text-[11px] font-bold text-accent">완료</span>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      </div>
    )
  }

  /* ── 에러 화면 ── */
  if (phase === 'error') {
    return (
      <div className="min-h-screen bg-bg flex flex-col">
        <NavBar title="스크래핑" onBack={() => navigate('/url-input')} />
        <div className="flex-1 flex flex-col items-center justify-center px-[28px]">
          <div
            className="w-[64px] h-[64px] rounded-full flex items-center justify-center mb-[16px]"
            style={{ background: '#FDECEA' }}
          >
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#D32F2F" strokeWidth="2" strokeLinecap="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="15" y1="9" x2="9" y2="15" />
              <line x1="9" y1="9" x2="15" y2="15" />
            </svg>
          </div>
          <p className="text-[16px] font-bold text-text-primary mb-[6px]">스크래핑 실패</p>
          <p className="text-[13px] text-text-secondary text-center mb-[28px]">{errorMessage}</p>
          <button
            onClick={() => navigate('/url-input')}
            className="px-[24px] py-[12px] rounded-[14px] text-[14px] font-semibold text-white"
            style={{ background: 'var(--color-accent)' }}
          >
            다시 시도하기
          </button>
        </div>
      </div>
    )
  }

  /* ── 결과 화면 ── */
  if (!scrapeData) return null
  const { image_urls, ai_recommended_image_index, ranked_candidate_indices, title, price, furniture_guess, dimensions_from_listing, description } = scrapeData

  return (
    <div className="min-h-screen bg-bg flex flex-col">
      <NavBar title="이미지 선택" onBack={() => navigate('/url-input')} />

      <div className="flex-1 overflow-y-auto px-[24px] pt-[8px] pb-[160px]">
        {/* 상품 정보 카드 */}
        <div className="bg-surface rounded-[16px] border border-border p-[16px] mb-[20px]">
          <div className="flex items-center gap-[6px] mb-[8px]">
            <span className="text-[11px] font-bold text-accent uppercase tracking-[0.05em]">상품 정보</span>
          </div>
          <h2 className="text-[15px] font-bold text-text-primary leading-[1.4] mb-[6px]">{title}</h2>
          <div className="flex items-center gap-[8px] flex-wrap mb-[6px]">
            {price && (
              <span className="text-[14px] font-bold text-accent">{price}</span>
            )}
            {furniture_guess && (
              <span className="px-[8px] py-[2px] rounded-[8px] bg-surface-2 text-[11px] font-semibold text-text-secondary">
                {furniture_guess.type}
                {furniture_guess.confidence === 'high' && ' ✓'}
              </span>
            )}
          </div>
          {dimensions_from_listing && (
            <div className="flex items-center gap-[4px] mb-[6px]">
              <span className="text-[11px] text-text-secondary">판매글 치수:</span>
              <span className="text-[11px] font-semibold text-text-primary">
                {dimensions_from_listing.width_cm} × {dimensions_from_listing.depth_cm} × {dimensions_from_listing.height_cm} cm
              </span>
            </div>
          )}
          {description && (
            <p className="text-[12px] text-text-secondary leading-[1.5] mt-[4px] line-clamp-2">{description}</p>
          )}
        </div>

        {/* 선택된 이미지 프리뷰 */}
        <div className="mb-[20px]">
          <div className="relative w-full rounded-[16px] overflow-hidden border border-border bg-surface">
            <img
              src={image_urls[selectedIndex]}
              alt="선택된 이미지"
              crossOrigin="anonymous"
              referrerPolicy="no-referrer"
              className="w-full object-contain"
              style={{ aspectRatio: '4/3', background: '#F0EBE3' }}
            />
            {selectedIndex === ai_recommended_image_index && (
              <div
                className="absolute top-[10px] left-[10px] flex items-center gap-[4px] px-[10px] py-[4px] rounded-[8px] text-white text-[11px] font-bold"
                style={{ background: 'var(--color-accent)' }}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round">
                  <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14l-5-4.87 6.91-1.01L12 2z" />
                </svg>
                AI 추천
              </div>
            )}
          </div>
        </div>

        {/* 이미지 선택 섹션 */}
        <div className="mb-[12px]">
          <div className="flex items-center gap-[8px] mb-[4px]">
            <span className="text-[11px] font-bold text-accent uppercase tracking-[0.05em]">이미지 선택</span>
          </div>
          <p className="text-[12px] text-text-secondary">
            AI 추천 이미지가 강조 표시됩니다. 다른 이미지를 클릭해 선택을 바꿀 수 있습니다.
          </p>
        </div>

        {/* 이미지 그리드 */}
        <div className="grid grid-cols-3 gap-[8px]">
          {image_urls.map((url, i) => {
            const isSelected = i === selectedIndex
            const isRecommended = i === ai_recommended_image_index
            const rank = ranked_candidate_indices.indexOf(i)

            return (
              <button
                key={i}
                onClick={() => setSelectedIndex(i)}
                className="relative rounded-[12px] overflow-hidden border-2 transition-all"
                style={{
                  borderColor: isSelected ? 'var(--color-accent)' : 'var(--color-border)',
                  boxShadow: isSelected
                    ? '0 0 0 3px color-mix(in srgb, var(--color-accent) 18%, transparent)'
                    : 'none',
                }}
              >
                <img
                  src={url}
                  alt={`후보 ${i + 1}`}
                  crossOrigin="anonymous"
                  referrerPolicy="no-referrer"
                  className="w-full object-cover"
                  style={{ aspectRatio: '1/1', background: '#F0EBE3' }}
                />
                {isRecommended && (
                  <div
                    className="absolute top-[4px] right-[4px] w-[20px] h-[20px] rounded-full flex items-center justify-center"
                    style={{ background: 'var(--color-accent)' }}
                  >
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3" strokeLinecap="round">
                      <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14l-5-4.87 6.91-1.01L12 2z" />
                    </svg>
                  </div>
                )}
                {rank >= 0 && rank < 3 && (
                  <div
                    className="absolute bottom-[4px] left-[4px] w-[18px] h-[18px] rounded-full flex items-center justify-center text-[9px] font-bold text-white"
                    style={{ background: 'rgba(0,0,0,0.55)' }}
                  >
                    {rank + 1}
                  </div>
                )}
                {isSelected && (
                  <div className="absolute inset-0 flex items-center justify-center" style={{ background: 'rgba(212,132,90,0.18)' }}>
                    <div
                      className="w-[28px] h-[28px] rounded-full flex items-center justify-center"
                      style={{ background: 'var(--color-accent)' }}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    </div>
                  </div>
                )}
              </button>
            )
          })}
        </div>

        {/* 선택 레이블 */}
        <div className="mt-[12px] flex items-center gap-[6px]">
          <span className="text-[12px] text-text-secondary">선택된 이미지:</span>
          <span className="text-[12px] font-bold text-text-primary">
            {selectedIndex + 1}번
            {selectedIndex === ai_recommended_image_index && ' (AI 추천)'}
          </span>
        </div>
      </div>

      {/* 하단 CTA */}
      <div className="fixed bottom-0 left-0 right-0 px-[24px] pb-[40px] pt-[16px] bg-gradient-to-t from-bg via-bg to-transparent">
        <button
          onClick={handleProcess}
          disabled={submitting}
          className="w-full py-[17px] rounded-[18px] text-white text-[16px] font-bold flex items-center justify-center gap-[8px] transition-opacity"
          style={{
            background: 'linear-gradient(135deg, var(--color-accent), #E8A070)',
            boxShadow: '0 6px 24px color-mix(in srgb, var(--color-accent) 33%, transparent)',
            opacity: submitting ? 0.5 : 1,
          }}
        >
          {submitting ? '처리 시작 중...' : '이 이미지로 처리하기'}
          {!submitting && (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round">
              <line x1="5" y1="12" x2="19" y2="12" />
              <polyline points="12 5 19 12 12 19" />
            </svg>
          )}
        </button>
      </div>
    </div>
  )
}
