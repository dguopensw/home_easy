---
name: ar-interaction
description: |
  WebAR 환경에서 모바일 터치 제스처(단일 드래그로 Y축 회전, 두 손가락 핀치로 스케일)와 버튼 제어(회전/리프트/스케일/재배치)를 구현하는 가이드. ar-interaction-builder 에이전트가 사용한다.
---

# AR Interaction 구현 가이드

## 전제 조건

- Three.js 모델 참조는 `getPlacedModel()` 콜백으로 받는다 (Core에 직접 접근 금지)
- 모든 제스처는 `overlayRef` div 위에서 캡처한다 (WebXR DOM overlay)
- `isModelPlaced === false`이면 모든 핸들러가 즉시 반환한다
- Three.js transform 적용은 렌더 루프 밖에서 직접 수정해도 된다 (WebXR 렌더러가 다음 프레임에 반영)

---

## 제스처 상태 관리

```typescript
// ref로 관리 — state 업데이트가 불필요한 제스처 중간 값
const gestureState = useRef({
  isDragging: false,
  lastTouchX: 0,
  isPinching: false,
  lastPinchDist: 0,
})
```

---

## 단일 손가락 드래그 → Y축 회전

```typescript
const ROTATION_SPEED = 0.008 // rad/px

const handleTouchStart = (e: TouchEvent) => {
  if (e.touches.length === 1) {
    gestureState.current.isDragging = true
    gestureState.current.lastTouchX = e.touches[0].clientX
  }
}

const handleTouchMove = (e: TouchEvent) => {
  const model = getPlacedModel()
  if (!model || !isModelPlaced) return

  if (e.touches.length === 1 && gestureState.current.isDragging) {
    const dx = e.touches[0].clientX - gestureState.current.lastTouchX
    model.rotation.y += dx * ROTATION_SPEED
    gestureState.current.lastTouchX = e.touches[0].clientX
    e.preventDefault() // 페이지 스크롤 방지
  }
}
```

---

## 두 손가락 핀치 → 스케일 미세 조정

```typescript
const MIN_SCALE = 0.1
const MAX_SCALE = 5.0

const getPinchDist = (e: TouchEvent): number =>
  Math.hypot(
    e.touches[1].clientX - e.touches[0].clientX,
    e.touches[1].clientY - e.touches[0].clientY,
  )

// handleTouchStart에 추가:
if (e.touches.length === 2) {
  gestureState.current.isPinching = true
  gestureState.current.lastPinchDist = getPinchDist(e)
}

// handleTouchMove에 추가:
if (e.touches.length === 2 && gestureState.current.isPinching) {
  const model = getPlacedModel()
  if (!model) return
  const dist = getPinchDist(e)
  if (gestureState.current.lastPinchDist > 0) {
    const ratio = dist / gestureState.current.lastPinchDist
    const newScale = Math.max(MIN_SCALE, Math.min(MAX_SCALE, model.scale.x * ratio))
    model.scale.setScalar(newScale)
  }
  gestureState.current.lastPinchDist = dist
}
```

---

## TouchEnd 정리

```typescript
const handleTouchEnd = (e: TouchEvent) => {
  if (e.touches.length < 2) {
    gestureState.current.isPinching = false
    gestureState.current.lastPinchDist = 0
  }
  if (e.touches.length === 0) {
    gestureState.current.isDragging = false
  }
}
```

---

## 이벤트 등록/해제

```typescript
useEffect(() => {
  const overlay = overlayRef.current
  if (!overlay) return

  overlay.addEventListener('touchstart', handleTouchStart, { passive: false })
  overlay.addEventListener('touchmove', handleTouchMove, { passive: false })
  overlay.addEventListener('touchend', handleTouchEnd)

  return () => {
    overlay.removeEventListener('touchstart', handleTouchStart)
    overlay.removeEventListener('touchmove', handleTouchMove)
    overlay.removeEventListener('touchend', handleTouchEnd)
  }
}, [isModelPlaced]) // isModelPlaced 변경 시 재등록
```

---

## 버튼 제어 함수

```typescript
const ROTATE_STEP = Math.PI / 8   // 22.5도
const LIFT_STEP   = 0.05          // 5cm (Three.js meter)
const SCALE_STEP  = 0.1           // 10%

export function createARButtonControls(getPlacedModel: () => THREE.Object3D | null) {
  const withModel = (fn: (m: THREE.Object3D) => void) => () => {
    const m = getPlacedModel()
    if (m) fn(m)
  }

  return {
    rotateLeft:  withModel(m => { m.rotation.y -= ROTATE_STEP }),
    rotateRight: withModel(m => { m.rotation.y += ROTATE_STEP }),
    liftUp:      withModel(m => { m.position.y = Math.min(m.position.y + LIFT_STEP, 2.0) }),
    liftDown:    withModel(m => { m.position.y = Math.max(m.position.y - LIFT_STEP, 0.0) }),
    scaleUp:     withModel(m => { m.scale.multiplyScalar(1 + SCALE_STEP).clampScalar(MIN_SCALE, MAX_SCALE) }),
    scaleDown:   withModel(m => { m.scale.multiplyScalar(1 - SCALE_STEP).clampScalar(MIN_SCALE, MAX_SCALE) }),
  }
}
```

> `Vector3.clampScalar`는 THREE.Vector3 메서드이므로 scale에 적용 가능.

---

## useARGestures 훅 완성 구조

```typescript
export function useARGestures({ overlayRef, getPlacedModel, isModelPlaced }: UseARGesturesOptions): UseARGesturesReturn {
  const gestureState = useRef({ ... })

  // 핸들러 정의 (위 패턴 적용)
  // useEffect로 이벤트 등록/해제
  // 버튼 함수 반환

  const buttons = createARButtonControls(getPlacedModel)

  return {
    ...buttons,
    currentRotationY: getPlacedModel()?.rotation.y ?? 0,
    currentScale: getPlacedModel()?.scale.x ?? 1,
  }
}
```

---

## 주의사항

- **passive: false**: `touchmove`에서 `e.preventDefault()`를 호출하려면 `{ passive: false }` 필수
- **드래그 vs 탭 구분**: touchstart ~ touchend 거리가 10px 미만이면 탭으로 처리 (배치 트리거용)
- **제스처 충돌**: 핀치 중에는 드래그 핸들러가 동작하지 않도록 `isPinching` 체크 필수
- **overlay pointer-events**: 제스처를 받아야 하는 구간에서만 `pointer-events: auto`로 전환
