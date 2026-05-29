# AR Planner Architecture - WebXR AR Core

> 생성일: 2026-05-29
> 브랜치: AR_not_unity_codex
> 목적: Unity WebGL iframe 방식을 Three.js + WebXR로 교체하기 위한 아키텍처 설계

---

## 1. 파일 구조

### 새로 생성할 파일

```
frontend/src/pages/ARPage/
├── ARPage.tsx                        # [React 빌더] 전면 재작성
├── types.ts                          # [공유] 모든 빌더가 import하는 타입 정의
├── hooks/
│   ├── useWebXR.ts                   # [Core 빌더] WebXR 세션, 렌더 루프, Hit Test, GLB 로딩
│   └── useARGestures.ts              # [Interaction 빌더] 터치 회전, 핀치 줌, Y축 이동
├── lib/
│   ├── xr-session.ts                 # [Core 빌더] WebXR 세션 생명주기 (start/end/cleanup)
│   ├── model-loader.ts               # [Core 빌더] GLTFLoader + Draco, 치수 스케일 적용
│   ├── reticle.ts                    # [Core 빌더] reticle 메시 생성 및 Hit Test 업데이트
│   ├── gesture-handler.ts            # [Interaction 빌더] 터치 이벤트 해석 (회전/스케일/이동)
│   └── platform-detect.ts            # [Core 빌더] iOS/Android UA 감지, WebXR 지원 여부
├── components/
│   ├── ARControls.tsx                # [React 빌더] 확장 (회전/스케일/재배치/높이조절 버튼 추가)
│   ├── ARHint.tsx                    # [유지] 기존 코드 그대로 사용
│   └── IOSFallback.tsx               # [React 빌더] iOS model-viewer 폴백 컴포넌트
```

### 수정할 기존 파일

| 파일 | 담당 | 변경 내용 |
|------|------|----------|
| `frontend/src/pages/ARPage/ARPage.tsx` | React 빌더 | Unity iframe 제거, WebXR canvas + overlay 구조로 전면 교체 |
| `frontend/src/pages/ARPage/components/ARControls.tsx` | React 빌더 | 기존 duplicate/delete/capture를 회전/스케일/재배치/높이/캡처로 교체 |
| `frontend/src/pages/PreviewPage/ModelPreviewPage.tsx` | React 빌더 | navigate('/ar') 호출 시 `dimensions` state 추가 |

### 삭제 대상

| 파일/디렉토리 | 사유 |
|---------------|------|
| `public/unity/` (존재 시) | Unity WebGL 빌드 파일 불필요 |

---

## 2. 공유 타입 인터페이스

아래 타입은 `frontend/src/pages/ARPage/types.ts`에 정의하며, 모든 빌더가 이 파일만 import한다.

```typescript
// ─── 라우터 State ───
export interface ARRouteState {
  glbUrl: string
  dimensions: { w: number; h: number; d: number } // cm 단위
  sourceUrl: string
}

// ─── 씬 설정 ───
export interface ARSceneConfig {
  glbUrl: string
  dimensions: { w: number; h: number; d: number } // cm 단위
  canvasRef: React.RefObject<HTMLCanvasElement | null>
  overlayRef: React.RefObject<HTMLDivElement | null>
}

// ─── 배치 상태 ───
export interface ARPlacementState {
  isPlaced: boolean
  position: { x: number; y: number; z: number }
  rotationY: number        // 라디안
  scale: number            // uniform scale 배수 (1.0 = 원본)
  elevationY: number       // 바닥 기준 Y축 오프셋 (m)
}

// ─── useWebXR 반환 타입 ───
export interface UseWebXRReturn {
  // 상태
  isSupported: boolean
  isSessionActive: boolean
  isModelPlaced: boolean
  hasHitTest: boolean
  error: string | null

  // 액션
  startSession: () => Promise<void>
  endSession: () => void
  placeModel: () => void
  resetModel: () => void

  // 내부 Three.js 객체 접근 (Interaction 빌더용)
  getPlacedModel: () => THREE.Object3D | null
}

// ─── useARGestures 반환 타입 ───
export interface UseARGesturesReturn {
  // 현재 제스처 값
  rotationY: number
  scaleFactor: number
  elevationY: number

  // 버튼 기반 제어 (DOM overlay에서 호출)
  rotateLeft: () => void
  rotateRight: () => void
  scaleUp: () => void
  scaleDown: () => void
  moveUp: () => void
  moveDown: () => void
  resetTransform: () => void

  // 터치 이벤트 바인딩 (canvas에 연결)
  handlers: {
    onTouchStart: (e: TouchEvent) => void
    onTouchMove: (e: TouchEvent) => void
    onTouchEnd: (e: TouchEvent) => void
  }
}

// ─── 플랫폼 감지 ───
export type ARPlatform = 'android-webxr' | 'ios-quicklook' | 'unsupported'
```

