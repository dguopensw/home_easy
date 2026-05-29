# React Builder - Completion Record

> Date: 2026-05-29
> Branch: AR_not_unity_codex

---

## Modified Files

| # | File | Action | Summary |
|---|------|--------|---------|
| 1 | `frontend/src/pages/ARPage/ARPage.tsx` | Rewritten | Unity iframe/events fully removed. Integrated `useWebXR` + `useARGestures` hooks. Canvas + DOM overlay structure. iOS detection -> IOSFallback. WebXR unsupported -> message + back button. Pre-placement tap area. Post-placement ARControls. NavBar onBack calls `endSession()`. Dimensions conversion from `{width,height,depth}` to `{w,h,d}` with fallback defaults. |
| 2 | `frontend/src/pages/ARPage/components/ARControls.tsx` | Rewritten | Removed `onDuplicate`/`onDelete` buttons. Added: `onRotateLeft`, `onRotateRight`, `onLiftUp`, `onLiftDown`, `onScaleUp`, `onScaleDown`, `onReset`. Retained capture button. Glass-morphism style preserved (`rgba(255,255,255,0.15)`, `backdropFilter: blur(8px)`). |
| 3 | `frontend/src/pages/ARPage/components/IOSFallback.tsx` | Created | Dynamically loads model-viewer 3.5.0 CDN script. Renders `<model-viewer>` with `ar` + `ar-modes="quick-look"` + `camera-controls`. TypeScript JSX IntrinsicElements declaration for `model-viewer`. |
| 4 | `frontend/src/pages/PreviewPage/ModelPreviewPage.tsx` | Modified | Navigate to `/ar` now passes `dimensions: { w, h, d }` converted from `{ width, height, depth }`. |

---

## Removed Unity Dependencies

| Removed item | Location |
|-------------|----------|
| `window.unityInstance` global type declaration | ARPage.tsx |
| `unity:ready` event listener | ARPage.tsx useEffect |
| `unity:planeFound` event listener | ARPage.tsx useEffect |
| `window.unityInstance.SendMessage()` calls | ARPage.tsx handlers |
| `<iframe src="/unity/index.html">` | ARPage.tsx JSX |
| `iframeRef` | ARPage.tsx |

---

## Router State Contract

```typescript
// PreviewPage -> ARPage
navigate('/ar', {
  state: {
    glbUrl: string,           // S3 GLB URL
    dimensions: { w, h, d },  // cm, converted from {width, height, depth}
    sourceUrl: string,
  }
})

// ARPage -> ResultPage
navigate('/result', { state: { sourceUrl } })
```

---

## Integration Points

- `useWebXR` (from Core builder): `startSession`, `endSession`, `placeModel`, `resetModel`, `getPlacedModel`, `isSupported`, `isSessionActive`, `isModelPlaced`, `error`
- `useARGestures` (from Interaction builder): `rotateLeft`, `rotateRight`, `liftUp`, `liftDown`, `scaleUp`, `scaleDown`
- Touch gesture handlers auto-registered on overlay element by `useARGestures`
