# 프론트엔드 온보딩 가이드
# 집에 가구 쉽다 (Easy Furniture Fit)

> AR 페이지, Preview 페이지 담당 팀원을 위한 설명 문서입니다.

---

## 1. 개발 환경 시작하기

```bash
cd frontend
pnpm install     # 패키지 설치 (처음 한 번만)
pnpm run dev     # 개발 서버 실행 → http://localhost:5173
```

> **주의**: `pnpm install` 을 먼저 해야 `pnpm run dev`가 동작합니다.

---

## 2. 기술 스택 한눈에 보기

| 역할 | 기술 | 한 줄 설명 |
|------|------|-----------|
| UI 프레임워크 | React 18 | 컴포넌트 기반 화면 구성 |
| 언어 | TypeScript | JS에 타입을 추가한 언어 |
| 빌드 도구 | Vite | 빠른 개발 서버 |
| 스타일 | Tailwind CSS v4 | 클래스로 스타일 적용 |
| 라우팅 | React Router v6 | URL에 따라 페이지 전환 |
| 패키지 관리 | pnpm | npm/yarn 대신 사용 |

---

## 3. 폴더 구조

```
frontend/
├── public/
│   └── example.glb        # 개발용 3D 모델 샘플
│
├── src/
│   ├── api/
│   │   └── furniture.ts   # 백엔드 API 호출 함수 모음
│   │
│   ├── components/        # 여러 페이지에서 공통으로 쓰는 컴포넌트
│   │   ├── Button.tsx
│   │   ├── NavBar.tsx
│   │   ├── ProgressBar.tsx
│   │   └── Toast.tsx
│   │
│   ├── pages/             # 각 화면(URL 하나 = 폴더 하나)
│   │   ├── HomePage/
│   │   ├── UrlInputPage/
│   │   ├── LoadingPage/
│   │   ├── PreviewPage/       ← 담당 페이지
│   │   │   ├── ModelPreviewPage.tsx
│   │   │   └── components/    # 이 페이지에서만 쓰는 컴포넌트
│   │   ├── ARPage/            ← 담당 페이지
│   │   │   ├── ARPage.tsx
│   │   │   └── components/
│   │   │       ├── ARControls.tsx
│   │   │       └── ARHint.tsx
│   │   ├── HistoryPage/
│   │   └── ResultPage/
│   │
│   ├── index.css          # 디자인 토큰(색상 변수), 전역 애니메이션
│   ├── main.tsx           # 앱 진입점
│   └── router.tsx         # URL ↔ 페이지 매핑 정의
│
└── index.html             # HTML 껍데기 (model-viewer 스크립트 포함)
```

### 폴더 규칙

- **페이지 파일명**: `XxxPage.tsx` (예: `ARPage.tsx`, `ModelPreviewPage.tsx`)
- **페이지 전용 컴포넌트**: 해당 페이지 폴더 안 `components/` 에 작성
- **공통 컴포넌트**: 두 개 이상의 페이지에서 쓰이면 `src/components/` 로 이동

---

## 4. 디자인 규칙 (꼭 지켜주세요!)

### 4-1. 크기는 항상 px 단위로

Tailwind의 arbitrary value 방식을 사용합니다.

```tsx
// ✅ 올바른 방식
<div className="px-[24px] py-[16px] rounded-[12px] text-[14px]">

// ❌ 쓰지 않는 방식
<div className="px-6 py-4 rounded-xl text-sm">
```

### 4-2. 색상은 디자인 토큰으로

`src/index.css`에 정의된 CSS 변수를 사용합니다.
단, **같은 색상을 1~2번만 쓰는 경우**는 하드코딩해도 괜찮습니다.

```tsx
// ✅ 여러 곳에서 반복 사용되는 색상 → 토큰 사용
<p className="text-text-primary bg-surface-2">
<div className="border-border text-accent">

// ✅ 해당 컴포넌트에서만 1~2번 쓰는 색상 → 하드코딩 허용
style={{ background: '#2C1810' }}   // 히어로 배경색 (HomePage에서만 사용)
style={{ color: 'rgba(255,255,255,0.6)' }}  // 흰색 반투명 (LoadingPage 다크 배경 위)
```

**사용 가능한 토큰:**

