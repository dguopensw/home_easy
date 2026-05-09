export default function ARHint() {
  return (
    <div className="absolute bottom-[140px] left-[24px] right-[24px] z-20">
      <div
        className="rounded-[16px] px-[16px] py-[12px] text-center"
        style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(8px)' }}
      >
        <p className="text-white text-[13px] leading-relaxed">
          조명이 밝은 공간에서 바닥을 향해<br />천천히 카메라를 움직여주세요
        </p>
      </div>
    </div>
  )
}
