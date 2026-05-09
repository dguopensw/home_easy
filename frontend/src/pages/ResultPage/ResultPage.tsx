import { useNavigate, useLocation } from 'react-router-dom'

export default function ResultPage() {
  const navigate = useNavigate()
  const { state } = useLocation()
  const sourceUrl: string = state?.sourceUrl ?? 'https://www.daangn.com/articles/12345678'

  return (
    <div className="min-h-screen bg-bg flex flex-col">
      <div className="flex-1 flex flex-col items-center justify-center px-[28px] py-[24px]">

        {/* 완료 아이콘 */}
        <div
          className="w-[90px] h-[90px] rounded-full flex items-center justify-center mb-[22px]"
          style={{
            background: 'linear-gradient(135deg, var(--color-accent), #E8A070)',
            boxShadow: '0 14px 36px color-mix(in srgb, var(--color-accent) 31%, transparent)',
          }}
        >
          <svg width="42" height="42" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round">
            <polyline points="20 6 9 17 4 12" />
          </svg>
        </div>

        <h2 className="text-[26px] font-extrabold text-text-primary mb-[8px]">배치 완료!</h2>
        <p className="text-[14px] text-text-secondary text-center leading-[1.7] mb-[36px]">
          3D 배치 이미지가 저장되었어요.
        </p>

        {/* 결과 카드 */}
        <div className="w-full bg-surface rounded-[20px] overflow-hidden border border-border mb-[28px]">
          {/* 썸네일 — 사선 줄무늬 패턴 */}
          <div
            className="w-full flex items-center justify-center"
            style={{
              aspectRatio: '16/9',
              backgroundImage: 'repeating-linear-gradient(45deg, #C4B5A2, #C4B5A2 8px, #D4C5B2 8px, #D4C5B2 16px)',
            }}
          >
            <div
              className="px-[18px] py-[8px] rounded-[10px] text-[12px] font-semibold"
              style={{ background: 'rgba(255,255,255,0.8)', color: '#7A6048' }}
            >
              AR 배치 결과
            </div>
          </div>

          {/* 카드 하단 정보 */}
          <div className="px-[16px] py-[14px] flex justify-between items-center">
            <div>
              <p className="text-[15px] font-bold text-text-primary">소파 (원목 2인)</p>
              <p className="text-[12px] text-text-secondary">방 배치 완료 · 방금 전</p>
            </div>
            {/* 별점 */}
            <div className="flex gap-[2px]">
              {[1, 2, 3, 4, 5].map((s) => (
                <svg key={s} width="14" height="14" viewBox="0 0 24 24" fill={s <= 4 ? '#E8A84C' : 'none'} stroke="#E8A84C" strokeWidth="2">
                  <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
                </svg>
              ))}
            </div>
          </div>
        </div>

        {/* 버튼 */}
        <div className="flex flex-col gap-[10px] w-full">
          <button
            data-testid="result-share-button"
            className="w-full py-[16px] rounded-[18px] text-white text-[15px] font-bold flex items-center justify-center gap-[8px]"
            style={{
              background: 'linear-gradient(135deg, var(--color-accent), #E8A070)',
            }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.8" strokeLinecap="round">
              <circle cx="18" cy="5" r="3" />
              <circle cx="6" cy="12" r="3" />
              <circle cx="18" cy="19" r="3" />
              <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
              <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
            </svg>
            공유하기
          </button>
          <button
            onClick={() => navigate('/url-input')}
            data-testid="result-home-button"
            className="w-full py-[16px] rounded-[18px] text-[15px] font-semibold text-text-primary bg-surface-2 border border-border"
          >
            다른 가구 배치하기
          </button>
          {sourceUrl && (
            <a
              href={sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              data-testid="result-buy-button"
              className="w-full py-[16px] rounded-[18px] text-[15px] font-semibold text-text-secondary text-center border border-border bg-surface"
            >
              구매하러 가기 →
            </a>
          )}
        </div>

      </div>
    </div>
  )
}
