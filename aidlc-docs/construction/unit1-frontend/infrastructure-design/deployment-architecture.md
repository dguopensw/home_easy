# Deployment Architecture — Unit 1 Frontend
# 집에 가구 쉽다 (Easy Furniture Fit)

---

## 배포 흐름

```
개발자 로컬
    │
    │ git push origin main
    ▼
GitHub (opensw/frontend)
    │
    │ Vercel GitHub App 감지
    ▼
Vercel Build
    │  pnpm install
    │  pnpm build  (vite build)
    │  → dist/ 생성
    ▼
Vercel Edge Network
    │  dist/ 정적 파일 배포
    │  HTTPS 자동 적용
    ▼
사용자 브라우저 (모바일 Chrome/Safari)
```

---

## Unity WebGL 배포 흐름

```
unity-ar/ 에서 Unity WebGL 빌드
    │
    │ 수동 복사
    ▼
frontend/public/unity/
    │
    │ pnpm build 시 dist/unity/ 에 포함
    ▼
Vercel 자동 배포
```

> Unity 빌드는 수동 작업 — Unity Editor에서 WebGL 빌드 후 `frontend/public/unity/`에 복사

---

## vercel.json 설정

```json
{
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```

> React Router의 클라이언트 사이드 라우팅을 위해 모든 경로를 `index.html`로 리다이렉트
