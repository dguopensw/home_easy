# Logical Components — Unit 1 Frontend
# 집에 가구 쉽다 (Easy Furniture Fit)

---

## 컴포넌트 구성

```
frontend/src/
├── router.tsx                  ← React.lazy + Suspense 적용 라우트
├── index.css                   ← Tailwind directives + 전역 스타일
├── main.tsx                    ← 앱 진입점, BrowserRouter
├── api/
│   └── furniture.ts            ← API 호출 함수 (fetch 기반)
├── pages/
│   ├── HomePage/
│   ├── UrlInputPage/
│   ├── LoadingPage/
│   ├── PreviewPage/
│   ├── ARPage/
│   ├── HistoryPage/
│   └── ResultPage/
└── components/
    ├── Button.tsx
    ├── ProgressBar.tsx
    ├── Toast.tsx
    └── NavBar.tsx
```

---

## API 레이어 (`src/api/furniture.ts`)

```typescript
// 백엔드 API 베이스 URL (환경변수)
const BASE_URL = import.meta.env.VITE_API_URL

export const startGeneration = async (url: string): Promise<{ job_id: string }> => {
  const res = await fetch(`${BASE_URL}/furniture/gen/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  })
  if (!res.ok) throw new Error('generation_failed')
  return res.json()
}

export const createSSEConnection = (jobId: string): EventSource =>
  new EventSource(`${BASE_URL}/furniture/gen/status/${jobId}`)
```

---

## 환경변수

| 변수 | 설명 | 예시 |
|------|------|------|
| `VITE_API_URL` | 백엔드 API 베이스 URL | `https://api.example.com` |

> Vercel 대시보드에서 환경변수 설정 필요