| 토큰 | 색상 | 용도 |
|------|------|------|
| `bg-bg` | `#F5F0EA` | 페이지 기본 배경 |
| `bg-surface` | `#FFFFFF` | 카드, 입력창 배경 |
| `bg-surface-2` | `#EDE7DE` | 보조 배경, 칩 |
| `text-text-primary` | `#1A1208` | 기본 텍스트 |
| `text-text-secondary` | `#8A7460` | 보조 텍스트, 힌트 |
| `text-accent` / `bg-accent` | `#D4845A` | 포인트 색상 |
| `border-border` | `rgba(0,0,0,0.06)` | 테두리 |

### 4-3. 인라인 style은 토큰을 CSS 변수로

Tailwind 클래스로 표현 안 되는 경우에만 `style` prop 사용합니다.

```tsx
// ✅ CSS 변수 사용
style={{ background: 'var(--color-accent)' }}
style={{ color: 'rgba(255,255,255,0.6)' }}

// ❌ 색상 하드코딩
style={{ background: '#D4845A' }}
```

---

## 5. 페이지 간 데이터 전달 방법

React Router의 `navigate state`를 사용합니다. (Redux, Context 없음)

### props로 하면 안 되나요?

안 됩니다. props는 **부모 컴포넌트 → 자식 컴포넌트**로 값을 내려줄 때 쓰는 방식인데,
페이지 간에는 부모-자식 관계가 없습니다.

```
// 일반 컴포넌트 관계 (props 가능)
<ModelPreviewPage glbUrl={url} />   ← 부모가 자식을 직접 렌더링

// 페이지 관계 (props 불가)
/preview  →  /ar                    ← Router가 각 페이지를 독립적으로 렌더링
                                       ARPage 입장에서 PreviewPage는 '부모'가 아님
```

페이지는 Router가 URL에 따라 직접 렌더링하므로, 이전 페이지가 다음 페이지에 props를 줄 수 없습니다.
그래서 `navigate`로 이동할 때 `state`에 데이터를 실어 보내는 방식을 사용합니다.

### 보내는 쪽

```tsx
import { useNavigate } from 'react-router-dom'

const navigate = useNavigate()

// 이동하면서 데이터 함께 전달
navigate('/result', { state: { sourceUrl: 'https://...' } })
```

### 받는 쪽

```tsx
import { useLocation } from 'react-router-dom'

const { state } = useLocation()
const sourceUrl = state?.sourceUrl ?? ''  // 없을 때 기본값 처리 필수
```

### 전체 데이터 흐름

```
UrlInputPage  →  /loading   { jobId, sourceUrl }
LoadingPage   →  /preview   { glbUrl, dimensions, sourceUrl }
PreviewPage   →  /ar        { glbUrl, sourceUrl }
ARPage        →  /result    { sourceUrl }
```

---

## 6. 담당 페이지 상세 설명

### 6-1. PreviewPage (`src/pages/PreviewPage/ModelPreviewPage.tsx`)

> **현재 상태**: 1차 UI 구현 완료. 전체적인 레이아웃과 동작은 갖춰져 있으나, Unity AR 연동 완료 후 필요에 따라 수정해도 좋습니다.

**역할**: AI가 생성한 3D 모델을 보여주고, AR 배치로 넘어가는 페이지

**받는 데이터** (LoadingPage에서 전달):
```ts
{
  glbUrl: string      // 3D 모델 파일 경로 (예: '/example.glb')
  dimensions: {       // AI가 추정한 가구 치수
    width: number
    height: number
    depth: number
  }
  sourceUrl: string   // 원본 게시글 URL (ARPage로 그대로 전달)
}
```

**주요 구조**:
- **헤더**: 뒤로가기 + "3D 미리보기" + `3D / 치수` 탭 스위처
- **3D 탭**: `<model-viewer>` 웹 컴포넌트로 .glb 파일 렌더링
  - 로딩 오버레이 (파일 로드 완료 전까지 표시)
  - 드래그/핀치 힌트 뱃지
  - 정보 카드 (가구명, 출처, W/H/D 치수 칩)
- **치수 탭**: SVG 소파 도식 + 치수 목록
- **하단 버튼**: "AR로 방에 배치하기" → `/ar`로 이동

**`model-viewer` 사용법**:
```tsx
// index.html에 스크립트가 이미 로드되어 있음
// src 속성에 .glb 파일 경로만 넣으면 됨
<model-viewer
  src={glbUrl}
  camera-controls=""
  auto-rotate=""
  shadow-intensity="1"
  style={{ width: '100%', height: '100%' }}
/>
```