---

## 3. iOS/Android 분기 전략

### 플랫폼 감지 (`lib/platform-detect.ts`)

```typescript
export function detectARPlatform(): ARPlatform {
  const ua = navigator.userAgent

  // iOS: Safari, Chrome on iOS 등
  const isIOS = /iPad|iPhone|iPod/.test(ua) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)

  if (isIOS) return 'ios-quicklook'

  // Android: WebXR 지원 여부 확인은 비동기이므로 여기서는 UA만 판별
  const isAndroid = /Android/i.test(ua)
  if (isAndroid && 'xr' in navigator) return 'android-webxr'

  return 'unsupported'
}

// 비동기 정밀 검사
export async function checkWebXRHitTestSupport(): Promise<boolean> {
  if (!navigator.xr) return false
  return navigator.xr.isSessionSupported('immersive-ar')
}
```

### 플랫폼별 처리 방식

| 플랫폼 | 렌더링 방식 | Hit Test | 모델 배치 |
|--------|------------|----------|----------|
| **Android (Chrome 89+)** | Three.js WebGLRenderer + WebXR `immersive-ar` | WebXR Hit Test API | 커스텀 reticle + 탭 배치 |
| **iOS (Safari/Chrome)** | `<model-viewer>` 컴포넌트 + `ar` 속성 | Apple Quick Look 내장 | Quick Look 내장 AR 뷰어 |
| **미지원 브라우저** | 안내 메시지 표시 후 뒤로가기 유도 | N/A | N/A |

### ARPage 분기 흐름

```
ARPage mount
  |
  v
detectARPlatform()
  |
  +-- 'android-webxr' --> WebXR 모드: canvas + useWebXR + useARGestures
  |
  +-- 'ios-quicklook' --> IOSFallback: <model-viewer src={glbUrl} ar ar-modes="scene-viewer quick-look" />
  |
  +-- 'unsupported'   --> 안내 메시지: "이 브라우저는 AR을 지원하지 않습니다"
```

---

## 4. 의존성 패키지

### 필수 (dependencies)

| 패키지 | 버전 | 용도 |
|--------|------|------|
| `three` | `^0.170.0` | 3D 렌더링, WebXR 렌더 루프 |
| `@google/model-viewer` | `^4.0.0` | iOS Quick Look AR 폴백 |

### 필수 (devDependencies)

| 패키지 | 버전 | 용도 |
|--------|------|------|
| `@types/three` | `^0.170.0` | Three.js 타입 정의 |

### 내장 모듈 (별도 설치 불필요)

| import 경로 | 용도 |
|-------------|------|
| `three/examples/jsm/loaders/GLTFLoader.js` | GLB/GLTF 로딩 |
| `three/examples/jsm/loaders/DRACOLoader.js` | Draco 압축 GLB 지원 |
| `three/examples/jsm/webxr/XREstimatedLight.js` | 광원 추정 (선택) |

### WebXR 타입

Three.js `^0.170.0`에 `@types/webxr`가 포함되어 있으므로 별도 설치 불필요. 만약 `XRHitTestSource` 등의 타입이 누락되면 `@types/webxr` (`^0.5.0`)를 추가한다.

---

## 5. 스케일 계산 방법

### 공식

```
1. GLB 로드 후 object.scale.set(1, 1, 1)로 초기화
2. box = new THREE.Box3().setFromObject(object)
3. size = box.getSize(new THREE.Vector3())  // 원본 크기 (Three.js 단위 = m)
4. targetM = { w: targetCm.w / 100, h: targetCm.h / 100, d: targetCm.d / 100 }
5. sx = targetM.w / size.x
   sy = targetM.h / size.y
   sz = targetM.d / size.z
6. uniformScale = Math.min(sx, sy, sz)
7. object.scale.setScalar(uniformScale)
8. 바닥 정렬: boxAfter = Box3.setFromObject(object), object.position.y -= boxAfter.min.y
```

