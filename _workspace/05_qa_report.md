# WebAR QA 보고서

## 요구사항 검증 결과

| # | 요구사항 | 상태 | 근거 파일:라인 |
|---|---------|------|--------------|
| R1 | S3 GLB URL 수신 | PASS | ARPage.tsx:20, useWebXR.ts:19,87, model-loader.ts:22 |
| R2 | 휴대폰 카메라 켜기 | PASS | xr-session.ts:55, ARPage.tsx:70-72, IOSFallback.tsx:41-48 |
| R3 | 바닥 감지 + reticle | PASS | xr-session.ts:56,77, reticle.ts:8-23, useWebXR.ts:82-84, reticle.ts:41 |
| R4 | 터치로 GLB 배치 | PASS | ARPage.tsx:116-122, useWebXR.ts:164-185 |
| R5 | 치수 기반 스케일 | PASS | ARPage.tsx:24-29, useWebXR.ts:88, model-loader.ts:48-81 |
| R6 | 드래그/버튼 회전 | PASS | gesture-handler.ts:78-83,123-127, ARControls.tsx:29-33, ARPage.tsx:149-151 |
| R7 | 크기 조정/재배치/리프트 | PASS | gesture-handler.ts:85-97,129-142, useWebXR.ts:187-201, ARControls.tsx:35-49 |

## 경계면 정합성

| 경계면 | 상태 | 이슈 |
|-------|------|------|
| ARPage → useWebXR 파라미터 | PASS | `{ canvasRef, overlayRef, glbUrl, dimensions }` 가 `ARSceneConfig` 인터페이스(types.ts:11-16)와 일치 |
| ARPage → useARGestures 파라미터 | PASS | `{ overlayRef, getPlacedModel, isModelPlaced }` 가 `UseARGesturesOptions`(useARGestures.ts:20-24)와 일치 |
| ARPage → ARControls props | PASS | 8개 prop(onRotateLeft~onCapture) 모두 ARControlsProps(ARControls.tsx:1-10)와 일치 |
| PreviewPage navigate state → ARPage state 소비 | PASS | PreviewPage:213에서 `{ glbUrl, dimensions: { w, h, d }, sourceUrl }` 전달, ARPage:20-29에서 동일 키로 소비. width/height/depth → w/h/d 변환 로직도 존재 |
| types.ts UseARGesturesReturn vs 실제 hook 반환 | WARN | types.ts:47-65의 `UseARGesturesReturn`은 실제 useARGestures.ts:26-33의 반환 타입과 불일치 (stale 타입). 런타임 영향 없음 — ARPage가 types.ts의 해당 타입을 import하지 않음 |

## 상세 검증 근거

### R1: S3 GLB URL 수신
- **ARPage.tsx:20** — `const glbUrl: string = state?.glbUrl ?? ''` 로 router state에서 추출
- **ARPage.tsx:45** — `useWebXR({ canvasRef, overlayRef, glbUrl, dimensions })` 로 hook에 전달
- **useWebXR.ts:19** — `const { canvasRef, overlayRef, glbUrl, dimensions } = config` 로 수신
- **useWebXR.ts:87** — `const model = await loadGLB(glbUrl)` 로 로더 호출
- **model-loader.ts:14-38** — `GLTFLoader`가 전달받은 `url`로 `loader.load(url, ...)` 실행

### R2: 휴대폰 카메라 켜기
- **xr-session.ts:55** — `navigator.xr!.requestSession('immersive-ar', { requiredFeatures: ['hit-test'], ... })` 호출
- **ARPage.tsx:70-72** — `isIOSDevice()` 분기로 iOS일 때 `<IOSFallback>` 렌더링
- **IOSFallback.tsx:41-48** — `<model-viewer ar ar-modes="quick-look">` 로 iOS AR Quick Look 지원

### R3: 바닥 감지 + reticle
- **xr-session.ts:56** — `requiredFeatures: ['hit-test']` 명시
- **xr-session.ts:77** — `session.requestHitTestSource!({ space: viewerSpace })` 호출
- **reticle.ts:8-23** — `createReticle()` 로 RingGeometry 기반 reticle 메시 생성
- **useWebXR.ts:82-84** — `scene.add(reticle)` 로 씬에 추가
- **reticle.ts:41** — `frame.getHitTestResults(hitTestSource)` 로 히트 결과 확인 후 `reticle.visible` 및 `reticle.matrix` 업데이트

