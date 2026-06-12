import { useEffect, useRef, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { rescaleGlbToBlobUrl } from './lib/rescaleGlb'

interface Dimensions {
  width: number
  height: number
  depth: number
}

// 백엔드 furniture_guess.type(영문) → 표시용 한글 라벨
const FURNITURE_TYPE_LABEL: Record<string, string> = {
  chair: '의자',
  desk: '책상',
  table: '테이블',
  sofa: '소파',
  cabinet: '수납장',
  shelf: '선반',
  bed: '침대',
  dresser: '화장대',
  unknown: '가구',
}

export default function ModelPreviewPage() {
  const navigate = useNavigate()
  const { state } = useLocation()
  const glbUrl: string = state?.glbUrl ?? 'https://opensw-3dmodel-budget-918183255815-ap-northeast-2-an.s3.ap-northeast-2.amazonaws.com/models/23623df5.glb'
  const dimensions: Dimensions = state?.dimensions ?? { width: 120, height: 85, depth: 60 }
  const furnitureType: string | undefined = state?.furnitureType
  const furnitureLabel = FURNITURE_TYPE_LABEL[furnitureType ?? 'unknown'] ?? furnitureType ?? '가구'

  const [tab, setTab] = useState<'3d' | '치수'>('3d')
  const [loaded, setLoaded] = useState(false)
  const [isPreparingAR, setIsPreparingAR] = useState(false)
  // 실측 스케일로 리패킹한 GLB blob URL (model-viewer src로 사용)
  const [scaledGlbUrl, setScaledGlbUrl] = useState<string | null>(null)

  const mvRef = useRef<any>(null)
  const wasInAr = useRef(false) // 실제 AR 카메라 내부로 진입 성공했는지 여부

  // GLB를 실측 W/H/D 기준으로 uniform 스케일업 후 blob으로 리패킹.
  // 이렇게 해야 model-viewer의 Scene Viewer / Quick Look AR이 실제 크기로 배치됨.
  useEffect(() => {
    if (!glbUrl) return
    let revoked = false
    let createdUrl: string | null = null

    setScaledGlbUrl(null)
    setLoaded(false)
    rescaleGlbToBlobUrl(glbUrl, dimensions)
      .then((url) => {
        if (revoked) {
          URL.revokeObjectURL(url)
          return
        }
        createdUrl = url
        setScaledGlbUrl(url)
      })
      .catch((err) => {
        // 리스케일 실패 시 원본 URL로 폴백 (크기는 GLB 고유 크기)
        console.error('GLB 리스케일 실패, 원본으로 폴백:', err)
        if (!revoked) setScaledGlbUrl(glbUrl)
      })

    return () => {
      revoked = true
      if (createdUrl) URL.revokeObjectURL(createdUrl)
    }
  }, [glbUrl, dimensions.width, dimensions.height, dimensions.depth])

  // 1. model-viewer 스크립트 동적 로드
  useEffect(() => {
    if (!customElements.get('model-viewer')) {
      const script = document.createElement('script')
      script.type = 'module'
      script.src = 'https://ajax.googleapis.com/ajax/libs/model-viewer/3.5.0/model-viewer.min.js'
      document.head.appendChild(script)
    }
  }, [])

  // 2. AR 상태 변화 및 화면 복귀 통합 감지 시스템
  useEffect(() => {
    const el = mvRef.current
    if (!el) return

    const onLoad = () => setLoaded(true)
    const onError = () => setLoaded(true)
    
    // [공통] AR이 종료되었을 때 Result 페이지로 안전하게 이동시키는 함수
    const moveToResultPage = () => {
      if (wasInAr.current) {
        wasInAr.current = false // 즉시 플래그를 꺼서 뒤로가기/중복 네비게이션 방지
        setIsPreparingAR(false)
        console.log('AR 종료 감지 -> Result 페이지로 이동')
        navigate('/result', { state: { dimensions, glbUrl }, replace: true })
      }
    }

    // [WebXR / 안드로이드 내장 크롬 대응]
    const handleArStatus = (event: any) => {
      const status = event.detail.status
      console.log('AR 상태 변경:', status)
      
      if (status === 'presenting') {
        setIsPreparingAR(false)
        wasInAr.current = true // 실제 카메라 화면이 안착했을 때만 true로 변경!
      } else if (status === 'not-presenting') {
        moveToResultPage()
      } else if (status === 'failed') {
        setIsPreparingAR(false)
        wasInAr.current = false
        alert('AR 환경을 실행할 수 없습니다. HTTPS 연결이나 기기 권한을 확인해주세요.')
      }
    }

    // [iOS Quick Look / 안드로이드 Scene Viewer 외부 앱 스위칭 대응]
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        // 내부 브라우저가 가려지고 외부 시스템 AR 카메라가 정상 구동됨
        if (isPreparingAR) {
          setIsPreparingAR(false)
          wasInAr.current = true // 정상 구동 완료 시점에만 true 세팅!
        }
      } else if (document.visibilityState === 'visible') {
        // 사용자가 AR 화면에서 'X' 버튼을 누르고 웹브라우저로 다시 돌아옴
        if (wasInAr.current) {
          // iOS 시스템 전환 타이밍 안정을 위해 미세한 유예 딜레이 후 이동
          setTimeout(() => {
            moveToResultPage()
          }, 100)
        }
      }
    }

    el.addEventListener('load', onLoad)
    el.addEventListener('error', onError)
    el.addEventListener('ar-status', handleArStatus)
    document.addEventListener('visibilitychange', handleVisibilityChange)
    
    const fallback = setTimeout(() => setLoaded(true), 6000)

    return () => {
      el.removeEventListener('load', onLoad)
      el.removeEventListener('error', onError)
      el.removeEventListener('ar-status', handleArStatus)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      clearTimeout(fallback)
    }
  }, [glbUrl, navigate, dimensions, isPreparingAR])

  return (
    <div className="min-h-screen bg-bg flex flex-col relative">
      
      {/* AR 준비 중 전체화면 오버레이 */}
      {/* AR 준비 중 전체화면 가이드 오버레이 */}
      {isPreparingAR && (
        <div className="absolute inset-0 z-50 flex flex-col items-center justify-center bg-bg px-[28px]">
          {/* 로딩 스피너 */}
          <div className="w-[48px] h-[48px] rounded-full border-[4px] border-t-accent mb-[24px]" 
              style={{ borderColor: 'color-mix(in srgb, var(--color-accent) 25%, transparent)', borderTopColor: 'var(--color-accent)', animation: 'spin 0.9s linear infinite' }} />
          
          <h2 className="text-[20px] font-bold text-text-primary mb-[12px]">AR 카메라를 켜고 있습니다</h2>
          
          {/* 💡 실용적인 AR 안내 가이드 박스 추가 */}
          <div className="w-full bg-surface-2 rounded-[20px] p-[20px] mb-[24px] border border-border">
            <p className="text-[14px] font-bold text-text-primary mb-[10px] text-center">💡 이렇게 사용해 보세요!</p>
            <ul className="text-[13px] text-text-secondary space-y-[8px] break-keep">
              <li className="flex items-start gap-[6px]">
                <span className="text-accent">1.</span>
                <span>카메라가 켜지면 **주변 바닥을 천천히 비추며** 스마트폰을 움직여 주세요.</span>
              </li>
              <li className="flex items-start gap-[6px]">
                <span className="text-accent">2.</span>
                <span>바닥이 인식되면 소파가 나타납니다. **한 손가락으로 드래그**하여 이동할 수 있습니다.</span>
              </li>
              <li className="flex items-start gap-[6px]">
                <span className="text-accent">3.</span>
                <span>**두 손가락을 돌리면** 가구의 방향을 회전할 수 있습니다.</span>
              </li>
            </ul>
          </div>

          <p className="text-[12px] text-text-thirdly text-center">
            3D 파일 변환 및 카메라 구동에 최대 5~10초가 소요됩니다.
          </p>
        </div>
      )}

      {/* 헤더 */}
      <div className="flex items-center px-[16px] py-[12px] gap-[8px] flex-shrink-0">
        <button
          onClick={() => navigate(-1)}
          className="w-[38px] h-[38px] rounded-full bg-surface-2 flex items-center justify-center text-text-primary flex-shrink-0"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
            <path d="m15 18-6-6 6-6" />
          </svg>
        </button>
        <span className="text-[17px] font-bold text-text-primary">3D 미리보기</span>
        <div className="ml-auto flex gap-[2px] bg-surface-2 rounded-[10px] p-[3px]">
          {(['3d', '치수'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
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

      {/* --- 3D 탭 화면 --- */}
      <div style={{ display: tab === '3d' ? 'block' : 'none' }}>
        <div className="mx-[20px] rounded-[24px] overflow-hidden relative" style={{ background: 'var(--color-surface-2)', height: 320 }}>
          <model-viewer
            ref={mvRef}
            src={scaledGlbUrl ?? undefined}
            alt="3D 가구 모델"
            ar
            ar-modes="webxr scene-viewer quick-look"
            ar-scale="fixed"
            disable-zoom
            camera-controls=""
            auto-rotate=""
            auto-rotate-delay="500"
            rotation-per-second="20deg"
            
            /* 사용자가 조절할 필요 없도록, 호불호 없는 가장 깔끔한 그래픽 표준값으로 자동 고정 */
            shadow-intensity="1.2"
            exposure="1.0"
            environment-image="neutral"
            
            style={{ width: '100%', height: '100%', background: 'transparent' } as React.CSSProperties}
          />
          {!loaded && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-[10px]" style={{ background: 'rgba(237,231,222,0.85)', backdropFilter: 'blur(2px)' }}>
              <div className="w-[32px] h-[32px] rounded-full border-[3px] border-t-accent" style={{ borderColor: 'color-mix(in srgb, var(--color-accent) 25%, transparent)', borderTopColor: 'var(--color-accent)', animation: 'spin 0.9s linear infinite' }} />
              <span className="text-[12px] text-text-secondary font-semibold">3D 모델 불러오는 중…</span>
            </div>
          )}
        </div>

        {/* 정보 카드 */}
        <div className="mx-[20px] mt-[16px] bg-surface rounded-[20px] p-[16px] border border-border flex-shrink-0">
          <div className="flex justify-between items-start mb-[14px]">
            <div>
              <p className="text-[17px] font-extrabold text-text-primary mb-[4px]">{furnitureLabel}</p>
              <p className="text-[12px] text-text-secondary">당근마켓 게시글 · 3D 생성 완료</p>
            </div>
            <div className="px-[10px] py-[4px] rounded-[20px] text-[11px] font-bold text-accent border flex-shrink-0" style={{ background: 'color-mix(in srgb, var(--color-accent) 10%, transparent)', borderColor: 'color-mix(in srgb, var(--color-accent) 33%, transparent)' }}>
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
      </div>

      {/* --- 치수 탭 화면 --- */}
      <div className="flex-1 overflow-y-auto px-[20px]" style={{ display: tab === '치수' ? 'block' : 'none' }}>
        <div className="bg-surface-2 rounded-[20px] overflow-hidden mb-[16px]">
          <div className="aspect-video flex items-center justify-center" style={{ background: '#D4C5B2' }}>
            <svg viewBox="0 0 280 160" style={{ width: '80%', maxWidth: 260 }}>
               <rect x="40" y="60" width="200" height="60" rx="6" fill="var(--color-accent)" opacity="0.8" />
               <rect x="38" y="48" width="22" height="74" rx="5" fill="var(--color-accent)" />
               <rect x="220" y="48" width="22" height="74" rx="5" fill="var(--color-accent)" />
               <rect x="40" y="82" width="200" height="20" rx="4" fill="var(--color-accent)" opacity="0.5" />
               <text x="140" y="155" textAnchor="middle" fill="#E07A5F" fontSize="11" fontWeight="700">W · {dimensions.width}cm</text>
               <text x="8" y="90" textAnchor="middle" fill="#3B82F6" fontSize="10" fontWeight="700" transform="rotate(-90,8,88)">H · {dimensions.height}</text>
               <text x="140" y="105" textAnchor="middle" fill="rgba(255,255,255,0.6)" fontSize="10">D · {dimensions.depth}cm</text>
            </svg>
          </div>
        </div>
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

      {/* CTA 버튼 */}
      <div className="px-[20px] pb-[36px] pt-[16px] flex-shrink-0 mt-auto">
        <button
          onClick={() => {
            if (mvRef.current && typeof mvRef.current.activateAR === 'function') {
              setIsPreparingAR(true)
              try {
                mvRef.current.activateAR()
                
                // 타임아웃 안전장치: 구동 실패 시 무한 로딩 해제용
                setTimeout(() => {
                  setIsPreparingAR((currentLoading) => {
                    if (currentLoading && !wasInAr.current) {
                      console.log("⏱️ 5초간 AR 진입 신호 부재 -> 로딩 오버레이 초기화");
                      return false; 
                    }
                    return currentLoading;
                  })
                }, 5000)

              } catch (error) {
                console.error("AR 실행 에러:", error)
                setIsPreparingAR(false)
                wasInAr.current = false
                alert("AR 가상 카메라를 실행할 수 없습니다.")
              }
            } else {
              alert("3D 기능을 준비 중입니다. 잠시 후 다시 시도해 주세요.")
            }
          }}
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