---

### 6-2. ARPage (`src/pages/ARPage/ARPage.tsx`)

> **현재 상태**: 더미 UI입니다. Unity iframe 자리와 버튼 레이아웃만 잡혀 있고, 실제 AR 동작은 Unity 구현 후 연동해야 합니다. 이 페이지는 담당자분이 Unity와 함께 완성하는 페이지입니다.

**역할**: Unity WebGL로 AR 카메라 화면을 보여주고, 가구를 배치하는 페이지

**받는 데이터** (PreviewPage에서 전달):
```ts
{
  glbUrl: string     // AR에 배치할 3D 모델 경로
  sourceUrl: string  // ResultPage로 그대로 전달
}
```

**현재 구조**:
- **Unity iframe**: `/unity/index.html`을 iframe으로 띄우는 자리 (Unity 빌드 파일 필요)
- **ARHint**: 바닥 인식 안내 메시지 (`components/ARHint.tsx`)
- **ARControls**: 복제/삭제/촬영 버튼 (`components/ARControls.tsx`)
- **촬영 버튼**: 누르면 1.2초 후 `/result`로 이동

---

## 7. Unity ↔ ARPage 연동 가이드



### Unity 코드 작업 위치

Unity 관련 코드는 **`unity-ar/`** 폴더에서 작업합니다. (`frontend/` 폴더가 아닙니다)

```
opensw/                   ← 모노레포 루트
├── frontend/             ← React 코드 (ARPage.tsx 등)
├── unity-ar/             ← Unity 프로젝트 코드 ← 여기서 작업
│   └── Assets/
│       ├── Scripts/
│       │   ├── ARController.cs
│       │   ├── PlacementManager.cs
│       │   └── JSBridge.cs
│       └── Plugins/
│           └── WebGL/
│               └── bridge.jslib   ← JS 브릿지 파일
├── backend/
└── ai-pipeline/
```

### Unity 빌드 후 배치

Unity WebGL 빌드가 완료되면 결과물을 `frontend/public/unity/`에 복사해야 iframe이 로드됩니다:

```
frontend/public/unity/    ← 빌드 결과물을 여기에 복사
├── index.html
├── Build/
│   ├── *.wasm
│   ├── *.js
│   └── *.data
└── TemplateData/
```

ARPage의 iframe이 `/unity/index.html`을 바라보고 있습니다:
```tsx
<iframe src="/unity/index.html" allow="camera; gyroscope; accelerometer" />
```



### Unity 전체 흐름


> **참고용 문서입니다.** Unity 구현 방식에 따라 실제 연동 코드는 달라질 수 있습니다. 아래 내용은 React ↔ Unity 간 통신 구조를 이해하기 위한 참고 자료로 활용해 주세요. unity 전체 흐름에 대한 설명부터는 현준님이 생각하시는 방향대로 구현하시고, 아래는 참가 하시면 된ㅂ니다

```
1. ARPage 진입 → iframe으로 /unity/index.html 로드
2. Unity 초기화 완료 → JS로 'unity:ready' 이벤트 발생
3. React가 이벤트 수신 → SendMessage로 .glb URL 전달
4. Unity가 3D 모델 로드 → 바닥 인식 시작
5. 바닥 인식 성공 → JS로 'unity:planeFound' 이벤트 발생
6. React가 ARHint 숨김 처리
7. 사용자가 촬영 버튼 클릭 → SendMessage로 캡처 명령
8. React가 /result로 이동
```

### Unity → React (이벤트 발생)

Unity C# 코드에서 JavaScript 함수를 호출해 이벤트를 발생시킵니다.

**Unity C# 코드:**
```csharp
// Unity WebGL에서 JS 호출하는 방법
using System.Runtime.InteropServices;

[DllImport("__Internal")]
private static extern void SendToReact(string eventName);

// 사용 예시
SendToReact("unity:ready");       // Unity 초기화 완료 시
SendToReact("unity:planeFound");  // 바닥 인식 성공 시
```

**JS 브릿지 파일** (`unity-ar/Assets/Plugins/WebGL/bridge.jslib`):
```javascript
mergeInto(LibraryManager.library, {
  SendToReact: function(eventNamePtr) {
    var eventName = UTF8ToString(eventNamePtr);
    window.dispatchEvent(new CustomEvent(eventName));
  }
});
```