### R4: 터치로 GLB 배치
- **ARPage.tsx:116-122** — `!isModelPlaced && isSessionActive` 조건에서 전체화면 투명 div에 `onClick={placeModel}` 연결
- **useWebXR.ts:169-175** — `reticle.matrix.decompose(position, quaternion, scale)` 로 reticle 월드 좌표 추출
- **useWebXR.ts:178-179** — `model.position.set(position.x, position.y + model.position.y, position.z)` 후 `scene.add(model)`
- **useWebXR.ts:182** — 배치 후 `reticle.visible = false` 로 reticle 숨김

### R5: 치수 기반 스케일
- **ARPage.tsx:24-29** — `state?.dimensions`에서 `{w,h,d}` 직접 추출 또는 `{width,height,depth}` → `{w,h,d}` 변환, 기본값 `{60,80,40}`
- **useWebXR.ts:88** — `applyDimensionScale(model, dimensions)` 호출
- **model-loader.ts:56** — `new THREE.Box3().setFromObject(object)` 로 원본 크기 측정
- **model-loader.ts:63-75** — cm→m 변환 후 per-axis ratio 계산, `Math.min(sx,sy,sz)` uniform scale 적용

### R6: 드래그/버튼 회전
- **gesture-handler.ts:78-83** — 단일 터치 `touchmove`에서 `model.rotation.y += dx * ROTATION_SPEED` (0.008 rad/px)
- **gesture-handler.ts:123-127** — `rotateLeft`: `m.rotation.y -= ROTATE_STEP(22.5deg)`, `rotateRight`: `m.rotation.y += ROTATE_STEP`
- **useARGestures.ts:78-81** — `createButtonControls(getPlacedModel)` 로 버튼 콜백 생성
- **ARControls.tsx:29-33** — `onRotateLeft`, `onRotateRight` 버튼 렌더링

### R7: 크기 조정/재배치/리프트
- **gesture-handler.ts:85-97** — 2-finger pinch로 `model.scale.setScalar(newScale)`, MIN_SCALE=0.1 ~ MAX_SCALE=5.0
- **gesture-handler.ts:135-142** — `scaleUp` (×1.1), `scaleDown` (×0.9) 버튼 함수
- **gesture-handler.ts:129-133** — `liftUp`: `position.y += 0.05m` (max 2.0m), `liftDown`: `position.y -= 0.05m` (min 0.0m)
- **useWebXR.ts:187-201** — `resetModel()`: `scene.remove(model)`, `reticle.visible = true`, `setIsModelPlaced(false)` → reticle 모드 복귀
- **ARControls.tsx:47** — `onReset` 버튼이 `resetModel`에 연결

## 발견된 이슈

### WARN: types.ts의 UseARGesturesReturn이 실제 구현과 불일치 (non-blocking)
- **문제**: `types.ts:47-65`에 정의된 `UseARGesturesReturn` 타입이 실제 `useARGestures.ts:26-33`의 반환 타입과 다름. types.ts 버전에는 `rotationY`, `scaleFactor`, `elevationY`, `moveUp`, `moveDown`, `resetTransform`, `handlers` 가 있으나, 실제 hook은 `rotateLeft`, `rotateRight`, `liftUp`, `liftDown`, `scaleUp`, `scaleDown` 만 반환함.
- **영향**: 런타임 영향 없음. ARPage.tsx가 types.ts의 해당 타입을 import하지 않고, useARGestures.ts 자체에서 정의한 `UseARGesturesReturn`을 사용함.
- **수정 방향**: types.ts의 `UseARGesturesReturn`을 실제 hook 반환과 일치하도록 업데이트하거나, 사용하지 않는다면 삭제.

## 최종 판정

**PASS**

7가지 요구사항 모두 충족. 경계면 정합성 검증 통과. types.ts에 stale 타입 정의가 하나 존재하나 런타임 동작에 영향 없는 경미한 이슈.