### 축 매핑

| 치수 | Three.js 축 | 설명 |
|------|-------------|------|
| w (너비) | X | 좌우 |
| h (높이) | Y | 상하 |
| d (깊이) | Z | 전후 |

### Math.min을 사용하는 이유

GLB 모델의 원본 비율이 목표 치수 비율과 다를 수 있으므로, 가장 작은 비율로 uniform scale하면 모델이 목표 바운딩 박스 안에 완전히 들어온다. 모델이 찌그러지지 않고 원본 비율을 유지한다.

### Interaction 빌더의 미세 조정

사용자가 핀치 또는 버튼으로 스케일을 변경하면:
```
object.scale.setScalar(uniformScale * userScaleFactor)
```
`userScaleFactor`는 `UseARGesturesReturn.scaleFactor` (기본값 1.0, 범위 0.5~2.0).

---

## 6. 파일 경계 규칙

각 빌더가 수정/생성하는 파일은 **절대 겹치지 않는다**. 충돌 방지를 위해 아래 표를 엄격히 준수한다.

### Core 빌더 담당 파일

| 파일 | 작업 |
|------|------|
| `hooks/useWebXR.ts` | 새로 생성 |
| `lib/xr-session.ts` | 새로 생성 |
| `lib/model-loader.ts` | 새로 생성 |
| `lib/reticle.ts` | 새로 생성 |
| `lib/platform-detect.ts` | 새로 생성 |

### Interaction 빌더 담당 파일

| 파일 | 작업 |
|------|------|
| `hooks/useARGestures.ts` | 새로 생성 |
| `lib/gesture-handler.ts` | 새로 생성 |

### React 빌더 담당 파일

| 파일 | 작업 |
|------|------|
| `ARPage.tsx` | 전면 재작성 |
| `components/ARControls.tsx` | 확장 재작성 |
| `components/IOSFallback.tsx` | 새로 생성 |
| `../PreviewPage/ModelPreviewPage.tsx` | navigate state에 dimensions 추가 |

### 공유 파일 (Planner가 생성, 모든 빌더가 읽기 전용)

| 파일 | 작업 |
|------|------|
| `types.ts` | Planner가 생성. 빌더들은 import만 한다 |

### 유지 (수정 불필요)

| 파일 | 사유 |
|------|------|
| `components/ARHint.tsx` | 기존 UI 그대로 사용 |
| `src/router.tsx` | `/ar` 라우트 이미 존재, 변경 불필요 |

---

## 7. 라우터 State 계약

### 현재 상태 (수정 전)

```typescript
// PreviewPage에서 ARPage로 navigate
navigate('/ar', { state: { glbUrl, sourceUrl } })
```

**문제점**: `dimensions`가 전달되지 않아 AR에서 스케일 적용 불가.

### 변경 후 계약

```typescript
// PreviewPage의 navigate 호출 (React 빌더가 수정)
navigate('/ar', {
  state: {
    glbUrl: string,           // S3 GLB 파일 URL
    dimensions: {             // 치수 추정 결과 (cm 단위)
      w: number,              // 너비
      h: number,              // 높이
      d: number,              // 깊이
    },
    sourceUrl: string,        // 원본 상품 URL (결과 페이지 전달용)
  }
})
```

### ARPage에서 수신

```typescript
const { state } = useLocation()
const {
  glbUrl = '',
  dimensions = { w: 60, h: 80, d: 40 },  // 기본값 (폴백)
  sourceUrl = '',
} = (state as ARRouteState) ?? {}
```

### 매핑 참고

PreviewPage의 기존 `Dimensions` 타입은 `{ width, height, depth }`이다. navigate 시 `{ w: dimensions.width, h: dimensions.height, d: dimensions.depth }`로 변환하여 전달한다. AR 내부에서는 짧은 키(`w`, `h`, `d`)를 사용한다.

---

## 8. DOM Overlay 구조

WebXR `immersive-ar` 세션에서는 브라우저가 카메라 피드 위에 WebGL canvas를 렌더링하므로, 일반 React DOM이 보이지 않는다. **DOM Overlay** 기능을 사용하면 특정 HTML 요소를 AR 세션 위에 표시할 수 있다.

### 구조