**React(ARPage)에서 수신:**
```tsx
// ARPage.tsx 안에 이미 작성되어 있음
window.addEventListener('unity:ready', () => {
  // Unity 준비 완료 → 모델 URL 전달
  window.unityInstance?.SendMessage('ARController', 'LoadModel', glbUrl)
})

window.addEventListener('unity:planeFound', () => {
  // 바닥 인식 → 힌트 메시지 숨기기
  setShowHint(false)
})
```

### React → Unity (명령 전달)

React에서 `window.unityInstance.SendMessage()`로 Unity C# 메서드를 호출합니다.

**React 코드 (이미 ARPage.tsx에 작성됨):**
```tsx
// 모델 로드 명령
window.unityInstance?.SendMessage('ARController', 'LoadModel', glbUrl)

// 선택된 가구 복제
window.unityInstance?.SendMessage('PlacementManager', 'DuplicateSelected')

// 선택된 가구 삭제
window.unityInstance?.SendMessage('PlacementManager', 'DeleteSelected')

// 화면 캡처
window.unityInstance?.SendMessage('ARController', 'CaptureScreen')
```

**Unity C#에서 수신 (구현 필요):**
```csharp
// GameObject 이름이 'ARController'인 오브젝트에 붙는 스크립트
public class ARController : MonoBehaviour
{
    public void LoadModel(string glbUrl)
    {
        // glbUrl로 .glb 파일 로드
    }

    public void CaptureScreen()
    {
        // 화면 캡처 처리
    }
}

// GameObject 이름이 'PlacementManager'인 오브젝트에 붙는 스크립트
public class PlacementManager : MonoBehaviour
{
    public void DuplicateSelected() { /* 복제 */ }
    public void DeleteSelected()    { /* 삭제 */ }
}
```

> **주의**: `SendMessage`의 첫 번째 인자는 Unity **GameObject의 이름**과 정확히 일치해야 합니다. (`'ARController'`, `'PlacementManager'`)

### `window.unityInstance` 등록

Unity 빌드 시 생성되는 `index.html`의 로더 콜백에 아래 한 줄을 추가해야 React가 `SendMessage`를 호출할 수 있습니다.

```javascript
// unity-ar 빌드 결과물의 index.html 안 createUnityInstance 콜백에 추가
createUnityInstance(canvas, config).then((unityInstance) => {
  window.unityInstance = unityInstance;  // ← 이 줄 추가
});
```

---

## 8. 하위 컴포넌트 (ARPage)

| 파일 | 역할 | 수정 필요 여부 |
|------|------|--------------|
| `ARHint.tsx` | "바닥을 향해 카메라를 움직여주세요" 안내 메시지 | 문구 수정 가능 |
| `ARControls.tsx` | 복제(⊕) / 삭제(🗑️) / 촬영(○) 버튼 그룹 | Unity 연동 후 동작 확인 필요 |

---

## 9. 자주 쓰는 패턴(그냥 web개발 작업할 때 자주 쓰는 패턴을 담았습니다)

### 뒤로가기

```tsx
const navigate = useNavigate()
<button onClick={() => navigate(-1)}>뒤로</button>
```

### NavBar 사용

```tsx
import NavBar from '@/components/NavBar'
<NavBar title="3D 미리보기" onBack={() => navigate(-1)} />
```

### 조건부 렌더링

```tsx
{isLoading && <Spinner />}
{tab === '3d' ? <ModelView /> : <DimensionsView />}
```

### useEffect 기본 패턴

```tsx
useEffect(() => {
  // 실행할 코드

  return () => {
    // 컴포넌트가 사라질 때 정리 (이벤트 리스너 제거 등)
  }
}, [의존성])  // 이 값이 바뀔 때마다 재실행
```

---

## 10. 주의사항

- **`pnpm run dev` 전에 반드시 `pnpm install`** 실행
- **px 단위 사용** — `px-[24px]` 형식으로
- **색상은 반복 사용 시 토큰으로** — 1~2번만 쓰는 색상은 하드코딩 허용
- **state 기본값 처리 필수** — `state?.glbUrl ?? ''` 처럼 없을 때 대비
- `@/` 는 `src/` 의 alias — `import NavBar from '@/components/NavBar'`처럼 사용
- **Unity SendMessage 오브젝트명** — Unity GameObject 이름과 정확히 일치해야 함
