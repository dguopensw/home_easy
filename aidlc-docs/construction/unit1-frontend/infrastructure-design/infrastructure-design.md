# Infrastructure Design — Unit 1 Frontend
# 집에 가구 쉽다 (Easy Furniture Fit)

---

## 인프라 구성

| 항목 | 서비스 | 내용 |
|------|--------|------|
| 호스팅 | Vercel | React PWA 정적 파일 서빙 |
| CDN | Vercel Edge Network | 전 세계 엣지 캐싱 (자동) |
| HTTPS | Vercel 자동 발급 | Let's Encrypt SSL 인증서 |
| 도메인 | Vercel 기본 도메인 | `xxx.vercel.app` (MVP) |
| CI/CD | Vercel GitHub 연동 | main 브랜치 push → 자동 배포 |
| 환경변수 | Vercel Dashboard | `VITE_API_URL` 설정 |

---

## 환경 구성

| 환경 | 브랜치 | URL |
|------|--------|-----|
| Production | `main` | `xxx.vercel.app` |
| Preview | PR 브랜치 | `xxx-git-branch.vercel.app` (자동 생성) |

---

## 정적 파일 구성

| 파일/폴더 | 설명 |
|----------|------|
| `dist/` | Vite 빌드 결과물 (Vercel이 서빙) |
| `dist/unity/` | Unity WebGL 빌드 결과물 |
| `dist/assets/` | JS/CSS 번들 (코드 스플리팅 청크 포함) |

---

## 환경변수

| 변수명 | 환경 | 값 |
|--------|------|-----|
| `VITE_API_URL` | Production | `https://api.{ec2-domain}.com` |
| `VITE_API_URL` | Preview | `https://api.{ec2-domain}.com` (동일) |

> `VITE_` 접두사 필수 — Vite가 빌드 시 번들에 인라인
