---
name: webxr-ar-core
description: |
  Three.js + WebXR Device API를 사용한 AR 핵심 구현 가이드. WebXR immersive-ar 세션, Hit Test API로 바닥 감지, reticle 렌더링, GLTFLoader로 GLB 로딩, 치수(w/h/d cm) 기반 모델 스케일 적용 방법을 다룬다. ar-core-builder 에이전트가 사용하며, ar-planner 에이전트도 참조한다.
---

# WebXR AR Core 구현 가이드

## 핵심 의존성

```json
{
  "three": "^0.170.0",
  "@types/three": "^0.170.0"
}
```

Three.js r152+ 부터 `three/addons` import 경로 사용 가능. 하위 호환을 위해 `three/examples/jsm/...` 경로를 우선 사용한다.

---

## WebXR 세션 생명주기

### 1. 지원 여부 확인
```typescript
export async function isWebXRSupported(): Promise<boolean> {
  if (!navigator.xr) return false
  return navigator.xr.isSessionSupported('immersive-ar')
}
```

### 2. 세션 시작
```typescript
export async function startARSession(
  canvas: HTMLCanvasElement,
  overlayEl: HTMLElement,
): Promise<{ session: XRSession; renderer: THREE.WebGLRenderer }> {
  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true })
  renderer.setPixelRatio(window.devicePixelRatio)
  renderer.xr.enabled = true

  const session = await navigator.xr!.requestSession('immersive-ar', {
    requiredFeatures: ['hit-test'],
    optionalFeatures: ['dom-overlay', 'light-estimation'],
    domOverlay: { root: overlayEl },
  })

  await renderer.xr.setSession(session)
  return { session, renderer }
}
```

### 3. 세션 종료 및 정리
```typescript
export function cleanupARSession(
  session: XRSession | null,
  renderer: THREE.WebGLRenderer | null,
  hitTestSource: XRHitTestSource | null,
) {
  hitTestSource?.cancel()
  renderer?.setAnimationLoop(null)
  renderer?.dispose()
  session?.end().catch(() => {}) // 이미 종료된 경우 무시
}
```

---

## Hit Test (바닥 감지)

```typescript
export async function setupHitTest(session: XRSession): Promise<XRHitTestSource> {
  const viewerSpace = await session.requestReferenceSpace('viewer')
  const hitTestSource = await session.requestHitTestSource!({ space: viewerSpace })
  return hitTestSource
}

// 렌더 루프 내에서:
export function updateReticle(
  frame: XRFrame,
  hitTestSource: XRHitTestSource,
  referenceSpace: XRReferenceSpace,
  reticle: THREE.Object3D,
): boolean {
  const hits = frame.getHitTestResults(hitTestSource)
  if (hits.length > 0) {
    const pose = hits[0].getPose(referenceSpace)
    if (pose) {
      reticle.visible = true
      reticle.matrix.fromArray(pose.transform.matrix)
      return true
    }
  }
  reticle.visible = false
  return false
}
```

---

## Reticle 생성

```typescript
export function createReticle(): THREE.Mesh {
  const geometry = new THREE.RingGeometry(0.08, 0.12, 32).rotateX(-Math.PI / 2)
  const material = new THREE.MeshBasicMaterial({
    color: 0x4fc3f7,
    side: THREE.DoubleSide,
    opacity: 0.85,
    transparent: true,
  })
  const mesh = new THREE.Mesh(geometry, material)
  mesh.matrixAutoUpdate = false
  mesh.visible = false
  return mesh
}
```

---

## GLB 로딩 및 치수 스케일