```tsx
// ARPage.tsx (React 빌더 담당)
<div className="relative w-full h-screen">
  {/* WebXR 렌더링 대상 */}
  <canvas ref={canvasRef} className="w-full h-full" />

  {/* DOM Overlay: WebXR 세션 중 카메라 위에 떠 있는 UI */}
  <div ref={overlayRef} id="ar-overlay" className="absolute inset-0 pointer-events-none">
    {/* pointer-events-auto로 개별 요소 활성화 */}

    {/* 상단 네비게이션 */}
    <div className="pointer-events-auto absolute top-0 left-0 right-0 z-10">
      <NavBar title="AR 배치" onBack={handleExit} />
    </div>

    {/* 힌트 메시지 (바닥 감지 전) */}
    {!hasHitTest && <ARHint />}

    {/* 하단 컨트롤 (배치 후 표시) */}
    {isModelPlaced && (
      <div className="pointer-events-auto">
        <ARControls
          onRotateLeft={gestures.rotateLeft}
          onRotateRight={gestures.rotateRight}
          onScaleUp={gestures.scaleUp}
          onScaleDown={gestures.scaleDown}
          onMoveUp={gestures.moveUp}
          onMoveDown={gestures.moveDown}
          onReset={resetModel}
          onCapture={handleCapture}
        />
      </div>
    )}

    {/* 배치 전: 탭 안내 */}
    {hasHitTest && !isModelPlaced && (
      <div className="pointer-events-auto absolute bottom-[120px] left-0 right-0 text-center">
        <button onClick={placeModel} className="...">
          화면을 탭하여 가구 배치
        </button>
      </div>
    )}
  </div>
</div>
```

### 핵심 규칙

1. **overlayRef**를 `requestSession` 옵션의 `domOverlay.root`에 전달한다:
   ```typescript
   const session = await navigator.xr!.requestSession('immersive-ar', {
     requiredFeatures: ['hit-test'],
     optionalFeatures: ['dom-overlay'],
     domOverlay: { root: overlayRef.current! },
   })
   ```

2. **overlay 루트는 `pointer-events: none`**, 개별 인터랙티브 요소만 `pointer-events: auto`로 설정한다. 이렇게 하면 overlay를 통한 탭이 WebXR 세션의 select 이벤트로 전달되어 Hit Test 기반 배치가 가능하다.

3. **overlay 내부에서는 터치 이벤트가 WebXR과 공유된다**. 버튼 영역 외의 터치는 gesture-handler가 처리한다 (드래그 회전 등).

4. **canvas와 overlay는 같은 부모 div 아래에 위치**하며, overlay는 `absolute inset-0`으로 canvas 위에 겹친다.

### iOS에서의 차이

iOS 폴백(`IOSFallback.tsx`)에서는 DOM Overlay를 사용하지 않는다. `<model-viewer>` 컴포넌트가 자체 AR 뷰어(Quick Look)를 실행하므로, AR 진입 전까지는 일반 React DOM으로 프리뷰를 보여주고, AR 버튼 탭 시 네이티브 Quick Look으로 전환된다.

---

## 에러 핸들링 요약

| 상황 | 처리 |
|------|------|
| WebXR 미지원 브라우저 | `ARPlatform === 'unsupported'` -> 안내 메시지 + 뒤로가기 버튼 |
| iOS Safari | `ARPlatform === 'ios-quicklook'` -> `<model-viewer>` 폴백 |
| Hit Test 소스 획득 실패 | 재시도 1회, 실패 시 "수동 배치 모드" (화면 중앙에 배치) |
| GLB 로드 실패 | `error` state 설정, 사용자에게 "모델을 불러올 수 없습니다" 표시 |
| 세션 예기치 않은 종료 | `session.onend` 이벤트로 cleanup, 상태 초기화 |
| glbUrl 누락 (state 없음) | 기본값 표시 후 뒤로가기 유도 |

---

## 실행 순서

1. **Planner** (본 문서): 아키텍처 확정, `types.ts` 생성
2. **Core 빌더**: `lib/xr-session.ts`, `lib/model-loader.ts`, `lib/reticle.ts`, `lib/platform-detect.ts`, `hooks/useWebXR.ts`
3. **Interaction 빌더**: `lib/gesture-handler.ts`, `hooks/useARGestures.ts`
4. **React 빌더**: `ARPage.tsx`, `ARControls.tsx`, `IOSFallback.tsx`, PreviewPage navigate 수정
