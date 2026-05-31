import { useNavigate, useLocation } from 'react-router-dom'

export default function ResultPage() {
  const navigate = useNavigate()
  const { state } = useLocation()
  const sourceUrl =state?.sourceUrl ??localStorage.getItem('sourceUrl') ??'https://www.daangn.com/articles/12345678'

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


        {/* 버튼 */}
        <div className="flex flex-col gap-[10px] w-full">
          
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
           <button
            onClick={() => navigate('/')}
            data-testid="result-home-button"
            className="w-full py-[16px] rounded-[18px] text-[15px] font-semibold text-text-primary bg-surface-3 border border-border"
          >
            메인 화면으로 이동
          </button>
        </div>

      </div>
    </div>
  )
}