```typescript
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader.js'

export async function loadGLB(url: string): Promise<THREE.Group> {
  const loader = new GLTFLoader()
  // Draco 압축 지원 (선택)
  const dracoLoader = new DRACOLoader()
  dracoLoader.setDecoderPath('https://www.gstatic.com/draco/versioned/decoders/1.5.6/')
  loader.setDRACOLoader(dracoLoader)

  return new Promise((resolve, reject) => {
    loader.load(
      url,
      (gltf) => resolve(gltf.scene),
      undefined,
      (err) => reject(err),
    )
  })
}

/**
 * 모델을 목표 치수에 맞게 스케일 조정.
 * @param object Three.js 오브젝트
 * @param targetCm { w, h, d } 목표 치수 (cm 단위)
 */
export function applyDimensionScale(
  object: THREE.Object3D,
  targetCm: { w: number; h: number; d: number },
) {
  // 현재 스케일을 1로 초기화한 뒤 바운딩 박스 계산
  object.scale.set(1, 1, 1)
  const box = new THREE.Box3().setFromObject(object)
  const size = box.getSize(new THREE.Vector3())

  if (size.x === 0 || size.y === 0 || size.z === 0) return // 잘못된 모델 방어

  const targetM = {
    w: targetCm.w / 100,
    h: targetCm.h / 100,
    d: targetCm.d / 100,
  }

  // 각 축의 스케일 비율 중 최솟값으로 uniform scale → 모델이 박스 안에 들어오게
  const sx = targetM.w / size.x
  const sy = targetM.h / size.y
  const sz = targetM.d / size.z
  const uniformScale = Math.min(sx, sy, sz)

  object.scale.setScalar(uniformScale)

  // 바닥에 붙이기: 모델 하단이 y=0이 되도록 이동
  const boxAfter = new THREE.Box3().setFromObject(object)
  object.position.y -= boxAfter.min.y
}
```

---

## 렌더 루프 전체 구조

```typescript
function startRenderLoop(
  renderer: THREE.WebGLRenderer,
  scene: THREE.Scene,
  camera: THREE.PerspectiveCamera,
  hitTestSource: XRHitTestSource,
  referenceSpace: XRReferenceSpace,
  reticle: THREE.Object3D,
  onHitFound: (hasHit: boolean) => void,
) {
  renderer.setAnimationLoop((timestamp, frame) => {
    if (!frame) return

    const hasHit = updateReticle(frame, hitTestSource, referenceSpace, reticle)
    onHitFound(hasHit)

    renderer.render(scene, camera)
  })
}
```

---

## useWebXR 훅 스켈레톤

```typescript
import { useCallback, useEffect, useRef, useState } from 'react'

export function useWebXR({ canvasRef, overlayRef, glbUrl, dimensions }) {
  const [isSupported, setIsSupported] = useState(false)
  const [isSessionActive, setIsSessionActive] = useState(false)
  const [isModelPlaced, setIsModelPlaced] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const sessionRef = useRef<XRSession | null>(null)
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null)
  const sceneRef = useRef<THREE.Scene | null>(null)
  const modelRef = useRef<THREE.Object3D | null>(null)
  const reticleRef = useRef<THREE.Mesh | null>(null)
  const hitTestSourceRef = useRef<XRHitTestSource | null>(null)

  useEffect(() => {
    isWebXRSupported().then(setIsSupported)
  }, [])

  const startSession = useCallback(async () => {
    // ... 세션 초기화, GLB 로드, reticle 생성, 렌더 루프 시작
  }, [glbUrl, dimensions, canvasRef, overlayRef])

  const endSession = useCallback(() => {
    cleanupARSession(sessionRef.current, rendererRef.current, hitTestSourceRef.current)
    setIsSessionActive(false)
    setIsModelPlaced(false)
  }, [])

  const placeModel = useCallback(() => {
    if (!reticleRef.current?.visible || !modelRef.current || !sceneRef.current) return
    // reticle 위치에 모델 고정
    const pos = new THREE.Vector3()
    reticleRef.current.getWorldPosition(pos)
    modelRef.current.position.copy(pos)
    sceneRef.current.add(modelRef.current)
    reticleRef.current.visible = false
    setIsModelPlaced(true)
  }, [])

  const resetModel = useCallback(() => {
    if (!modelRef.current || !sceneRef.current) return
    sceneRef.current.remove(modelRef.current)
    if (reticleRef.current) reticleRef.current.visible = true
    setIsModelPlaced(false)
  }, [])

  const getPlacedModel = useCallback(() => modelRef.current, [])

  useEffect(() => () => endSession(), [endSession])

  return { isSupported, isSessionActive, isModelPlaced, error, startSession, endSession, placeModel, resetModel, getPlacedModel }
}
```

---

## 주의사항

- **HTTPS 필수**: WebXR은 secure context에서만 동작. 개발 시 `vite --https` 또는 ngrok 사용
- **Android Chrome 전용**: WebXR Hit Test는 현재 Android Chrome 89+에서만 지원
- **S3 CORS**: GLB URL이 S3에 있다면 S3 버킷에 CORS 헤더 설정 필요 (`Access-Control-Allow-Origin: *`)
- **참조 공간**: `local-floor` 보다 `local`이 hit-test와 더 안정적으로 동작함

## 참조

상세 패턴이 필요하면 `references/` 디렉토리 추가 예정.
